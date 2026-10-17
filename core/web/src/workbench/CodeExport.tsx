/**
 * Developer code export (AW-16 §1): the current analysis as commented Python and SQL, or a reproducible bundle
 * (README, both scripts, a dependency-free chart writer, expected results, the filtered rows as Parquet and
 * pre-rendered figures). The server builds the files; this view previews them before anything is downloaded.
 * No raw HTML is injected anywhere: README Markdown and code are rendered as React elements.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useLocale } from "./Locale";
import type { ChartSpec, CodeExportResult, Filters } from "./types";
import { Download, Spinner, Confirmed, Query, Report, Info } from "./BrandIcons";

const BASE = "/v1/dashboard/workbench";
type Tab = "README.md" | "analysis.py" | "analysis.sql";

function saveBytes(name: string, base64: string, type: string) {
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function saveText(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function size(bytes: number, locale: string) {
  const f = new Intl.NumberFormat(locale === "tr" ? "tr-TR" : "en-GB", { maximumFractionDigits: 1 });
  return bytes >= 1048576 ? f.format(bytes / 1048576) + " MB" : bytes >= 1024 ? f.format(bytes / 1024) + " KB" : bytes + " B";
}

/* ---------- code view: line numbers, comments, strings and keywords ---------- */
// Keywords are matched as whole words with Unicode-aware edges, so "için" never lights up "in".
const PY_WORDS =
  "def|return|import|from|for|in|if|elif|else|with|as|class|while|try|except|raise|not|and|or|None|True|False|lambda|yield|pass|assert";
const SQL_WORDS =
  "SELECT|FROM|WHERE|GROUP|BY|ORDER|LIMIT|AND|OR|AS|ON|JOIN|LEFT|INNER|WITH|CREATE|REPLACE|TEMP|VIEW|SET|VARIABLE|COUNT|SUM|DISTINCT|DESC|ASC|CASE|WHEN|THEN|ELSE|END|IS|NULL|NOT|IN|HAVING|DATE|CAST|COPY|TO";
const keywordSplitter = (words: string) => new RegExp(`(?<![\\p{L}\\p{N}_])(${words})(?![\\p{L}\\p{N}_])`, "u");
const PY_KEYWORDS = keywordSplitter(PY_WORDS);
const SQL_KEYWORDS = keywordSplitter(SQL_WORDS);

