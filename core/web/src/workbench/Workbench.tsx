import { TableWrap } from "./TableWrap";
import {
  RotateCcw,
  ExternalLink,
  ArrowUpRight,
  X,
  ChevronRight,
  ChevronDown,
  ArrowRight,
  Download,
  ArrowDownToLine,
  Filter,
  Settings2,
  SlidersHorizontal,
  Info,
  LogOut,
  CheckCircle2,
  Table2,
  FileText,
  ShieldCheck,
  Send,
  MessageSquare,
  Network,
  Activity,
  ZoomIn,
  ZoomOut,
} from "./BrandIcons";
import {
  Layers,
  Globe2,
  Database,
  Search,
  HelpCircle,
  BookOpen,
  Upload,
  Code2,
  Bookmark,
} from "./BrandIcons";
import modelArt from "./assets/model-studio.jpeg";
import relationshipArt from "./assets/relationship-explorer.jpeg";
import { AnalystAvatar, AvatarPicker, Mascot } from "./Avatars";
import { ChartStudio } from "./ChartStudio";
import { CodeExport } from "./CodeExport";
import type { ChartSpec } from "./types";
import { Sun, Moon, PeriodChange } from "./BrandIcons";
import {
  Overview,
  Assistant,
  Trend,
  Decision,
  Findings,
  Workspace as WorkspaceGlyph,
  Guide,
  Menu,
  GrossSales,
  Orders,
  Units,
  AverageOrder,
  Markets,
  Run,
  Spinner,
} from "./BrandIcons";
import React, { useEffect, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type ModuleMap, type Session } from "../api";
import { DecisionStudio } from "./DecisionStudio";
import { ModelStudio } from "./ModelStudio";
import { Preparation } from "./Preparation";
import { TemporalView } from "./TemporalView";
import { ScopeView } from "./Scope";
import { DEFAULT_EDGE_LIMIT, EDGE_LIMITS, edgeScale, neighbourhood, strongest } from "./network";
import { ExpertTools, CompareRuns } from "./ExpertTools";
import { LocaleProvider, useLocale } from "./Locale";
import { UsageMeter } from "./UsageMeter";
import type {
  AnalysisResult,
  Dataset,
  Filters,
  GraphNode,
  Locale,
  SavedRun,
  Section,
  ChartTab,
  DecisionTab,
} from "./types";
const BASE = "/v1/dashboard/workbench";
import { csvCell as cell } from "./csv";
const titles: Record<Section, [string, string]> = {
  overview: ["Genel bakış", "Overview"],
  chart: ["Grafik stüdyosu", "Chart studio"],
  decision: ["Karar stüdyosu", "Decision studio"],
  findings: ["Bulgularım", "My findings"],
};
const SECTIONS: Section[] = ["overview", "chart", "decision", "findings"];
const CHART_TABS: ChartTab[] = ["chart", "network", "temporal", "sql"];
const DECISION_TABS: DecisionTab[] = ["ask", "brief", "model"];
/** The page lives in the address hash (#chart/network, #decision/brief), so back and links reopen it (v3 G8). */
function viewFromAddress(): { section: Section; chartTab?: ChartTab; decisionTab?: DecisionTab } {
  const [head, tab] = window.location.hash.replace(/^#/, "").split("/");
  // Pre-v3 links: the assistant and the network pages now live inside the two studios.
  if (head === "analysis") return { section: "decision", decisionTab: "ask" };
  if (head === "network") return { section: "chart", chartTab: "network" };
  const section = SECTIONS.includes(head as Section) ? (head as Section) : "overview";
  return {
    section,
    chartTab: section === "chart" && CHART_TABS.includes(tab as ChartTab) ? (tab as ChartTab) : undefined,
    decisionTab: section === "decision" && DECISION_TABS.includes(tab as DecisionTab) ? (tab as DecisionTab) : undefined,
  };
}
function download(name: string, text: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
/** v3 G8: the sections inside a studio, as a tab list that is also reachable from the address. */
function StudioTabs({
  label,
  value,
  tabs,
  onChange,
}: {
  label: string;
  value: string;
  tabs: [string, string][];
  onChange: (v: string) => void;
}) {
  return (
    <div className="wb-studio-tabs" role="tablist" aria-label={label}>
      {tabs.map(([id, text]) => (
        <button
          key={id}
          role="tab"
          aria-selected={value === id}
          className={value === id ? "active" : ""}
          onClick={() => onChange(id)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  wide?: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog?.open) dialog?.showModal();
    dialog
      ?.querySelector<HTMLInputElement>('input:not([type="file"]),textarea')
      ?.focus();
  }, [title]);
  useEffect(() => () => ref.current?.close(), []);
  return (
    <dialog
      className={"wb-dialog" + (wide ? " wb-dialog-wide" : "")}
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="wb-dialog-head">
        <h2>{title}</h2>
        <button
          className="wb-icon"
          onClick={onClose}
          aria-label="Kapat / Close"
        >
          <X size={20} />
        </button>
      </div>
      <div className="wb-dialog-body">{children}</div>
    </dialog>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="wb-empty">
      <Mascot pose="searching" size={140} className="wb-empty-art" />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
export function Workbench(p: {
  session: Session;
  csrf: string | null;
  map: ModuleMap;
  navigate: (p: string) => void;
  logout: () => void;
}) {
  const [locale, setLocale] = useState<Locale>("tr");
  // Screen readers and native date fields follow the document language, so it tracks the interface language.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  return (
    <LocaleProvider value={locale}>
      <Workspace {...p} locale={locale} setLocale={setLocale} />
    </LocaleProvider>
  );
}
function Workspace({
  session,
  csrf,
  map,
  navigate,
  logout,
  locale,
  setLocale,
}: {
  session: Session;
  csrf: string | null;
  map: ModuleMap;
  navigate: (p: string) => void;
  logout: () => void;
  locale: Locale;
  setLocale: (l: Locale) => void;
}) {
  const { t } = useLocale();
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light",
  );
  const initialView = useRef(viewFromAddress()).current;
  const [section, setSection] = useState<Section>(initialView.section),
    [chartTab, setChartTab] = useState<ChartTab>(initialView.chartTab ?? "chart"),
    [decisionTab, setDecisionTab] = useState<DecisionTab>(initialView.decisionTab ?? "ask"),
    // A request routed from the ask box to the Chart studio; `n` remounts the studio so it starts from it.
    [chartRequest, setChartRequest] = useState<{ text: string; n: number } | null>(null),
    [routed, setRouted] = useState(""),
    [ask, setAsk] = useState(""),
    [datasets, setDatasets] = useState<Dataset[]>([]),
    [dataset, setDataset] = useState("uci"),
    [result, setResult] = useState<AnalysisResult | null>(null),
    [busy, setBusy] = useState(false),
    [childJobs, setChildJobs] = useState(0),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [draft, setDraft] = useState<Filters>({}),
    [applied, setApplied] = useState<Filters>({}),
    appliedRef = useRef<Filters>({}),
    [question, setQuestion] = useState(""),
    [useLlm, setUseLlm] = useState(false),
    [providerReady, setProviderReady] = useState(false),
    // Display name of the configured language model, e.g. "GPT-OSS 20B · Groq"; null when none is configured.
    [providerLabel, setProviderLabel] = useState<string | null>(null),
    [graphMode, setGraphMode] = useState("copurchase"),
    // Whether postage, fees and adjustments count as products in product views (v3 G5).
    [includeService, setIncludeService] = useState(false),
    [minimum, setMinimum] = useState(2),
    [modal, setModal] = useState<
      | "help"
      | "search"
      | "evidence"
      | "source"
      | "import"
      | "save"
      | "metrics"
      | "avatar"
      | "code"
      | "scope"
      | null
    >(null),
    [codeChart, setCodeChart] = useState<ChartSpec | null>(null),
    [search, setSearch] = useState(""),
    [runs, setRuns] = useState<SavedRun[]>([]),
    [archivedRuns, setArchivedRuns] = useState<SavedRun[]>([]),
    [showArchive, setShowArchive] = useState(false),
    [saveTitle, setSaveTitle] = useState(""),
    [admin, setAdmin] = useState(false),
    [menu, setMenu] = useState(false),
    [dataTab, setDataTab] = useState<"chart" | "data" | "quality">("chart"),
    [saved, setSaved] = useState(false),
    [avatar, setAvatar] = useState<string | null>(null),
    [avatarSaving, setAvatarSaving] = useState(false);
  const working = busy || childJobs > 0;
  const childJobsRef = useRef(0);
  function activity(delta: number) {
    childJobsRef.current = Math.max(0, childJobsRef.current + delta);
    setChildJobs(childJobsRef.current);
  }
  const requestVersion = useRef(0),
    inFlight = useRef(false);
  const num = (n: number) =>
      new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
        maximumFractionDigits: 0,
      }).format(n),
    money = (n: number) =>
      new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", {
        style: "currency",
        currency: "GBP",
        maximumFractionDigits: 2,
      }).format(n);
  async function catalog() {
    activity(1);
    try {
      const r = await api.get<{
        datasets: Dataset[];
        provider: { connected: boolean; configured?: boolean; label?: string | null };
      }>(BASE + "/catalog");
      if (r.ok) {
        setDatasets(r.data.datasets);
        setProviderReady(
          r.data.provider.configured ?? r.data.provider.connected,
        );
        setProviderLabel(r.data.provider.label ?? null);
      } else setError(r.error.detail);
      const p = await api.get<{ avatar: string }>(BASE + "/profile");
      if (p.ok) setAvatar(p.data.avatar);
    } finally {
      activity(-1);
    }
  }
  async function history() {
    const r = await api.get<{ runs: SavedRun[] }>(BASE + "/runs");
    if (r.ok) setRuns(r.data.runs);
    const a = await api.get<{ runs: SavedRun[] }>(BASE + "/runs?archived=1");
    if (a.ok) setArchivedRuns(a.data.runs);
  }
  async function archiveRun(id: string, archived: boolean) {
    const r = await api.post(
      BASE + "/runs/" + id + "/archive",
      { archived },
      csrf,
    );
    if (r.ok) {
      await history();
      setNotice(
        archived
          ? t("Bulgu arşivlendi.", "Finding archived.")
          : t("Bulgu geri yüklendi.", "Finding restored."),
      );
    } else setError(r.error.detail);
  }
  async function analyze(
    o: {
      id?: string;
      filters?: Filters;
      prompt?: string;
      mode?: string;
      min?: number;
      /** Set when the filters come from the browser history, so the address is not pushed again. */
      fromHistory?: boolean;
      include?: boolean;
    } = {},
  ) {
    if (inFlight.current || childJobsRef.current > 0) return;
    inFlight.current = true;
    const version = ++requestVersion.current;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const r = await api.post<AnalysisResult>(
        BASE + "/run",
        {
          dataset: o.id || dataset,
          filters: o.filters ?? applied,
          question: o.prompt || "",
          use_llm: !!o.prompt && useLlm,
          graph_mode: o.mode || graphMode,
          min_shared: o.min ?? minimum,
          include_service: o.include ?? includeService,
          locale,
        },
        csrf,
      );
      if (version === requestVersion.current) {
        if (r.ok) {
          setResult(r.data);
          setSaved(false);
          setApplied(r.data.filters);
          appliedRef.current = r.data.filters;
          setDraft(r.data.filters);
          if (r.data.scope) setIncludeService(r.data.scope.include_service);
          if (!o.fromHistory) syncAddress(r.data.filters);
          void history();
        } else setError(r.error.detail);
      }
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  }
  useEffect(() => {
    // The view's filters live in the address (?country=…&start=…&end=), so a link reopens the same view and the
    // browser's back button returns from a country to all countries (v3 G4).
    const initial = filtersFromAddress();
    if (filtersKey(initial)) replaceAddress(initial);
    void catalog().then(() => analyze({ filters: initial, fromHistory: true }));
    void history();
    const back = () => {
      const v = viewFromAddress();
      setSection(v.section);
      if (v.chartTab) setChartTab(v.chartTab);
      if (v.decisionTab) setDecisionTab(v.decisionTab);
      const f = filtersFromAddress();
      if (filtersKey(f) !== filtersKey(appliedRef.current)) void analyze({ filters: f, fromHistory: true });
    };
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);
  // Server-written text (answers, method notes) is rendered in the request locale: refresh it on a switch.
  const firstLocale = useRef(locale);
  useEffect(() => {
    if (locale !== firstLocale.current && result) void analyze();
    firstLocale.current = locale;
  }, [locale]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setModal("search");
      }
      if (e.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  function clearFilter(key?: keyof Filters) {
    const next: Filters = key ? { ...applied, [key]: undefined } : {};
    if (key) delete next[key];
    setDraft(next);
    void analyze({ filters: next });
  }
  function go(s: Section, tab?: ChartTab | DecisionTab) {
    setSection(s);
    if (s === "chart" && tab) setChartTab(tab as ChartTab);
    if (s === "decision" && tab) setDecisionTab(tab as DecisionTab);
    setMenu(false);
    setModal(null);
    setRouted("");
    if (s === "findings") void history();
    const ct = s === "chart" ? ((tab as ChartTab) ?? chartTab) : null,
      dt = s === "decision" ? ((tab as DecisionTab) ?? decisionTab) : null;
    const hash = "#" + s + (ct && ct !== "chart" ? "/" + ct : dt && dt !== "ask" ? "/" + dt : "");
    if (window.location.hash !== hash && !(s === "overview" && !window.location.hash))
      window.history.pushState(null, "", window.location.pathname + window.location.search + hash);
  }
  /** v3 G8: one ask box. The router picks the studio; the destination studio does its own validation. */
  async function askAnything(text: string) {
    const q = text.trim();
    if (!q) return;
    const r = await api.post<{ studio: "chart" | "decision" }>(BASE + "/route", { text: q, locale }, csrf);
    const studio = r.ok ? r.data.studio : "decision",
      from = section;
    setAsk("");
    if (studio === "chart") {
      go("chart", "chart");
      setChartRequest({ text: q, n: Date.now() });
      setRouted(t("Bu bir grafik isteği; Grafik stüdyosunda açıldı.", "This is a chart request; it opened in the Chart studio."));
    } else {
      go("decision", "ask");
      setQuestion(q);
      // Only say where the request went when it actually moved the analyst somewhere.
      if (from !== "decision")
        setRouted(t("Bu bir soru; Karar stüdyosunda yanıtlanıyor.", "This is a question; the Decision studio answers it."));
      void analyze({ prompt: q });
    }
  }
  function changeDataset(id: string) {
    setDataset(id);
    setResult(null);
    setDraft({});
    setApplied({});
    setQuestion("");
    void analyze({ id, filters: {} });
  }
  function exportCsv() {
    if (!result) return;
    const keys = Object.keys(result.preview[0] || {});
    download(
      "analysis-preview.csv",
      "\uFEFF" +
        [keys, ...result.preview.map((r) => keys.map((k) => r[k]))]
          .map((r) => r.map(cell).join(","))
          .join("\r\n"),
      "text/csv;charset=utf-8",
    );
    setNotice(
      t(
        "İlk 30 satırın önizlemesi indirildi.",
        "First 30 preview rows downloaded.",
      ),
    );
  }
  async function save() {
    if (!result) return;
    const r = await api.post(
      BASE + "/runs/" + result.run_id + "/save",
      { title: saveTitle },
      csrf,
    );
    if (r.ok) {
      setSaved(true);
      setModal(null);
      setNotice(
        t(
          "Bulgu kaydedildi. Bulgularım bölümünden açabilirsiniz.",
          "Finding saved. Open it from My findings.",
        ),
      );
      void history();
    } else setError(r.error.detail);
  }
  async function openRun(id: string) {
    const r = await api.get<{
      result: AnalysisResult;
      run_id: string;
      recipe: SavedRun["recipe"];
      saved: boolean;
    }>(BASE + "/runs/" + id);
    if (r.ok) {
      setResult({ ...r.data.result, run_id: r.data.run_id });
      setDataset(r.data.recipe.dataset);
      setApplied(r.data.recipe.filters);
      setDraft(r.data.recipe.filters);
      syncAddress(r.data.recipe.filters);
      setGraphMode(r.data.recipe.graph_mode);
      setMinimum(r.data.recipe.min_shared);
      setIncludeService(r.data.recipe.include_service === true);
      setQuestion(r.data.recipe.question || "");
      setSaved(r.data.saved);
      go("decision", "ask");
    } else setError(r.error.detail);
  }
  const selected = datasets.find((d) => d.id === dataset),
    s = result?.summary,
    source = selected?.source,
    filtered = !!(applied.country || applied.start || applied.end);
  const nav = [
    { id: "overview" as const, icon: Overview },
    { id: "chart" as const, icon: Trend },
    { id: "decision" as const, icon: Decision },
    { id: "findings" as const, icon: Findings },
  ];
  /** Old entry points (modals) now open a studio tab. */
  const open = (target: "chart" | "network" | "temporal" | "sql" | "decisions" | "model" | "ask") =>
    target === "decisions"
      ? go("decision", "brief")
      : target === "model"
        ? go("decision", "model")
        : target === "ask"
          ? go("decision", "ask")
          : go("chart", target);
  return (
    <div className="wb" data-theme={theme}>
      <a className="wb-skip" href="#wb-main">
        {t("İçeriğe geç", "Skip to content")}
      </a>
      <aside className={"wb-sidebar" + (menu ? " is-open" : "")}>
        <button
          className="wb-mobile-close wb-icon"
          aria-label={t("Menüyü kapat", "Close navigation")}
          onClick={() => setMenu(false)}
        >
          <X size={20} />
        </button>
        <div className="wb-brand">
          {/* The mascot hangs from the top edge of the sidebar above the wordmark (AW-16). */}
          <span className="wb-brandmark is-hanging">
            <Mascot pose="hanging" size={88} />
          </span>
          <div>
            context<span>layer</span>
            <small>ANALYTICS WORKSPACE</small>
          </div>
        </div>
        <div className="wb-project">
          <span className="wb-avatar wb-project-mark">
            <WorkspaceGlyph size={20} />
          </span>
          <div>
            {t("Analiz çalışma alanı", "Analytics workspace")}
            <small>{t("Satış analitiği", "Retail analytics")}</small>
          </div>
        </div>
        <p className="wb-nav-label">{t("ÇALIŞMA ALANI", "WORKSPACE")}</p>
        <nav aria-label={t("Ana gezinme", "Main navigation")}>
          {nav.map((n) => (
            <button
              key={n.id}
              className={section === n.id ? "active" : ""}
              onClick={() => go(n.id)}
            >
              <n.icon size={20} className="wb-brand-nav-icon" />
              {t(...titles[n.id])}
              {n.id === "findings" && runs.some((x) => x.saved) && (
                <span className="wb-count">
                  {runs.filter((x) => x.saved).length}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="wb-nav-tools">
          <button onClick={() => setAdmin(!admin)} aria-expanded={admin}>
            <Settings2 size={20} />
            {t("Yönetim araçları", "Administration")}
            <ChevronDown size={16} />
          </button>
          {admin && (
            <div className="wb-admin-list">
              {map.modules
                .filter((x) => x.id !== "workspace")
                .map((m) => (
                  <button key={m.id} onClick={() => navigate(m.path)}>
                    {m.title}
                    <ArrowUpRight size={16} />
                  </button>
                ))}
            </div>
          )}
        </div>
        <div className="wb-sidebar-bottom">
          <button onClick={() => setModal("help")}>
            <Guide size={20} />
            {t("Kullanım rehberi", "Getting started")}
          </button>
          <div className="wb-user">
            <button
              type="button"
              className="wb-portrait-button"
              onClick={() => setModal("avatar")}
              aria-label={t("Profil görselini değiştir", "Change profile portrait")}
            >
              {avatar ? <AnalystAvatar id={avatar} size={36} /> : <span className="wb-portrait wb-portrait-pending" />}
            </button>
            <div title={`${session.display || session.subject} · ${t("Analist", "Analyst")}`}>
              <span>{session.display || session.subject}</span>
              <small>{t("Analist", "Analyst")}</small>
            </div>
            <button
              className="wb-icon"
              onClick={logout}
              aria-label={t("Çıkış yap", "Sign out")}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="wb-frame">
        <header className="wb-topbar">
          <button
            className="wb-icon wb-mobile-toggle"
            onClick={() => setMenu(!menu)}
            aria-label={t("Menüyü aç", "Open navigation")}
          >
            <Menu size={20} />
          </button>
          <div className="wb-breadcrumb">
            {t("Çalışma alanı", "Workspace")}
            <ChevronRight size={16} />
            <strong>{t(...titles[section])}</strong>
          </div>
          <div className="wb-top-actions">
            <button
              className="wb-icon wb-theme-toggle"
              aria-label={
                theme === "light"
                  ? t("Koyu temaya geç", "Switch to dark theme")
                  : t("Açık temaya geç", "Switch to light theme")
              }
              aria-pressed={theme === "dark"}
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              title={t("Görünüm", "Appearance")}
            >
              {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            <button
              className="wb-command"
              aria-label={t("Bir işlem bul", "Find an action")}
              onClick={() => setModal("search")}
            >
              <Search size={16} />
              <span>{t("Bir işlem bul…", "Find an action…")}</span>
              <kbd>⌘ K</kbd>
            </button>
            <button
              className="wb-icon wb-language"
              onClick={() => setLocale(locale === "tr" ? "en" : "tr")}
              aria-label={t(
                "Switch interface to English",
                "Arayüzü Türkçe yap",
              )}
            >
              <Globe2 size={16} />
              {locale.toUpperCase()}
            </button>
            <button
              className="wb-icon"
              onClick={() => setModal("help")}
              aria-label={t("Yardım", "Help")}
            >
              <HelpCircle size={20} />
            </button>
          </div>
        </header>
        <main id="wb-main" tabIndex={-1}>
          <div className="wb-page-heading">
            <div>
              <h1>
                {section === "overview"
                  ? t("Satış özeti", "Sales overview")
                  : t(...titles[section])}
              </h1>
              <p>
                {section === "overview"
                  ? t(
                      "Satış, sipariş ve ürün dağılımını inceleyin.",
                      "Review sales, orders and product performance.",
                    )
                  : section === "chart"
                    ? t(
                        "İstediğiniz grafiği yazın; ilişki ağı, dönem değişimi ve SQL de burada.",
                        "Describe the chart you want; the relationship network, change over time and SQL live here too.",
                      )
                    : section === "decision"
                      ? t(
                          "Soru sorun, karar özeti çıkarın, tahmin modeli deneyin; her sonuç kanıtıyla.",
                          "Ask a question, build a decision brief, try a prediction model; every result with its evidence.",
                        )
                      : t(
                          "Analizleri kaynak ve filtreleriyle yeniden açın.",
                          "Reopen analyses with their sources and filters.",
                        )}
              </p>
            </div>
            <div className="wb-heading-actions">
              <button
                className="wb-btn"
                onClick={() => setModal("source")}
                disabled={!selected}
              >
                <BookOpen size={16} />
                {t("Veri hakkında", "About data")}
              </button>
              <button
                className="wb-btn wb-primary"
                onClick={() => setModal("import")}
              >
                <Upload size={16} />
                {t("Veri ekle", "Add data")}
              </button>
            </div>
          </div>
          {error && (
            <div role="alert" className="wb-alert wb-alert-error">
              <Info size={20} />
              <span>{error}</span>
              <button
                className="wb-icon"
                onClick={() => setError("")}
                aria-label="Kapat"
              >
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="wb-alert wb-alert-success">
              <CheckCircle2 size={20} />
              {notice}
            </div>
          )}
          <div className="wb-scope">
          <div className="wb-sourcebar">
            <div className="wb-source-select">
              <span className="wb-source-icon">
                <Database size={20} />
              </span>
              <label>
                <span>{t("AKTİF VERİ SETİ", "ACTIVE DATASET")}</span>
                <select
                  value={dataset}
                  onChange={(e) => changeDataset(e.target.value)}
                  disabled={working}
                  aria-label={t("Veri seti seç", "Choose dataset")}
                >
                  {datasets.map((d) => (
                    <option value={d.id} key={d.id}>
                      {d.title}
                    </option>
                  ))}
                </select>
              </label>
              <span className="wb-source-origin">
                {source?.kind === "public"
                  ? t("Kaynak · Açık veri", "Source · Public data")
                  : source?.kind === "uploaded"
                    ? t("Yüklenen veri", "Uploaded data")
                    : t("Örnek veri", "Sample data")}
              </span>
            </div>
            <div className="wb-source-stats">
              <span>
                {num(selected?.rows || 0)} {t("satır", "rows")}
              </span>
              <i />
              <span>
                {selected?.start} — {selected?.end}
              </span>
              <UsageMeter count={working ? 1 : 0} />
            </div>
          </div>
          {section !== "findings" && (
            <form
              className="wb-filterbar"
              onSubmit={(e) => {
                e.preventDefault();
                void analyze({ filters: draft });
              }}
            >
              <span className="wb-filter-title">
                <Filter size={16} />
                {t("Görünümü daralt", "Refine your view")}
              </span>
              <label>
                {t("Ülke", "Country")}
                <select
                  value={draft.country || ""}
                  onChange={(e) =>
                    setDraft({ ...draft, country: e.target.value })
                  }
                  aria-label={t("Ülke filtresi", "Country filter")}
                >
                  <option value="">{t("Tüm ülkeler", "All countries")}</option>
                  {selected?.countries.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("Başlangıç", "From")}
                <input
                  type="date"
                  value={draft.start || ""}
                  onChange={(e) =>
                    setDraft({ ...draft, start: e.target.value })
                  }
                />
              </label>
              <label>
                {t("Bitiş", "To")}
                <input
                  type="date"
                  value={draft.end || ""}
                  onChange={(e) => setDraft({ ...draft, end: e.target.value })}
                />
              </label>
              <button
                className="wb-btn wb-apply"
                disabled={working}
                type="submit"
              >
                {working ? (
                  <Spinner size={16} className="spin" />
                ) : (
                  <SlidersHorizontal size={16} />
                )}{" "}
                {t("Uygula", "Apply")}
              </button>
              {filtered && (
                <button
                  className="wb-text-btn"
                  type="button"
                  disabled={working}
                  onClick={() => {
                    setDraft({});
                    void analyze({ filters: {} });
                  }}
                >
                  {t("Temizle", "Clear")}
                </button>
              )}
            </form>
          )}
          {section !== "findings" && filtered && (
            <div className="wb-active-filters" role="region" aria-label={t("Etkin filtreler", "Active filters")}>
              <span>{t("Etkin filtre:", "Active filters:")}</span>
              {(["country", "start", "end"] as const).map((k) =>
                applied[k] ? (
                  <button key={k} className="wb-filter-chip" disabled={working} onClick={() => clearFilter(k)}
                    aria-label={t(`${FILTER_NAMES[k][0]} filtresini kaldır`, `Remove ${FILTER_NAMES[k][1]} filter`)}>
                    {t(FILTER_NAMES[k][0], FILTER_NAMES[k][1])}: <b>{k === "country" ? applied[k] : dateText(applied[k]!)}</b>
                    <X size={16} />
                  </button>
                ) : null,
              )}
              <button className="wb-text-btn" disabled={working} onClick={() => clearFilter()}>
                {t("Tümünü temizle", "Clear all")}
              </button>
            </div>
          )}
          </div>
          {working && (
            <div className="wb-loading-bar" role="status">
              {t(
                "Veri ve ilişkiler hesaplanıyor…",
                "Computing data and relationships…",
              )}
            </div>
          )}
          {s && section === "overview" && (
            <div className="wb-kpis">
              <Kpi
                title={t("Brüt satış", "Gross sales")}
                value={money(s.gross_sales)}
                subtitle={t(
                  "İade ve iptaller hariç · GBP",
                  "Returns/cancellations excluded · GBP",
                )}
                icon={<GrossSales size={20} />}
                primary
                action={
                  result?.scope ? (
                    <button className="wb-why" onClick={() => setModal("scope")}>
                      {t("Neden? Ne dışarıda?", "Why? What is left out?")}
                    </button>
                  ) : undefined
                }
              />
              <Kpi
                title={t("Sipariş", "Orders")}
                value={num(s.orders)}
                subtitle={t("Benzersiz fatura", "Distinct invoices")}
                icon={<Orders size={20} />}
              />
              <Kpi
                title={t("Satılan adet", "Units sold")}
                value={num(s.units)}
                subtitle={`${num(s.products)} ${t("farklı ürün", "distinct products")}`}
                icon={<Units size={20} />}
              />
              <Kpi
                title={t("Ortalama sipariş", "Average order value")}
                value={money(s.aov)}
                subtitle={t("Brüt satış / sipariş", "Gross sales / orders")}
                icon={<AverageOrder size={20} />}
              />
            </div>
          )}
          {!result && !working && section !== "findings" && (
            <Empty
              title={t("Henüz sonuç yok", "No result yet")}
              text={t(
                "Bir veri seti seçip Uygula ile başlayın.",
                "Choose a dataset and select Apply.",
              )}
            />
          )}
          {result && section === "overview" && (
            <>
              <div className="wb-overview-grid">
                <section className="wb-panel wb-trend">
                  <div className="wb-panel-head">
                    <div>
                      <h2>
                        {t(
                          "Satışların zaman içindeki görünümü",
                          "Sales over time",
                        )}
                      </h2>
                      <p>
                        {t(
                          "Aylık brüt satış · ilk ve son ay kısmi olabilir; dönem kapsamını kontrol edin.",
                          "Monthly gross sales · the first and last months may be partial; check the date range.",
                        )}
                      </p>
                    </div>
                    <div
                      className="wb-tabs"
                      role="tablist"
                      aria-label={t("Veri görünümü", "Data view")}
                    >
                      {(["chart", "data", "quality"] as const).map((v, i) => (
                        <button
                          role="tab"
                          aria-selected={dataTab === v}
                          key={v}
                          onClick={() => setDataTab(v)}
                        >
                          {
                            [
                              t("Grafik", "Chart"),
                              t("Veri", "Data"),
                              t("Kalite", "Quality"),
                            ][i]
                          }
                        </button>
                      ))}
                    </div>
                  </div>
                  {dataTab === "chart" ? (
                    result.series.length ? (
                      <div className="wb-chart">
                        <ResponsiveContainer width="100%" height={260}>
                          <AreaChart
                            data={result.series.map((x) => ({
                              ...x,
                              sales: x.pence / 100,
                            }))}
                            margin={{ top: 15, right: 15, bottom: 0, left: 0 }}
                          >
                            <defs>
                              <linearGradient
                                id="salesFill"
                                x1="0"
                                y1="0"
                                x2="0"
                                y2="1"
                              >
                                <stop
                                  offset="0%"
                                  stopColor="#5a6ce8"
                                  stopOpacity={0.2}
                                />
                                <stop
                                  offset="100%"
                                  stopColor="#5a6ce8"
                                  stopOpacity={0.01}
                                />
                              </linearGradient>
                            </defs>
                            <CartesianGrid
                              vertical={false}
                              stroke="var(--border)"
                            />
                            <XAxis
                              dataKey="period"
                              tickLine={false}
                              axisLine={false}
                              fontSize={12}
                              tickMargin={12}
                              interval="preserveStartEnd"
                              minTickGap={28}
                            />
                            <YAxis
                              tickFormatter={(n) =>
                                n >= 1000
                                  ? `£${Math.round(n / 1000)}k`
                                  : `£${n}`
                              }
                              tickLine={false}
                              axisLine={false}
                              fontSize={12}
                              width={60}
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
                            <Area
                              isAnimationActive={false}
                              type="monotone"
                              dataKey="sales"
                              name={t("Brüt satış", "Gross sales")}
                              stroke="var(--accent)"
                              strokeWidth={3}
                              fill="url(#salesFill)"
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <Empty
                        title={t(
                          "Bu aralıkta satış yok",
                          "No sales in this range",
                        )}
                        text={t(
                          "Filtreleri temizleyerek tekrar deneyin.",
                          "Clear filters and try again.",
                        )}
                      />
                    )
                  ) : dataTab === "data" ? (
                    <DataTable result={result} />
                  ) : (
                    <Quality data={result.dataset} num={num} />
                  )}
                  <div className="wb-panel-footer">
                    <span>
                      <ShieldCheck size={16} />
                      {t(
                        "Metrik tanımı ve hesap kaydı mevcut",
                        "Metric definition and calculation recorded",
                      )}
                    </span>
                    <span className="wb-panel-footer-actions">
                      <button onClick={() => open("chart")}>
                        {t("Stüdyoda düzenle", "Edit in studio")}
                        <ArrowRight size={16} />
                      </button>
                      <button onClick={() => setModal("evidence")}>
                        {t("Kanıtı incele", "Inspect evidence")}
                        <ArrowRight size={16} />
                      </button>
                    </span>
                  </div>
                </section>
                <section className="wb-panel wb-country">
                  <div className="wb-panel-head">
                    <div>
                      <h2>{t("Ülkelere göre satış", "Sales by country")}</h2>
                      <p>
                        {applied.country
                          ? t(`Yalnız ${applied.country} gösteriliyor`, `Showing ${applied.country} only`)
                          : t("Aynı tanım, karşılaştırılabilir tutarlar", "One definition, comparable totals")}
                      </p>
                    </div>
                    {applied.country ? (
                      <button className="wb-btn wb-back-all" disabled={working} onClick={() => clearFilter("country")}>
                        <RotateCcw size={16} />
                        {t("Tüm ülkelere dön", "Back to all countries")}
                      </button>
                    ) : (
                      <Markets size={20} />
                    )}
                  </div>
                  <div className="wb-ranking">
                    {result.countries.slice(0, 5).map((c, i) => (
                      <button
                        key={c.label}
                        disabled={working}
                        onClick={() => {
                          setDraft({ ...draft, country: c.label });
                          void analyze({
                            filters: { ...applied, country: c.label },
                          });
                        }}
                      >
                        <span className="wb-rank-num">0{i + 1}</span>
                        <div>
                          <div className="wb-rank-label">
                            <strong>{c.label}</strong>
                            <span>{money(c.pence / 100)}</span>
                          </div>
                          <div className="wb-rank-bar">
                            <i
                              style={{
                                width: `${(c.pence / (result.countries[0]?.pence || 1)) * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                        <ChevronRight size={16} />
                      </button>
                    ))}
                  </div>
                  <p className="wb-card-note">
                    {applied.country
                      ? t(
                          "Diğer ülkeleri görmek için “Tüm ülkelere dön”, filtre çipindeki ✕ veya tarayıcının geri tuşu.",
                          "To see every country again: “Back to all countries”, the ✕ on the filter chip, or the browser's back button.",
                        )
                      : t("Bir ülkeye tıklayarak görünümü filtreleyin.", "Select a country to filter this view.")}
                  </p>
                </section>
              </div>
              <div className="wb-lower-grid">
                <section className="wb-panel wb-start wb-ask">
                  <div className="wb-start-symbol">
                    <MessageSquare size={24} />
                  </div>
                  <div>
                    <div className="wb-eyebrow">{t("SORU VEYA GRAFİK İSTEĞİ", "QUESTION OR CHART REQUEST")}</div>
                    <h2>{t("Ne öğrenmek veya görmek istiyorsunuz?", "What do you want to learn or see?")}</h2>
                    <p>
                      {t(
                        "Yazın; grafik istekleri Grafik stüdyosunda, sorular Karar stüdyosunda açılır.",
                        "Type it; chart requests open in the Chart studio, questions in the Decision studio.",
                      )}
                    </p>
                    <form
                      className="wb-ask-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void askAnything(ask);
                      }}
                    >
                      <label htmlFor="wb-ask" className="sr-only">
                        {t("Soru veya grafik isteği", "Question or chart request")}
                      </label>
                      <input
                        id="wb-ask"
                        value={ask}
                        maxLength={8000}
                        onChange={(e) => setAsk(e.target.value)}
                        placeholder={t("Örn. Almanya ile Fransa'yı karşılaştır · En çok satan ürün hangisi?", "e.g. Compare Germany and France · Which product sells the most?")}
                      />
                      <button className="wb-btn wb-primary" disabled={working || !ask.trim()}>
                        <Send size={16} />
                        {t("Sor", "Ask")}
                      </button>
                    </form>
                    <div className="wb-starters">
                      {[
                        t("Satışları özetle", "Summarize sales"),
                        t("Son 6 ay, Almanya ile Fransa", "Last 6 months, Germany vs France"),
                      ].map((q) => (
                        <button key={q} disabled={working} onClick={() => void askAnything(q)}>
                          {q}
                          <ArrowRight size={16} />
                        </button>
                      ))}
                    </div>
                  </div>
                </section>
                <section className="wb-panel wb-network-teaser">
                  <div>
                    <div className="wb-eyebrow">
                      {t("ÜRÜN İLİŞKİLERİ", "CONNECT THE DOTS")}
                    </div>
                    <h2>
                      {t(
                        "Birlikte hangi ürünler alınıyor?",
                        "Which products are bought together?",
                      )}
                    </h2>
                    <p>
                      {result.graph.edges.length}{" "}
                      {t("görünen ilişki", "visible relationships")} ·{" "}
                      {result.graph.nodes.length} {t("ürün", "products")}
                    </p>
                    <button
                      className="wb-text-btn"
                      onClick={() => go("chart", "network")}
                    >
                      {t("İlişki ağını aç", "Explore network")}
                      <ArrowRight size={16} />
                    </button>
                  </div>
                  <img
                    src={relationshipArt}
                    className="wb-relationship-art"
                    alt=""
                    width="128"
                    height="128"
                    loading="lazy"
                  />
                </section>
              </div>
            </>
          )}
          {section === "overview" && (
            <div className="wb-studio-cards">
              <button type="button" className="wb-panel wb-studio-card" onClick={() => go("chart", "chart")}>
                <Trend size={24} />
                <span>
                  <strong>{t("Grafik stüdyosu", "Chart studio")}</strong>
                  <small>
                    {t(
                      "İstediğiniz grafiği yazın · ilişki ağı · zaman içindeki değişim · SQL",
                      "Describe any chart · relationship network · change over time · SQL",
                    )}
                  </small>
                </span>
                <ChevronRight size={20} />
              </button>
              <button type="button" className="wb-panel wb-studio-card" onClick={() => go("decision", "ask")}>
                <Decision size={24} />
                <span>
                  <strong>{t("Karar stüdyosu", "Decision studio")}</strong>
                  <small>
                    {t(
                      "Soru-cevap · karar özeti, tahmin ve senaryo · tahmin modeli",
                      "Questions · decision brief, forecast and scenario · prediction model",
                    )}
                  </small>
                </span>
                <ChevronRight size={20} />
              </button>
            </div>
          )}
          {routed && (section === "chart" || section === "decision") && (
            <p className="wb-routed" role="status">
              <Info size={16} />
              {routed}
            </p>
          )}
          {section === "chart" && (
            <StudioTabs
              label={t("Grafik stüdyosu bölümleri", "Chart studio sections")}
              value={chartTab}
              onChange={(v) => go("chart", v as ChartTab)}
              tabs={[
                ["chart", t("Grafik", "Chart")],
                ["network", t("İlişki ağı", "Relationship network")],
                ["temporal", t("Zaman içindeki değişim", "Change over time")],
                ["sql", t("Gelişmiş: SQL", "Advanced: SQL")],
              ]}
            />
          )}
          {section === "chart" && chartTab === "chart" && (
            <section className="wb-panel wb-studio-page">
              <ChartStudio
                key={chartRequest?.n ?? 0}
                dataset={dataset}
                filters={applied}
                csrf={csrf}
                providerReady={providerReady}
                providerLabel={providerLabel}
                initialPrompt={chartRequest?.text}
                onExportCode={(spec) => {
                  setCodeChart(spec);
                  setModal("code");
                }}
              />
            </section>
          )}
          {section === "chart" && chartTab === "temporal" && result && (
            <section className="wb-panel wb-studio-page">
              <TemporalView
                activity={activity}
                data={result.dataset}
                filters={applied}
                csrf={csrf}
                busy={working}
                minimum={minimum}
                includeService={includeService}
                asDialog
              />
            </section>
          )}
          {section === "chart" && chartTab === "sql" && (
            <section className="wb-panel wb-studio-page">
              <ExpertTools activity={activity} dataset={dataset} filters={applied} csrf={csrf} busy={working} asDialog />
            </section>
          )}
          {section === "decision" && (
            <StudioTabs
              label={t("Karar stüdyosu bölümleri", "Decision studio sections")}
              value={decisionTab}
              onChange={(v) => go("decision", v as DecisionTab)}
              tabs={[
                ["ask", t("Soru-cevap", "Questions")],
                ["brief", t("Karar özeti ve tahmin", "Decision brief and forecast")],
                ["model", t("Tahmin modeli", "Prediction model")],
              ]}
            />
          )}
          {section === "decision" && decisionTab === "brief" && (
            <section className="wb-panel wb-studio-page">
              <DecisionStudio
                dataset={dataset}
                filters={applied}
                csrf={csrf}
                providerReady={providerReady}
                providerLabel={providerLabel}
                busy={busy || childJobs > 0}
                activity={activity}
              />
            </section>
          )}
          {section === "decision" && decisionTab === "model" && (
            <section className="wb-panel wb-studio-page">
              <ModelStudio csrf={csrf} busy={busy || childJobs > 0} activity={activity} />
            </section>
          )}
          {result && section === "decision" && decisionTab === "ask" && (
            <div className="wb-analysis-grid">
              <section className="wb-panel wb-chat">
                <div className="wb-panel-head">
                  <div>
                    <h2>{t("Analiz sorusu", "Analysis question")}</h2>
                    <p>
                      {t(
                        "Geçerli veri seti ve filtreler üzerinden çalışır.",
                        "Uses the current dataset and filters.",
                      )}
                    </p>
                  </div>
                  <ShieldCheck size={20} />
                </div>
                {result.answer ? (
                  <div className="wb-answer">
                    <div className="wb-answer-state">
                      <ShieldCheck size={16} />
                      {result.answer.status === "verified"
                        ? t(
                            "Hesaplanan sonuçla doğrulandı",
                            "Verified against computed result",
                          )
                        : t(
                            "Sınır / açıklama gerekiyor",
                            "Limit / clarification required",
                          )}
                    </div>
                    <p>{result.answer.text}</p>
                    {result.planner &&
                      result.planner.status !== "planned" &&
                      result.planner.status !== "blocked" && (
                        <p className="wb-provider-notice" role="status">
                          {result.planner.http_status === 429
                            ? t(
                                "Dil modelinin kullanım sınırı doldu (429). Standart analiz sonucu gösteriliyor.",
                                "The language model's usage limit was reached (429). Showing the standard analysis.",
                              )
                            : result.planner.http_status === 402
                            ? t(
                                "Dil modeli kullanılamıyor: sağlayıcı hesabında kredi gerekiyor (402). Standart analiz sonucu gösteriliyor.",
                                "The language model is unavailable: the provider account needs credits (402). Showing the standard analysis.",
                              )
                            : t(
                                "Dil modeli planı alınamadı. Standart analiz sonucu gösteriliyor.",
                                "Language-model planning is unavailable. Showing the standard analysis.",
                              )}
                        </p>
                      )}
                    {result.planner?.status === "planned" && (
                      <p className="wb-plan-receipt">
                        {t("Model planı", "Model plan")}
                        {providerLabel ? ` (${providerLabel})` : ""}:{" "}
                        {result.planner.intent} ·{" "}
                        {t(
                          "Sayılar hesap kaydından",
                          "Figures from calculation record",
                        )}
                      </p>
                    )}
                    <div className="wb-answer-citations">
                      <button onClick={() => setModal("metrics")}>
                        <FileText size={16} />
                        retail-v1
                      </button>
                      <button onClick={() => setModal("evidence")}>
                        <Database size={16} />
                        {t("Hesap kaydı", "Calculation record")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="wb-chat-welcome">
                    <MessageSquare size={32} />
                    <h3>
                      {t(
                        "Neyi öğrenmek istersiniz?",
                        "What would you like to learn?",
                      )}
                    </h3>
                    <p>
                      {t(
                        "Brüt satış, ülke dağılımı veya ürün ilişkileriyle başlayın.",
                        "Start with gross sales, country breakdowns or product relationships.",
                      )}
                    </p>
                  </div>
                )}
                <div className="wb-question-chips">
                  {[
                    t("Brüt satışları özetle", "Summarize gross sales"),
                    t(
                      "En çok satan ürünler hangileri?",
                      "Which products sell the most?",
                    ),
                  ].map((q) => (
                    <button
                      key={q}
                      disabled={working}
                      onClick={() => {
                        setQuestion(q);
                        void analyze({ prompt: q });
                      }}
                    >
                      {q}
                      <ArrowRight size={16} />
                    </button>
                  ))}
                </div>
                <div className="wb-analysis-mode">
                  <label>
                    <input
                      type="checkbox"
                      checked={useLlm}
                      disabled={!providerReady || working}
                      onChange={(e) => setUseLlm(e.target.checked)}
                    />
                    {t("Dil modeliyle yorumla", "Interpret with the language model")}
                  </label>
                  <span>
                    {useLlm
                      ? t(
                          `Soru sağlayıcıya (${providerLabel ?? "—"}) gönderilir; veri satırları gönderilmez.`,
                          `Your question is sent to ${providerLabel ?? "the provider"}; data rows stay local.`,
                        )
                      : t("Standart analiz", "Standard analysis")}
                  </span>
                </div>
                <form
                  className="wb-composer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (question.trim()) void askAnything(question);
                  }}
                >
                  <label htmlFor="wb-question" className="sr-only">
                    {t("Analiz sorunuz", "Your analysis question")}
                  </label>
                  <textarea
                    id="wb-question"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    maxLength={8000}
                    placeholder={t(
                      "Örn. En çok satan ürünler hangileri?",
                      "e.g. Which products sell the most?",
                    )}
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                        e.preventDefault();
                        if (question.trim()) void askAnything(question);
                      }
                    }}
                  />
                  <div>
                    <span>
                      {t(
                        "⌘ / Ctrl + Enter ile çalıştır",
                        "⌘ / Ctrl + Enter to run",
                      )}
                    </span>
                    <button
                      className="wb-btn wb-primary"
                      disabled={working || !question.trim()}
                    >
                      {working ? (
                        <Spinner className="spin" size={16} />
                      ) : (
                        <Send size={16} />
                      )}{" "}
                      {t("Analiz et", "Analyze")}
                    </button>
                  </div>
                </form>
                <p className="wb-footnote">
                  {t(
                    "Tutarlar brüt satıştır. Kâr ve tahmin için ek veri gerekir.",
                    "Amounts are gross sales. Profit and forecasting require additional data.",
                  )}
                </p>
              </section>
              <aside className="wb-panel wb-context">
                <h2>{t("Analizin bağlamı", "Analysis context")}</h2>
                <dl>
                  <dt>{t("Kaynak", "Source")}</dt>
                  <dd>{result.dataset.title}</dd>
                  <dt>{t("Kapsam", "Scope")}</dt>
                  <dd>
                    {filtered
                      ? t("Filtrelenmiş veri", "Filtered data")
                      : t("Tüm dönem ve ülkeler", "All dates and countries")}
                  </dd>
                  <dt>{t("Para birimi", "Currency")}</dt>
                  <dd>GBP</dd>
                  <dt>{t("Hesaplanan satır", "Computed rows")}</dt>
                  <dd>{num(result.summary.rows)}</dd>
                  <dt>{t("Metrik sürümü", "Metric version")}</dt>
                  <dd>retail-v1</dd>
                </dl>
                <button className="wb-btn" onClick={() => setModal("evidence")}>
                  <Code2 size={16} />
                  {t("SQL ve kanıt", "SQL and evidence")}
                </button>
                <button
                  className="wb-btn"
                  onClick={() => {
                    setSaveTitle(question || "Satış analizi");
                    setModal("save");
                  }}
                >
                  <Bookmark size={16} />
                  {saved
                    ? t("Kaydedildi", "Saved")
                    : t("Bulguyu kaydet", "Save finding")}
                </button>
              </aside>
            </div>
          )}
          {result && section === "chart" && chartTab === "network" && (
            <NetworkView
              result={result}
              busy={working}
              mode={graphMode}
              minimum={minimum}
              setMinimum={setMinimum}
              onMode={(m) => {
                setGraphMode(m);
                void analyze({ mode: m });
              }}
              onRecalculate={() => void analyze({ min: minimum })}
              money={money}
              onScope={() => setModal("scope")}
            />
          )}
          {section === "findings" && (
            <CompareRuns
              runs={runs}
              csrf={csrf}
              blocked={working}
              activity={activity}
            />
          )}
          {section === "findings" && (
            <section className="wb-panel">
              <div className="wb-panel-head">
                <div>
                  <h2>
                    {showArchive
                      ? t("Arşiv", "Archive")
                      : t("Kaydedilen bulgular", "Saved findings")}
                  </h2>
                  <button
                    className="wb-btn"
                    onClick={() => setShowArchive(!showArchive)}
                  >
                    {showArchive
                      ? t("Bulgulara dön", "Back to findings")
                      : t("Arşivi aç", "Open archive")}
                  </button>
                  <p>
                    {t(
                      "Yalnızca bu oturum kimliğine ait kayıtlar gösterilir.",
                      "Only your signed-in identity’s records are shown.",
                    )}
                  </p>
                </div>
                <button className="wb-btn" onClick={() => void history()}>
                  <RotateCcw size={16} />
                  {t("Yenile", "Refresh")}
                </button>
              </div>
              {(showArchive ? archivedRuns : runs).some((r) => r.saved) ? (
                <div className="wb-findings">
                  {(showArchive ? archivedRuns : runs)
                    .filter((r) => r.saved)
                    .map((r) => (
                      <article key={r.run_id}>
                        <span className="wb-finding-icon">
                          <Findings size={20} />
                        </span>
                        <div>
                          <h3>{r.title}</h3>
                          <p>
                            {datasets.find((d) => d.id === r.recipe.dataset)
                              ?.title || r.recipe.dataset}{" "}
                            ·{" "}
                            {new Date(r.created_at).toLocaleString(
                              locale === "tr" ? "tr-TR" : "en-GB",
                            )}
                          </p>
                          <span>
                            {money(r.summary.gross_sales)} ·{" "}
                            {num(r.summary.orders)} {t("sipariş", "orders")}
                          </span>
                        </div>
                        <button
                          className="wb-btn"
                          onClick={() => void openRun(r.run_id)}
                        >
                          {t("Aç", "Open")}
                          <ArrowUpRight size={16} />
                        </button>
                        <button
                          className="wb-btn"
                          disabled={working}
                          onClick={() =>
                            void archiveRun(r.run_id, !showArchive)
                          }
                        >
                          {showArchive
                            ? t("Geri yükle", "Restore")
                            : t("Arşivle", "Archive")}
                        </button>
                        <button
                          className="wb-btn"
                          disabled={working}
                          onClick={() => {
                            setDataset(r.recipe.dataset);
                            setDraft(r.recipe.filters);
                            setApplied(r.recipe.filters);
                            go("decision", "ask");
                            void analyze({
                              id: r.recipe.dataset,
                              filters: r.recipe.filters,
                              prompt: r.recipe.question,
                              mode: r.recipe.graph_mode,
                              min: r.recipe.min_shared,
                              include: r.recipe.include_service === true,
                            });
                          }}
                        >
                          {t("Yeniden çalıştır", "Rerun")}
                          <Run size={16} />
                        </button>
                      </article>
                    ))}
                </div>
              ) : (
                <Empty
                  title={t(
                    "Henüz kayıtlı bulgu yok.",
                    "No saved findings yet.",
                  )}
                  text={t(
                    "Bir soru çalıştırıp Bulguyu kaydet seçeneğini kullanın.",
                    "Run a question and select Save finding.",
                  )}
                />
              )}
            </section>
          )}
          {result && (section === "overview" || (section === "decision" && decisionTab === "ask") || (section === "chart" && chartTab === "network")) && (
            <div className="wb-bottom-actions">
              <span>
                <CheckCircle2 size={16} />
                {t("Sonuç kaydı", "Result record")} {result.run_id.slice(0, 8)}{" "}
                · {result.evidence.duration_ms} ms
              </span>
              <div>
                {/* Metric definitions live in the evidence dialog and the command palette, next to the SQL they explain. */}
                {/* Progressive disclosure: both downloads behind one choice (Hick–Hyman). */}
                <details className="wb-export-menu">
                  <summary className="wb-text-btn">
                    <Download size={16} />
                    {t("Dışa aktar", "Export")}
                  </summary>
                  <div role="group" aria-label={t("Dışa aktarım biçimleri", "Export formats")}>
                    <button className="wb-text-btn" onClick={exportCsv}>
                      {t("Önizleme CSV", "Preview CSV")}
                    </button>
                    <button
                      className="wb-text-btn"
                      onClick={() =>
                        download("analysis.json", JSON.stringify(result, null, 2))
                      }
                    >
                      {t("Analiz JSON", "Analysis JSON")}
                    </button>
                    <button
                      className="wb-text-btn"
                      onClick={() => {
                        setCodeChart(null);
                        setModal("code");
                      }}
                    >
                      {t("Python, SQL ve README", "Python, SQL and README")}
                    </button>
                  </div>
                </details>
                {/* The analysis view already offers "Save finding" beside the answer; no second save button. */}
                {!(section === "decision" && decisionTab === "ask") && (
                  <button
                    className="wb-btn"
                    onClick={() => {
                      setSaveTitle(question || "Satış analizi");
                      setModal("save");
                    }}
                  >
                    <Bookmark size={16} />
                    {saved ? t("Kaydedildi", "Saved") : t("Kaydet", "Save")}
                  </button>
                )}
              </div>
            </div>
          )}
          <footer className="wb-footer">
            <span>
              Context Layer <i /> {t("Analytics", "Analytics")}
            </span>
            <span>
              <ShieldCheck size={16} />
              {t("Hesap kaydı mevcut", "Calculation record available")}
            </span>
          </footer>
        </main>
      </div>
      {modal && (
        <Modal
          wide={modal === "code" || modal === "scope"}
          title={
            modal === "source"
              ? t("Verinin kaynağı ve sınırları", "Data provenance and limits")
              : modal === "evidence"
                ? t("Hesaplama kanıtı", "Calculation evidence")
                : modal === "metrics"
                  ? t("Metrik sözlüğü", "Metric dictionary")
                  : modal === "save"
                    ? t("Bulguyu kaydet", "Save finding")
                        : modal === "avatar"
                          ? t("Profil görseli", "Profile portrait")
                            : modal === "code"
                              ? t("Analizi kod olarak dışa aktar", "Export the analysis as code")
                            : modal === "scope"
                              ? t("Kapsam ve dışlamalar", "Scope and exclusions")
                        : modal === "import"
                          ? t("Veri hazırlama", "Prepare data")
                          : modal === "search"
                            ? t("Bir işlem bulun", "Find an action")
                            : t(
                                "İlk bulgunuza dört adım",
                                "Four steps to your first finding",
                              )
          }
          onClose={() => {
            setModal(null);
            setSearch("");
          }}
        >
          {error && (
            <p role="alert" className="wb-error-text">
              {error}
            </p>
          )}
          {modal === "source" && selected && (
            <>
              <span className="wb-badge blue">
                {selected.source.kind === "public"
                  ? t("Açık veri", "Public data")
                  : selected.source.kind === "uploaded"
                    ? t("Yüklenen veri", "Uploaded data")
                    : t("Örnek veri", "Sample data")}
              </span>
              <h3>{selected.title}</h3>
              <p>{selected.source.description}</p>
              <dl className="wb-detail-list">
                <dt>{t("Yayımlayan", "Publisher")}</dt>
                <dd>{selected.source.publisher}</dd>
                <dt>{t("Lisans", "License")}</dt>
                <dd>{selected.source.license}</dd>
                <dt>SHA-256</dt>
                <dd>
                  <code>{selected.sha256}</code>
                </dd>
              </dl>
              <div className="wb-callout">{selected.definition}</div>
              {selected.source.url && (
                <a
                  href={selected.source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="wb-btn"
                >
                  {t("Resmî kaynak", "Official source")}
                  <ExternalLink size={16} />
                </a>
              )}
              <Quality data={selected} num={num} />
              <h3>{t("Veri şeması", "Data schema")}</h3>
              <div className="wb-schema">
                {selected.schema.map((c) => (
                  <span key={c.name}>
                    <code>{c.name}</code>
                    <small>{c.type}</small>
                  </span>
                ))}
              </div>
            </>
          )}
          {modal === "evidence" && result && (
            <>
              <div className="wb-callout">{result.dataset.definition}</div>
              <h3>{t("Çalıştırılan SQL", "Executed SQL")}</h3>
              <pre>{result.evidence.sql}</pre>
              <h3>{t("Bağlanan parametreler", "Bound parameters")}</h3>
              <pre>{JSON.stringify(result.evidence.parameters, null, 2)}</pre>
              <dl className="wb-detail-list">
                <dt>Recipe</dt>
                <dd>{result.evidence.recipe_version}</dd>
                <dt>Dataset SHA-256</dt>
                <dd>
                  <code>{result.evidence.dataset_sha256}</code>
                </dd>
                <dt>Output SHA-256</dt>
                <dd>
                  <code>{result.evidence.output_sha256}</code>
                </dd>
              </dl>
              <h3>{t("Metrik tanımları", "Metric definitions")}</h3>
              {result.metrics.map((m) => (
                <article className="wb-metric-definition" key={m.id}>
                  <h4>{m.title}</h4>
                  <code>{m.formula}</code>
                  <p>{m.note}</p>
                </article>
              ))}
              <button
                className="wb-btn"
                onClick={() =>
                  download(
                    "evidence.json",
                    JSON.stringify(result.evidence, null, 2),
                  )
                }
              >
                <Download size={16} />
                {t("Kanıtı indir", "Download evidence")}
              </button>
            </>
          )}
          {modal === "code" && (
            <CodeExport dataset={dataset} filters={applied} chart={codeChart} csrf={csrf} />
          )}
          {modal === "avatar" && avatar && (
            <AvatarPicker
              value={avatar}
              saving={avatarSaving}
              onChoose={async (id) => {
                setAvatarSaving(true);
                const r = await api.put<{ avatar: string }>(BASE + "/profile", { avatar: id }, csrf);
                setAvatarSaving(false);
                if (r.ok) {
                  setAvatar(r.data.avatar);
                  setModal(null);
                  setNotice(t("Profil görseli güncellendi.", "Profile portrait updated."));
                } else setError(r.error.detail || t("Profil görseli kaydedilemedi.", "Could not save the portrait."));
              }}
            />
          )}
          {modal === "scope" && result?.scope && (
            <ScopeView
              scope={result.scope}
              money={money}
              num={num}
              busy={working}
              onIncludeService={(v) => {
                setIncludeService(v);
                void analyze({ include: v });
              }}
            />
          )}
          {modal === "metrics" &&
            result?.metrics.map((m) => (
              <article className="wb-metric-definition" key={m.id}>
                <h3>{m.title}</h3>
                <code>{m.formula}</code>
                <p>{m.note}</p>
              </article>
            ))}
          {modal === "save" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <label className="wb-field">
                {t("Bulgu başlığı", "Finding title")}
                <input
                  autoFocus
                  required
                  maxLength={120}
                  value={saveTitle}
                  onChange={(e) => setSaveTitle(e.target.value)}
                />
              </label>
              <p>
                {t(
                  "Sonuç, veri sürümü, filtreler ve kanıt birlikte saklanır.",
                  "Result, data version, filters and evidence are saved together.",
                )}
              </p>
              <button className="wb-btn wb-primary" type="submit">
                <Bookmark size={16} />
                {t("Kaydet", "Save")}
              </button>
            </form>
          )}
          {modal === "import" && (
            <Preparation
              csrf={csrf}
              busy={busy || childJobs > 0}
              activity={activity}
              onImported={async (d) => {
                setModal(null);
                await catalog();
                changeDataset(d.id);
                setNotice(
                  t(
                    "Veri içe aktarıldı. Kalite raporu ve kaynak kaydı hazır.",
                    "Data imported. Quality report and provenance are ready.",
                  ),
                );
              }}
            />
          )}
          {modal === "help" && (
            <>
              <Mascot pose="waving" size={120} className="wb-help-mascot" />
              <ol className="wb-help-steps">
                {[
                  [
                    t("Veriyi seçin", "Choose data"),
                    t(
                      "Örnek veriyle deneyin veya UCI veri setini inceleyin.",
                      "Start with the controlled demo, then try UCI real open data.",
                    ),
                  ],
                  [
                    t("Kapsamı belirleyin", "Set the scope"),
                    t(
                      "Ülke ve tarih seçip Uygula deyin. Boş tarih bütün dönemi kapsar.",
                      "Choose country/dates and Apply. Empty dates include the full period.",
                    ),
                  ],
                  [
                    t("Sorun veya grafik isteyin", "Ask or request a chart"),
                    t(
                      "Genel bakıştaki kutuya yazın: grafik istekleri Grafik stüdyosunda, sorular Karar stüdyosunda açılır. Kanıtı açın.",
                      "Type in the overview box: chart requests open in the Chart studio, questions in the Decision studio. Open the evidence.",
                    ),
                  ],
                  [
                    t("Bulguyu kaydedin", "Save a finding"),
                    t(
                      "Başlık verip Bulgularım üzerinden açın veya yeniden çalıştırın.",
                      "Give it a title, then open it or rerun it from My findings.",
                    ),
                  ],
                ].map(([h, p]) => (
                  <li key={h}>
                    <strong>{h}</strong>
                    <p>{p}</p>
                  </li>
                ))}
              </ol>
              <h3>{t("Uzman kontrolleri", "Expert controls")}</h3>
              <p>
                ⌘/Ctrl+K · {t("komut araması", "command search")}
                <br />
                ⌘/Ctrl+Enter · {t("soruyu çalıştır", "run question")}
                <br />
                Esc · {t("diyaloğu kapat", "close dialog")}
              </p>
              <div className="wb-callout">
                {t(
                  "Dil modeli seçeneği soruyu bir analiz planına çevirir; sayılar yerel hesaplardan gelir. Kâr, dönüşüm, tahmin ve nedensellik için ek veri/yöntem gerekir.",
                  "The language-model option turns a question into an analysis plan; numbers come from local calculations. Profit, conversion, forecasting and causality need more data or methods.",
                )}
              </div>
            </>
          )}
          {modal === "search" && (
            <>
              <label className="wb-search-input">
                <Search size={20} />
                <input
                  autoFocus
                  aria-label={t("İşlem ara", "Search actions")}
                  placeholder={t(
                    "Ağ, kanıt, veri, dışa aktar…",
                    "Network, evidence, data, export…",
                  )}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <div className="wb-command-results">
                {[
                  ...nav.map((n) => ({
                    label: t(...titles[n.id]),
                    action: () => go(n.id),
                  })),
                  {
                    label: t(
                      "Uzman SQL laboratuvarı ve bağlam arama",
                      "Expert SQL laboratory and context search",
                    ),
                    action: () => open("sql"),
                  },
                  {
                    label: t("İlişki ağı", "Relationship network"),
                    action: () => open("network"),
                  },
                  {
                    label: t(
                      "Zaman içindeki ağ değişimi",
                      "Network change over time",
                    ),
                    action: () => open("temporal"),
                  },
                  {
                    label: t("Analizleri karşılaştır", "Compare analyses"),
                    action: () => {
                      go("findings");
                      setTimeout(
                        () =>
                          document
                            .querySelector<HTMLDetailsElement>(".wb-comparison")
                            ?.setAttribute("open", ""),
                        0,
                      );
                    },
                  },
                  {
                    label: t(
                      "SQL ve hesaplama kanıtı",
                      "SQL and calculation evidence",
                    ),
                    action: () => setModal("evidence"),
                  },
                  {
                    label: t(
                      "Veri hazırlama ve CSV içe aktar",
                      "Prepare data and import CSV",
                    ),
                    action: () => setModal("import"),
                  },
                  {
                    label: t(
                      "Tahmin modeli ve deneylerim (Karar stüdyosu)",
                      "Prediction model and experiments (Decision studio)",
                    ),
                    action: () => open("model"),
                  },
                  {
                    label: t(
                      "Karar stüdyosu, tahmin ve senaryolar",
                      "Decision studio, forecasts and scenarios",
                    ),
                    action: () => open("decisions"),
                  },
                  {
                    label: t(
                      "Grafik stüdyosu: istediğiniz grafiği yazın",
                      "Chart studio: describe any chart",
                    ),
                    action: () => open("chart"),
                  },
                  {
                    label: t(
                      "Analizi Python, SQL ve README olarak dışa aktar",
                      "Export the analysis as Python, SQL and README",
                    ),
                    action: () => {
                      setCodeChart(null);
                      setModal("code");
                    },
                  },
                  {
                    label: t("Metrik sözlüğü", "Metric dictionary"),
                    action: () => setModal("metrics"),
                  },
                  {
                    label: t("Veri kalite raporu", "Data quality report"),
                    action: () => {
                      go("overview");
                      setDataTab("quality");
                    },
                  },
                  {
                    label: t("Önizlemeyi CSV indir", "Export preview CSV"),
                    action: () => {
                      exportCsv();
                      setModal(null);
                    },
                  },
                  {
                    label: t("Kullanım rehberi", "Getting started guide"),
                    action: () => setModal("help"),
                  },
                ]
                  .filter((x) =>
                    x.label
                      .toLocaleLowerCase(locale)
                      .includes(search.toLocaleLowerCase(locale)),
                  )
                  .map((x) => (
                    <button key={x.label} onClick={x.action}>
                      {x.label}
                      <ArrowRight size={16} />
                    </button>
                  ))}
              </div>
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
function Kpi({
  title,
  value,
  subtitle,
  icon,
  primary = false,
  action,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  primary?: boolean;
  /** A small control after the subtitle, e.g. "Why?" for what the number leaves out. */
  action?: React.ReactNode;
}) {
  return (
    <section className={"wb-kpi" + (primary ? " primary" : "")}>
      <div>
        <i aria-hidden="true">{icon}</i>
        <span>{title}</span>
      </div>
      <strong
        title={value}
        className={value.length > 12 ? "is-long" : undefined}
      >
        {value}
      </strong>
      <p>
        {subtitle}
        {action}
      </p>
    </section>
  );
}
function DataTable({ result }: { result: AnalysisResult }) {
  const { t } = useLocale();
  return (
    <TableWrap>
      <table>
        <caption>
          {t(
            "İlk 30 satırın önizlemesi; tüm sonuç değildir.",
            "Preview of the first 30 rows; not the full result.",
          )}
        </caption>
        <thead>
          <tr>
            {["Fatura", "Ürün", "Adet", "GBP", "Tarih", "Ülke"].map((x) => (
              <th scope="col" key={x}>
                {x}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.preview.map((r, i) => (
            <tr key={i}>
              <td>{r.invoice}</td>
              <td>{r.product}</td>
              <td>{r.quantity}</td>
              <td>{r.unit_price}</td>
              <td>{r.date}</td>
              <td>{r.country}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}
function Quality({ data, num }: { data: Dataset; num: (n: number) => string }) {
  const { t } = useLocale(),
    q = data.quality;
  return (
    <div className="wb-quality">
      <div className="wb-quality-score">
        <ShieldCheck size={24} />
        <div>
          <strong>
            {t(
              "Dönüşümler görünür ve kayıtlı",
              "Transformations are visible and recorded",
            )}
          </strong>
          <p>
            {t(
              "Kontroller örtüşebilir; sayılar ham veri profiline aittir.",
              "Checks may overlap; counts profile raw data.",
            )}
          </p>
        </div>
      </div>
      <dl>
        {[
          [t("Ham satır", "Raw rows"), q.raw_rows],
          [t("Analize alınan", "Included rows"), data.rows],
          [t("Dışlanan satır", "Excluded rows"), q.excluded_rows],
          [t("İptal kaydı", "Cancellations"), q.cancelled_rows],
          [
            t("Müşteri kimliği eksik", "Missing customer ID"),
            q.missing_customer,
          ],
          [
            t("Tekrarlı satır (korundu)", "Duplicates (retained)"),
            q.duplicate_rows,
          ],
        ].map(([l, n]) => (
          <div key={String(l)}>
            <dt>{l}</dt>
            <dd>{num(Number(n || 0))}</dd>
          </div>
        ))}
      </dl>
      <p>
        {t(
          "Eksik müşteri kimliği satış toplamını engellemez. Tekrarlar otomatik silinmedi.",
          "Missing customer ID does not invalidate sales totals. Duplicates were not removed automatically.",
        )}
      </p>
    </div>
  );
}
/** Labels that can be drawn without colliding: most-connected first, each kept only if its box clears every
 * label already placed and every other node. The rest appear on hover/focus, so no name is lost, only the
 * overprinting. Positions are in viewBox units, which zoom scales uniformly, so the result is zoom-invariant. */
function readableLabels(
  nodes: { id: string; x: number; y: number; degree: number; label: string }[],
  text: (n: { label: string }) => string,
  keep?: string,
): Set<string> {
  const place = (n: { x: number; y: number }) => ({ cx: 375 + n.x * 270, cy: 230 + n.y * 165 });
  const radius = (n: { degree: number }) => 15 + Math.min(9, n.degree / 2);
  const boxes: { l: number; r: number; t: number; b: number }[] = [];
  const shown = new Set<string>();
  const order = [...nodes].sort((a, b) => (a.id === keep ? -1 : b.id === keep ? 1 : b.degree - a.degree));
  for (const n of order) {
    const { cx, cy } = place(n);
    const w = text(n).length * 7.2 + 8;
    const box = { l: cx - w / 2, r: cx + w / 2, t: cy + 25, b: cy + 43 };
    const hitsLabel = boxes.some((o) => box.l < o.r && box.r > o.l && box.t < o.b && box.b > o.t);
    const hitsNode = nodes.some((m) => {
      if (m.id === n.id) return false;
      const p = place(m), r = radius(m);
      return p.cx + r > box.l && p.cx - r < box.r && p.cy + r > box.t && p.cy - r < box.b;
    });
    if (n.id === keep || (!hitsLabel && !hitsNode)) {
      boxes.push(box);
      shown.add(n.id);
    }
  }
  return shown;
}

const FILTER_NAMES: Record<keyof Filters, [string, string]> = {
  country: ["Ülke", "Country"],
  start: ["Başlangıç", "From"],
  end: ["Bitiş", "To"],
};
const FILTER_KEYS = ["country", "start", "end"] as const;
function filtersFromAddress(): Filters {
  const q = new URLSearchParams(window.location.search),
    out: Filters = {};
  for (const k of FILTER_KEYS) {
    const v = q.get(k);
    if (v && (k === "country" ? v.length <= 80 : /^\d{4}-\d{2}-\d{2}$/.test(v))) out[k] = v;
  }
  return out;
}
function filtersKey(f: Filters) {
  return FILTER_KEYS.map((k) => (f[k] ? `${k}=${encodeURIComponent(f[k]!)}` : "")).filter(Boolean).join("&");
}
function addressFor(f: Filters) {
  const q = new URLSearchParams(window.location.search);
  for (const k of FILTER_KEYS) {
    if (f[k]) q.set(k, f[k]!);
    else q.delete(k);
  }
  const query = q.toString();
  return window.location.pathname + (query ? "?" + query : "") + window.location.hash;
}
function replaceAddress(f: Filters) {
  window.history.replaceState(window.history.state, "", addressFor(f));
}
/** A new history entry only when the filters actually changed, so back steps through distinct views. */
function syncAddress(f: Filters) {
  if (filtersKey(f) !== filtersKey(filtersFromAddress())) window.history.pushState(null, "", addressFor(f));
}
/** ISO date (yyyy-mm-dd) as dd.mm.yyyy, matching the date inputs' Turkish order. */
function dateText(iso: string) {
  const [y, m, d] = iso.split("-");
  return y && m && d ? `${d}.${m}.${y}` : iso;
}

function NetworkView({
  result,
  busy,
  mode,
  minimum,
  setMinimum,
  onMode,
  onRecalculate,
  money,
  onScope,
}: {
  result: AnalysisResult;
  busy: boolean;
  mode: string;
  minimum: number;
  setMinimum: (v: number) => void;
  onMode: (m: string) => void;
  onRecalculate: () => void;
  money: (n: number) => string;
  onScope: () => void;
}) {
  const { t } = useLocale();
  const [selected, setSelected] = useState<GraphNode | null>(null),
    [zoom, setZoom] = useState(1),
    [filter, setFilter] = useState(""),
    [table, setTable] = useState(false),
    [limit, setLimit] = useState<number>(DEFAULT_EDGE_LIMIT),
    [hover, setHover] = useState<string | null>(null);
  const g = result.graph,
    colors = [
      "#6674e5",
      "#299b8c",
      "#df9b41",
      "#b36ca6",
      "#557ea3",
      "#bd6d4d",
      "#7f9e4e",
      "#8564b2",
      "#439cad",
      "#ad8b35",
      "#be6683",
      "#687d4c",
    ];
  const nodes = g.nodes.filter(
      (n) =>
        !filter ||
        n.label.toLocaleLowerCase().includes(filter.toLocaleLowerCase()) ||
        n.id.toLowerCase().includes(filter.toLowerCase()),
    ),
    ids = new Set(nodes.map((n) => n.id)),
    linked = strongest(g.edges.filter((e) => ids.has(e.source) && ids.has(e.target)), 0),
    edges = strongest(linked, limit),
    scale = edgeScale(edges),
    focus = neighbourhood(edges, hover ?? selected?.id ?? null),
    copurchase = g.mode !== "similarity",
    weightText = (w: number) =>
      copurchase
        ? `${Math.round(w)} ${t("ortak fatura", "shared invoices")}`
        : `${t("benzerlik", "similarity")} ${w.toFixed(2)}`,
    nodeText = (n: { label: string }) =>
      n.label.length > (nodes.length > 16 ? 12 : 23)
        ? n.label.slice(0, nodes.length > 16 ? 11 : 21) + "…"
        : n.label,
    labelled = readableLabels(nodes, nodeText, selected?.id);
  const canvasRef = useRef<HTMLDivElement>(null);
  useEffect(() => setSelected(null), [result.run_id]);
  // On a phone the graph keeps its legible scale and scrolls sideways; open it on the centre, not the left edge.
  useEffect(() => {
    const el = canvasRef.current;
    if (el && el.scrollWidth > el.clientWidth) el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2;
  }, [result.run_id, table]);
  return (
    <section className="wb-panel">
      <div className="wb-panel-head">
        <div>
          <h2>{t("Ürün ilişkileri", "Product relationships")}</h2>
          <p>
            {nodes.length} {t("düğüm", "nodes")} ·{" "}
            {edges.length < linked.length
              ? t(`en güçlü ${edges.length} / ${linked.length} kenar`, `strongest ${edges.length} of ${linked.length} edges`)
              : `${edges.length} ${t("kenar", "edges")}`}{" "}
            · {g.communities || 0}{" "}
            {t("topluluk", "communities")}
          </p>
        </div>
        <div className="wb-tabs">
          <button
            className={!table ? "active" : ""}
            onClick={() => setTable(false)}
          >
            <Network size={16} />
            {t("Ağ", "Graph")}
          </button>
          <button
            className={table ? "active" : ""}
            onClick={() => setTable(true)}
          >
            <Table2 size={16} />
            {t("Tablo", "Table")}
          </button>
        </div>
      </div>
      <div className="wb-network-controls">
        <label>
          {t("İlişki tanımı", "Relationship definition")}
          <select
            value={mode}
            disabled={busy}
            onChange={(e) => onMode(e.target.value)}
          >
            <option value="copurchase">
              {t("Aynı faturada birlikte alım", "Same-invoice co-purchase")}
            </option>
            <option value="similarity">
              {t(
                "Satış profili benzerliği · PoliEco",
                "Sales profile similarity · PoliEco",
              )}
            </option>
          </select>
        </label>
        <label>
          {t("En az ortak sipariş", "Minimum shared orders")}
          <input
            type="number"
            min={1}
            max={100}
            value={minimum}
            disabled={mode !== "copurchase"}
            onChange={(e) =>
              setMinimum(
                Math.max(1, Math.min(100, Math.round(Number(e.target.value)))),
              )
            }
          />
        </label>
        <button className="wb-btn" disabled={busy} onClick={onRecalculate}>
          {t("Ağı hesapla", "Compute network")}
        </button>
        <label>
          {t("Gösterilen bağ", "Links shown")}
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {EDGE_LIMITS.map((n) => (
              <option key={n} value={n}>
                {n ? t(`En güçlü ${n}`, `Strongest ${n}`) : t(`Tümü (${linked.length})`, `All (${linked.length})`)}
              </option>
            ))}
          </select>
        </label>
        <label className="wb-node-search">
          <Search size={16} />
          <input
            aria-label={t("Ürün bul", "Find product")}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("Ürün bul…", "Find product…")}
          />
        </label>
      </div>
      <div className="wb-callout wb-graph-note">
        <Info size={16} />
        <span>
          {g.note}{" "}
          {result.scope?.service.lines ? (
            <>
              {g.include_service
                ? t(
                    `Kargo, ücret ve düzeltme kalemleri ürün olarak dahil (${result.scope.service.lines} satır).`,
                    `Postage, fees and adjustments are counted as products (${result.scope.service.lines} lines).`,
                  )
                : t(
                    `Kargo, ücret ve düzeltme kalemleri ürün sayılmadı (${result.scope.service.lines} satır, ${money(result.scope.service.pence / 100)}).`,
                    `Postage, fees and adjustments are not counted as products (${result.scope.service.lines} lines, ${money(result.scope.service.pence / 100)}).`,
                  )}{" "}
              <button className="wb-why" onClick={onScope}>
                {t("Neden? Değiştir", "Why? Change")}
              </button>
            </>
          ) : null}
        </span>
      </div>
      {table ? (
        <TableWrap>
          <table>
            <caption>
              {t(
                "Grafiğin tablo alternatifi",
                "Table alternative to the graph",
              )}
            </caption>
            <thead>
              <tr>
                <th>{t("Ürün", "Product")}</th>
                <th>{t("Bağlantı", "Degree")}</th>
                <th>{t("Topluluk", "Community")}</th>
                <th>Betweenness</th>
                <th>{t("Brüt satış", "Gross sales")}</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((n) => (
                <tr key={n.id}>
                  <td>{n.label}</td>
                  <td>{n.degree}</td>
                  <td>{n.community + 1}</td>
                  <td>{n.brokerage}</td>
                  <td>{money(n.pence / 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <table>
            <caption>
              {t(
                "Görünen ilişkilerin ağırlıkları; filtre ve alt ağ sınırları geçerlidir.",
                "Visible edge weights; current filters and subgraph limits apply.",
              )}
            </caption>
            <thead>
              <tr>
                <th>{t("Kaynak ürün", "Source product")}</th>
                <th>{t("Hedef ürün", "Target product")}</th>
                <th>
                  {mode === "copurchase"
                    ? t("Ortak fatura", "Shared invoices")
                    : t("Profil benzerliği", "Profile similarity")}
                </th>
              </tr>
            </thead>
            <tbody>
              {linked.map((e) => (
                <tr key={e.source + ":" + e.target}>
                  <td>
                    {nodes.find((n) => n.id === e.source)?.label || e.source}
                  </td>
                  <td>
                    {nodes.find((n) => n.id === e.target)?.label || e.target}
                  </td>
                  <td>{e.weight}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : (
        <div className="wb-network-layout">
          <div className="wb-network-canvas" ref={canvasRef}>
            <svg
              role="group"
              aria-label={t(
                "Ürün ilişki ağı; düğümlere klavyeyle erişilebilir.",
                "Product network; nodes are keyboard accessible.",
              )}
              viewBox="0 0 750 460"
            >
              <g
                transform={`translate(${375 - 375 * zoom},${230 - 230 * zoom}) scale(${zoom})`}
              >
                {/* Weakest first, so a strong link is never painted over by a weak one. */}
                {[...edges].reverse().map((e) => {
                  const a = nodes.find((n) => n.id === e.source),
                    b = nodes.find((n) => n.id === e.target);
                  if (!a || !b) return null;
                  const st = scale.style(e.weight),
                    lit = focus && focus.has(a.id) && focus.has(b.id) && (a.id === (hover ?? selected?.id) || b.id === (hover ?? selected?.id));
                  return (
                    <line
                      aria-hidden="true"
                      key={e.source + ":" + e.target}
                      x1={375 + a.x * 270}
                      y1={230 + a.y * 165}
                      x2={375 + b.x * 270}
                      y2={230 + b.y * 165}
                      className={`wb-edge is-${st.tier}${st.negative ? " is-negative" : ""}${lit ? " is-lit" : ""}`}
                      strokeDasharray={st.negative ? "5 4" : undefined}
                      strokeWidth={lit ? st.width + 1 : st.width}
                      strokeLinecap="round"
                      opacity={focus ? (lit ? Math.max(0.9, st.opacity) : 0.07) : st.opacity}
                    >
                      <title>
                        {a.label} ↔ {b.label}: {weightText(e.weight)}
                      </title>
                    </line>
                  );
                })}
                {/* The lit links of the hovered or selected product carry their value at the midpoint. */}
                {focus &&
                  edges.map((e) => {
                    const id = hover ?? selected?.id,
                      a = nodes.find((n) => n.id === e.source),
                      b = nodes.find((n) => n.id === e.target);
                    if (!a || !b || (a.id !== id && b.id !== id)) return null;
                    return (
                      <text
                        key={"w" + e.source + ":" + e.target}
                        className="wb-edge-value"
                        x={375 + ((a.x + b.x) / 2) * 270}
                        y={230 + ((a.y + b.y) / 2) * 165 + 4}
                        textAnchor="middle"
                      >
                        {copurchase ? Math.round(e.weight) : e.weight.toFixed(2)}
                      </text>
                    );
                  })}
                {nodes.map((n) => (
                  <g
                    key={n.id}
                    transform={`translate(${375 + n.x * 270},${230 + n.y * 165})`}
                    data-label={labelled.has(n.id) ? "shown" : "on-hover"}
                    tabIndex={0}
                    role="button"
                    aria-label={`${n.label}, ${n.degree} ${t("bağlantı", "connections")}`}
                    onClick={() => setSelected(n)}
                    onMouseEnter={() => setHover(n.id)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(n.id)}
                    onBlur={() => setHover(null)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(n);
                      }
                    }}
                    className={`wb-graph-node${focus && !focus.has(n.id) ? " is-faded" : ""}`}
                  >
                    <title>
                      {n.label} · {t("Topluluk", "Community")} {n.community + 1}
                    </title>
                    {/* Invisible hit ring: the largest radius that never overlaps a neighbour (layout keeps 72
                        units between centres), so every node is an adequate, unambiguous target (Fitts). */}
                    <circle r={36} className="wb-graph-hit" />
                    <circle
                      r={15 + Math.min(9, n.degree / 2)}
                      fill={colors[n.community % colors.length]}
                      stroke={selected?.id === n.id ? "#1e2b57" : "white"}
                      strokeWidth={selected?.id === n.id ? 4 : 3}
                    />
                    <text y={37} textAnchor="middle" className={labelled.has(n.id) ? undefined : "is-quiet"}>
                      {nodeText(n)}
                    </text>
                  </g>
                ))}
              </g>
            </svg>
            <div className="wb-zoom">
              <button
                className="wb-icon"
                aria-label={t("Yakınlaştır", "Zoom in")}
                onClick={() => setZoom(Math.min(1.8, zoom + 0.2))}
              >
                <ZoomIn size={20} />
              </button>
              <button
                className="wb-icon"
                aria-label={t("Uzaklaştır", "Zoom out")}
                onClick={() => setZoom(Math.max(0.6, zoom - 0.2))}
              >
                <ZoomOut size={20} />
              </button>
              <button
                className="wb-icon"
                aria-label={t("Görünümü sıfırla", "Reset view")}
                onClick={() => {
                  setZoom(1);
                  setSelected(null);
                  setFilter("");
                }}
              >
                <RotateCcw size={16} />
              </button>
            </div>
            <span className="wb-canvas-hint">
              {t(
                "Bir ürünün üzerine gelin veya seçin · düğüm rengi topluluğu gösterir",
                "Hover or select a product · node colour shows the community",
              )}
            </span>
            <div className="wb-edge-legend" aria-label={t("Bağ gücü göstergesi", "Link strength legend")}>
            <span className="wb-edge-legend-title">
              {copurchase ? t("Bağ gücü (ortak fatura)", "Link strength (shared invoices)") : t("Bağ gücü (benzerlik)", "Link strength (similarity)")}
            </span>
            {scale.legend.map((l) => {
              const mid = scale.style(l.to);
              const fmt = (v: number) => (copurchase ? String(Math.round(v)) : v.toFixed(2));
              return (
                <span key={l.tier} className="wb-edge-legend-item">
                  <svg width="36" height="12" aria-hidden="true">
                    <line x1="2" y1="6" x2="34" y2="6" className={`wb-edge is-${l.tier}`} strokeWidth={mid.width} strokeLinecap="round" opacity={mid.opacity} />
                  </svg>
                  {l.tier === "weak" ? t("zayıf", "weak") : l.tier === "mid" ? t("orta", "medium") : t("güçlü", "strong")} {fmt(l.from)}–{fmt(l.to)}
                </span>
              );
            })}
            {!copurchase && (
              <span className="wb-edge-legend-item">
                <svg width="36" height="12" aria-hidden="true">
                  <line x1="2" y1="6" x2="34" y2="6" className="wb-edge is-negative" strokeWidth={2} strokeDasharray="5 4" />
                </svg>
                {t("kesik: ters yönlü benzerlik", "dashed: opposite profile")}
              </span>
            )}
          </div>
          </div>
          <aside className="wb-node-detail">
            {selected ? (
              <>
                <span className="wb-badge blue">{selected.id}</span>
                <h3>{selected.label}</h3>
                <dl>
                  <dt>{t("Brüt satış", "Gross sales")}</dt>
                  <dd>{money(selected.pence / 100)}</dd>
                  <dt>{t("Bağlantı sayısı", "Degree")}</dt>
                  <dd>{selected.degree}</dd>
                  <dt>{t("Topluluk", "Community")}</dt>
                  <dd>{selected.community + 1}</dd>
                  <dt>Betweenness</dt>
                  <dd>{selected.brokerage}</dd>
                </dl>
                <p>
                  {t(
                    "Merkeziyet gerçek etki veya gelir garantisi değildir.",
                    "Centrality does not establish influence or revenue impact.",
                  )}
                </p>
              </>
            ) : (
              <>
                <Network size={32} />
                <h3>{t("Ürün ayrıntıları", "Product details")}</h3>
                <p>
                  {t(
                    "Bir ürünü seçerek satışını ve ağ içindeki yerini inceleyin.",
                    "Select a product to inspect its sales and network position.",
                  )}
                </p>
                <p className="wb-small" title={g.source_method}>
                  {g.mode === "similarity"
                    ? t("Benzerlik çekirdeği (PoliEco) · NetworkX yerleşimi, seed 47", "PoliEco similarity kernel · NetworkX layout, seed 47")
                    : t("Gözlenen fatura birlikteliği · NetworkX yerleşimi, seed 47", "Observed invoice co-occurrence · NetworkX layout, seed 47")}
                </p>
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
