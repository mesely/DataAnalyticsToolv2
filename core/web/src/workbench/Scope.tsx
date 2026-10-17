import React from "react";
import { TableWrap } from "./TableWrap";
import { useLocale } from "./Locale";
import type { ScopeInfo } from "./types";

// v3 G5: every line the numbers leave out, with its count, its value and the reason. Rules that follow from the
// metric's definition (a cancellation is not a sale) are explained, not switchable; a choice that is a legitimate
// analytical option (whether postage and fees count as products) has a switch, and the screen says which is in use.

const REASONS: Record<string, { tr: [string, string]; en: [string, string] }> = {
  cancelled: {
    tr: ["İptal edilen fatura (C ile başlar)", "İptal satış değildir; brüt satış tanımı gereği dışarıda. Net satış için ayrıca düşülmesi gerekir."],
    en: ["Cancelled invoice (starts with C)", "A cancellation is not a sale; gross sales leaves it out by definition. Net sales would subtract it separately."],
  },
  invalid_number: {
    tr: ["Sayı olmayan veya kesirli miktar/fiyat", "Hesaplanamayan satır; tutar uydurulmaz."],
    en: ["Non-numeric or fractional quantity/price", "The line cannot be valued; no amount is invented."],
  },
  nonpositive_quantity: {
    tr: ["Sıfır veya negatif miktar (iptal dışı)", "Stok, hasar ve düzeltme kayıtları; satış değildir."],
    en: ["Zero or negative quantity (not a cancellation)", "Stock, damage and correction records; not sales."],
  },
  nonpositive_price: {
    tr: ["Sıfır veya negatif fiyat", "Bedelsiz kalemler ve muhasebe düzeltmeleri (ör. kötü borç düzeltmesi)."],
    en: ["Zero or negative price", "Free-of-charge lines and accounting adjustments (e.g. bad-debt adjustment)."],
  },
  missing_field: {
    tr: ["Tarih, fatura veya ürün bilgisi eksik", "Hangi döneme veya ürüne ait olduğu bilinemez."],
    en: ["Missing date, invoice or product", "The line cannot be placed in a period or product."],
  },
};

