/**
 * Context Layer icon vocabulary — every icon is a glyph from the original Gemini-generated family
 * (assets/glyphs/gemini-batch-*.json → tools/design/glyphs.py → glyphs.generated.ts). One meaning per glyph:
 * the exported names below are semantic, and legacy names used by older screens map onto them.
 * No stock icon library is used anywhere in the workspace.
 */
import { glyph } from "./Glyph";

// Shell and navigation
export const Overview = glyph("overview"),
  Assistant = glyph("assistant"),
  NetworkGlyph = glyph("network"),
  Findings = glyph("findings"),
  Admin = glyph("admin"),
  Guide = glyph("guide"),
  Workspace = glyph("workspace"),
  LogOut = glyph("logout"),
  Search = glyph("search"),
  HelpCircle = glyph("help"),
  Language = glyph("language"),
  Sun = glyph("theme_light"),
  Moon = glyph("theme_dark"),
  Menu = glyph("menu"),
  X = glyph("close"),
  NarrowView = glyph("narrow_view");

// Data and actions
export const Dataset = glyph("dataset"),
  AboutData = glyph("about_data"),
  Upload = glyph("upload"),
  Download = glyph("download"),
  ExternalLink = glyph("external"),
  Open = glyph("open"),
  ArrowRight = glyph("forward"),
  ChevronRight = glyph("chevron_right"),
  ChevronDown = glyph("chevron_down"),
  Reset = glyph("reset"),
  Apply = glyph("apply"),
  Confirmed = glyph("confirmed"),
  Run = glyph("run"),
  Spinner = glyph("spinner"),
  Info = glyph("info"),
  Save = glyph("save");

// Metrics and analytical tools
export const GrossSales = glyph("gross_sales"),
  Orders = glyph("orders"),
  Units = glyph("units"),
  AverageOrder = glyph("average_order"),
  Markets = glyph("markets"),
  Trend = glyph("trend"),
  TableView = glyph("table_view"),
  Report = glyph("report"),
  Verified = glyph("verified"),
  Query = glyph("query"),
  Send = glyph("send"),
  Experiment = glyph("experiment"),
  SavedExperiments = glyph("saved_experiments"),
  PeriodChange = glyph("period_change"),
  Decision = glyph("decision"),
  ZoomIn = glyph("zoom_in"),
  ZoomOut = glyph("zoom_out");

// Legacy names kept so screens read naturally; each maps to exactly one meaning above.
export const Database = Dataset,
  Globe2 = Language,
  BookOpen = AboutData,
  Code2 = Query,
  Bookmark = Save,
  Layers = Workspace,
  RotateCcw = Reset,
  ArrowUpRight = Open,
  ArrowDownToLine = Download,
  Filter = NarrowView,
  Settings2 = Admin,
  SlidersHorizontal = Apply,
  CheckCircle2 = Confirmed,
  Table2 = TableView,
  FileText = Report,
  ShieldCheck = Verified,
  MessageSquare = Assistant,
  Network = NetworkGlyph,
  Activity = Trend;
