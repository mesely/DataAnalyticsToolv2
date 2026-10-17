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
} from "./types";
const BASE = "/v1/dashboard/workbench";
import { csvCell as cell } from "./csv";
const titles: Record<Section, [string, string]> = {
  overview: ["Genel bakış", "Overview"],
  analysis: ["Analiz asistanı", "Analysis assistant"],
  network: ["İlişki ağı", "Relationship network"],
  findings: ["Bulgularım", "My findings"],
};
function download(name: string, text: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  const [section, setSection] = useState<Section>("overview"),
    [datasets, setDatasets] = useState<Dataset[]>([]),
    [dataset, setDataset] = useState("uci"),
    [result, setResult] = useState<AnalysisResult | null>(null),
    [busy, setBusy] = useState(false),
    [childJobs, setChildJobs] = useState(0),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [draft, setDraft] = useState<Filters>({}),
    [applied, setApplied] = useState<Filters>({}),
    [question, setQuestion] = useState(""),
    [useLlm, setUseLlm] = useState(false),
    [providerReady, setProviderReady] = useState(false),
    [graphMode, setGraphMode] = useState("copurchase"),
    [minimum, setMinimum] = useState(2),
    [modal, setModal] = useState<
      | "help"
      | "search"
      | "evidence"
      | "source"
      | "import"
      | "model"
      | "decisions"
      | "save"
      | "metrics"
      | "avatar"
      | "chart"
      | "code"
      | "sql"
      | "temporal"
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
        provider: { connected: boolean; configured?: boolean };
      }>(BASE + "/catalog");
      if (r.ok) {
        setDatasets(r.data.datasets);
        setProviderReady(
          r.data.provider.configured ?? r.data.provider.connected,
        );
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
          locale,
        },
        csrf,
      );
      if (version === requestVersion.current) {
        if (r.ok) {
          setResult(r.data);
          setSaved(false);
          setApplied(r.data.filters);
          void history();
        } else setError(r.error.detail);
      }
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  }
  useEffect(() => {
    void catalog().then(() => analyze());
    void history();
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
  function go(s: Section) {
    setSection(s);
    setMenu(false);
    setModal(null);
    if (s === "findings") void history();
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
      setGraphMode(r.data.recipe.graph_mode);
      setMinimum(r.data.recipe.min_shared);
      setQuestion(r.data.recipe.question || "");
      setSaved(r.data.saved);
      go("analysis");
    } else setError(r.error.detail);
  }
  const selected = datasets.find((d) => d.id === dataset),
    s = result?.summary,
    source = selected?.source,
    filtered = !!(applied.country || applied.start || applied.end);
  const nav = [
    { id: "overview" as const, icon: Overview },
    { id: "analysis" as const, icon: Assistant },
    { id: "network" as const, icon: Network },
    { id: "findings" as const, icon: Findings },
  ];
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
                  : section === "analysis"
                    ? t(
                        "Hesaplanan sonucu, varsayımları ve kanıtı birlikte görün.",
                        "See computed results, assumptions and evidence together.",
                      )
                    : section === "network"
                      ? t(
                          "Birlikte alım, profil benzerliği ve dönem değişimi.",
                          "Co-purchase, profile similarity and changes over time.",
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
          </div>
          {working && (
            <div className="wb-loading-bar" role="status">
              {t(
                "Veri ve ilişkiler hesaplanıyor…",
                "Computing data and relationships…",
              )}
            </div>
          )}
          {s && section !== "findings" && (
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
                      <button onClick={() => setModal("chart")}>
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
                        {t(
                          "Aynı tanım, karşılaştırılabilir tutarlar",
                          "One definition, comparable totals",
                        )}
                      </p>
                    </div>
                    <Markets size={20} />
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
                    {t(
                      "Bir ülkeye tıklayarak görünümü filtreleyin.",
                      "Select a country to filter this view.",
                    )}
                  </p>
                </section>
              </div>
              <div className="wb-lower-grid">
                <section className="wb-panel wb-start">
                  <div className="wb-start-symbol">
                    <MessageSquare size={24} />
                  </div>
                  <div>
                    <div className="wb-eyebrow">{t("ANALİZ", "ANALYSIS")}</div>
                    <h2>
                      {t("Satış analizi", "Ask your data the right question.")}
                    </h2>
                    <p>
                      {t(
                        "Hazır sorularla başlayın; sonucu kaynağıyla kontrol edin.",
                        "Start with a suggested question and verify its source.",
                      )}
                    </p>
                    <div className="wb-starters">
                      {/* One starter: the assistant screen holds the other example questions (Hick–Hyman). */}
                      {[t("Satışları özetle", "Summarize sales")].map((q) => (
                        <button
                          key={q}
                          disabled={working}
                          onClick={() => {
                            go("analysis");
                            setQuestion(q);
                            void analyze({ prompt: q });
                          }}
                        >
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
                      onClick={() => go("network")}
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
          {(section === "overview" || section === "analysis") && (
            <section className="wb-decision-entry">
              <div>
                <span className="wb-eyebrow">
                  {t("KARAR ÇALIŞMASI", "DECISION WORKSPACE")}
                </span>
                <h2>
                  {t(
                    "Bulguları bir sonraki adıma dönüştürün",
                    "Turn findings into a next step",
                  )}
                </h2>
                <p>
                  {t(
                    "Haftalık projeksiyon, varsayımsal senaryo ve dayanaklarına bağlı öneriler.",
                    "Weekly projections, hypothetical scenarios and evidence-linked recommendations.",
                  )}
                </p>
              </div>
              <button
                className="wb-btn"
                disabled={working}
                onClick={() => setModal("decisions")}
              >
                {t("Karar stüdyosunu aç", "Open decision studio")}
                <ArrowRight size={16} />
              </button>
            </section>
          )}
          {section === "analysis" && (
            <div className="wb-model-entry">
              <img
                src={modelArt}
                className="wb-model-entry-art"
                alt=""
                width="72"
                height="72"
                loading="lazy"
              />
              <div>
                <strong>{t("Model stüdyosu", "Model studio")}</strong>
                <span>
                  {t(
                    "Hedefinizi seçin, başlangıç modeliyle karşılaştırın.",
                    "Choose your target and compare against a baseline.",
                  )}
                </span>
              </div>
              <button
                className="wb-btn"
                disabled={working}
                onClick={() => setModal("model")}
              >
                {t("Model deneyi aç", "Open model experiment")}
                <ArrowRight size={16} />
              </button>
            </div>
          )}
          {section === "analysis" && (
            <div className="wb-model-entry wb-chart-entry">
              <Mascot pose="reading" size={72} className="wb-model-entry-art" />
              <div>
                <strong>{t("Grafik stüdyosu", "Chart studio")}</strong>
                <span>
                  {t(
                    "İstediğiniz grafiği yazın: dönemi daraltın, ülkeleri karşılaştırın, güven aralığı veya trend ekleyin.",
                    "Describe the chart you want: narrow the period, compare countries, add an interval or a trend.",
                  )}
                </span>
              </div>
              <button className="wb-btn" disabled={working} onClick={() => setModal("chart")}>
                {t("Stüdyoyu aç", "Open studio")}
                <ArrowRight size={16} />
              </button>
            </div>
          )}
          {section === "analysis" && (
            <button type="button" className="wb-panel wb-expert wb-expert-entry" onClick={() => setModal("sql")}>
              <span>
                <Code2 size={20} />
                <strong>{t("Uzman araçları", "Expert tools")}</strong>
                <small>{t("SQL laboratuvarı ve bağlam arama", "SQL laboratory and context search")}</small>
              </span>
              <ChevronRight size={20} />
            </button>
          )}
          {result && section === "analysis" && (
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
                          {result.planner.http_status === 402
                            ? t(
                                "Llama kullanılamıyor: Hugging Face hesabında çıkarım kredisi gerekiyor. Standart analiz sonucu gösteriliyor.",
                                "Llama is unavailable: Hugging Face inference credits are required. Showing the standard analysis.",
                              )
                            : t(
                                "Llama planı alınamadı. Standart analiz sonucu gösteriliyor.",
                                "Llama planning is unavailable. Showing the standard analysis.",
                              )}
                        </p>
                      )}
                    {result.planner?.status === "planned" && (
                      <p className="wb-plan-receipt">
                        {t("Llama planı", "Llama plan")}:{" "}
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
                    {t("Llama ile yorumla", "Interpret with Llama")}
                  </label>
                  <span>
                    {useLlm
                      ? t(
                          "Soru Hugging Face'e gönderilir; veri satırları gönderilmez.",
                          "Your question is sent to Hugging Face; data rows stay local.",
                        )
                      : t("Standart analiz", "Standard analysis")}
                  </span>
                </div>
                <form
                  className="wb-composer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (question.trim()) void analyze({ prompt: question });
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
                        if (question.trim()) void analyze({ prompt: question });
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
          {result && section === "network" && (
            <button type="button" className="wb-panel wb-expert wb-expert-entry" onClick={() => setModal("temporal")}>
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
            </button>
          )}
          {result && section === "network" && (
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
                            go("analysis");
                            void analyze({
                              id: r.recipe.dataset,
                              filters: r.recipe.filters,
                              prompt: r.recipe.question,
                              mode: r.recipe.graph_mode,
                              min: r.recipe.min_shared,
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
          {result && section !== "findings" && (
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
                {section !== "analysis" && (
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
          wide={modal === "decisions" || modal === "chart" || modal === "code" || modal === "sql" || modal === "temporal"}
          title={
            modal === "source"
              ? t("Verinin kaynağı ve sınırları", "Data provenance and limits")
              : modal === "evidence"
                ? t("Hesaplama kanıtı", "Calculation evidence")
                : modal === "metrics"
                  ? t("Metrik sözlüğü", "Metric dictionary")
                  : modal === "save"
                    ? t("Bulguyu kaydet", "Save finding")
                    : modal === "decisions"
                      ? t("Karar stüdyosu", "Decision studio")
                      : modal === "model"
                        ? t("Model stüdyosu", "Model studio")
                        : modal === "avatar"
                          ? t("Profil görseli", "Profile portrait")
                          : modal === "chart"
                            ? t("Grafik stüdyosu", "Chart studio")
                            : modal === "code"
                              ? t("Analizi kod olarak dışa aktar", "Export the analysis as code")
                            : modal === "sql"
                              ? t("Uzman araçları", "Expert tools")
                            : modal === "temporal"
                              ? t("Zaman içindeki değişim", "Change over time")
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
          {modal === "temporal" && result && (
            <TemporalView
              activity={activity}
              data={result.dataset}
              filters={applied}
              csrf={csrf}
              busy={working}
              minimum={minimum}
              asDialog
            />
          )}
          {modal === "sql" && (
            <ExpertTools activity={activity} dataset={dataset} filters={applied} csrf={csrf} busy={working} asDialog />
          )}
          {modal === "chart" && (
            <ChartStudio
              dataset={dataset}
              filters={applied}
              csrf={csrf}
              providerReady={providerReady}
              onExportCode={(spec) => {
                setCodeChart(spec);
                setModal("code");
              }}
            />
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
          {modal === "decisions" && (
            <DecisionStudio
              dataset={dataset}
              filters={applied}
              csrf={csrf}
              busy={busy || childJobs > 0}
              activity={activity}
            />
          )}
          {modal === "model" && (
            <ModelStudio
              csrf={csrf}
              busy={busy || childJobs > 0}
              activity={activity}
            />
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
                    t(
                      "Analiz edin ve ilişkileri görün",
                      "Analyze and explore relationships",
                    ),
                    t(
                      "Örnek soruyu çalıştırın; kanıtı açın; ağda bir ürünü seçin.",
                      "Run a suggested question; inspect evidence; select a product in the network.",
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
                  "Llama seçeneği soruyu bir analiz planına çevirir. Kâr, dönüşüm, tahmin ve nedensellik için ek veri/yöntem gerekir.",
                  "Local explanations are active; LLM is not connected. Profit, conversion, forecasting and causality are outside this scope.",
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
                    action: () => {
                      go("analysis");
                      setModal("sql");
                    },
                  },
                  {
                    label: t(
                      "Zaman içindeki ağ değişimi",
                      "Network change over time",
                    ),
                    action: () => {
                      go("network");
                      setModal("temporal");
                    },
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
                      "Model stüdyosu ve deneylerim",
                      "Model studio and experiments",
                    ),
                    action: () => setModal("model"),
                  },
                  {
                    label: t(
                      "Karar stüdyosu, tahmin ve senaryolar",
                      "Decision studio, forecasts and scenarios",
                    ),
                    action: () => setModal("decisions"),
                  },
                  {
                    label: t(
                      "Grafik stüdyosu: istediğiniz grafiği yazın",
                      "Chart studio: describe any chart",
                    ),
                    action: () => setModal("chart"),
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
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  primary?: boolean;
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
      <p>{subtitle}</p>
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

function NetworkView({
  result,
  busy,
  mode,
  minimum,
  setMinimum,
  onMode,
  onRecalculate,
  money,
}: {
  result: AnalysisResult;
  busy: boolean;
  mode: string;
  minimum: number;
  setMinimum: (v: number) => void;
  onMode: (m: string) => void;
  onRecalculate: () => void;
  money: (n: number) => string;
}) {
  const { t } = useLocale();
  const [selected, setSelected] = useState<GraphNode | null>(null),
    [zoom, setZoom] = useState(1),
    [filter, setFilter] = useState(""),
    [table, setTable] = useState(false);
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
    edges = g.edges.filter((e) => ids.has(e.source) && ids.has(e.target)),
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
            {nodes.length} {t("düğüm", "nodes")} · {edges.length}{" "}
            {t("kenar", "edges")} · {g.communities || 0}{" "}
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
        {g.note}
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
              {edges.map((e) => (
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
                {edges.map((e, i) => {
                  const a = nodes.find((n) => n.id === e.source),
                    b = nodes.find((n) => n.id === e.target);
                  if (!a || !b) return null;
                  const h =
                    selected && (selected.id === a.id || selected.id === b.id);
                  return (
                    <line
                      aria-hidden="true"
                      key={i}
                      x1={375 + a.x * 270}
                      y1={230 + a.y * 165}
                      x2={375 + b.x * 270}
                      y2={230 + b.y * 165}
                      stroke={
                        e.weight < 0 ? "#d88384" : h ? "#6173df" : "#c6cde5"
                      }
                      strokeDasharray={e.weight < 0 ? "5 4" : undefined}
                      strokeWidth={h ? 2 : 1.2}
                      opacity={selected && !h ? 0.3 : 0.65}
                    >
                      <title>
                        {a.label} ↔ {b.label}: {e.weight}
                      </title>
                    </line>
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
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(n);
                      }
                    }}
                    className="wb-graph-node"
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
                "Bir ürün seçin · renkler toplulukları gösterir",
                "Select a product · colors show communities",
              )}
            </span>
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
