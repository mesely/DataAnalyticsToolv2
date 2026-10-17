// Edge encoding for the relationship network (v3 G1). Strength is shown three ways at once — width, opacity and a
// three-step colour class — so the strongest links stand out without relying on colour alone. A square-root scale keeps
// one dominant pair (e.g. postage on most invoices) from flattening every other link to the minimum width.

export type NetEdge = { source: string; target: string; weight: number };
export type EdgeTier = "weak" | "mid" | "strong";
export type EdgeStyle = { width: number; opacity: number; tier: EdgeTier; negative: boolean; share: number };

export const EDGE_LIMITS = [20, 40, 80, 0] as const; // 0 = every computed link
export const DEFAULT_EDGE_LIMIT = 40;
const MIN_WIDTH = 1.2,
  MAX_WIDTH = 6;

const byStrength = (a: NetEdge, b: NetEdge) =>
  Math.abs(b.weight) - Math.abs(a.weight) || a.source.localeCompare(b.source) || a.target.localeCompare(b.target);

/** The `limit` strongest links by absolute weight (ties broken by id, so the cut is deterministic); 0 keeps all. */
export function strongest<E extends NetEdge>(edges: E[], limit: number): E[] {
  const sorted = [...edges].sort(byStrength);
  return limit > 0 ? sorted.slice(0, limit) : sorted;
}

export type EdgeScale = {
  style: (weight: number) => EdgeStyle;
  /** Weight bounds of each tier, in the edge's own unit, for the legend (strongest last). */
  legend: { tier: EdgeTier; from: number; to: number }[];
};

const OPACITY: Record<EdgeTier, number> = { weak: 0.5, mid: 0.75, strong: 0.95 };

/**
 * Width follows the weight itself (square-root scale between the visible minimum and maximum); the tone and opacity
 * follow rank, a third of the visible links per tier. Rank tiers keep the three tones in use even when one pair
 * dominates the weights — with weight-based tiers almost every link fell into "weak".
 */
export function edgeScale(edges: NetEdge[]): EdgeScale {
  const magnitudes = edges.map((e) => Math.abs(e.weight)).sort((a, b) => a - b);
  const n = magnitudes.length,
    lo = n ? magnitudes[0]! : 0,
    hi = n ? magnitudes[n - 1]! : 0;
  const rlo = Math.sqrt(lo),
    rhi = Math.sqrt(hi);
  const share = (m: number) => (rhi > rlo ? (Math.sqrt(m) - rlo) / (rhi - rlo) : 1);
  // Lower bounds of the mid and strong tiers: the weights at the 1/3 and 2/3 rank positions.
  const midFrom = n >= 3 ? magnitudes[Math.floor(n / 3)]! : hi,
    strongFrom = n >= 3 ? magnitudes[Math.floor((2 * n) / 3)]! : hi;
  // Largest visible weight under a bound, so tied weights never appear in two legend ranges.
  const below = (bound: number) => {
    const under = magnitudes.filter((m) => m < bound);
    return under.length ? under[under.length - 1]! : -1;
  };
  const tierOf = (m: number): EdgeTier => (m >= strongFrom ? "strong" : m >= midFrom ? "mid" : "weak");
  const legend: EdgeScale["legend"] = !n
    ? []
    : n < 3 || lo === hi
      ? [{ tier: "strong", from: lo, to: hi }]
      : (
          [
            { tier: "weak", from: lo, to: below(midFrom) },
            { tier: "mid", from: midFrom, to: below(strongFrom) },
            { tier: "strong", from: strongFrom, to: hi },
          ] as EdgeScale["legend"]
        ).filter((l) => l.from <= l.to && (l.tier === "strong" || l.from < strongFrom));
  return {
    legend,
    style: (weight) => {
      const m = Math.abs(weight),
        s = Math.max(0, Math.min(1, share(m))),
        tier = tierOf(m);
      return {
        share: s,
        width: +(MIN_WIDTH + s * (MAX_WIDTH - MIN_WIDTH)).toFixed(2),
        opacity: OPACITY[tier],
        tier,
        negative: weight < 0,
      };
    },
  };
}

/** Neighbours of a node among the given edges (the node itself included), for hover/selection focus. */
export function neighbourhood(edges: NetEdge[], id: string | null): Set<string> | null {
  if (!id) return null;
  const out = new Set([id]);
  for (const e of edges) {
    if (e.source === id) out.add(e.target);
    if (e.target === id) out.add(e.source);
  }
  return out;
}
