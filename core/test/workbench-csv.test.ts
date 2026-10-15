import { describe, it, expect } from "vitest";
import { csvCell } from "../web/src/workbench/csv.js";
describe("download preview CSV spreadsheet boundary", () => {
  it("blocks formulas after whitespace or BOM while preserving numeric cells", () => {
    for (const input of [
      "=1+1",
      " +SUM(1,2)",
      "\t@evil",
      "\ufeff=1+1",
      " \ufeff -1+2",
    ])
      expect(csvCell(input).startsWith("\"'")).toBe(true);
    expect(csvCell(-2.5)).toBe('"-2.5"');
    expect(csvCell(0)).toBe('"0"');
  });
  it("quotes separators, embedded quotes and multiline text without extra records", () => {
    expect(csvCell('a,"b"\nc')).toBe('"a,""b""\nc"');
    expect(csvCell(null)).toBe('""');
    expect(csvCell("safe\x00 text")).toBe('"safe text"');
  });
});
