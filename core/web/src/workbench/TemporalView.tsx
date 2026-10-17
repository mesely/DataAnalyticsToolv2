import { ChevronRight, Download, Info } from "./BrandIcons";
import { TableWrap } from "./TableWrap";
import React, { useEffect, useRef, useState } from "react";
import { PeriodChange, Spinner, Run } from "./BrandIcons";
import { api } from "../api";
import { useLocale } from "./Locale";
import type { Dataset, Filters } from "./types";
type Stage = {
  stage: string;
  months: string[];
  summary: {
    rows: number;
    orders: number;
    gross_pence: number;
    aov: number | null;
    product_hhi: number | null;
  };
  aov_bootstrap: {
    interval: [number, number] | null;
    reason?: string;
    n: number;
  };
  edges: { source: string; target: string; weight: number }[];
  edge_count: number;
  negative_affinity_share: number | null;
  coverage: {
    requested_start: string;
    requested_end: string;
    covered_days: number;
    requested_days: number;
    partial: boolean;
  };
};
type TemporalResult = {
  month: string;
  window: number;
  stages: Stage[];
  selected_products: { product_id: string; label: string }[];
  graph_comparison: {
    jaccard: number | null;
    new_edges: number;
    lost_edges: number;
    shared_edges: number;
    changes: {
      source: string;
      target: string;
      before: number;
      after: number;
      delta: number;
    }[];
  };
  notes: string[];
  evidence: {
    dataset_sha256: string;
    output_sha256: string;
    recipe_version: string;
    duration_ms: number;
  };
};
function middleMonth(data: Dataset) {
  const serial = (s: string) =>
    Number(s.slice(0, 4)) * 12 + Number(s.slice(5, 7)) - 1;
  const m = Math.floor((serial(data.start) + serial(data.end)) / 2);
  return `${Math.floor(m / 12)}-${String((m % 12) + 1).padStart(2, "0")}`;
}
export function TemporalView({
  data,
  filters,
  csrf,
  busy,
  minimum,
  activity,
  asDialog = false,
}: {
  data: Dataset;
  filters: Filters;
  csrf: string | null;
  busy: boolean;
  minimum: number;
  activity: (delta: number) => void;
  /** Rendered inside a modal dialog: the body only, without the collapsible panel. */
  asDialog?: boolean;
}) {
  const { t, locale } = useLocale(),
    [month, setMonth] = useState(middleMonth(data)),
    [windowMonths, setWindowMonths] = useState(1),
    [result, setResult] = useState<TemporalResult | null>(null),
    [running, setRunning] = useState(false),
    [error, setError] = useState("");
  const version = useRef(0),
    scope = JSON.stringify(filters);
  const fmt = new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
      maximumFractionDigits: 2,
    }),
    hhi = new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
      minimumFractionDigits: 4,
      maximumFractionDigits: 4,
    }),
    money = (n: number) =>
      new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
        style: "currency",
        currency: "GBP",
      }).format(n);
  useEffect(() => {
    version.current++;
    setMonth(middleMonth(data));
    setResult(null);
    setError("");
  }, [data.id, scope, minimum]);
  function invalidate() {
    version.current++;
    setResult(null);
    setError("");
  }
  async function run() {
    const current = version.current;
    setRunning(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<TemporalResult>(
        "/v1/dashboard/workbench/temporal",
        {
          dataset: data.id,
          filters,
          month,
          window: windowMonths,
          min_shared: minimum,
        },
        csrf,
      );
      if (current === version.current) {
        if (r.ok) setResult(r.data);
        else
          setError(
            r.error.detail ||
              t("Dönem analizi tamamlanamadı.", "Temporal analysis failed."),
          );
      }
    } finally {
      setRunning(false);
      activity(-1);
    }
  }
  function download() {
    if (!result) return;
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(result, null, 2)], {
          type: "application/json",
        }),
      ),
      a = document.createElement("a");
    a.href = url;
    a.download = "temporal-analysis.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const labels: Record<string, string> = {
      pre: t("Önceki dönem", "Before"),
      shock: t("Odak ay", "Focus month"),
      post: t("Sonraki dönem", "After"),
    },
    product = (id: string) =>
      result?.selected_products.find((p) => p.product_id === id)?.label || id;
  const body = (
      <div className="wb-expert-body">
        <p>
          {t(
            "Bir ayı çevresindeki dönemlerle karşılaştırın. Mevcut ülke ve tarih filtreleri uygulanır.",
            "Compare a month with its surrounding periods. Current country and date filters apply.",
          )}
        </p>
        {(data.id === "uci" || data.id === "uci2") && (
          <div className="wb-callout">
            {t(
              "UCI verisinde kargo, hizmet ve Manual gibi fatura kalemleri de korunur. Ürün/hizmet sınıflaması yapılmadan fiziksel ürün ilişkisi olarak yorumlamayın.",
              "UCI retains postage, service and Manual invoice lines. Interpret physical-product relationships only after product/service classification.",
            )}
          </div>
        )}
        <form
          className="wb-temporal-controls"
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
        >
          <label>
            {t("Odak ay", "Focus month")}
            <input
              type="month"
              required
              min={data.start.slice(0, 7)}
              max={data.end.slice(0, 7)}
              value={month}
              disabled={running}
              onChange={(e) => {
                invalidate();
                setMonth(e.target.value);
              }}
            />
          </label>
          <label>
            {t("Her iki taraftaki pencere", "Window on each side")}
            <select
              value={windowMonths}
              disabled={running}
              onChange={(e) => {
                invalidate();
                setWindowMonths(Number(e.target.value));
              }}
            >
              {[1, 2, 3].map((n) => (
                <option value={n} key={n}>
                  {n} {t("ay önce / ay sonra", "month(s) before / after")}
                </option>
              ))}
            </select>
          </label>
          <span>
            {t("Ortak sipariş eşiği", "Shared-order threshold")}: {minimum}
          </span>
          <button
            className="wb-btn wb-primary"
            disabled={busy || running || !month}
          >
            {running ? (
              <Spinner className="spin" size={16} />
            ) : (
              <Run size={16} />
            )}{" "}
            {t("Dönemleri karşılaştır", "Compare periods")}
          </button>
        </form>
        {error && (
          <p role="alert" className="wb-error-text">
            {error}
          </p>
        )}
        {result && (
          <div aria-live="polite">
            <p className="wb-small">
              {t(
                "Aralıklar betimleyicidir. — işareti yeterli veri veya yöntem koşulu olmadığını gösterir. Dönemleri karşılaştırırken takvim günlerini ve kapsamı dikkate alın.",
                "Intervals are descriptive. — means data or method conditions are insufficient. Compare periods with their calendar days and scope in mind.",
              )}
            </p>
            <div className="wb-temporal-stages">
              {result.stages.map((s) => (
                <section key={s.stage} className="wb-temporal-stage">
                  <div className="wb-eyebrow">{labels[s.stage]}</div>
                  <h3>{s.months.join(" · ")}</h3>
                  <span
                    className={
                      "wb-badge " + (s.coverage.partial ? "amber" : "green")
                    }
                  >
                    {s.coverage.partial
                      ? t("Kısmi tarih kapsamı", "Partial date coverage")
                      : t(
                          "Veri tarih sınırları içinde",
                          "Within dataset date bounds",
                        )}
                  </span>
                  <p>
                    {s.coverage.covered_days}/{s.coverage.requested_days}{" "}
                    {t("takvim günü", "calendar days")} ·{" "}
                    {fmt.format(s.summary.orders)} {t("sipariş", "orders")}
                  </p>
                  <strong className="wb-temporal-sales">
                    {s.summary.orders
                      ? money(s.summary.gross_pence / 100)
                      : t("Veri yok", "No data")}
                  </strong>
                  <small>{t("Dönem brüt satışı", "Period gross sales")}</small>
                  <dl>
                    <dt>{t("Ortalama sipariş", "Average order")}</dt>
                    <dd>
                      {s.summary.aov === null ? "—" : money(s.summary.aov)}
                    </dd>
                    <dt>{t("AOV %95 aralığı", "AOV 95% interval")}</dt>
                    <dd>
                      {s.aov_bootstrap.interval
                        ? s.aov_bootstrap.interval.map(money).join(" – ")
                        : s.aov_bootstrap.reason === "sample_limit"
                          ? t("Örnek sınırı", "Sample limit")
                          : t(
                              "En az 20 sipariş gerekli",
                              "At least 20 orders required",
                            )}
                    </dd>
                    <dt>{t("Ürün satış HHI", "Product sales HHI")}</dt>
                    <dd>
                      {s.summary.product_hhi === null
                        ? "—"
                        : hhi.format(s.summary.product_hhi)}
                    </dd>
                    <dt>{t("Birlikte alım kenarı", "Co-purchase edges")}</dt>
                    <dd>{s.edge_count}</dd>
                    <dt>
                      {t(
                        "Negatif profil ağırlığı payı",
                        "Negative profile weight share",
                      )}
                    </dt>
                    <dd>
                      {s.negative_affinity_share === null
                        ? "—"
                        : fmt.format(s.negative_affinity_share * 100) + "%"}
                    </dd>
                  </dl>
                </section>
              ))}
            </div>
            <div className="wb-callout">
              <Info size={16} />
              <span>
                {t(
                  "Önceki / sonraki dönem bağlantı örtüşmesi",
                  "Before / after edge overlap",
                )}
                :{" "}
                {result.graph_comparison.jaccard === null
                  ? "—"
                  : fmt.format(result.graph_comparison.jaccard * 100) +
                    "%"}{" "}
                · {result.graph_comparison.new_edges} {t("yeni", "new")} ·{" "}
                {result.graph_comparison.lost_edges} {t("kaybolan", "lost")} ·{" "}
                {result.selected_products.length}{" "}
                {t("sabit seçilmiş ürün", "fixed selected products")}
              </span>
            </div>
            <TableWrap>
              <table>
                <caption>
                  {t(
                    "Aynı ürün evreninde en büyük 15 kenar ağırlığı değişimi; kenarlar ortak fatura sayısını gösterir.",
                    "Largest 15 edge weight changes in the same product universe; edges count shared invoices.",
                  )}
                </caption>
                <thead>
                  <tr>
                    {[
                      t("Ürün çifti", "Product pair"),
                      t("Önce", "Before"),
                      t("Sonra", "After"),
                      t("Fark", "Delta"),
                    ].map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.graph_comparison.changes.map((e) => (
                    <tr key={e.source + e.target}>
                      <td>
                        {product(e.source)} ↔ {product(e.target)}
                      </td>
                      <td>{e.before}</td>
                      <td>{e.after}</td>
                      <td>
                        {e.delta > 0 ? "+" : ""}
                        {e.delta}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!result.graph_comparison.changes.length && (
                <p>
                  {t(
                    "Bu kapsamda değişen kenar yok.",
                    "No changed edges in this scope.",
                  )}
                </p>
              )}
            </TableWrap>
            <details className="wb-temporal-method">
              <summary>
                {t(
                  "Yöntem, belirsizlik ve sınırlar",
                  "Method, uncertainty and limits",
                )}
              </summary>
              <ul>
                {result.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
              <code>
                {result.evidence.recipe_version} ·{" "}
                {result.evidence.output_sha256}
              </code>
            </details>
            <button className="wb-btn" onClick={download}>
              <Download size={16} />
              {t(
                "Dönem analizi ve kanıt JSON",
                "Temporal analysis and evidence JSON",
              )}
            </button>
          </div>
        )}
      </div>
  );
  if (asDialog) return <div className="wb-expert wb-temporal is-dialog">{body}</div>;
  return (
    <details className="wb-panel wb-expert wb-temporal">
      <summary>
        <span>
          <PeriodChange size={20} />
          <strong>{t("Zaman içindeki değişim", "Change over time")}</strong>
          <small>
            {t(
              "Satış, yoğunlaşma ve aynı ürünlerin ilişkileri",
              "Sales, concentration and relationships of the same products",
            )}
          </small>
        </span>
        <ChevronRight size={20} />
      </summary>
{body}
    </details>
  );
}
