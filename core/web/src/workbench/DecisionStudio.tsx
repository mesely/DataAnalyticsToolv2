import { ChevronRight, ArrowRight } from "./BrandIcons";
import { TableWrap } from "./TableWrap";
import React, { useEffect, useRef, useState } from "react";
import { ReasoningTree } from "./Reasoning";
import { Findings, Database, Spinner } from "./BrandIcons";
import { api } from "../api";
import { useLocale } from "./Locale";
import type { Filters, RoutingReceipt } from "./types";
import { RoutingBadge } from "./Routing";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
const BASE = "/v1/dashboard/workbench";
type Reference = { path: string; value: number; unit: string; anchor: string };
type Recommendation = {
  id: string;
  title: string;
  explanation: string;
  evidence_refs: string[];
  support_score: number;
  score_components: Record<string, number>;
  missing: string[];
  steps: string[];
  model_focus?: boolean;
};
type Forecast = {
  status: string;
  reason?: string;
  complete_weeks: number;
  selected?: string;
  history: { period: string; pence: number }[];
  holdout?: {
    selected: {
      mae_gbp: number;
      rmse_gbp: number;
      wape: number | null;
      n: number;
    };
    naive: { mae_gbp: number };
    records: {
      target: string;
      actual_pence: number;
      predicted_pence: number;
    }[];
  };
  next?: {
    period: string;
    pence: number;
    lower_pence: number;
    upper_pence: number;
  };
  split?: { holdout_origins: number; development_origins: number };
  uncertainty?: {
    scaling: string;
    calibrated: boolean;
    levels: Record<
      string,
      {
        radius_pence: number;
        final_window_coverage: number | null;
        development_rolling_coverage: number | null;
        development_mean_width_gbp?: number | null;
        final_mean_width_gbp?: number | null;
        development_rolling_n: number;
      }
    >;
  };
  diagnostics?: Diagnostic[];
  period_slices?: {
    month: string;
    phase: string;
    n: number;
    selected_mae_gbp: number;
    naive_mae_gbp: number;
    selected_beats_naive: boolean;
    band_n: number;
    band_covered: number;
    band_mean_width_gbp: number | null;
  }[];
  slices?: {
    country: string;
    status: string;
    final?: { selected: { mae_gbp: number }; naive: { mae_gbp: number } };
    selected_beats_naive_final?: boolean;
    zero_weeks?: number;
  }[];
  leaderboard?: {
    method: string;
    development_mae_gbp: number;
    final_mae_gbp: number;
    final_improvement_vs_naive: number | null;
    selected: boolean;
  }[];
  notes: string[];
};

type Diagnostic = {
  code: string;
  severity: string;
  message: string;
  params?: Record<string, unknown>;
};

/** Turkish text for a forecast diagnostic, built from its code and params. English uses the server
 * message; an unknown code or missing params falls back to it as well, so nothing is ever hidden. */
function diagnosticTr(d: Diagnostic): string | null {
  const p = d.params;
  if (!p) return null;
  const pct = (v: unknown) => `%${Math.round(Number(v) * 100)}`;
  const gbp = (v: unknown) =>
    new Intl.NumberFormat("tr-TR", {
      style: "currency",
      currency: "GBP",
      maximumFractionDigits: 0,
    }).format(Number(v));
  switch (d.code) {
    case "seasonal_naive_unavailable":
      return `Mevsimsel naif yöntem (52 hafta) en az ${p.required} tam hafta ister; ${p.available} hafta var. Yıllık mevsimsellik bu geçmişle doğrulanamaz.`;
    case "zero_weeks":
      return `${p.count} tam haftada gözlenen brüt satış yok; sıfır sayıldı ve veri toplama boşluğu olabilir.`;
    case "outlier_weeks":
      return `Tipik düzeyden çok uzak haftalar (dayanıklı 3-sigma): ${(p.weeks as string[]).join(", ")}${p.more ? " …" : ""}.`;
    case "possible_level_shift":
      return "Son 8 haftanın ortalaması önceki 8 haftadan tipik haftalık değişimin iki katından fazla farklı; yapısal bir değişim dışlanamaz.";
    case "unstable_development_error":
      return `Seçilen yöntemin hatası geliştirme dönemlerinin ilk ve ikinci yarısı arasında iki kattan fazla değişiyor (MAE ${gbp(p.first_half_mae_gbp)} / ${gbp(p.second_half_mae_gbp)}).`;
    case "small_selection_margin":
      return "Seçilen yöntem geliştirmede naifi %5'ten az farkla geçiyor; naif yöntem neredeyse aynı iyilikte.";
    case "band_undercovers_development":
      return `%90 bandı, önceki artıklardan kurulduğunda değerlendirilen geliştirme dönemlerinin yalnız ${pct(p.coverage)}'ini kapsadı; gösterilen aralığı iyimser kabul edin.`;
    case "band_undercovers_final":
      return `Nominal %90 bandı ${p.origins} final dönemin yalnız ${pct(p.coverage)}'ini kapsadı. Bu gözlenen eksik kapsamadır, kalibre edilmiş %90 aralık değildir; final pencere ayar için hiç kullanılmaz.`;
    case "relative_band_collapsed":
      return "Göreli ölçek final pencerede veya sonraki dönemde sıfır tahminle karşılaştı; aralık sıfıra çöker. Kapsama ve genişlik betimseldir; bu aralık planlama için zayıftır.";
    case "final_window_worse_than_naive":
      return "Final pencerede seçilen yöntem naif referansı geçemedi; projeksiyonu zayıf kabul edin.";
    case "final_month_worse_than_naive":
      return `${(p.months as { month: string; weeks: number }[])
        .map((m) => `${m.month} (${m.weeks} final hafta)`)
        .join(", ")} döneminde seçilen yöntemin MAE'si naiften yüksek; final penceredeki üstünlük her ayda geçerli değil.`;
    case "slice_disagreement":
      return `Lider ülke dilimlerinin ${p.ready} tanesinden ${p.disagree} tanesinde, toplamda seçilen yöntem final pencerede naifi geçemedi; toplam sonuç her pazara aktarılamaz.`;
    default:
      return null;
  }
}

