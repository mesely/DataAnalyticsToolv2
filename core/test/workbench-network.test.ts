import { describe, expect, it } from "vitest";
import { edgeScale, neighbourhood, strongest } from "../web/src/workbench/network.js";

// v3 G1: link strength must read from width, opacity and tone together; these cases pin the encoding.
const E = (source: string, target: string, weight: number) => ({ source, target, weight });

describe("network edge encoding", () => {
  const edges = [E("a", "b", 825), E("a", "c", 400), E("b", "c", 330), E("c", "d", 300), E("d", "e", 260), E("e", "f", 229)];

  it("keeps the strongest links, deterministically", () => {
    expect(strongest(edges, 3).map((e) => e.weight)).toEqual([825, 400, 330]);
    expect(strongest(edges, 0)).toHaveLength(6);
    // Equal weights are ordered by id, so the cut never depends on input order.
    const tied = [E("z", "y", 5), E("a", "b", 5), E("m", "n", 5)];
    expect(strongest(tied, 2).map((e) => e.source)).toEqual(["a", "m"]);
    expect(strongest([...tied].reverse(), 2).map((e) => e.source)).toEqual(["a", "m"]);
  });

  it("scales width with the weight and tiers tone by rank", () => {
    const scale = edgeScale(edges);
    const top = scale.style(825),
      bottom = scale.style(229);
    expect(top.width).toBe(6);
    expect(bottom.width).toBe(1.2);
    expect(top.tier).toBe("strong");
    expect(bottom.tier).toBe("weak");
    expect(top.opacity).toBeGreaterThan(bottom.opacity);
    // A third of the links per tier, even though one weight dominates.
    const tiers = edges.map((e) => scale.style(e.weight).tier);
    expect(tiers.filter((t) => t === "strong")).toHaveLength(2);
    expect(tiers.filter((t) => t === "mid")).toHaveLength(2);
    expect(tiers.filter((t) => t === "weak")).toHaveLength(2);
  });

  it("gives the legend non-overlapping ranges that cover every visible weight", () => {
    const { legend, style } = edgeScale(edges);
    expect(legend.map((l) => l.tier)).toEqual(["weak", "mid", "strong"]);
    for (let i = 1; i < legend.length; i++) expect(legend[i]!.from).toBeGreaterThan(legend[i - 1]!.to);
    for (const e of edges) {
      const l = legend.find((x) => x.from <= e.weight && e.weight <= x.to);
      expect(l?.tier).toBe(style(e.weight).tier);
    }
  });

  it("handles ties, a single weight and negative similarity", () => {
    expect(edgeScale([]).legend).toEqual([]);
    const flat = edgeScale([E("a", "b", 3), E("b", "c", 3), E("c", "d", 3)]);
    expect(flat.legend).toEqual([{ tier: "strong", from: 3, to: 3 }]);
    expect(flat.style(3).width).toBe(6);
    const signed = edgeScale([E("a", "b", 0.8), E("b", "c", -0.4), E("c", "d", 0.2)]);
    expect(signed.style(-0.4).negative).toBe(true);
    expect(signed.style(-0.4).width).toBeGreaterThan(signed.style(0.2).width);
  });

  it("finds a node's neighbourhood among the visible links", () => {
    expect(neighbourhood(edges, null)).toBeNull();
    expect([...neighbourhood(edges, "c")!].sort()).toEqual(["a", "b", "c", "d"]);
  });
});
