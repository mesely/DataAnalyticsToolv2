import { ChevronRight, ArrowRight } from "./BrandIcons";
import React, { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Bookmark, Database } from "./BrandIcons";
import { api } from "../api";
import { useLocale } from "./Locale";
import type { Filters } from "./types";
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
  notes: string[];
};
type Brief = {
  decision_id: string;
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
  busy,
  activity,
}: {
  dataset: string;
  filters: Filters;
  csrf: string | null;
  busy: boolean;
  activity: (n: number) => void;
}) {
  const { t, locale } = useLocale();
  const [objective, setObjective] = useState("balanced"),
    [useLlm, setUseLlm] = useState(false),
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
          use_llm: useLlm,
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
  };
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
          <details className="wb-decision-llm">
            <summary>
              {t("Llama ile odak seçimi", "Llama focus selection")}
              <ChevronRight size={16} />
            </summary>
            <label className="wb-decision-check">
              <input
                type="checkbox"
                checked={useLlm}
                disabled={running || busy}
                onChange={(e) => {
                  setUseLlm(e.target.checked);
                  invalidate();
                }}
              />
              {t("Bu özet için Llama kullan", "Use Llama for this brief")}
            </label>
            <p>
              {t(
                "Yalnız sayısal özetler ve yöntem notları HF sağlayıcısına gönderilir. Ham satırlar ve ürün/ülke adları gönderilmez. Model, hesaplanan adaylar arasından odak seçer; puanları ve sayıları değiştiremez.",
                "Only numerical aggregates and methodology notes are sent to the HF provider. Raw rows and product/country labels stay local. The model selects focus among computed candidates; it cannot change scores or numbers.",
              )}
            </p>
          </details>
          <button
            className="wb-btn wb-primary"
            disabled={running || busy}
            type="submit"
          >
            {running ? (
              <Loader2 className="spin" size={17} />
            ) : (
              <ArrowRight size={17} />
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
          {brief.provider.status !== "not_requested" && (
            <p className="wb-provider-notice" role="status">
              {brief.provider.status === "selected"
                ? t(
                    "Llama odakları işaretledi. Sıralama ve puanlar yerel hesaplardan geliyor.",
                    "Llama focus marked. Local calculations determine scores and ordering.",
                  )
                : brief.provider.http_status === 402
                  ? t(
                      "Llama isteği kredi/faturalandırma nedeniyle tamamlanamadı (402). Aşağıdaki özet yerel hesaplardan üretildi.",
                      "Llama credit/billing gate (402). The brief below uses local calculations.",
                    )
                  : t(
                      "Llama seçimi kullanılamadı; yerel karar özeti gösteriliyor.",
                      "Llama selection unavailable; showing the local decision brief.",
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
                    {t("Llama odağı", "Llama focus")}
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
                      <Database size={14} />
                      {refLabel[k] || k}:{" "}
                      {brief.references[k]!.unit === "pence"
                        ? money(brief.references[k]!.value / 100)
                        : brief.references[k]!.unit === "GBP"
                          ? money(brief.references[k]!.value)
                          : brief.references[k]!.unit === "ratio"
                            ? `${number(brief.references[k]!.value * 100)}%`
                            : number(brief.references[k]!.value)}
                      <ArrowRight size={13} />
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
              <strong>
                {ref.unit === "pence"
                  ? money(ref.value / 100)
                  : ref.unit === "GBP"
                    ? money(ref.value)
                    : ref.unit === "ratio"
                      ? `${number(ref.value * 100)}%`
                      : number(ref.value)}
              </strong>
              <p>
                <code>{ref.path}</code> · {ref.unit}
              </p>
              <p>{brief.scope_note}</p>
              {ref.anchor === "country-ranking" && (
                <div className="wb-table-wrap">
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
                </div>
              )}
              {ref.anchor === "basket-network" && (
                <div className="wb-table-wrap">
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
                </div>
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
                      {t("Test MAE · 4 dönem", "Test MAE · 4 origins")}
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
                      {forecast.selected === "naive"
                        ? t("Son hafta", "Last week")
                        : t("Son 4 hafta ortalaması", "Last 4-week mean")}
                    </strong>
                    <small>
                      {t(
                        "Yalnız geliştirme dönemiyle seçildi",
                        "Selected using development origins only",
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
                        fontSize={10}
                        tick={{ fill: "var(--muted)" }}
                        tickFormatter={(s) => String(s).slice(5)}
                      />
                      <YAxis
                        width={60}
                        fontSize={10}
                        tick={{ fill: "var(--muted)" }}
                        tickFormatter={(n) => `£${Math.round(n / 1000)}k`}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "var(--surface)",
                          borderColor: "var(--border)",
                          color: "var(--ink)",
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
                <div className="wb-table-wrap">
                  <table>
                    <caption>
                      {t(
                        "Yöntem seçimine katılmayan son dört geçmiş test",
                        "Final four origins excluded from method selection",
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
                </div>
                <p>
                  {t(
                    "Aralık, geliştirme hatalarından ampirik bir banttır; kalibre edilmiş güven düzeyi içermez. Veri tarihîdir, bugünün ticaretini temsil etmeyebilir.",
                    "The band is empirical development error, without a calibrated confidence level. Historical data may not represent current trading.",
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
            <p>
              <code>{brief.output_sha256}</code>
            </p>
          </details>
        </div>
      )}
      <details className="wb-decision-history">
        <summary>
          <Bookmark size={17} />
          {t("Karar arşivim", "My decision archive")} · {history.length}
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