function highlight(line: string, lang: "py" | "sql"): React.ReactNode[] {
  const commentAt = (() => {
    // A comment marker outside a string literal ends the code part of the line.
    let quote: string | null = null;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]!;
      if (quote) {
        if (ch === quote) quote = null;
      } else if (ch === "'" || ch === '"') quote = ch;
      else if (lang === "py" && ch === "#") return i;
      else if (lang === "sql" && ch === "-" && line[i + 1] === "-") return i;
    }
    return -1;
  })();
  const code = commentAt >= 0 ? line.slice(0, commentAt) : line;
  const out: React.ReactNode[] = [];
  const keywords = lang === "py" ? PY_KEYWORDS : SQL_KEYWORDS;
  const parts = code.split(/('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/);
  parts.forEach((part, i) => {
    if (i % 2 === 1) out.push(<span key={"s" + i} className="tk-string">{part}</span>);
    else
      part.split(keywords).forEach((w, j) =>
        out.push(j % 2 === 1 ? <span key={"k" + i + "-" + j} className="tk-keyword">{w}</span> : w),
      );
  });
  if (commentAt >= 0) out.push(<span key="c" className="tk-comment">{line.slice(commentAt)}</span>);
  return out;
}

/** Python docstrings span lines; they are documentation, so they read as comments, not as code. */
function docstringMask(lines: string[]): boolean[] {
  const mask: boolean[] = [];
  let open = false;
  for (const l of lines) {
    const quotes = (l.match(/"""|\'\'\'/g) || []).length;
    if (open) {
      mask.push(true);
      if (quotes % 2 === 1) open = false;
    } else if (quotes > 0) {
      mask.push(true);
      if (quotes % 2 === 1) open = true;
    } else mask.push(false);
  }
  return mask;
}

function CodeView({ text, lang, label }: { text: string; lang: "py" | "sql"; label: string }) {
  const lines = useMemo(() => text.replace(/\n$/, "").split("\n"), [text]);
  const doc = useMemo(() => (lang === "py" ? docstringMask(lines) : lines.map(() => false)), [lines, lang]);
  return (
    <pre className="wb-code" tabIndex={0} aria-label={label}>
      <code>
        {lines.map((l, i) => (
          <span key={i} className="wb-code-line">
            <span className="wb-code-no" aria-hidden="true">
              {i + 1}
            </span>
            <span className={doc[i] ? "tk-doc" : undefined}>{doc[i] ? l : highlight(l, lang)}</span>
          </span>
        ))}
      </code>
    </pre>
  );
}

/* ---------- README: a small, safe Markdown subset rendered as elements ---------- */
function inline(text: string, key: string): React.ReactNode[] {
  // `code`, **bold**, [label](url) and ![alt](src); everything else is text.
  const out: React.ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|!\[[^\]]*\]\([^)]+\)|\[[^\]]+\]\([^)]+\))/g;
  let last = 0,
    m: RegExpExecArray | null,
    n = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    const k = key + "-" + n++;
    if (tok.startsWith("`")) out.push(<code key={k}>{tok.slice(1, -1)}</code>);
    else if (tok.startsWith("**")) out.push(<strong key={k}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("!")) {
      const alt = /!\[([^\]]*)\]\(([^)]+)\)/.exec(tok)!;
      out.push(
        <span key={k} className="wb-md-figure">
          <Report size={16} />
          {alt[1] || alt[2]} · <code>{alt[2]}</code>
        </span>,
      );
    } else {
      const link = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok)!;
      out.push(
        <span key={k} className="wb-md-link" title={link[2]}>
          {link[1]}
        </span>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
function Markdown({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    const key = "b" + i;
    if (line.startsWith("```")) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i]!.startsWith("```")) body.push(lines[i++]!);
      i++;
      blocks.push(
        <pre key={key} className="wb-md-pre">
          {body.join("\n")}
        </pre>,
      );
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = Math.min(h[1]!.length + 2, 6);
      blocks.push(React.createElement("h" + level, { key, className: "wb-md-h" }, inline(h[2]!, key)));
      i++;
      continue;
    }
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i]!.startsWith("|")) {
        const cells = lines[i]!.split("|").slice(1, -1).map((c) => c.trim());
        if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
        i++;
      }
      const [head, ...body] = rows;
      blocks.push(
        <div key={key} className="wb-md-table">
          <table>
            {head && (
              <thead>
                <tr>{head.map((c, j) => <th key={j}>{inline(c, key + "h" + j)}</th>)}</tr>
              </thead>
            )}
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri}>{r.map((c, j) => <td key={j}>{inline(c, key + ri + "-" + j)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i]!)) items.push(lines[i++]!.replace(/^\s*([-*]|\d+\.)\s+/, ""));
      blocks.push(
        React.createElement(
          ordered ? "ol" : "ul",
          { key, className: "wb-md-list" },
          items.map((it, j) => <li key={j}>{inline(it, key + j)}</li>),
        ),
      );
      continue;
    }
    if (!line.trim()) {
      i++;
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i]!.trim() && !/^(#|```|\||\s*([-*]|\d+\.)\s)/.test(lines[i]!)) para.push(lines[i++]!);
    blocks.push(<p key={key}>{inline(para.join(" "), key)}</p>);
  }
  return <div className="wb-md">{blocks}</div>;
}

export function CodeExport({
  dataset,
  filters,
  chart,
  csrf,
}: {
  dataset: string;
  filters: Filters;
  chart?: ChartSpec | null;
  csrf: string | null;
}) {
  const { t, locale } = useLocale();
  const [result, setResult] = useState<CodeExportResult | null>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState<Tab>("README.md"),
    [copied, setCopied] = useState(false);
  useEffect(() => {
    let live = true;
    setResult(null);
    setError("");
    void api
      .post<CodeExportResult>(BASE + "/export/code", { dataset, filters, locale, format: "bundle", ...(chart ? { chart } : {}) }, csrf)
      .then((r) => {
        if (!live) return;
        if (r.ok) setResult(r.data);
        else setError(r.error.detail || t("Paket hazırlanamadı.", "The bundle could not be prepared."));
      });
    return () => {
      live = false;
    };
  }, [dataset, JSON.stringify(filters), JSON.stringify(chart), locale]);

  const text = result?.preview[tab] ?? "";
  const scope = [
    filters.country,
    filters.start || filters.end ? `${filters.start || "…"} – ${filters.end || "…"}` : null,
  ].filter(Boolean);

  return (
    <div className="wb-code-export">
      <p className="wb-code-intro">
        {t(
          "Bu analizi bir geliştiriciye teslim edin: yorumlu Python ve SQL, açıklamalı README, süzülmüş veri ve beklenen sonuçlar. Paket, sonuçları tek komutla yeniden üretip doğrular.",
          "Hand this analysis to a developer: commented Python and SQL, a documented README, the filtered data and the expected results. The bundle reproduces and verifies the numbers with one command.",
        )}
      </p>
      <div className="wb-code-scope">
        <span className="wb-badge blue">{dataset}</span>
        {scope.length ? scope.map((s) => <span key={String(s)} className="wb-badge">{s}</span>) : (
          <span className="wb-badge">{t("Tüm kapsam", "Full scope")}</span>
        )}
        {chart && <span className="wb-badge">{t("Grafik dahil", "Chart included")}</span>}
      </div>
      {error && (
        <p role="alert" className="wb-error-text">
          {error}
        </p>
      )}
      {!result && !error && (
        <p className="wb-code-loading" role="status">
          <Spinner size={16} />
          {t("Paket hazırlanıyor ve sonuçlar kaydediliyor…", "Preparing the bundle and recording the results…")}
        </p>
      )}
      {result && (
        <div className="wb-code-layout">
          <aside className="wb-code-files" aria-label={t("Paket içeriği", "Bundle contents")}>
            <h3>{t("Paket içeriği", "Bundle contents")}</h3>
            <ul>
              {result.files.map((f) => (
                <li key={f.path}>
                  <span title={`${f.path} · SHA-256 ${f.sha256}`}>{f.path}</span>
                  <small>{size(f.bytes, locale)}</small>
                </li>
              ))}
            </ul>
            <div className={"wb-code-data" + (result.data_included ? "" : " is-missing")}>
              {result.data_included ? <Confirmed size={16} /> : <Info size={16} />}
              <span>
                {result.data_included
                  ? t("Süzülmüş satırlar Parquet olarak dahil.", "Filtered rows included as Parquet.")
                  : t("Veri 6 MB'ı aştı; README'de --data ile nasıl verileceği anlatılıyor.", "Data exceeded 6 MB; the README explains --data.")}
              </span>
            </div>
            <h3>{t("Çalıştırma", "Run it")}</h3>
            <pre className="wb-code-cmd">{"pip install -r requirements.txt\npython analysis.py --check"}</pre>
            <p className="wb-code-hash">
              SHA-256 <code>{result.sha256.slice(0, 16)}…</code>
            </p>
          </aside>
          <section className="wb-code-preview">
            <div className="wb-code-toolbar">
              <div className="wb-tabs" role="tablist" aria-label={t("Dosya önizlemesi", "File preview")}>
                {(["README.md", "analysis.py", "analysis.sql"] as Tab[]).map((name) => (
                  <button
                    key={name}
                    role="tab"
                    aria-selected={tab === name}
                    className={tab === name ? "active" : ""}
                    onClick={() => {
                      setTab(name);
                      setCopied(false);
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
              <button
                className="wb-text-btn"
                onClick={() => {
                  void navigator.clipboard?.writeText(text).then(() => setCopied(true));
                }}
              >
                {copied ? <Confirmed size={16} /> : <Query size={16} />}
                {copied ? t("Kopyalandı", "Copied") : t("Kopyala", "Copy")}
              </button>
            </div>
            {tab === "README.md" ? (
              <div className="wb-code-readme" tabIndex={0} aria-label="README.md">
                <Markdown text={text} />
              </div>
            ) : (
              <CodeView text={text} lang={tab === "analysis.py" ? "py" : "sql"} label={tab} />
            )}
          </section>
        </div>
      )}
      <div className="wb-code-actions">
        <button
          className="wb-btn primary"
          disabled={!result}
          onClick={() => result && saveBytes(result.filename, result.base64, result.content_type)}
        >
          <Download size={16} />
          {t("Geliştirici paketini indir (.zip)", "Download developer bundle (.zip)")}
          {result && <small>{size(result.bytes, locale)}</small>}
        </button>
        <button
          className="wb-btn"
          disabled={!result?.preview["analysis.py"]}
          onClick={() => result && saveText(result.filename.replace(/\.zip$/, ".py"), result.preview["analysis.py"] ?? "", "text/x-python")}
        >
          <Download size={16} />
          Python (.py)
        </button>
        <button
          className="wb-btn"
          disabled={!result?.preview["analysis.sql"]}
          onClick={() => result && saveText(result.filename.replace(/\.zip$/, ".sql"), result.preview["analysis.sql"] ?? "", "application/sql")}
        >
          <Download size={16} />
          SQL (.sql)
        </button>
      </div>
    </div>
  );
}
