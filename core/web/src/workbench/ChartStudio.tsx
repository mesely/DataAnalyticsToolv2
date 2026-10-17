/**
 * Chart Studio (AW-16 §2). The analyst asks for a chart in their own words — "son 6 ay", "Almanya ile Fransa'yı
 * karşılaştır", "%95 güven aralığı ekle" — and refines it step by step. Each request is planned into a validated
 * ChartSpec (by the configured language model when the analyst opts in and a provider is configured, otherwise by the local planner);
 * every number, interval and sentence on screen is computed by the local engine. The plan is shown as editable
 * facts (what changed, which planner), never as model prose.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  ErrorBar,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { useLocale } from "./Locale";
import { RoutingBadge } from "./Routing";
import type { ChartResult, ChartSpec, Filters } from "./types";
import { Mascot } from "./Avatars";
import { ReasoningTree } from "./Reasoning";
import { Send, Spinner, Reset, Download, Query, TableView, Trend, Info, Verified } from "./BrandIcons";

const BASE = "/v1/dashboard/workbench";
const SERIES = ["#6674e5", "#299b8c", "#df9b41", "#b36ca6", "#557ea3"];

type View = "chart" | "data" | "sql";

function csv(rows: Record<string, unknown>[]) {
  if (!rows.length) return "";
  const cols = Object.keys(rows[0]!);
  const cell = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => cell(r[c])).join(","))].join("\n") + "\n";
}
function save(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ChartStudio({
  dataset,
  filters,
  csrf,
  providerLabel,
  initialPrompt,
  onExportCode,
}: {
  dataset: string;
  filters: Filters;
  csrf: string | null;
  providerLabel?: string | null;
  initialPrompt?: string;
  onExportCode: (spec: ChartSpec) => void;
}) {
  const { t, locale } = useLocale();
  const [steps, setSteps] = useState<{ prompt: string; result: ChartResult }[]>([]),
    [prompt, setPrompt] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [view, setView] = useState<View>("chart");
  const chartRef = useRef<HTMLDivElement>(null);
  const current = steps[steps.length - 1]?.result ?? null;
  const fmt = useMemo(
    () => (unit: "GBP" | "count", v: number) =>
      new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", unit === "GBP"
        ? { style: "currency", currency: "GBP", maximumFractionDigits: v >= 1000 ? 0 : 2 }
        : { maximumFractionDigits: 0 }).format(v),
    [locale],
  );

  async function ask(text: string, base: ChartSpec | null) {
    setBusy(true);
    setError("");
    const r = await api.post<ChartResult>(
      BASE + "/chart",
      { dataset, filters, locale, prompt: text, base_spec: base },
      csrf,
    );
    setBusy(false);
    if (!r.ok) {
      setError(r.error.detail || t("Grafik hazırlanamadı.", "The chart could not be prepared."));
      return;
    }
    setSteps((s) => [...s, { prompt: text, result: r.data }]);
    setPrompt("");
    setView("chart");
  }
  useEffect(() => {
    setSteps([]);
    void ask(initialPrompt ?? "", null);
  }, [dataset, JSON.stringify(filters)]);

  const suggestions = current?.planner.status === "no_change" && steps[steps.length - 1]?.prompt && current.planner.suggestions?.length
    ? current.planner.suggestions
    : [
        t("Son 6 ay", "Last 6 months"),
        t("Almanya ile Fransa'yı karşılaştır", "Compare Germany and France"),
        t("Aylık ortalama sepet, %95 güven aralığı", "Monthly average order, 95% interval"),
        t("4 dönemlik hareketli ortalama ekle", "Add a 4-period moving average"),
        t("Doğrusal trend çizgisi ekle", "Add a linear trend line"),
        t("Ülkelere göre sipariş, İngiltere hariç", "Orders by country, except United Kingdom"),
      ];

  // Shape the engine's rows for the chart: one row per x; split series become columns.
  const spec = current?.spec;
  const isTime = spec ? spec.dimension === "month" || spec.dimension === "week" : false;
  const seriesNames = useMemo(
    // A single series is reported as "all"; only a country split produces named series.
    () => (current ? [...new Set(current.data.map((d) => d.series).filter((s): s is string => Boolean(s) && s !== "all"))] : []),
    [current],
  );
  const rows = useMemo(() => {
    if (!current) return [];
    const byX = new Map<string, Record<string, unknown>>();
    current.data.forEach((d) => {
      const row = byX.get(d.x) ?? { x: d.x };
      if (d.series && d.series !== "all") row[d.series] = d.value;
      else {
        row.value = d.value;
        // A mean of non-negative amounts cannot fall below zero: the drawn whisker stops at the axis; the
        // computed bound stays in the Data tab and the footnote says so.
        if (d.lower != null && d.upper != null) {
          row.ci = [d.value - Math.max(0, d.lower), d.upper - d.value];
          if (d.lower < 0) row.clipped = true;
        }
        row.n = d.n;
        row.partial = d.partial;
      }
      byX.set(d.x, row);
    });
    // Overlays come computed from the engine (complete periods only); they are joined by period.
    (current.overlays.moving_average?.points ?? []).forEach((m) => {
      const row = byX.get(m.x);
      if (row) row[m.series && m.series !== "all" ? m.series + " · MA" : "ma"] = m.value;
    });
    (current.overlays.trend?.line ?? []).forEach((p) => {
      const row = byX.get(p.x);
      if (row) row.trend = p.value;
    });
    return [...byX.values()];
  }, [current]);

  const unit = current?.unit ?? "GBP";
  const control = current?.overlays.control;
  const fieldLabel = (k: string) =>
    ({
      metric: t("Ölçü", "Measure"),
      dimension: t("Kırılım", "Breakdown"),
      chart: t("Grafik", "Chart"),
      start: t("Başlangıç", "Start"),
      end: t("Bitiş", "End"),
      countries: t("Ülkeler", "Countries"),
      exclude_countries: t("Hariç ülkeler", "Excluded countries"),
      split_by_country: t("Ülkeye göre ayır", "Split by country"),
      top_n: t("İlk N", "Top N"),
      statistic: t("İstatistik", "Statistic"),
      window: t("Pencere", "Window"),
      sort: t("Sıralama", "Sort"),
    })[k] ?? k;
  const VALUE_LABELS: Record<string, [string, string]> = {
    gross_sales: ["brüt satış", "gross sales"],
    orders: ["sipariş", "orders"],
    units: ["satılan adet", "units"],
    aov: ["ortalama sipariş", "average order"],
    month: ["ay", "month"],
    week: ["hafta", "week"],
    weekday: ["haftanın günü", "weekday"],
    country: ["ülke", "country"],
    product: ["ürün", "product"],
    line: ["çizgi", "line"],
    area: ["alan", "area"],
    bar: ["çubuk", "bar"],
    none: ["yok", "none"],
    ci95: ["%95 güven aralığı", "95% interval"],
    moving_average: ["hareketli ortalama", "moving average"],
    trend: ["doğrusal trend", "linear trend"],
    control_band: ["olağan değişim bandı (±2σ)", "control band (±2σ)"],
    natural: ["doğal sıra", "natural order"],
    value_desc: ["büyükten küçüğe", "largest first"],
    value_asc: ["küçükten büyüğe", "smallest first"],
  };
  const show = (v: unknown) => {
    if (v == null || v === "" || (Array.isArray(v) && !v.length)) return t("yok", "none");
    if (Array.isArray(v)) return v.join(", ");
    if (typeof v === "boolean") return v ? t("evet", "yes") : t("hayır", "no");
    const label = VALUE_LABELS[String(v)];
    return label ? t(label[0], label[1]) : String(v);
  };

  return (
    <div className="wb-chart-studio">
      <div className="wb-studio-intro">
        <Mascot pose="reading" size={56} />
        <div>
          <strong>{t("Ne görmek istediğinizi yazın", "Describe the chart you want")}</strong>
          <span>
            {t(
              "Dönemi daraltın, konuyu değiştirin, ülkeleri karşılaştırın veya istatistiksel dayanak ekleyin. Her istek mevcut grafiği adım adım değiştirir; sayılar yerel motorda hesaplanır.",
              "Narrow the period, change the subject, compare countries or add statistical support. Each request refines the current chart; every number is computed by the local engine.",
            )}
          </span>
        </div>
      </div>
      <form
        className="wb-studio-prompt"
        onSubmit={(e) => {
          e.preventDefault();
          if (prompt.trim() && !busy) void ask(prompt.trim(), current?.spec ?? null);
        }}
      >
        <label htmlFor="wb-chart-prompt" className="sr-only">
          {t("Grafik isteği", "Chart request")}
        </label>
        <input
          id="wb-chart-prompt"
          value={prompt}
          maxLength={500}
          placeholder={t("Örn. son 6 ay, Almanya ve Fransa", "e.g. last 6 months, Germany vs France")}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <button className="wb-btn primary" disabled={busy || !prompt.trim()}>
          {busy ? <Spinner size={16} /> : <Send size={16} />}
          {t("Uygula", "Apply")}
        </button>
      </form>
      <div className="wb-question-chips" aria-label={t("Önerilen istekler", "Suggested requests")}>
        {suggestions.map((s) => (
          <button key={s} type="button" disabled={busy} onClick={() => void ask(s, current?.spec ?? null)}>
            {s}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="wb-error-text">
          {error}
        </p>
      )}
      {!current && busy && (
        <p className="wb-code-loading" role="status">
          <Spinner size={16} />
          {t("Grafik hesaplanıyor…", "Computing the chart…")}
        </p>
      )}
      {current && spec && (
        <section className="wb-studio-result" aria-busy={busy}>
          <header className="wb-studio-head">
            <div>
              <h3>{current.title}</h3>
              <p>{current.subtitle}</p>
            </div>
            <div className="wb-tabs" role="tablist" aria-label={t("Görünüm", "View")}>
              {(
                [
                  ["chart", t("Grafik", "Chart"), <Trend key="i" size={16} />],
                  ["data", t("Veri", "Data"), <TableView key="i" size={16} />],
                  ["sql", "SQL", <Query key="i" size={16} />],
                ] as const
              ).map(([id, label, icon]) => (
                <button key={id} role="tab" aria-selected={view === id} className={view === id ? "active" : ""} onClick={() => setView(id)}>
                  {icon}
                  {label}
                </button>
              ))}
            </div>
          </header>
          <div className="wb-studio-plan">
            {current.planner.routing ? (
              <RoutingBadge routing={current.planner.routing} providerLabel={providerLabel} />
            ) : (
              <span className={"wb-badge " + (current.planner.source === "model" ? "blue" : "")}>
                <Verified size={16} />
                {current.planner.source === "model"
                  ? t("Model planladı · sayılar yerelde", "Planned by the model · numbers local")
                  : t("Yerel planlayıcı", "Local planner")}
              </span>
            )}
            {steps[steps.length - 1]!.prompt !== "" && current.planner.changes.map((c) => (
              <span key={c.field} className="wb-studio-change">
                <b>{fieldLabel(c.field)}</b> {show(c.from)} → {show(c.to)}
              </span>
            ))}
            {steps[steps.length - 1]!.prompt !== "" && current.planner.note && (current.planner.source === "model" || current.planner.status !== "planned" || "fallback" in current.planner) && (
              <span className="wb-studio-note">{current.planner.note}</span>
            )}
          </div>
          {current.warnings.length > 0 && (
            <ul className="wb-studio-warnings">
              {current.warnings.map((w) => (
                <li key={w}>
                  <Info size={16} />
                  {w}
                </li>
              ))}
            </ul>
          )}
          {view === "chart" && (
            <div className="wb-studio-chart" ref={chartRef}>
              {rows.length === 0 ? (
                <p className="wb-studio-empty">{t("Bu kapsamda veri yok.", "No data in this scope.")}</p>
              ) : (
                <ResponsiveContainer width="100%" height={isTime ? 320 : Math.max(240, rows.length * 32 + 40)}>
                  <ComposedChart
                    data={rows}
                    layout={isTime ? "horizontal" : "vertical"}
                    margin={{ top: 12, right: 24, bottom: 8, left: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={!isTime} horizontal={isTime} />
                    {isTime ? (
                      <>
                        <XAxis dataKey="x" fontSize={12} tickMargin={8} interval="preserveStartEnd" minTickGap={28} tick={{ fill: "var(--muted)" }} />
                        <YAxis width={72} domain={[0, "auto"]} fontSize={12} tick={{ fill: "var(--muted)" }} tickFormatter={(v) => fmt(unit, Number(v))} />
                      </>
                    ) : (
                      <>
                        {/* Totals and averages are non-negative: the axis starts at zero and an interval
                            bound below zero is clipped at the axis rather than stretching it. */}
                        <XAxis type="number" domain={[0, "auto"]} fontSize={12} tick={{ fill: "var(--muted)" }} tickFormatter={(v) => fmt(unit, Number(v))} />
                        <YAxis type="category" dataKey="x" width={168} fontSize={12} tick={{ fill: "var(--muted)" }} />
                      </>
                    )}
                    <Tooltip
                      contentStyle={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--ink)", borderRadius: 10, padding: 12 }}
                      formatter={(v, name) => [fmt(unit, Number(Array.isArray(v) ? v[0] : v)), String(name)]}
                    />
                    {control && isTime && (
                      <>
                        <ReferenceArea y1={control.lower} y2={control.upper} fill="var(--accent)" fillOpacity={0.08} />
                        <ReferenceLine y={control.mean} stroke="var(--muted)" strokeDasharray="4 4" />
                      </>
                    )}
                    {seriesNames.length > 0 ? (
                      seriesNames.flatMap((s, i) => [
                        <Line key={s} type="monotone" dataKey={s} name={s} stroke={SERIES[i % SERIES.length]} strokeWidth={2.5} dot={false} />,
                        ...(rows.some((r) => s + " · MA" in r)
                          ? [
                              <Line
                                key={s + "-ma"}
                                type="monotone"
                                dataKey={s + " · MA"}
                                name={`${s} · ${t("hareketli ort.", "moving avg.")} (${spec.window})`}
                                stroke={SERIES[i % SERIES.length]}
                                strokeWidth={1.5}
                                strokeDasharray="6 4"
                                dot={false}
                                connectNulls
                              />,
                            ]
                          : []),
                      ])
                    ) : spec.chart === "bar" ? (
                      <Bar dataKey="value" name={current.title} fill={SERIES[0]} radius={isTime ? [6, 6, 0, 0] : [0, 6, 6, 0]} maxBarSize={36}>
                        {rows.map((r, i) => (
                          <Cell key={i} fillOpacity={r.partial ? 0.45 : 1} />
                        ))}
                        {spec.statistic === "ci95" && <ErrorBar dataKey="ci" width={6} strokeWidth={1.5} stroke="var(--ink)" direction={isTime ? "y" : "x"} />}
                      </Bar>
                    ) : spec.chart === "area" ? (
                      <Area type="monotone" dataKey="value" name={current.title} stroke={SERIES[0]} fill={SERIES[0]} fillOpacity={0.18} strokeWidth={2.5} />
                    ) : (
                      <Line
                        type="monotone"
                        dataKey="value"
                        name={current.title}
                        stroke={SERIES[0]}
                        strokeWidth={2.5}
                        dot={(p: { cx?: number; cy?: number; index?: number; payload?: { partial?: boolean } }) => (
                          <circle
                            key={"d" + p.index}
                            cx={p.cx}
                            cy={p.cy}
                            r={p.payload?.partial ? 4 : 3}
                            fill={p.payload?.partial ? "var(--surface)" : SERIES[0]}
                            stroke={SERIES[0]}
                            strokeWidth={2}
                          />
                        )}
                      >
                        {spec.statistic === "ci95" && <ErrorBar dataKey="ci" width={6} strokeWidth={1.5} stroke="var(--ink)" direction="y" />}
                      </Line>
                    )}
                    {"ma" in (rows[0] ?? {}) || rows.some((r) => "ma" in r) ? (
                      <Line type="monotone" dataKey="ma" name={t(`Hareketli ortalama (${spec.window})`, `Moving average (${spec.window})`)} stroke="var(--glyph-dot)" strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls />
                    ) : null}
                    {rows.some((r) => "trend" in r) && (
                      <Line type="linear" dataKey="trend" name={t("Doğrusal trend", "Linear trend")} stroke="var(--muted)" strokeWidth={1.5} strokeDasharray="2 4" dot={false} connectNulls />
                    )}
                    {(seriesNames.length > 0 || rows.some((r) => "ma" in r || "trend" in r)) && <Legend wrapperStyle={{ fontSize: 12 }} />}
                  </ComposedChart>
                </ResponsiveContainer>
              )}
              {rows.some((r) => r.clipped) && (
                <p className="wb-studio-foot">
                  {t(
                    "Alt sınırı sıfırın altına inen aralıklar eksende kesildi; hesaplanan sınırlar Veri sekmesinde.",
                    "Intervals whose lower bound falls below zero are cut at the axis; the computed bounds are in the Data tab.",
                  )}
                </p>
              )}
              {rows.some((r) => r.partial) && (
                <p className="wb-studio-foot">{t("İçi boş nokta veya soluk çubuk: kısmi dönem; trend ve ortalamalara katılmaz.", "Hollow point or faded bar: partial period, excluded from trends and averages.")}</p>
              )}
            </div>
          )}
          {view === "data" && (
            <div className="wb-table-wrap" role="region" tabIndex={0} aria-label={t("Grafik verisi", "Chart data")}>
              <table>
                <thead>
                  <tr>
                    <th>{fieldLabel("dimension")}</th>
                    {seriesNames.length > 0 && <th>{t("Seri", "Series")}</th>}
                    <th>{t("Değer", "Value")}</th>
                    {spec.statistic === "ci95" && <th>%95 GA</th>}
                    {spec.statistic === "ci95" && <th>n</th>}
                  </tr>
                </thead>
                <tbody>
                  {current.data.map((d, i) => (
                    <tr key={i}>
                      <td>
                        {d.x}
                        {d.partial ? " *" : ""}
                      </td>
                      {seriesNames.length > 0 && <td>{d.series}</td>}
                      <td className="num">{fmt(unit, d.value)}</td>
                      {spec.statistic === "ci95" && (
                        <td className="num">{d.lower != null && d.upper != null ? `${fmt(unit, d.lower)} – ${fmt(unit, d.upper)}` : "—"}</td>
                      )}
                      {spec.statistic === "ci95" && <td className="num">{d.n ?? "—"}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {view === "sql" && (
            <pre className="wb-code wb-studio-sql" tabIndex={0} aria-label="SQL">
              <code>{current.sql}</code>
            </pre>
          )}
          {current.statements.length > 0 && (
            <ReasoningTree statements={current.statements} label={t("Yorum", "Commentary")} />
          )}
          <footer className="wb-studio-actions">
            <div className="wb-studio-steps" aria-label={t("Adımlar", "Steps")}>
              {steps.map((s, i) => (
                <span key={i} title={s.prompt} className={"wb-studio-step" + (i === steps.length - 1 ? " is-current" : "")}>
                  {i + 1}. {s.prompt || t("Başlangıç", "Start")}
                </span>
              ))}
            </div>
            <div className="wb-studio-buttons">
              <button className="wb-text-btn" disabled={steps.length < 2 || busy} onClick={() => setSteps((s) => s.slice(0, -1))}>
                <Reset size={16} />
                {t("Geri al", "Undo")}
              </button>
              <button
                className="wb-text-btn"
                onClick={() =>
                  save(
                    "chart-" + current.output_sha256.slice(0, 8) + ".csv",
                    csv(current.data.map((d) => ({ x: d.x, series: d.series ?? "", value: d.value, lower: d.lower ?? "", upper: d.upper ?? "", n: d.n ?? "" }))),
                    "text/csv",
                  )
                }
              >
                <Download size={16} />
                CSV
              </button>
              <button
                className="wb-text-btn"
                disabled={view !== "chart"}
                onClick={() => {
                  const svg = chartRef.current?.querySelector("svg.recharts-surface");
                  if (svg) save("chart-" + current.output_sha256.slice(0, 8) + ".svg", new XMLSerializer().serializeToString(svg), "image/svg+xml");
                }}
              >
                <Download size={16} />
                SVG
              </button>
              <button className="wb-btn" onClick={() => onExportCode(current.spec)}>
                <Query size={16} />
                {t("Koda aktar", "Export as code")}
              </button>
            </div>
          </footer>
        </section>
      )}
    </div>
  );
}
