import { describe, expect, it } from "vitest";
import { buildReasoning } from "../web/src/workbench/Reasoning.js";

// The reasoning tree links statements only through shared evidence ids; these cases pin that rule.
const S = (type: string, evidence: string[], text = type) => ({ type, text, evidence });

describe("reasoning tree", () => {
  it("numbers statements per type and chains fact → calculation → inference → recommendation", () => {
    const { nodes, roots, global } = buildReasoning(
      [
        S("fact", ["gross"]),
        S("fact", ["excluded"]),
        S("calculation", ["share", "gross"]),
        S("inference", ["share"]),
        S("recommendation", ["share"]),
        S("limitation", ["share"]),
        S("limitation", []),
      ],
      false,
    );
    expect(nodes.map((n) => n.id)).toEqual(["O1", "O2", "H1", "Ç1", "Ö1", "S1", "S2"]);
    expect(roots).toEqual([0, 1]);
    expect(nodes[2]!.parents).toEqual([0]);
    expect(nodes[3]!.parents).toEqual([2]);
    // The recommendation rests on the nearest lower layer that shares evidence: the inference, not the calculation.
    expect(nodes[4]!.parents).toEqual([3]);
    // A limitation hangs under the deepest statement it qualifies; one with no shared evidence is global.
    expect(nodes[4]!.limits).toEqual([5]);
    expect(global).toEqual([6]);
  });

  it("lists every parent of the nearest layer and uses English prefixes", () => {
    const { nodes } = buildReasoning([S("fact", ["a"]), S("assumption", ["b"]), S("calculation", ["a", "b"])], true);
    expect(nodes.map((n) => n.id)).toEqual(["F1", "A1", "C1"]);
    expect(nodes[2]!.parents).toEqual([0, 1]);
    expect(nodes[0]!.children).toEqual([2]);
  });

  it("keeps statements without evidence as roots instead of guessing a link", () => {
    const { roots, nodes } = buildReasoning([S("fact", []), S("calculation", []), S("inference", [])], false);
    expect(roots).toEqual([0, 1, 2]);
    expect(nodes.every((n) => n.parents.length === 0)).toBe(true);
  });
});
