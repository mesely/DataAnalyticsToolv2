/** Spreadsheet-safe CSV cell: preserve numeric values, quote text and prevent formulas. */
export function csvCell(value: unknown): string {
  let text = String(value ?? "")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "")
    .slice(0, 32000);
  if (
    typeof value !== "number" &&
    (/^[=+\-@]/.test(text.trimStart()) || /^[\t\r\n]/.test(text))
  )
    text = "'" + text;
  return '"' + text.replace(/"/g, '""') + '"';
}
