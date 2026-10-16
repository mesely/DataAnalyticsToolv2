import { ChevronRight, Download, ShieldCheck } from "./BrandIcons";
import { TableWrap } from "./TableWrap";
import { Search, BookOpen, Code2 } from "./BrandIcons";
import React, { useEffect, useRef, useState } from "react";
import { Play, Loader2 } from "lucide-react";
import { api } from "../api";
import { useLocale } from "./Locale";
import type { Filters, SavedRun } from "./types";
const BASE = "/v1/dashboard/workbench";
type QueryResult = {
  query_id: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  warnings: string[];
  evidence: {
    output_sha256: string;
    source_id: string;
    duration_ms: number;
    parameters: unknown[];
    scope_sql: string;
    statement: string;
    limits: { rows: number; timeout_s: number };
  };
};
type ContextHit = {
  id: string;
  kind: string;
  title: string;
  body: string;
  score: number;
};
function blobDownload(name: string, data: Blob) {
  const url = URL.createObjectURL(data),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const EXAMPLES: [string, string, string][] = [
  [
    "Ülke satışları",
    "Sales by country",
    "SELECT country, SUM(line_pence) / 100.0 AS gross_sales_gbp, COUNT(DISTINCT invoice) AS orders\nFROM transactions\nGROUP BY country\nORDER BY gross_sales_gbp DESC",
  ],
  [
    "Aylık trend",
    "Monthly trend",
    "SELECT strftime(order_date, '%Y-%m') AS month,\n       SUM(line_pence) / 100.0 AS gross_sales_gbp\nFROM transactions\nGROUP BY month\nORDER BY month",
  ],
  [
    "Ürünler",
    "Products",
    "SELECT product_id, MIN(product) AS product,\n       SUM(quantity) AS units, SUM(line_pence) / 100.0 AS gross_sales_gbp\nFROM transactions\nGROUP BY product_id\nORDER BY gross_sales_gbp DESC\nLIMIT 20",
  ],
];
export function ExpertTools({
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
  activity: (delta: number) => void;
}) {
  const { t } = useLocale(),
    [statement, setStatement] = useState(EXAMPLES[0]![2]),
    [result, setResult] = useState<QueryResult | null>(null),
    [running, setRunning] = useState(false),
    [exporting, setExporting] = useState(false),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [hits, setHits] = useState<ContextHit[]>([]),
    [searched, setSearched] = useState(false),
    [searching, setSearching] = useState(false),
    [searchError, setSearchError] = useState("");
  const version = useRef(0);
  const scope = JSON.stringify(filters);
  useEffect(() => {
    version.current++;
    setResult(null);
    setHits([]);
    setError("");
    setSearchError("");
    setSearched(false);
  }, [dataset, scope]);
  async function run() {
    const current = version.current;
    setRunning(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<QueryResult>(
        BASE + "/sql",
        { dataset, filters, statement },
        csrf,
      );
      if (current === version.current) {
        if (r.ok) setResult(r.data);
        else {
          setError(r.error.detail || t("Sorgu reddedildi.", "Query refused."));
          setResult(null);
        }
      }
    } finally {
      setRunning(false);
      activity(-1);
    }
  }
  async function search() {
    const current = version.current;
    setSearching(true);
    activity(1);
    setSearchError("");
    try {
      const r = await api.post<{ hits: ContextHit[] }>(
        BASE + "/context",
        { dataset, query },
        csrf,
      );
      if (current === version.current) {
        setSearched(true);
        if (r.ok) setHits(r.data.hits);
        else
          setSearchError(
            r.error.detail ||
              t("Arama tamamlanamadı.", "Search could not finish."),
          );
      }
    } finally {
      setSearching(false);
      activity(-1);
    }
  }
  async function exportResult(format: "csv" | "xlsx") {
    if (!result) return;
    setExporting(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<{ base64: string }>(
        BASE + "/sql/" + result.query_id + "/export",
        { format },
        csrf,
      );
      if (r.ok) {
        const bytes = Uint8Array.from(atob(r.data.base64), (c) =>
          c.charCodeAt(0),
        );
        blobDownload(
          "query-result." + format,
          new Blob([bytes], {
            type:
              format === "csv"
                ? "text/csv;charset=utf-8"
                : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          }),
        );
      } else
        setError(r.error.detail || t("Çıktı indirilemedi.", "Export failed."));
    } finally {
      setExporting(false);
      activity(-1);
    }
  }
  return (
    <details className="wb-panel wb-expert">
      <summary>
        <span>
          <Code2 size={19} />
          <strong>{t("Uzman araçları", "Expert tools")}</strong>
          <small>
            {t(
              "SQL laboratuvarı ve bağlam arama",
              "SQL laboratory and context search",
            )}
          </small>
        </span>
        <ChevronRight size={19} />
      </summary>
      <div className="wb-expert-body">
        <div className="wb-expert-grid">
          <section>
            <h2>{t("SQL laboratuvarı", "SQL laboratory")}</h2>
            <p>
              {t(
                "Seçili veri, ülke ve tarih filtreleri geçerlidir. 500 satır · 5 saniye · salt okuma.",
                "Uses the selected data, country and dates. 500 rows · 5 seconds · read only.",
              )}
            </p>
            <div className="wb-sql-examples">
              {EXAMPLES.map(([tr, en, sql]) => (
                <button
                  key={tr}
                  disabled={running}
                  className="wb-btn"
                  onClick={() => setStatement(sql)}
                >
                  {t(tr, en)}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void run();
              }}
            >
              <label htmlFor="wb-sql">{t("Sorgunuz", "Your query")}</label>
              <textarea
                id="wb-sql"
                className="wb-sql-editor"
                spellCheck={false}
                value={statement}
                maxLength={12000}
                onChange={(e) => setStatement(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    if (!running && !busy && statement.trim()) void run();
                  }
                }}
              />
              <div className="wb-sql-actions">
                <span>
                  <ShieldCheck size={14} />
                  {t("Şema ve güvenlik denetimi", "Schema and safety checks")}
                </span>
                <button
                  className="wb-btn wb-primary"
                  disabled={running || busy || !statement.trim()}
                >
                  {running ? (
                    <Loader2 size={16} className="spin" />
                  ) : (
                    <Play size={16} />
                  )}{" "}
                  {t("Sorguyu çalıştır", "Run query")}
                </button>
              </div>
            </form>
            <p className="wb-small">
              {t(
                "transactions: fatura ürün satırı. Sipariş = COUNT(DISTINCT invoice). Join, müşteri kimliği ve dış dosya erişimi kapalı.",
                "transactions: invoice product rows. Orders = COUNT(DISTINCT invoice). Joins, customer identifiers and external files are disabled.",
              )}
            </p>
            {error && (
              <p className="wb-error-text" role="alert">
                {error}
              </p>
            )}
          </section>
          <aside className="wb-context-search">
            <h2>
              <BookOpen size={17} /> {t("Bağlamı bulun", "Find context")}
            </h2>
            <p>
              {t(
                "Metrik, formül ve kolonları seçili veri setinde arayın.",
                "Search metrics, formulas and columns in the selected dataset.",
              )}
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void search();
              }}
            >
              <label htmlFor="wb-context-query">
                {t("Metrik veya kolon", "Metric or column")}
              </label>
              <div>
                <input
                  id="wb-context-query"
                  maxLength={300}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t(
                    "brüt satış, sipariş, country…",
                    "gross sales, orders, country…",
                  )}
                />
                <button
                  className="wb-btn"
                  disabled={searching || running || busy || !query.trim()}
                  aria-label={t("Bağlamda ara", "Search context")}
                >
                  <Search size={17} />
                </button>
              </div>
            </form>
            {searchError && (
              <p role="alert" className="wb-error-text">
                {searchError}
              </p>
            )}
            <div aria-live="polite">
              {hits.map((h) => (
                <details key={h.kind + h.id}>
                  <summary>
                    <span>
                      {h.title}
                      <small>{h.kind}</small>
                    </span>
                    <ChevronRight size={14} />
                  </summary>
                  <p>{h.body}</p>
                </details>
              ))}
              {searched && !hits.length && !searchError && (
                <p>
                  {t(
                    "Eşleşme yok. Metrik veya kolon adını deneyin.",
                    "No match. Try a metric or column name.",
                  )}
                </p>
              )}
            </div>
            <details className="wb-schema-help">
              <summary>
                {t("Kullanılabilir kolonlar", "Available columns")}
              </summary>
              <code>
                invoice, product_id, product, quantity, unit_price, order_date,
                country, line_pence
              </code>
            </details>
          </aside>
        </div>
        {result && (
          <section className="wb-query-result" aria-live="polite">
            <div className="wb-panel-head">
              <div>
                <h2>{t("Sorgu sonucu", "Query result")}</h2>
                <p>
                  {result.row_count} {t("satır", "rows")} ·{" "}
                  {result.evidence.duration_ms} ms ·{" "}
                  {result.truncated
                    ? t(
                        "İlk 500 satır; sonuç kesildi",
                        "First 500 rows; result truncated",
                      )
                    : t("Sonuç tamamlandı", "Result complete")}
                </p>
              </div>
              <div className="wb-sql-exports">
                <button
                  className="wb-btn"
                  disabled={exporting || running}
                  onClick={() => void exportResult("csv")}
                >
                  <Download size={15} />
                  CSV
                </button>
                <button
                  className="wb-btn"
                  disabled={exporting || running}
                  onClick={() => void exportResult("xlsx")}
                >
                  <Download size={15} />
                  Excel
                </button>
              </div>
            </div>
            <TableWrap className="wb-query-table">
              <table>
                <caption>
                  {t(
                    "Çalıştırılan sorgunun sonucu; metrik tanımı SQL ifadenize bağlıdır.",
                    "Executed query results; metric meaning depends on your SQL.",
                  )}
                </caption>
                <thead>
                  <tr>
                    {result.columns.map((c) => (
                      <th scope="col" key={c}>
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((r, i) => (
                    <tr key={i}>
                      {result.columns.map((c) => (
                        <td key={c}>{r[c] === null ? "—" : String(r[c])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!result.rows.length && (
                <p>
                  {t(
                    "Bu sorgu satır döndürmedi.",
                    "This query returned no rows.",
                  )}
                </p>
              )}
            </TableWrap>
            <details className="wb-query-evidence">
              <summary>
                {t("Bu sorgunun kanıtı", "Evidence for this query")}
              </summary>
              <p>
                {t(
                  "Çalıştırılan ifade ve filtre kapsamı; veriyi değiştirmez.",
                  "Executed statement and filter scope; data is unchanged.",
                )}
              </p>
              <pre>{result.evidence.statement}</pre>
              <pre>
                {result.evidence.scope_sql}
                {"\n"}
                {JSON.stringify(result.evidence.parameters)}
              </pre>
              <code>{result.evidence.output_sha256}</code>
              <button
                className="wb-btn"
                onClick={() =>
                  blobDownload(
                    "query-evidence.json",
                    new Blob([JSON.stringify(result.evidence, null, 2)], {
                      type: "application/json",
                    }),
                  )
                }
              >
                <Download size={15} />
                {t("Kanıt JSON", "Evidence JSON")}
              </button>
            </details>
          </section>
        )}
      </div>
    </details>
  );
}

type Comparison = {
  metrics: {
    metric: string;
    before: number;
    after: number;
    delta: number;
    percent: number | null;
  }[];
  same_dataset_version: boolean;
  same_filters: boolean;
  before_filters: Filters;
  after_filters: Filters;
  currency: string;
  note: string;
};
export function CompareRuns({
  runs,
  csrf,
  blocked,
  activity,
}: {
  runs: SavedRun[];
  csrf: string | null;
  blocked: boolean;
  activity: (delta: number) => void;
}) {
  const { t, locale } = useLocale(),
    [before, setBefore] = useState(""),
    [after, setAfter] = useState(""),
    [result, setResult] = useState<Comparison | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const v = useRef(0);
  const count = runs.length;
  useEffect(() => {
    if (!before && runs[1]) setBefore(runs[1].run_id);
    if (!after && runs[0]) setAfter(runs[0].run_id);
  }, [count]);
  function change(which: "before" | "after", id: string) {
    v.current++;
    setResult(null);
    setError("");
    (which === "before" ? setBefore : setAfter)(id);
  }
  async function compare() {
    const current = v.current;
    setBusy(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<Comparison>(
        BASE + "/compare",
        { before_id: before, after_id: after },
        csrf,
      );
      if (current === v.current) {
        if (r.ok) setResult(r.data);
        else {
          setResult(null);
          setError(
            r.error.detail ||
              t("Karşılaştırma yapılamadı.", "Comparison failed."),
          );
        }
      }
    } finally {
      setBusy(false);
      activity(-1);
    }
  }
  const scope = (f: Filters) =>
      [
        f.country || t("Tüm ülkeler", "All countries"),
        f.start || "…",
        f.end || "…",
      ].join(" · "),
    format = (metric: string, value: number) =>
      metric === "gross_pence" || metric === "aov"
        ? new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
            style: "currency",
            currency: "GBP",
          }).format(metric === "gross_pence" ? value / 100 : value)
        : new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB").format(
            value,
          );
  const labels: Record<string, string> = {
    gross_pence: t("Brüt satış", "Gross sales"),
    orders: t("Sipariş", "Orders"),
    units: t("Satılan adet", "Units sold"),
    aov: t("Ortalama sipariş", "Average order value"),
  };
  return (
    <details className="wb-panel wb-expert wb-comparison">
      <summary>
        <span>
          <Code2 size={18} />
          <strong>
            {t("İki analizi karşılaştırın", "Compare two analyses")}
          </strong>
          <small>
            {t("Son 100 kayıt · B − A", "Last 100 records · B − A")}
          </small>
        </span>
        <ChevronRight size={18} />
      </summary>
      <div className="wb-expert-body">
        <div className="wb-compare-controls">
          {(["before", "after"] as const).map((which, i) => (
            <label key={which}>
              {i === 0 ? "A · " : "B · "}
              {t(
                i === 0 ? "Başlangıç analizi" : "Karşılaştırılan analiz",
                i === 0 ? "Baseline analysis" : "Compared analysis",
              )}
              <select
                value={which === "before" ? before : after}
                disabled={busy || blocked}
                onChange={(e) => change(which, e.target.value)}
              >
                <option value="">{t("Kayıt seçin", "Choose a record")}</option>
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.title} · {scope(r.recipe.filters)} ·{" "}
                    {r.run_id.slice(0, 6)}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <button
            className="wb-btn wb-primary"
            disabled={busy || blocked || !before || !after}
            onClick={() => void compare()}
          >
            {t("Karşılaştır", "Compare")}
          </button>
        </div>
        {error && (
          <p role="alert" className="wb-error-text">
            {error}
          </p>
        )}
        {result && (
          <>
            <div className="wb-callout">
              {result.same_dataset_version
                ? t("Aynı veri sürümü", "Same data version")
                : t("Farklı veri sürümleri", "Different data versions")}{" "}
              ·{" "}
              {result.same_filters
                ? t("Aynı filtreler", "Same filters")
                : t("Farklı filtre kapsamları", "Different filter scopes")}
              <br />
              A: {scope(result.before_filters)}
              <br />
              B: {scope(result.after_filters)}
            </div>
            <TableWrap>
              <table>
                <caption>
                  {t(
                    "B − A; farklar nedensellik göstermez. Sıfır bazda yüzde tanımsızdır.",
                    "B − A; differences do not establish causality. Percent is undefined at a zero baseline.",
                  )}
                </caption>
                <thead>
                  <tr>
                    {[
                      t("Metrik", "Metric"),
                      "A",
                      "B",
                      t("Fark", "Delta"),
                      "%",
                    ].map((x) => (
                      <th key={x}>{x}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.metrics.map((m) => (
                    <tr key={m.metric}>
                      <th scope="row">{labels[m.metric] || m.metric}</th>
                      <td>{format(m.metric, m.before)}</td>
                      <td>{format(m.metric, m.after)}</td>
                      <td>{format(m.metric, m.delta)}</td>
                      <td>
                        {m.percent === null ? "—" : m.percent.toFixed(2) + "%"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </>
        )}
      </div>
    </details>
  );
}
