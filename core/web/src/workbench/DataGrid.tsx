import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { useLocale } from "./Locale";
import { RoutingBadge } from "./Routing";
import { TableWrap } from "./TableWrap";
import { Download, Send, Spinner, Info, Trend, Reset, ChevronDown, X } from "./BrandIcons";
import type { Filters, RoutingReceipt } from "./types";

// v3 G3: the overview's data table. Rows or a summary of the current scope; click a header to sort (Shift for a
// second and third key), type under a header to filter, page through, hide/rename/reorder columns (a view setting
// for the session — the source never changes), download what is shown as CSV or Excel, or ask the table in a sentence.

const BASE = "/v1/dashboard/workbench";
type Column = { name: string; type: "text" | "date" | "int" | "decimal" | "pence"; label: string };
type Row = Record<string, string | number | null>;
type Sort = { column: string; dir: "asc" | "desc" };
type ColFilter = { column: string; op: string; value: unknown };
type TableResult = {
  view: "rows" | "summary";
  group_by: string[];
  columns: Column[];
  rows: Row[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  evidence: { sql: string };
  note_top_n?: number;
  asked?: {
    prompt: string;
    spec: Record<string, unknown>;
    planner: { source: string; routing?: RoutingReceipt; note?: string };
    warnings: string[];
    request: { view: "summary"; group_by: string[]; filters_table: ColFilter[]; sort: Sort[]; page_size: number; filters: Filters };
  };
};
type ViewPrefs = { hidden: string[]; labels: Record<string, string>; order: string[] };

const GROUP_OPTIONS = ["country", "month", "week", "weekday", "product"] as const;
const PAGE_SIZES = [25, 50, 100, 500];

// Column settings live for the session only, in memory: the workspace keeps nothing in browser storage (D-103.1).
const sessionPrefs = new Map<string, ViewPrefs>();
function loadPrefs(key: string): ViewPrefs {
  return sessionPrefs.get(key) ?? { hidden: [], labels: {}, order: [] };
}
function savePrefs(key: string, p: ViewPrefs) {
  sessionPrefs.set(key, p);
}

export function DataGrid({
  dataset,
  filters,
  csrf,
  includeService,
  providerLabel,
  onOpenChart,
}: {
  dataset: string;
  filters: Filters;
  csrf: string | null;
  includeService: boolean;
  providerLabel?: string | null;
  onOpenChart: (prompt: string) => void;
}) {
  const { t, locale } = useLocale();
  const [view, setView] = useState<"rows" | "summary">("rows"),
    [groups, setGroups] = useState<string[]>(["country"]),
    [sort, setSort] = useState<Sort[] | null>(null),
    [colFilters, setColFilters] = useState<Record<string, string>>({}),
    [page, setPage] = useState(1),
    [size, setSize] = useState(50),
    [data, setData] = useState<TableResult | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [question, setQuestion] = useState(""),
    [asked, setAsked] = useState<TableResult["asked"] | null>(null),
    [showColumns, setShowColumns] = useState(false),
    [downloading, setDownloading] = useState<"" | "csv" | "xlsx">("");
  const prefKey = `cl-table:${dataset}:${view}:${groups.join("+")}`;
  const [prefs, setPrefs] = useState<ViewPrefs>(() => loadPrefs(prefKey));
  useEffect(() => setPrefs(loadPrefs(prefKey)), [prefKey]);
  const version = useRef(0);

  const nf = useMemo(() => new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB"), [locale]);
  const mf = useMemo(
    () => new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", { style: "currency", currency: "GBP" }),
    [locale],
  );
  const days = locale === "tr" ? ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"] : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const columnFilters = (cols: Column[], raw0: Record<string, string> = colFilters): ColFilter[] =>
    Object.entries(raw0).flatMap(([name, raw]) => {
      const col = cols.find((c) => c.name === name),
        v = raw.trim();
      if (!col || !v) return [];
      if (col.type === "text") return [{ column: name, op: "contains", value: v }];
      // Numbers and dates: "10", ">=10", "<=10", "10..20" (dates as yyyy-mm-dd).
      const range = v.match(/^(.+?)\.\.(.+)$/);
      const parse = (x: string) => (col.type === "date" ? x.trim() : Number(x.trim().replace(",", ".")) * (col.type === "pence" ? 100 : 1));
      if (range) return [{ column: name, op: "gte", value: parse(range[1]!) }, { column: name, op: "lte", value: parse(range[2]!) }];
      const m = v.match(/^(>=|<=|>|<|=)?\s*(.+)$/)!;
      const op = { ">=": "gte", ">": "gte", "<=": "lte", "<": "lte", "=": "eq" }[m[1] || "="]!;
      return [{ column: name, op, value: parse(m[2]!) }];
    }).filter((f) => typeof f.value === "string" || Number.isFinite(f.value as number));

  async function load(
    next: Partial<{ view: "rows" | "summary"; groups: string[]; sort: Sort[] | null; page: number; size: number; colFilters: Record<string, string> }> = {},
  ) {
    const v = next.view ?? view,
      g = next.groups ?? groups,
      body = {
        dataset,
        filters,
        locale,
        include_service: includeService,
        view: v,
        group_by: v === "summary" ? g : [],
        sort: (next.sort === undefined ? sort : next.sort) ?? undefined,
        page: next.page ?? page,
        page_size: next.size ?? size,
        // Column filters belong to the columns on screen; a new view or grouping starts without them.
        filters_table: columnFilters(data?.columns ?? [], next.colFilters ?? colFilters),
      };
    const mine = ++version.current;
    setBusy(true);
    setError("");
    const r = await api.post<TableResult>(BASE + "/table", body, csrf);
    if (mine !== version.current) return;
    setBusy(false);
    if (r.ok) {
      setData(r.data);
      setAsked(null);
    } else setError(r.error.detail || t("Tablo yüklenemedi.", "The table could not be loaded."));
  }
  useEffect(() => {
    setPage(1);
    void load({ page: 1 });
  }, [dataset, JSON.stringify(filters), includeService, locale]);

  async function ask(text: string) {
    const q = text.trim();
    if (!q) return;
    const mine = ++version.current;
    setBusy(true);
    setError("");
    const r = await api.post<TableResult>(BASE + "/table/ask", { dataset, filters, locale, prompt: q, include_service: includeService }, csrf);
    if (mine !== version.current) return;
    setBusy(false);
    if (r.ok && r.data.asked) {
      setData(r.data);
      setAsked(r.data.asked);
      setView("summary");
      setGroups(r.data.asked.request.group_by);
      setSort(r.data.asked.request.sort);
      setSize(r.data.asked.request.page_size);
      setPage(1);
      setColFilters({});
    } else if (!r.ok) setError(r.error.detail || t("Soru tabloya çevrilemedi.", "The question could not be turned into a table."));
  }

  async function download(format: "csv" | "xlsx") {
    if (!data) return;
    setDownloading(format);
    setError("");
    const visible = ordered.map((c) => c.name);
    const r = await api.post<{ filename: string; content_type: string; base64: string }>(
      BASE + "/table/export",
      {
        dataset,
        filters: asked?.request.filters ?? filters,
        locale,
        include_service: includeService,
        view: data.view,
        group_by: data.group_by,
        sort: sort ?? undefined,
        filters_table: asked ? asked.request.filters_table : columnFilters(data.columns),
        format,
        columns: visible,
        labels: prefs.labels,
      },
      csrf,
    );
    setDownloading("");
    if (!r.ok) {
      setError(r.error.detail || t("İndirilemedi.", "The download failed."));
      return;
    }
    const bytes = Uint8Array.from(atob(r.data.base64), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: r.data.content_type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = r.data.filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const cols = data?.columns ?? [];
  const ordered = useMemo(() => {
    const byName = new Map(cols.map((c) => [c.name, c]));
    const order = [...prefs.order.filter((n) => byName.has(n)), ...cols.map((c) => c.name).filter((n) => !prefs.order.includes(n))];
    return order.map((n) => byName.get(n)!).filter((c) => !prefs.hidden.includes(c.name));
  }, [cols, prefs]);
  const label = (c: Column) => prefs.labels[c.name] || c.label;
  const show = (c: Column, v: Row[string]) => {
    if (v === null || v === undefined) return "—";
    if (c.type === "pence") return mf.format(Number(v) / 100);
    if (c.type === "decimal") return mf.format(Number(v));
    if (c.type === "int") return c.name === "weekday" ? days[Number(v) - 1] ?? String(v) : nf.format(Number(v));
    return String(v);
  };
  const currentSort = sort ?? (data?.view === "rows" ? [{ column: "order_date", dir: "asc" as const }] : [{ column: "gross_pence", dir: "desc" as const }]);
  function clickSort(name: string, multi: boolean) {
    const i = currentSort.findIndex((s) => s.column === name);
    let next: Sort[];
    if (multi) {
      next = i >= 0 ? currentSort.map((s, j) => (j === i ? { ...s, dir: s.dir === "asc" ? "desc" : "asc" } : s)) : [...currentSort, { column: name, dir: "asc" as const }].slice(-3);
    } else next = [{ column: name, dir: i === 0 && currentSort[0]!.dir === "desc" ? "asc" : i === 0 ? "desc" : name.includes("pence") || ["orders", "units", "lines"].includes(name) ? "desc" : "asc" }];
    setSort(next);
    setPage(1);
    void load({ sort: next, page: 1 });
  }
  function updatePrefs(p: ViewPrefs) {
    setPrefs(p);
    savePrefs(prefKey, p);
  }
  function move(name: string, delta: number) {
    const names = [...prefs.order.filter((n) => cols.some((c) => c.name === n)), ...cols.map((c) => c.name).filter((n) => !prefs.order.includes(n))];
    const i = names.indexOf(name),
      j = i + delta;
    if (i < 0 || j < 0 || j >= names.length) return;
    [names[i], names[j]] = [names[j]!, names[i]!];
    updatePrefs({ ...prefs, order: names });
  }

  return (
    <section className="wb-panel wb-grid-panel" aria-busy={busy}>
      <div className="wb-panel-head">
        <div>
          <h2>{t("Veri tablosu", "Data table")}</h2>
          <p>
            {t(
              "Başlığa tıklayarak sıralayın (Shift ile ikinci sütun), başlığın altına yazarak filtreleyin. Kaynak veri değişmez.",
              "Click a header to sort (Shift for a second column), type under a header to filter. The source data never changes.",
            )}
          </p>
        </div>
        <div className="wb-tabs" role="tablist" aria-label={t("Tablo görünümü", "Table view")}>
          {(["rows", "summary"] as const).map((v) => (
            <button
              key={v}
              role="tab"
              aria-selected={view === v}
              className={view === v ? "active" : ""}
              onClick={() => {
                setView(v);
                setSort(null);
                setColFilters({});
                setAsked(null);
                setPage(1);
                void load({ view: v, sort: null, page: 1, colFilters: {} });
              }}
            >
              {v === "rows" ? t("Satırlar", "Rows") : t("Özet", "Summary")}
            </button>
          ))}
        </div>
      </div>

      <form
        className="wb-grid-ask"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
      >
        <label htmlFor="wb-grid-ask" className="sr-only">
          {t("Tabloya sor", "Ask the table")}
        </label>
        <input
          id="wb-grid-ask"
          value={question}
          maxLength={500}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t("Tabloya sorun: örn. Almanya'da en çok satan 5 ürün", "Ask the table: e.g. top 5 products in Germany")}
        />
        <button className="wb-btn" disabled={busy || !question.trim()}>
          <Send size={16} />
          {t("Sor", "Ask")}
        </button>
      </form>

      {asked && (
        <div className="wb-grid-asked" role="status">
          <RoutingBadge routing={asked.planner.routing} providerLabel={providerLabel} />
          <span>
            {t("Soru:", "Question:")} <b>{asked.prompt}</b>
          </span>
          <button className="wb-text-btn" onClick={() => onOpenChart(asked.prompt)}>
            <Trend size={16} />
            {t("Grafik stüdyosunda aç", "Open in the Chart studio")}
          </button>
          <button
            className="wb-text-btn"
            onClick={() => {
              setQuestion("");
              setSort(null);
              setView("rows");
              setColFilters({});
              void load({ view: "rows", sort: null, page: 1, colFilters: {} });
            }}
          >
            <Reset size={16} />
            {t("Tabloya dön", "Back to the table")}
          </button>
          {asked.warnings.map((w) => (
            <span key={w} className="wb-small">
              <Info size={16} /> {w}
            </span>
          ))}
        </div>
      )}

      <div className="wb-grid-toolbar">
        {view === "summary" && !asked && (
          <>
            {[0, 1].map((i) => (
              <label key={i}>
                {i === 0 ? t("Gruplama", "Group by") : t("İkinci gruplama", "Then by")}
                <select
                  value={groups[i] ?? ""}
                  onChange={(e) => {
                    const g = [...groups];
                    if (e.target.value) g[i] = e.target.value;
                    else g.splice(i, 1);
                    const next = g.filter((x, k) => x && g.indexOf(x) === k);
                    if (!next.length) return;
                    setGroups(next);
                    setSort(null);
                    setColFilters({});
                    setPage(1);
                    void load({ groups: next, sort: null, page: 1, colFilters: {} });
                  }}
                >
                  {i === 1 && <option value="">{t("Yok", "None")}</option>}
                  {GROUP_OPTIONS.map((g) => (
                    <option key={g} value={g}>
                      {{ country: t("Ülke", "Country"), month: t("Ay", "Month"), week: t("Hafta", "Week"), weekday: t("Haftanın günü", "Weekday"), product: t("Ürün", "Product") }[g]}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </>
        )}
        <label>
          {t("Sayfa başına", "Per page")}
          <select
            value={size}
            onChange={(e) => {
              const n = Number(e.target.value);
              setSize(n);
              setPage(1);
              void load({ size: n, page: 1 });
            }}
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="wb-btn" aria-expanded={showColumns} onClick={() => setShowColumns(!showColumns)}>
          {t("Sütunlar", "Columns")}
          <ChevronDown size={16} />
        </button>
        {Object.values(colFilters).some((v) => v.trim()) && (
          <button
            type="button"
            className="wb-text-btn"
            onClick={() => {
              setColFilters({});
              void load({ page: 1, colFilters: {} });
            }}
          >
            <X size={16} />
            {t("Sütun filtrelerini temizle", "Clear column filters")}
          </button>
        )}
        <span className="wb-grid-spacer" />
        <button type="button" className="wb-btn" disabled={!data || !!downloading} onClick={() => void download("csv")}>
          {downloading === "csv" ? <Spinner size={16} className="spin" /> : <Download size={16} />} CSV
        </button>
        <button type="button" className="wb-btn" disabled={!data || !!downloading} onClick={() => void download("xlsx")}>
          {downloading === "xlsx" ? <Spinner size={16} className="spin" /> : <Download size={16} />} Excel
        </button>
      </div>

      {showColumns && data && (
        <div className="wb-grid-columns" role="group" aria-label={t("Sütun ayarları", "Column settings")}>
          {[...prefs.order.filter((n) => cols.some((c) => c.name === n)), ...cols.map((c) => c.name).filter((n) => !prefs.order.includes(n))].map((name, i, all) => {
            const c = cols.find((x) => x.name === name)!;
            return (
              <div key={name} className="wb-grid-column">
                <input
                  type="checkbox"
                  aria-label={t(`${c.label} sütununu göster`, `Show ${c.label}`)}
                  checked={!prefs.hidden.includes(name)}
                  onChange={(e) =>
                    updatePrefs({ ...prefs, hidden: e.target.checked ? prefs.hidden.filter((h) => h !== name) : [...prefs.hidden, name] })
                  }
                />
                <input
                  className="wb-grid-rename"
                  aria-label={t(`${c.label} için görünen ad`, `Display name for ${c.label}`)}
                  value={prefs.labels[name] ?? ""}
                  placeholder={c.label}
                  maxLength={60}
                  onChange={(e) => updatePrefs({ ...prefs, labels: { ...prefs.labels, [name]: e.target.value } })}
                />
                <button type="button" className="wb-icon" disabled={i === 0} aria-label={t("Sola taşı", "Move left")} onClick={() => move(name, -1)}>
                  ‹
                </button>
                <button type="button" className="wb-icon" disabled={i === all.length - 1} aria-label={t("Sağa taşı", "Move right")} onClick={() => move(name, 1)}>
                  ›
                </button>
              </div>
            );
          })}
          <button type="button" className="wb-text-btn" onClick={() => updatePrefs({ hidden: [], labels: {}, order: [] })}>
            <Reset size={16} />
            {t("Varsayılan sütunlar", "Default columns")}
          </button>
        </div>
      )}

      {error && (
        <p className="wb-alert wb-alert-error" role="alert">
          <Info size={16} /> {error}
        </p>
      )}

      {data && (
        <TableWrap className="wb-grid-wrap">
          <table className="wb-grid">
            <caption className="sr-only">{t("Veri tablosu", "Data table")}</caption>
            <thead>
              <tr>
                {ordered.map((c) => {
                  const k = currentSort.findIndex((s) => s.column === c.name);
                  const dir = k >= 0 ? currentSort[k]!.dir : null;
                  return (
                    <th key={c.name} scope="col" aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"} className={c.type === "text" || c.type === "date" ? "" : "is-num"}>
                      <button type="button" disabled={!!asked} onClick={(e) => clickSort(c.name, e.shiftKey)}>
                        {label(c)}
                        {dir && (
                          <span aria-hidden="true">
                            {dir === "asc" ? " ▲" : " ▼"}
                            {currentSort.length > 1 ? k + 1 : ""}
                          </span>
                        )}
                      </button>
                    </th>
                  );
                })}
              </tr>
              {!asked && (
                <tr className="wb-grid-filters">
                  {ordered.map((c) => (
                    <td key={c.name}>
                      <input
                        aria-label={t(`${label(c)} filtresi`, `Filter ${label(c)}`)}
                        value={colFilters[c.name] ?? ""}
                        placeholder={c.type === "text" ? t("içerir…", "contains…") : c.type === "date" ? "2011-01-01..2011-03-31" : ">= 10"}
                        onChange={(e) => setColFilters({ ...colFilters, [c.name]: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            setPage(1);
                            void load({ page: 1 });
                          }
                        }}
                        onBlur={() => {
                          setPage(1);
                          void load({ page: 1 });
                        }}
                      />
                    </td>
                  ))}
                </tr>
              )}
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i}>
                  {ordered.map((c) => (
                    <td key={c.name} className={c.type === "text" || c.type === "date" ? "" : "is-num"}>
                      {show(c, r[c.name] ?? null)}
                    </td>
                  ))}
                </tr>
              ))}
              {!data.rows.length && (
                <tr>
                  <td colSpan={ordered.length}>{t("Bu filtrelerle satır yok.", "No rows for these filters.")}</td>
                </tr>
              )}
            </tbody>
          </table>
        </TableWrap>
      )}

      {data && (
        <div className="wb-grid-pager">
          <span>
            {asked && data.note_top_n
              ? t(`İlk ${data.note_top_n} sonuç`, `Top ${data.note_top_n} results`)
              : t(`${nf.format(data.total)} satır · sayfa ${data.page}/${data.pages}`, `${nf.format(data.total)} rows · page ${data.page} of ${data.pages}`)}
          </span>
          {!asked && (
            <span>
              <button type="button" className="wb-btn" disabled={busy || page <= 1} onClick={() => { setPage(1); void load({ page: 1 }); }} aria-label={t("İlk sayfa", "First page")}>
                «
              </button>
              <button type="button" className="wb-btn" disabled={busy || page <= 1} onClick={() => { setPage(page - 1); void load({ page: page - 1 }); }} aria-label={t("Önceki sayfa", "Previous page")}>
                ‹
              </button>
              <button type="button" className="wb-btn" disabled={busy || page >= data.pages} onClick={() => { setPage(page + 1); void load({ page: page + 1 }); }} aria-label={t("Sonraki sayfa", "Next page")}>
                ›
              </button>
              <button type="button" className="wb-btn" disabled={busy || page >= data.pages} onClick={() => { setPage(data.pages); void load({ page: data.pages }); }} aria-label={t("Son sayfa", "Last page")}>
                »
              </button>
            </span>
          )}
          <details className="wb-grid-sql">
            <summary>SQL</summary>
            <code>{data.evidence.sql}</code>
          </details>
        </div>
      )}
    </section>
  );
}