export function ScopeView({
  scope,
  money,
  num,
  busy,
  onIncludeService,
}: {
  scope: ScopeInfo;
  money: (n: number) => string;
  num: (n: number) => string;
  busy: boolean;
  onIncludeService: (include: boolean) => void;
}) {
  const { t, locale } = useLocale();
  const reasons = (scope.exclusions || []).filter((e) => e.rows > 0);
  const partial = scope.periods.filter((p) => p.partial);
  const adjustment = scope.service.groups.find((g) => g.kind === "adjustment");
  return (
    <div className="wb-scope-panel">
      <section>
        <h3>{t("1 · Brüt satışa hiç girmeyen satırlar", "1 · Lines gross sales never counts")}</h3>
        <p className="wb-small">
          {t(
            "Bu kurallar metriğin tanımıdır; açılıp kapatılmaz. Sayılar veri setinin tamamı içindir.",
            "These rules define the metric and cannot be switched off. Counts cover the whole dataset.",
          )}
        </p>
        {reasons.length ? (
          <TableWrap>
            <table>
              <thead>
                <tr>
                  <th>{t("Neden", "Reason")}</th>
                  <th>{t("Satır", "Lines")}</th>
                  <th>{t("Satır tutarı", "Line value")}</th>
                  <th>{t("Neden doğru?", "Why it is right")}</th>
                </tr>
              </thead>
              <tbody>
                {reasons.map((e) => {
                  const r = REASONS[e.reason];
                  const [label, why] = r ? (locale === "en" ? r.en : r.tr) : [e.reason, ""];
                  return (
                    <tr key={e.reason}>
                      <td>{label}</td>
                      <td>{num(e.rows)}</td>
                      <td>{money(e.pence / 100)}</td>
                      <td>{why}</td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td>{t("Toplam dışlanan", "Total excluded")}</td>
                  <td>{num(reasons.reduce((a, e) => a + e.rows, 0))}</td>
                  <td colSpan={2}>
                    {scope.raw_rows ? t(`${num(scope.raw_rows)} ham satırdan`, `of ${num(scope.raw_rows)} raw lines`) : ""}
                  </td>
                </tr>
              </tfoot>
            </table>
          </TableWrap>
        ) : (
          <p>
            {scope.excluded_rows != null
              ? t(
                  `${num(scope.excluded_rows)} satır dışlandı. Bu veri seti hazırlanırken neden bazında döküm kaydedilmedi; yeniden içe aktarıldığında görünür.`,
                  `${num(scope.excluded_rows)} lines were excluded. This dataset was prepared before the per-reason breakdown was recorded; it appears after a re-import.`,
                )
              : t("Dışlanan satır bilgisi yok.", "No exclusion record.")}
          </p>
        )}
      </section>

      <section>
        <h3>{t("2 · Toplamda kalan ama ürün sayılmayan kalemler", "2 · Lines in the total that are not products")}</h3>
        <p className="wb-small">
          {t(
            "Kargo, posta, elle girilmiş kalem, ücret ve muhasebe düzeltmeleri faturada ayrı stok koduyla durur. Brüt satış toplamı bunları içerir; ürün sıralaması, ilişki ağı ve zaman içindeki değişim varsayılan olarak içermez. Yoksa “en çok satan ürün” sorusunun cevabı bir kargo kalemi olur.",
            "Postage, carriage, manual entries, fees and accounting adjustments sit on invoices under their own stock codes. The gross-sales total includes them; the product ranking, the relationship network and change over time leave them out by default — otherwise the best-selling product would be a postage line.",
          )}
        </p>
        {scope.service.lines ? (
          <>
            <TableWrap>
              <table>
                <thead>
                  <tr>
                    <th>{t("Tür", "Kind")}</th>
                    <th>{t("Stok kodları", "Stock codes")}</th>
                    <th>{t("Satır", "Lines")}</th>
                    <th>{t("Brüt satıştaki tutar", "Amount in gross sales")}</th>
                  </tr>
                </thead>
                <tbody>
                  {scope.service.groups.map((g) => (
                    <tr key={g.kind}>
                      <td>{g.label}</td>
                      <td>{g.codes.map((c) => `${c.code} (${c.label})`).join(", ")}</td>
                      <td>{num(g.lines)}</td>
                      <td>{money(g.pence / 100)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={2}>{t("Bu görünümde toplam", "Total in this view")}</td>
                    <td>{num(scope.service.lines)}</td>
                    <td>{money(scope.service.pence / 100)}</td>
                  </tr>
                </tfoot>
              </table>
            </TableWrap>
            {adjustment && (
              <p className="wb-callout wb-scope-flag">
                {t(
                  `Dikkat: brüt satış toplamı ${money(adjustment.pence / 100)} tutarında muhasebe düzeltmesi içeriyor (ör. “Adjust bad debt”). Bu bir satış değildir; tanım (retail-v1) değişene kadar toplamda kalır ve burada açıkça gösterilir.`,
                  `Note: the gross-sales total contains ${money(adjustment.pence / 100)} of accounting adjustments (e.g. “Adjust bad debt”). That is not a sale; it stays in the total until the definition (retail-v1) changes, and is shown here openly.`,
                )}
              </p>
            )}
            <label className="wb-check wb-scope-toggle">
              <input
                type="checkbox"
                checked={scope.include_service}
                disabled={busy}
                onChange={(e) => onIncludeService(e.target.checked)}
              />
              {t(
                "Bu kalemleri ürün analizlerine dahil et (sıralama, ilişki ağı, zaman içindeki değişim)",
                "Count these lines as products (ranking, relationship network, change over time)",
              )}
            </label>
          </>
        ) : (
          <p>{t("Bu görünümde böyle bir kalem yok.", "There are no such lines in this view.")}</p>
        )}
      </section>

      <section>
        <h3>{t("3 · Kısmi dönemler", "3 · Partial periods")}</h3>
        {scope.periods.length ? (
          <ul className="wb-scope-periods">
            {scope.periods.map((p) => (
              <li key={p.edge}>
                <b>{p.month}</b>:{" "}
                {t(`${p.month_days} günün ${p.covered_days} günü kapsamda`, `${p.covered_days} of ${p.month_days} days in scope`)}
                {p.partial ? t(" — kısmi", " — partial") : t(" — tam", " — complete")}
              </li>
            ))}
          </ul>
        ) : null}
        <p className="wb-small">
          {partial.length
            ? t(
                "Kısmi ay grafikte içi boş nokta veya soluk çubukla gösterilir; trend, ortalama ve hareketli ortalamaya katılmaz. Birkaç günlük bir ay tam aylarla aynı çizgiye konursa satış çöküşü gibi görünür; bu yüzden dışarıda tutmak doğrudur. Sayısı Veri sekmesinde her zaman görünür.",
                "A partial month is drawn as a hollow point or faded bar and is left out of trends, averages and moving averages. A month of a few days on the same line as full months looks like a collapse in sales, so leaving it out is the right call. Its value is always in the Data tab.",
              )
            : t("Bu görünümde kısmi ay yok; hesaplara her ay katılır.", "No partial month in this view; every month takes part in the calculations.")}
        </p>
      </section>
    </div>
  );
}