function forecastMethodLabel(id: string | undefined): [string, string] {
  const label = id ? FORECAST_METHOD_LABELS[id] : undefined;
  return label ?? [id ?? "—", id ?? "—"];
}

const FORECAST_METHOD_LABELS: Record<string, [string, string]> = {
  naive: ["Son hafta", "Last week"],
  seasonal_naive: ["Geçen sezonun aynı haftası", "Same week last season"],
  drift: [
    "Son hafta + ortalama haftalık değişim",
    "Last week plus average weekly change",
  ],
  mean2: ["Son 2 hafta ortalaması", "Last 2-week mean"],
  mean4: ["Son 4 hafta ortalaması", "Last 4-week mean"],
  mean8: ["Son 8 hafta ortalaması", "Last 8-week mean"],
  "ses_0.2": ["Üstel düzleştirme (α 0,2)", "Exponential smoothing (α 0.2)"],
  "ses_0.5": ["Üstel düzleştirme (α 0,5)", "Exponential smoothing (α 0.5)"],
  "ses_0.8": ["Üstel düzleştirme (α 0,8)", "Exponential smoothing (α 0.8)"],
  "holt_damped_0.3_0.1": [
    "Sönümlü Holt eğilimi (α 0,3)",
    "Damped Holt trend (α 0.3)",
  ],
  "holt_damped_0.6_0.1": [
    "Sönümlü Holt eğilimi (α 0,6)",
    "Damped Holt trend (α 0.6)",
  ],
};
type Statement = {
  type: string;
  text: string;
  evidence: string[];
  candidate?: string;
};
type Brief = {
  decision_id: string;
  routing?: Record<string, RoutingReceipt>;
  objective: string;
  dataset_sha256: string;
  filters: Filters;
  output_sha256: string;
  summary: string;
  references: Record<string, Reference>;
  recommendations: Recommendation[];
  forecast: Forecast;
  scenario: null | {
    baseline_pence: number;
    assumed_gross_pence: number;
    gross_delta_pence: number;
    budget_pence: number;
  };
  score_policy: { note: string };
  scope_note: string;
  context_xml: string;
  analysis_context_xml?: string;
  narrative?: {
    version: string;
    local: Statement[];
    model: Statement[] | null;
    provider: { status: string; http_status?: number; attempts?: number };
  };
  report_markdown: string;
  knowledge: {
    id: string;
    title: string;
    body: string;
    url?: string;
    sha256: string;
  }[];
  provider: { status: string; http_status?: number };
  artifacts: {
    countries: { label: string; pence: number }[];
    products: { label: string; pence: number }[];
    graph: {
      nodes: { id: string; label: string }[];
      edges: { source: string; target: string; weight: number }[];
    };
  };
};
type History = {
  decision_id: string;
  dataset_id: string;
  created_at: string;
  summary: string;
};
function saveFile(name: string, body: string, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type })),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function DecisionStudio({
  dataset,
  filters,
  csrf,
  providerLabel,
  busy,
  activity,
}: {
  dataset: string;
  filters: Filters;
  csrf: string | null;
  providerLabel: string | null;
  busy: boolean;
  activity: (n: number) => void;
}) {
  const { t, locale } = useLocale();
  const [objective, setObjective] = useState("balanced"),
    [withScenario, setWithScenario] = useState(false),
    [volume, setVolume] = useState("5"),
    [price, setPrice] = useState("0"),
    [budget, setBudget] = useState("0");
  const [brief, setBrief] = useState<Brief | null>(null),
    [history, setHistory] = useState<History[]>([]),
    [running, setRunning] = useState(false),
    [revision, setRevision] = useState(0),
    [error, setError] = useState(""),
    [refKey, setRefKey] = useState("");
  const version = useRef(0),
    top = useRef<HTMLDivElement>(null),
    reference = useRef<HTMLElement>(null),
    scope = JSON.stringify(filters);
  useEffect(() => {
    version.current++;
    setBrief(null);
    setRefKey("");
    setError("");
  }, [dataset, scope]);
  async function loadHistory() {
    const r = await api.get<{ decisions: History[] }>(BASE + "/decisions");
    if (r.ok) setHistory(r.data.decisions);
  }
  useEffect(() => {
    void loadHistory();
  }, []);
  useEffect(() => {
    if (brief) top.current?.closest("dialog")?.scrollTo({ top: 0 });
  }, [revision]);
  useEffect(() => {
    if (refKey) {
      reference.current?.scrollIntoView({ block: "nearest" });
      reference.current?.focus();
    }
  }, [refKey]);
  const money = (n: number) =>
    new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
      style: "currency",
      currency: "GBP",
      maximumFractionDigits: 2,
    }).format(n);
  const number = (n: number) =>
    new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
      maximumFractionDigits: 3,
    }).format(n);
  async function run() {
    const current = version.current;
    setRunning(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<Brief>(
        BASE + "/decisions",
        {
          dataset,
          filters,
          locale,
          objective,
          ...(withScenario
            ? {
                scenario: {
                  volume_pct: Number(volume),
                  price_pct: Number(price),
                  budget_gbp: Number(budget),
                },
              }
            : {}),
        },
        csrf,
      );
      if (current === version.current) {
        if (r.ok) {
          setBrief(r.data);
          setRevision((n) => n + 1);
          setRefKey("");
          void loadHistory();
        } else
          setError(
            r.error.detail ||
              t("Karar özeti oluşturulamadı.", "Decision brief failed."),
          );
      }
    } finally {
      setRunning(false);
      activity(-1);
    }
  }
  async function open(id: string) {
    setRunning(true);
    activity(1);
    setError("");
    const current = version.current;
    try {
      const r = await api.get<Brief>(BASE + "/decisions/" + id);
      if (current === version.current) {
        if (r.ok) {
          setBrief(r.data);
          setRevision((n) => n + 1);
          setRefKey("");
        } else setError(t("Kayıt bulunamadı.", "Record not found."));
      }
    } finally {
      setRunning(false);
      activity(-1);
    }
  }
  function invalidate() {
    version.current++;
    setBrief(null);
    setRefKey("");
  }
  const ref = brief?.references[refKey],
    forecast = brief?.forecast;
  const chart = forecast?.history.slice(-16).map((w) => {
    const match = forecast.holdout?.records.find((r) => r.target === w.period);
    return {
      period: w.period,
      observed: w.pence / 100,
      predicted: match ? match.predicted_pence / 100 : undefined,
    };
  });
  const refLabel: Record<string, string> = {
    gross: t("Brüt satış", "Gross sales"),
    orders: t("Sipariş", "Orders"),
    excluded: t("Dışlanan satır", "Excluded rows"),
    duplicates: t("Tekrar satır", "Duplicate rows"),
    country_share: t("Lider ülke payı", "Leading country share"),
    basket_support: t("Birlikte alım", "Co-purchase"),
    forecast_mae: t("Tahmin hatası", "Forecast error"),
    baseline_mae: t("Referans hatası", "Benchmark error"),
    scenario_base: t("Senaryo başlangıcı", "Scenario baseline"),
    scenario_delta: t("Varsayımsal fark", "Assumed delta"),
    complete_weeks: t("Tam hafta", "Complete weeks"),
    final_origins: t("Son test dönemi sayısı", "Final-origin count"),
    business_validation: t("İş doğrulaması", "Business validation"),
    next_point: t("Sonraki hafta projeksiyonu", "Next-week projection"),
    scenario_volume: t("Varsayılan hacim değişimi", "Assumed volume change"),
    scenario_price: t("Varsayılan fiyat değişimi", "Assumed price change"),
  };
  // Locale percent style ("%84,6" in Turkish, "84.6%" in English), one decimal like the narrative text.
  const percent = (ratio: number) =>
    new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
      style: "percent",
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(ratio);
  const formatRef = (k: string) => {
    const r = brief?.references[k];
    if (!r) return k;
    return r.unit === "pence"
      ? money(r.value / 100)
      : r.unit === "GBP"
        ? money(r.value)
        : r.unit === "ratio"
          ? percent(r.value)
          : r.unit === "percent"
            ? percent(r.value / 100)
            : number(r.value);
  };
  // Evidence chips under each statement open the referenced calculation; the tree shows how statements chain.
  const evidenceChips = (s: { evidence?: string[] }) =>
    s.evidence && s.evidence.length > 0 ? (
      <div className="wb-evidence-links">
        {s.evidence.map((k) => (
          <button
            key={k}
            className="wb-text-btn"
            onClick={() => {
              setRefKey(k);
              if (refKey === k) reference.current?.focus();
            }}
          >
            <Database size={16} />
            {refLabel[k] || k}: {formatRef(k)}
            <ArrowRight size={16} />
          </button>
        ))}
      </div>
    ) : null;
  const narrativeList = (items: Statement[]) => (
    <ReasoningTree
      statements={items}
      renderEvidence={evidenceChips}
      label={t("Analist anlatısı", "Analyst narrative")}
    />
  );
  return (
    <div className="wb-decision-studio" ref={top}>
      {!brief && (
        <div className="wb-decision-intro">
          <div className="wb-eyebrow">
            {t("VERİDEN KARARA", "FROM EVIDENCE TO ACTION")}
          </div>
          <h3>
            {t(
              "Bir sonraki adımı dayanaklarıyla seçin.",
              "Choose the next step with its evidence.",
            )}
          </h3>
          <p>
            {t(
              "Ölçümü gözden geçirin, haftalık tahmini sınayın ve varsayımlarınızı karşılaştırın. Her önerinin sınırlarını ve kaynaklarını birlikte görün.",
              "Review measurement, test a weekly forecast and compare assumptions. Inspect the evidence and limits behind every recommendation.",
            )}
          </p>
        </div>
      )}
      <details
        className="wb-decision-config"
        open={!brief}
        key={"config-" + revision}
      >
        <summary>
          {brief
            ? t("Yeni analiz ayarları", "New analysis settings")
            : t("Analiz ayarları", "Analysis settings")}
        </summary>
        <form
          className="wb-decision-form"
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
        >
          <label>
            {t("Karar odağı", "Decision focus")}
            <select
              value={objective}
              disabled={running || busy}
              onChange={(e) => {
                setObjective(e.target.value);
                invalidate();
              }}
            >
              <option value="balanced">
                {t("Dengeli inceleme", "Balanced review")}
              </option>
              <option value="growth">
                {t("Büyüme fırsatlarını incele", "Investigate growth")}
              </option>
              <option value="resilience">
                {t("Dayanıklılık ve risk", "Resilience and risk")}
              </option>
            </select>
          </label>
          <label className="wb-decision-check">
            <input
              type="checkbox"
              checked={withScenario}
              disabled={running || busy}
              onChange={(e) => {
                setWithScenario(e.target.checked);
                invalidate();
              }}
            />
            {t(
              "Fiyat ve hacim senaryosu ekle",
              "Add a price and volume scenario",
            )}
          </label>
          {withScenario && (
            <fieldset className="wb-scenario-inputs">
              <legend>
                {t(
                  "Varsayımlar · son tam hafta esas alınır",
                  "Assumptions · last complete week baseline",
                )}
              </legend>
              <label>
                {t("Hacim değişimi (%)", "Volume change (%)")}
                <input
                  type="number"
                  required
                  min="-50"
                  max="100"
                  step="0.1"
                  value={volume}
                  disabled={running || busy}
                  onChange={(e) => {
                    setVolume(e.target.value);
                    invalidate();
                  }}
                />
              </label>
              <label>
                {t("Fiyat değişimi (%)", "Price change (%)")}
                <input
                  type="number"
                  required
                  min="-50"
                  max="100"
                  step="0.1"
                  value={price}
                  disabled={running || busy}
                  onChange={(e) => {
                    setPrice(e.target.value);
                    invalidate();
                  }}
                />
              </label>
              <label>
                {t("Deney bütçesi (£)", "Experiment budget (£)")}
                <input
                  type="number"
                  required
                  min="0"
                  max="1000000"
                  step="0.01"
                  value={budget}
                  disabled={running || busy}
                  onChange={(e) => {
                    setBudget(e.target.value);
                    invalidate();
                  }}
                />
              </label>
              <p>
                {t(
                  "Fiyat ve hacim bağımsız varsayımlardır. Talep tepkisi, kâr ve yatırım getirisi hesaplanmaz.",
                  "Price and volume are independent assumptions. Demand response, profit and ROI are not calculated.",
                )}
              </p>
            </fieldset>
          )}
          <button
            className="wb-btn wb-primary"
            disabled={running || busy}
            type="submit"
          >
            {running ? (
              <Spinner className="spin" size={18} />
            ) : (
              <ArrowRight size={16} />
            )}{" "}
            {t("Karar özeti oluştur", "Build decision brief")}
          </button>
        </form>
      </details>
      {error && (
        <p className="wb-alert" role="alert">
          {error}
        </p>
      )}
      {brief && (
        <div className="wb-decision-result" key={revision}>
          <header className="wb-decision-head">
            <div>
              <span className="wb-eyebrow">
                {t("KARAR ÖZETİ", "DECISION BRIEF")}
              </span>
              <h3>{brief.summary}</h3>
              <p>
                {Object.keys(brief.filters).length
                  ? JSON.stringify(brief.filters)
                  : t("Veri setinin tamamı", "Entire dataset")}{" "}
                · {brief.dataset_sha256.slice(0, 12)}
              </p>
            </div>
            <div className="wb-decision-downloads">
              <button
                className="wb-btn"
                onClick={() =>
                  saveFile(
                    "decision-brief.md",
                    brief.report_markdown,
                    "text/markdown;charset=utf-8",
                  )
                }
              >
                {t("Raporu indir", "Download report")}
              </button>
              <button
                className="wb-text-btn"
                onClick={() =>
                  saveFile(
                    "decision-brief.json",
                    JSON.stringify(brief, null, 2),
                    "application/json",
                  )
                }
              >
                JSON
              </button>
            </div>
          </header>
          {brief.routing && (
            <div className="wb-routing-row">
              <RoutingBadge routing={brief.routing.decision_focus} providerLabel={providerLabel} />
              <RoutingBadge routing={brief.routing.decision_narrative} providerLabel={providerLabel} />
            </div>
          )}
          {brief.provider.status !== "not_requested" && (
            <p className="wb-provider-notice" role="status">
              {brief.provider.status === "selected"
                ? t(
                    "Dil modeli odakları işaretledi. Sıralama ve puanlar yerel hesaplardan geliyor.",
                    "The language model marked focus items. Local calculations determine scores and ordering.",
                  )
                : brief.provider.http_status === 429
                  ? t(
                      "Dil modelinin kullanım sınırı doldu (429). Aşağıdaki özet yerel hesaplardan üretildi.",
                      "The language model's usage limit was reached (429). The brief below uses local calculations.",
                    )
                : brief.provider.http_status === 402
                  ? t(
                      "Dil modeli isteği kredi/faturalandırma nedeniyle tamamlanamadı (402). Aşağıdaki özet yerel hesaplardan üretildi.",
                      "Language-model credit/billing gate (402). The brief below uses local calculations.",
                    )
                  : t(
                      "Dil modeli seçimi kullanılamadı; yerel karar özeti gösteriliyor.",
                      "Language-model selection unavailable; showing the local decision brief.",
                    )}
            </p>
          )}
          <details className="wb-score-explainer">
            <summary>
              {t(
                "Dayanak skoru nasıl okunmalı?",
                "How to read the support score",
              )}
            </summary>
            <p>{brief.score_policy.note}</p>
            <p>
              {t(
                "İzlenebilirlik 40 · 30+ sipariş 20 · bağımsız geçmiş testte referanstan düşük hata 20 · iş doğrulaması 20 (henüz 0).",
                "Traceability 40 · 30+ orders 20 · lower error than naive on held-out origins 20 · business validation 20 (currently 0).",
              )}
            </p>
          </details>
          {brief.narrative && (
            <section
              className="wb-narrative-section"
              aria-label={t("Analist anlatısı", "Analyst narrative")}
            >
              <div className="wb-panel-head">
                <div>
                  <h3>{t("Analist anlatısı", "Analyst narrative")}</h3>
                  <p>
                    {t(
                      "Her cümle türüyle etiketlidir ve dayandığı hesaba bağlıdır. Sayılar yalnız yerel hesaplardan gelir.",
                      "Every sentence is typed and linked to the calculation it rests on. Numbers come only from local calculations.",
                    )}
                  </p>
                </div>
              </div>
              {narrativeList(brief.narrative.local)}
              {brief.narrative.provider.status !== "not_requested" && (
                <p className="wb-provider-notice" role="status">
                  {brief.narrative.provider.status === "accepted"
                    ? t(
                        "Model anlatısının biçimi, atıfları, sayıları ve her sayının ölçü ile dönem bağı kontrol edildi. Bu kelime düzeyinde bir kontroldür; yorumların anlamca doğru olduğunu kanıtlamaz, dayanakları inceleyin. Yerel anlatı yukarıda korunur.",
                        "The model narrative's schema, citations, numbers and each number's measure and period were checked. This is a word-level check and does not prove its interpretations are correct; inspect the evidence. The local narrative above is kept.",
                      )
                    : brief.narrative.provider.status === "rejected"
                      ? t(
                          "Model anlatısı doğrulamayı geçemedi (bilinmeyen dayanak, desteklenmeyen sayı, yanlış ölçüye ya da döneme bağlanmış değer veya şema); iki denemeden sonra yerel anlatı gösteriliyor.",
                          "The model narrative failed validation (unknown evidence, unsupported number, a value attached to the wrong measure or period, or schema) after two attempts; the local narrative is shown.",
                        )
                      : brief.narrative.provider.http_status === 429
                        ? t(
                            "Model anlatısı kullanım sınırı nedeniyle alınamadı (429); yerel anlatı gösteriliyor.",
                            "Model narrative unavailable: the usage limit was reached (429); the local narrative is shown.",
                          )
                      : brief.narrative.provider.http_status === 402
                        ? t(
                            "Model anlatısı kredi/faturalandırma nedeniyle alınamadı (402); yerel anlatı gösteriliyor.",
                            "Model narrative unavailable due to the credit/billing gate (402); the local narrative is shown.",
                          )
                        : t(
                            "Model anlatısı kullanılamadı; yerel anlatı gösteriliyor.",
                            "Model narrative unavailable; the local narrative is shown.",
                          )}
                </p>
              )}
              {brief.narrative.model && (
                <details className="wb-narrative-model">
                  <summary>
                    {t(
                      "Model yorumu · biçim ve sayı kontrolü",
                      "Model interpretation · schema and numbers checked",
                    )}{" "}
                    · {brief.narrative.model.length}
                  </summary>
                  {narrativeList(brief.narrative.model)}
                </details>
              )}
            </section>
          )}
          <ol className="wb-recommendations">
            {brief.recommendations.map((c, i) => (
              <li key={c.id}>
                <div className="wb-recommendation-title">
                  <span className="wb-step-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h4>{c.title}</h4>
                  <span className="wb-support-score">
                    {c.support_score}
                    <small>/100</small>
                  </span>
                </div>
                {c.model_focus && (
                  <span className="wb-model-focus">
                    {t("Model odağı", "Model focus")}
                  </span>
                )}
                <p>{c.explanation}</p>
                <div className="wb-evidence-links">
                  {c.evidence_refs.map((k) => (
                    <button
                      key={k}
                      className="wb-text-btn"
                      onClick={() => {
                        setRefKey(k);
                        if (refKey === k) reference.current?.focus();
                      }}
                    >
                      <Database size={16} />
                      {refLabel[k] || k}: {formatRef(k)}
                      <ArrowRight size={16} />
                    </button>
                  ))}
                </div>
                <details>
                  <summary>
                    {t(
                      "Karar adımları ve eksik bilgiler",
                      "Decision steps and missing evidence",
                    )}
                  </summary>
                  <ol>
                    {c.steps.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ol>
                  <ul>
                    {c.missing.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                  <p className="wb-score-parts">
                    {Object.entries(c.score_components)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ")}
                  </p>
                </details>
              </li>
            ))}
          </ol>
          {ref && (
            <section
              className="wb-evidence-inspector"
              ref={reference}
              tabIndex={-1}
              aria-label={t("Seçilen dayanak", "Selected evidence")}
            >
              <h4>{refLabel[refKey]}</h4>
              <strong>{formatRef(refKey)}</strong>
              <p>
                <code>{ref.path}</code> · {ref.unit}
              </p>
              <p>{brief.scope_note}</p>
              {ref.anchor === "country-ranking" && (
                <TableWrap>
                  <table>
                    <thead>
                      <tr>
                        <th>{t("Ülke", "Country")}</th>
                        <th>{t("Brüt satış", "Gross sales")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {brief.artifacts.countries.map((c) => (
                        <tr key={c.label}>
                          <td>{c.label}</td>
                          <td>{money(c.pence / 100)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
              )}
              {ref.anchor === "basket-network" && (
                <TableWrap>
                  <table>
                    <thead>
                      <tr>
                        <th>{t("Ürün çifti", "Product pair")}</th>
                        <th>{t("Fatura", "Invoices")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...brief.artifacts.graph.edges]
                        .sort((a, b) => b.weight - a.weight)
                        .slice(0, 10)
                        .map((e, i) => (
                          <tr key={i}>
                            <td>
                              {[e.source, e.target]
                                .map(
                                  (id) =>
                                    brief.artifacts.graph.nodes.find(
                                      (n) => n.id === id,
                                    )?.label || id,
                                )
                                .join(" · ")}
                            </td>
                            <td>{e.weight}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </TableWrap>
              )}
              <small>SHA-256 · {brief.output_sha256.slice(0, 20)}</small>
            </section>
          )}
          <section className="wb-forecast-result">
            <div className="wb-panel-head">
              <div>
                <h3>
                  {t("Haftalık satış projeksiyonu", "Weekly sales projection")}
                </h3>
                <p>
                  {forecast?.complete_weeks}{" "}
                  {t(
                    "tam hafta · bir hafta ileri",
                    "complete weeks · one week ahead",
                  )}
                </p>
              </div>
            </div>
            {forecast?.status === "ready" &&
            forecast.next &&
            forecast.holdout ? (
              <>
                <div className="wb-forecast-metrics">
                  <div>
                    <span>
                      {t("Sonraki hafta", "Next week")} · {forecast.next.period}
                    </span>
                    <strong>{money(forecast.next.pence / 100)}</strong>
                    <small>
                      {money(forecast.next.lower_pence / 100)} –{" "}
                      {money(forecast.next.upper_pence / 100)}
                    </small>
                  </div>
                  <div>
                    <span>
                      {t(
                        `Test MAE · ${forecast.split?.holdout_origins ?? forecast.holdout.records.length} dönem`,
                        `Test MAE · ${forecast.split?.holdout_origins ?? forecast.holdout.records.length} origins`,
                      )}
                    </span>
                    <strong>{money(forecast.holdout.selected.mae_gbp)}</strong>
                    <small>
                      {t("Naif referans", "Naive benchmark")}:{" "}
                      {money(forecast.holdout.naive.mae_gbp)}
                    </small>
                  </div>
                  <div>
                    <span>{t("Seçilen yöntem", "Selected method")}</span>
                    <strong>
                      {t(...forecastMethodLabel(forecast.selected))}
                    </strong>
                    <small>
                      {t(
                        `${forecast.split?.development_origins ?? "—"} geliştirme dönemiyle, ${forecast.leaderboard?.length ?? "—"} kayıtlı yöntem arasından seçildi`,
                        `Chosen among ${forecast.leaderboard?.length ?? "—"} registered methods on ${forecast.split?.development_origins ?? "—"} development origins only`,
                      )}
                    </small>
                  </div>
                </div>
                {forecast.holdout.selected.mae_gbp >=
                  forecast.holdout.naive.mae_gbp && (
                  <p className="wb-provider-notice">
                    {t(
                      "Seçilen yöntem son testte naif referansı geçemedi. Bu projeksiyon tek başına operasyon kararı için yeterli değildir.",
                      "The selected method did not beat naive on the final test. This projection alone is insufficient for an operating decision.",
                    )}
                  </p>
                )}
                {forecast.diagnostics && forecast.diagnostics.length > 0 && (
                  <ul className="wb-forecast-diagnostics">
                    {forecast.diagnostics.map((d) => (
                      <li key={d.code} data-severity={d.severity}>
                        {(locale === "tr" && diagnosticTr(d)) || d.message}
                      </li>
                    ))}
                  </ul>
                )}
                <div
                  className="wb-decision-chart"
                  role="img"
                  aria-label={t(
                    "Haftalık brüt satış ve geçmiş test tahminleri; değerler alttaki tabloda.",
                    "Weekly gross sales and held-out predictions; values in the table below.",
                  )}
                >
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={chart}>
                      <CartesianGrid vertical={false} stroke="var(--border)" />
                      <XAxis
                        dataKey="period"
                        fontSize={12}
                        tick={{ fill: "var(--muted)" }}
                        tickFormatter={(s) => String(s).slice(5)}
                        interval="preserveStartEnd"
                        minTickGap={28}
                      />
                      <YAxis
                        width={60}
                        fontSize={12}
                        tick={{ fill: "var(--muted)" }}
                        tickFormatter={(n) => `£${Math.round(n / 1000)}k`}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "var(--surface)",
                          borderColor: "var(--border)",
                          color: "var(--ink)",
                          borderRadius: 10,
                          padding: 12,
                        }}
                        formatter={(v) => money(Number(v))}
                      />
                      <Line
                        dataKey="observed"
                        name={t("Gözlenen", "Observed")}
                        stroke="var(--accent)"
                        dot={false}
                        strokeWidth={2}
                        isAnimationActive={false}
                      />
                      <Line
                        dataKey="predicted"
                        name={t("Geçmiş test tahmini", "Held-out prediction")}
                        stroke="#bb955b"
                        strokeDasharray="5 4"
                        connectNulls={false}
                        dot={false}
                        strokeWidth={2}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <TableWrap>
                  <table>
                    <caption>
                      {t(
                        `Yöntem seçimine katılmayan son ${forecast.split?.holdout_origins ?? forecast.holdout.records.length} geçmiş test`,
                        `Final ${forecast.split?.holdout_origins ?? forecast.holdout.records.length} origins excluded from method selection`,
                      )}
                    </caption>
                    <thead>
                      <tr>
                        <th>{t("Hafta başlangıcı", "Week start")}</th>
                        <th>{t("Gözlenen", "Observed")}</th>
                        <th>{t("Öngörü", "Prediction")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecast.holdout.records.map((r) => (
                        <tr key={r.target}>
                          <td>{r.target}</td>
                          <td>{money(r.actual_pence / 100)}</td>
                          <td>{money(r.predicted_pence / 100)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
                {forecast.slices &&
                  forecast.slices.some((s) => s.status === "ready") && (
                    <TableWrap>
                      <table>
                        <caption>
                          {t(
                            "Lider ülke dilimleri · aynı final dönemlerinde seçilen yöntem ve naif; yalnız teşhis, seçimi değiştirmez",
                            "Leading-country slices · selected method and naive on the same final origins; diagnostic only, never selects",
                          )}
                        </caption>
                        <thead>
                          <tr>
                            <th>{t("Ülke", "Country")}</th>
                            <th>{t("Seçilen MAE", "Selected MAE")}</th>
                            <th>{t("Naif MAE", "Naive MAE")}</th>
                            <th>{t("Sıfır hafta", "Zero weeks")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {forecast.slices
                            .filter((s) => s.status === "ready" && s.final)
                            .map((s) => (
                              <tr key={s.country}>
                                <th scope="row">{s.country}</th>
                                <td>
                                  {money(s.final!.selected.mae_gbp)}
                                  {!s.selected_beats_naive_final &&
                                    " · " +
                                      t("naifi geçemedi", "did not beat naive")}
                                </td>
                                <td>{money(s.final!.naive.mae_gbp)}</td>
                                <td>{s.zero_weeks ?? 0}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </TableWrap>
                  )}
                {forecast.period_slices && forecast.period_slices.length > 0 && (
                  <details className="wb-prep-details">
                    <summary>
                      {t(
                        "Aylara göre hata ve %90 bant kapsaması",
                        "Error and 90% band coverage by month",
                      )}
                    </summary>
                    <TableWrap
                      label={t(
                        "Aylara göre hata tablosu, yatay kaydırılabilir",
                        "Error by month table, horizontally scrollable",
                      )}
                    >
                      <table>
                        <caption>
                          {t(
                            "Hedef haftanın ayı. Geliştirme bantları yalnız önceki hatalardan kurulur (ilk 8 dönemde bant yok); son pencere sabit yarıçapı kullanır. Teşhistir, seçimi değiştirmez; aylar birkaç hafta içerir.",
                            "Month of the target week. Development bands use earlier errors only (none for the first 8 origins); the final window uses the fixed radius. Diagnostic, never selects; months hold a few weeks.",
                          )}
                        </caption>
                        <thead>
                          <tr>
                            <th scope="col">{t("Ay", "Month")}</th>
                            <th scope="col">{t("Aşama", "Phase")}</th>
                            <th scope="col">{t("Hafta", "Weeks")}</th>
                            <th scope="col">{t("Seçilen MAE", "Selected MAE")}</th>
                            <th scope="col">{t("Naif MAE", "Naive MAE")}</th>
                            <th scope="col">{t("Bant içinde", "Inside band")}</th>
                            <th scope="col">{t("Ort. genişlik", "Mean width")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {forecast.period_slices.map((m) => (
                            <tr key={m.month + m.phase}>
                              <th scope="row">{m.month}</th>
                              <td>
                                {m.phase === "final"
                                  ? t("Son pencere", "Final")
                                  : t("Geliştirme", "Development")}
                              </td>
                              <td>{m.n}</td>
                              <td>
                                {money(m.selected_mae_gbp)}
                                {!m.selected_beats_naive &&
                                  " · " + t("naifi geçemedi", "did not beat naive")}
                              </td>
                              <td>{money(m.naive_mae_gbp)}</td>
                              <td>
                                {m.band_n ? `${m.band_covered}/${m.band_n}` : "—"}
                              </td>
                              <td>
                                {m.band_mean_width_gbp === null
                                  ? "—"
                                  : money(m.band_mean_width_gbp)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </TableWrap>
                  </details>
                )}
                <p>
                  {t(
                    "Aralık, geliştirme hatalarından ampirik bir banttır; kalibre edilmiş güven düzeyi içermez. Veri tarihîdir, bugünün ticaretini temsil etmeyebilir.",
                    "The band is empirical development error, without a calibrated confidence level. Historical data may not represent current trading.",
                  )}
                  {forecast.uncertainty?.levels["0.9"] &&
                    forecast.uncertainty.levels["0.9"]
                      .development_rolling_coverage !== null && (
                      <>
                        {" "}
                        {t(
                          `%90 bandı, yalnız önceki geliştirme hatalarından kurulduğunda ${forecast.uncertainty.levels["0.9"].development_rolling_n} geliştirme döneminin %${Math.round(forecast.uncertainty.levels["0.9"].development_rolling_coverage * 100)}'ini kapsadı; son pencerede %${Math.round((forecast.uncertainty.levels["0.9"].final_window_coverage ?? 0) * 100)}.`,
                          `Built only from earlier development errors, the 90% band covered ${Math.round(forecast.uncertainty.levels["0.9"].development_rolling_coverage * 100)}% of ${forecast.uncertainty.levels["0.9"].development_rolling_n} development origins; ${Math.round((forecast.uncertainty.levels["0.9"].final_window_coverage ?? 0) * 100)}% of the final window.`,
                        )}
                        {forecast.uncertainty.levels["0.9"]
                          .final_mean_width_gbp != null && (
                          <>
                            {" "}
                            {t(
                              `Ortalama bant genişliği: geliştirmede ${money(forecast.uncertainty.levels["0.9"].development_mean_width_gbp ?? 0)}, son testte ${money(forecast.uncertainty.levels["0.9"].final_mean_width_gbp)}. Geliştirme kapsaması bant seçiminde kullanıldı; bağımsız kalibrasyon ölçümü değildir.`,
                              `Mean band width: ${money(forecast.uncertainty.levels["0.9"].development_mean_width_gbp ?? 0)} on development, ${money(forecast.uncertainty.levels["0.9"].final_mean_width_gbp)} on the final window. Development coverage was used to select the scaling; it is not independent calibration evidence.`,
                            )}
                          </>
                        )}
                      </>
                    )}
                </p>
              </>
            ) : (
              <p>
                {t(
                  "Geliştirme ve bağımsız test için en az 16 tam hafta gerekli. Bu kapsamda yeterli geçmiş bulunamadı.",
                  "At least 16 complete weeks are required for development and independent testing. This scope lacks sufficient history.",
                )}
              </p>
            )}
          </section>
          {brief.scenario && (
            <section className="wb-scenario-result">
              <h3>{t("Varsayımsal senaryo", "Hypothetical scenario")}</h3>
              <div className="wb-forecast-metrics">
                <div>
                  <span>{t("Son tam hafta", "Last complete week")}</span>
                  <strong>{money(brief.scenario.baseline_pence / 100)}</strong>
                </div>
                <div>
                  <span>
                    {t("Varsayımsal brüt satış", "Assumed gross sales")}
                  </span>
                  <strong>
                    {money(brief.scenario.assumed_gross_pence / 100)}
                  </strong>
                </div>
                <div>
                  <span>
                    {t("Brüt fark · kâr değildir", "Gross delta · not profit")}
                  </span>
                  <strong>
                    {money(brief.scenario.gross_delta_pence / 100)}
                  </strong>
                  <small>
                    {t("Ayrı bütçe", "Separate budget")}:{" "}
                    {money(brief.scenario.budget_pence / 100)}
                  </small>
                </div>
              </div>
              <p>
                {t(
                  "Bu hesap bir etki tahmini değildir. Fiyat ve hacim bağımsız değişir; marj, esneklik ve kapasite doğrulanmadan karar vermeyin.",
                  "This is not an effect forecast. Price and volume vary independently; validate margin, elasticity and capacity before deciding.",
                )}
              </p>
            </section>
          )}
          <details className="wb-decision-methods">
            <summary>
              {t(
                "Yöntem notları ve hesap kaydı",
                "Methodology and calculation record",
              )}
            </summary>
            {brief.knowledge.map((d) => (
              <article key={d.id}>
                <h4>{d.title}</h4>
                <p>{d.body}</p>
                {d.url && (
                  <a href={d.url} target="_blank" rel="noreferrer">
                    {t("Yöntem kaynağı", "Method source")}
                  </a>
                )}
              </article>
            ))}
            <button
              className="wb-btn"
              onClick={() =>
                saveFile(
                  "decision-context.xml",
                  brief.context_xml,
                  "application/xml",
                )
              }
            >
              {t("LLM bağlamını XML indir", "Download LLM context XML")}
            </button>
            {brief.analysis_context_xml && (
              <button
                className="wb-btn"
                onClick={() =>
                  saveFile(
                    "analysis-context.xml",
                    brief.analysis_context_xml!,
                    "application/xml",
                  )
                }
              >
                {t(
                  "Anlatı kanıt paketini XML indir",
                  "Download narrative evidence packet XML",
                )}
              </button>
            )}
            <p>
              <code>{brief.output_sha256}</code>
            </p>
          </details>
        </div>
      )}
      <details className="wb-decision-history">
        <summary>
          <Findings size={20} />
          {t("Karar arşivim", "My decision archive")} · {history.length}
          <ChevronRight size={20} />
        </summary>
        <ul>
          {history.map((h) => (
            <li key={h.decision_id}>
              <div>
                <strong>{h.summary}</strong>
                <small>
                  {new Date(h.created_at).toLocaleString(
                    locale === "tr" ? "tr-TR" : "en-GB",
                  )}{" "}
                  · {h.dataset_id}
                </small>
              </div>
              <button
                className="wb-btn"
                disabled={running || busy}
                onClick={() => void open(h.decision_id)}
              >
                {t("Aç", "Open")}
              </button>
            </li>
          ))}
        </ul>
        {!history.length && (
          <p>
            {t(
              "Oluşturduğunuz karar özetleri burada saklanır.",
              "Your decision briefs will be saved here.",
            )}
          </p>
        )}
      </details>
    </div>
  );
}
