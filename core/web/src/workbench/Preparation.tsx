import { RotateCcw, ArrowRight, Download, CheckCircle2 } from "./BrandIcons";
import { Search, Upload } from "./BrandIcons";
import preparationArt from "./assets/data-preparation.jpeg";
import React, { useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "../api";
import { useLocale } from "./Locale";
import type { Dataset } from "./types";
const BASE = "/v1/dashboard/workbench";
const FIELDS: [string, string, string][] = [
  ["invoice", "Sipariş numarası", "Order number"],
  ["product_id", "Ürün kodu", "Product code"],
  ["product", "Ürün adı", "Product name"],
  ["quantity", "Miktar", "Quantity"],
  ["unit_price", "Birim fiyat · GBP", "Unit price · GBP"],
  ["order_date", "Tarih · YYYY-MM-DD", "Date · YYYY-MM-DD"],
  ["country", "Ülke", "Country"],
  ["customer_id", "Müşteri kodu · isteğe bağlı", "Customer code · optional"],
];
export type DataProfile = {
  version: string;
  source_sha256: string;
  delimiter: string;
  profile: {
    rows: number;
    duplicate_rows: number;
    columns: {
      name: string;
      type: string;
      missing: number;
      distinct: number;
      leading_zero: boolean;
    }[];
  };
  suggested_mapping: Record<string, string>;
  receipt?: string;
  preview?: {
    retained_rows: number;
    removed_duplicates: number;
    orders: number;
    gross_pence: number;
    quality: {
      excluded_rows: number;
      duplicate_rows: number;
      missing_customer: number;
    };
  };
};
export function Preparation({
  csrf,
  busy,
  activity,
  onImported,
}: {
  csrf: string | null;
  busy: boolean;
  activity: (n: number) => void;
  onImported: (d: Dataset) => void;
}) {
  const { t, locale } = useLocale();
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [profile, setProfile] = useState<DataProfile | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [trim, setTrim] = useState(true);
  const [dedup, setDedup] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const locked = busy || loading;
  const number = (n: number) =>
    n.toLocaleString(locale === "tr" ? "tr-TR" : "en-GB");
  function invalidate() {
    setProfile((p) =>
      p ? { ...p, preview: undefined, receipt: undefined } : null,
    );
    setError("");
  }
  async function inspect(preview: boolean) {
    if (locked) return;
    const current = ++generation.current;
    setLoading(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<DataProfile>(
        BASE + "/prepare",
        {
          csv: text,
          ...(preview
            ? { mapping, options: { trim, drop_duplicates: dedup } }
            : {}),
        },
        csrf,
      );
      if (current !== generation.current) return;
      if (r.ok) {
        setProfile(r.data);
        if (!preview) setMapping(r.data.suggested_mapping);
      } else {
        if (preview) invalidate();
        setError(r.error.detail);
      }
    } finally {
      setLoading(false);
      activity(-1);
    }
  }
  async function commit() {
    if (locked || !profile?.receipt) return;
    setLoading(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<Dataset>(
        BASE + "/import",
        {
          csv: text,
          title: name.replace(/\.csv$/i, "") || "Yüklenen CSV",
          mapping,
          options: { trim, drop_duplicates: dedup },
          receipt: profile.receipt,
        },
        csrf,
      );
      if (r.ok) onImported(r.data);
      else setError(r.error.detail);
    } finally {
      setLoading(false);
      activity(-1);
    }
  }
  return (
    <div className="wb-preparation">
      <ol
        className="wb-prep-steps"
        aria-label={t("Veri hazırlama adımları", "Preparation steps")}
      >
        {[
          t("Dosya", "File"),
          t("Eşleme", "Mapping"),
          t("Önizleme", "Preview"),
        ].map((s, i) => (
          <li
            key={s}
            aria-current={
              (profile?.preview ? 2 : profile ? 1 : 0) === i
                ? "step"
                : undefined
            }
          >
            <span>{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
      {!profile && (
        <div className="wb-feature-intro">
          <img src={preparationArt} alt="" width="116" height="116" />
          <div>
            <h3>
              {t(
                "Dağınık tablodan güvenilir analize",
                "From raw tables to reliable analysis",
              )}
            </h3>
            <p>
              {t(
                "Önce yapıyı görün, sonra alanları eşleyin. Sonucu onaylamadan önce kontrol edin.",
                "Inspect the structure, map the fields, and review the result before confirming.",
              )}
            </p>
          </div>
        </div>
      )}
      {profile && (
        <p>
          {t(
            "CSV dosyanızın yapısını inceleyin. Satış analizi için alanları eşleyip içe aktarmadan önce sonucu görün.",
            "Inspect any CSV schema. For sales analysis, map its fields and preview the result before importing.",
          )}
        </p>
      )}
      <div className="wb-prep-file">
        <label className="wb-upload">
          <Upload size={24} />
          <strong>{name || t("CSV dosyası seçin", "Choose a CSV file")}</strong>
          <span>
            {t(
              "UTF-8 · virgül, noktalı virgül veya sekme · 2 MB / 10.000 satır",
              "UTF-8 · comma, semicolon or tab · 2 MB / 10,000 rows",
            )}
          </span>
          <input
            type="file"
            accept=".csv,text/csv,text/tab-separated-values"
            disabled={locked}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              ++generation.current;
              setProfile(null);
              setMapping({});
              setError("");
              setText("");
              setName(file.name);
              if (file.size > 2_000_000) {
                setError(t("CSV sınırı 2 MB.", "CSV limit is 2 MB."));
                return;
              }
              const bytes = await file.arrayBuffer();
              try {
                setText(
                  new TextDecoder("utf-8", { fatal: true }).decode(bytes),
                );
              } catch {
                setError(
                  t(
                    "Dosyayı UTF-8 CSV olarak kaydedin.",
                    "Save the file as UTF-8 CSV.",
                  ),
                );
              }
            }}
          />
        </label>
        <a className="wb-btn" href={BASE + "/sample.csv"}>
          <Download size={15} />
          {t("Örnek CSV", "Sample CSV")}
        </a>
      </div>
      {!profile && (
        <button
          className="wb-btn wb-primary"
          disabled={!text || locked}
          onClick={() => void inspect(false)}
        >
          {loading ? (
            <Loader2 className="spin" size={16} />
          ) : (
            <Search size={16} />
          )}{" "}
          {t("Sütunları incele", "Inspect columns")}
        </button>
      )}
      {profile && (
        <>
          <div className="wb-prep-summary" role="status">
            <span>
              <b>{number(profile.profile.rows)}</b> {t("satır", "rows")}
            </span>
            <span>
              <b>{profile.profile.columns.length}</b> {t("sütun", "columns")}
            </span>
            <span>
              <b>{number(profile.profile.duplicate_rows)}</b>{" "}
              {t("yinelenen satır", "duplicate rows")}
            </span>
          </div>
          <details className="wb-prep-details">
            <summary>
              {t("Sütun kalitesini incele", "Inspect column quality")}
            </summary>
            <div className="wb-table-wrap">
              <table>
                <caption>
                  {t(
                    "Tür tahminleri kaynak değerleri değiştirmez.",
                    "Inferred types do not change source values.",
                  )}
                </caption>
                <thead>
                  <tr>
                    {[
                      t("Sütun", "Column"),
                      t("Tür", "Type"),
                      t("Boş", "Missing"),
                      t("Benzersiz", "Distinct"),
                    ].map((h) => (
                      <th key={h} scope="col">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {profile.profile.columns.map((c) => (
                    <tr key={c.name}>
                      <th scope="row">
                        {c.name}
                        {c.leading_zero && (
                          <small>
                            {" "}
                            ·{" "}
                            {t(
                              "baştaki sıfır korunur",
                              "leading zero preserved",
                            )}
                          </small>
                        )}
                      </th>
                      <td>
                        {
                          (
                            {
                              text: t("metin", "text"),
                              integer: t("tam sayı", "integer"),
                              number: t("sayı", "number"),
                              date: t("tarih", "date"),
                              empty: t("boş", "empty"),
                            } as Record<string, string>
                          )[c.type]
                        }
                      </td>
                      <td>{number(c.missing)}</td>
                      <td>{number(c.distinct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <h3>{t("Satış alanlarını eşleyin", "Map the sales fields")}</h3>
          <p className="wb-muted">
            {t(
              "Her satır bir fatura kalemi olmalı. Para birimi GBP; miktar ve fiyat ondalık nokta kullanır. Ülke ve tarih dönüşümü otomatik yapılmaz.",
              "Each row must represent one invoice line. Currency is GBP; quantity and price use a decimal dot. Country and date conversion is explicit.",
            )}
          </p>
          <div className="wb-prep-mapping">
            {FIELDS.map(([key, tr, en]) => (
              <label className="wb-field" key={key}>
                {t(tr, en)}
                <select
                  disabled={locked}
                  value={mapping[key] || ""}
                  onChange={(e) => {
                    setMapping({ ...mapping, [key]: e.target.value });
                    invalidate();
                  }}
                >
                  <option value="">
                    {key === "customer_id"
                      ? t("Kullanma", "Omit")
                      : t("Sütun seçin", "Choose column")}
                  </option>
                  {profile.profile.columns.map((c) => (
                    <option value={c.name} key={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <div className="wb-prep-options">
            <label>
              <input
                type="checkbox"
                checked={trim}
                disabled={locked}
                onChange={(e) => {
                  setTrim(e.target.checked);
                  invalidate();
                }}
              />
              {t("Baş/son boşlukları temizle", "Trim surrounding spaces")}
            </label>
            <label>
              <input
                type="checkbox"
                checked={dedup}
                disabled={locked}
                onChange={(e) => {
                  setDedup(e.target.checked);
                  invalidate();
                }}
              />
              {t("Tamamen aynı satırları çıkar", "Remove exact duplicate rows")}
            </label>
          </div>
          {profile.preview && (
            <div className="wb-prep-preview" role="status">
              <div>
                <CheckCircle2 size={20} />
                <h3>{t("İçe aktarılacak sonuç", "Import preview")}</h3>
              </div>
              <dl>
                <div>
                  <dt>{t("Geçerli satır", "Valid rows")}</dt>
                  <dd>{number(profile.preview.retained_rows)}</dd>
                </div>
                <div>
                  <dt>{t("Sipariş", "Orders")}</dt>
                  <dd>{number(profile.preview.orders)}</dd>
                </div>
                <div>
                  <dt>{t("Brüt satış", "Gross sales")}</dt>
                  <dd>
                    {(profile.preview.gross_pence / 100).toLocaleString(
                      locale === "tr" ? "tr-TR" : "en-GB",
                      { style: "currency", currency: "GBP" },
                    )}
                  </dd>
                </div>
              </dl>
              <p>
                {t("Kalite kurallarıyla dışlanan", "Excluded by quality rules")}
                : {number(profile.preview.quality.excluded_rows)} ·{" "}
                {t("Çıkarılan tekrar", "Duplicates removed")}:{" "}
                {number(profile.preview.removed_duplicates)} ·{" "}
                {t("Müşteri kodu eksik", "Missing customer code")}:{" "}
                {number(profile.preview.quality.missing_customer)}
              </p>
              <small>
                {t(
                  "İptal/iade hariç pozitif satış; net gelir değildir. Tekrarlar yalnız seçtiyseniz çıkarılır.",
                  "Positive sales excluding cancellations/returns; not net revenue. Duplicates are removed only if selected.",
                )}
              </small>
            </div>
          )}
          <div className="wb-prep-actions">
            <button
              className="wb-btn"
              disabled={locked}
              onClick={() => {
                setTrim(true);
                setDedup(false);
                setMapping(profile.suggested_mapping);
                invalidate();
              }}
            >
              <RotateCcw size={15} />
              {t("Taslağı sıfırla", "Reset draft")}
            </button>
            <button
              className="wb-btn wb-primary"
              disabled={
                locked || FIELDS.slice(0, -1).some(([k]) => !mapping[k])
              }
              onClick={() => void (profile.preview ? commit() : inspect(true))}
            >
              {loading ? (
                <Loader2 className="spin" size={16} />
              ) : (
                <ArrowRight size={16} />
              )}{" "}
              {profile.preview
                ? t("Onayla ve içe aktar", "Confirm and import")
                : t("Sonucu önizle", "Preview result")}
            </button>
          </div>
        </>
      )}
      {error && (
        <p className="wb-error-text" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
