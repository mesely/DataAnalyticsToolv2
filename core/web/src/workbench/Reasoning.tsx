/**
 * Reasoning tree: typed statements (fact, assumption, calculation, inference, recommendation, limitation) shown as
 * the chain they form. A statement rests on the earlier statements of the nearest lower layer that cite the same
 * evidence; facts and assumptions are the roots. Limitations hang under the deepest statement they qualify, or in a
 * closing group when they qualify the whole result. Every statement is numbered per type (O1, H2 … / F1, C2 …) so
 * the "rests on" references are short and exact.
 *
 * The links are derived only from shared evidence ids, so the same component reads the local narrative, a validated
 * model narrative and Chart Studio commentary without any model judgement about relationships.
 */
import React, { useMemo, useState } from "react";
import { useLocale } from "./Locale";

export interface ReasonStatement {
  type: string;
  text: string;
  evidence?: string[];
}

const RANK: Record<string, number> = { fact: 0, assumption: 0, calculation: 1, inference: 2, recommendation: 3 };
const PREFIX: Record<string, [string, string]> = {
  fact: ["O", "F"],
  assumption: ["V", "A"],
  calculation: ["H", "C"],
  inference: ["Ç", "I"],
  recommendation: ["Ö", "R"],
  limitation: ["S", "L"],
};
const LABEL: Record<string, [string, string]> = {
  fact: ["Olgu", "Fact"],
  assumption: ["Varsayım", "Assumption"],
  calculation: ["Hesap", "Calculation"],
  inference: ["Çıkarım", "Inference"],
  recommendation: ["Öneri", "Recommendation"],
  limitation: ["Sınır", "Limitation"],
};

interface Node {
  index: number;
  id: string;
  s: ReasonStatement;
  parents: number[];
  children: number[];
  limits: number[];
}

export function buildReasoning(statements: ReasonStatement[], en: boolean) {
  const counters: Record<string, number> = {};
  const nodes: Node[] = statements.map((s, index) => {
    const p = PREFIX[s.type] ?? ["•", "•"];
    counters[s.type] = (counters[s.type] ?? 0) + 1;
    return { index, id: (en ? p[1] : p[0]) + counters[s.type], s, parents: [], children: [], limits: [] };
  });
  const shares = (a: Node, b: Node) => (a.s.evidence ?? []).some((e) => (b.s.evidence ?? []).includes(e));
  const ranked = nodes.filter((n) => n.s.type in RANK);
  for (const n of ranked) {
    const r = RANK[n.s.type]!;
    if (r === 0) continue;
    const below = ranked.filter((m) => RANK[m.s.type]! < r && shares(m, n));
    if (!below.length) continue;
    const nearest = Math.max(...below.map((m) => RANK[m.s.type]!));
    n.parents = below.filter((m) => RANK[m.s.type] === nearest).map((m) => m.index);
    nodes[n.parents[0]!]!.children.push(n.index);
  }
  const global: number[] = [];
  for (const n of nodes.filter((x) => x.s.type === "limitation")) {
    const owners = ranked.filter((m) => shares(m, n));
    if (!owners.length) {
      global.push(n.index);
      continue;
    }
    const deepest = owners.reduce((a, b) => (RANK[b.s.type]! >= RANK[a.s.type]! ? b : a));
    deepest.limits.push(n.index);
    n.parents = [deepest.index];
  }
  const roots = ranked.filter((n) => n.parents.length === 0).map((n) => n.index);
  return { nodes, roots, global };
}

export function ReasoningTree({
  statements,
  renderEvidence,
  label,
}: {
  statements: ReasonStatement[];
  renderEvidence?: (s: ReasonStatement) => React.ReactNode;
  label: string;
}) {
  const { t, locale } = useLocale();
  const en = locale === "en";
  const { nodes, roots, global } = useMemo(() => buildReasoning(statements, en), [statements, en]);
  const [focus, setFocus] = useState<number | null>(null);
  // Hovering a statement highlights its chain: what it rests on and what rests on it.
  const related = useMemo(() => {
    if (focus == null) return null;
    const set = new Set<number>([focus]);
    const up = (i: number) => nodes[i]!.parents.forEach((p) => (set.has(p) ? null : (set.add(p), up(p))));
    const down = (i: number) =>
      [...nodes[i]!.children, ...nodes[i]!.limits].forEach((c) => (set.has(c) ? null : (set.add(c), down(c))));
    up(focus);
    down(focus);
    return set;
  }, [focus, nodes]);

  const typeLabel = (type: string) => {
    const l = LABEL[type];
    return l ? (en ? l[1] : l[0]) : type;
  };

  const renderNode = (i: number, depth: number): React.ReactNode => {
    const n = nodes[i]!;
    const extra = n.parents.slice(1).map((p) => nodes[p]!.id);
    const dim = related != null && !related.has(i);
    return (
      <li
        key={i}
        className={"wb-reason" + (dim ? " is-dim" : "") + (related?.has(i) && focus === i ? " is-focus" : "")}
        data-type={n.s.type}
        onMouseEnter={() => setFocus(i)}
        onMouseLeave={() => setFocus(null)}
      >
        <div className="wb-reason-row">
          <span className="wb-reason-id" aria-label={`${typeLabel(n.s.type)} ${n.id}`}>
            {n.id}
          </span>
          <div className="wb-reason-body">
            <span className="wb-reason-type">{typeLabel(n.s.type)}</span>
            <p>{n.s.text}</p>
            {extra.length > 0 && (
              <span className="wb-reason-basis">
                {t("Ayrıca dayanır:", "Also rests on:")} {extra.join(", ")}
              </span>
            )}
            {renderEvidence?.(n.s)}
          </div>
        </div>
        {n.limits.length > 0 && (
          <ul className="wb-reason-limits" aria-label={t("Bu adımın sınırları", "Limits of this step")}>
            {n.limits.map((l) => (
              <li
                key={l}
                className={"wb-reason-limit" + (related != null && !related.has(l) ? " is-dim" : "")}
                onMouseEnter={() => setFocus(l)}
                onMouseLeave={() => setFocus(null)}
              >
                <span className="wb-reason-id is-limit">{nodes[l]!.id}</span>
                <p>{nodes[l]!.s.text}</p>
              </li>
            ))}
          </ul>
        )}
        {n.children.length > 0 && <ol className="wb-reason-children">{n.children.map((c) => renderNode(c, depth + 1))}</ol>}
      </li>
    );
  };

  return (
    <div className="wb-reasoning" aria-label={label}>
      <ol className="wb-reason-roots">{roots.map((r) => renderNode(r, 0))}</ol>
      {global.length > 0 && (
        <section className="wb-reason-global" aria-label={t("Tüm sonuç için sınırlar", "Limits of the whole result")}>
          <h4>{t("Tüm sonuç için sınırlar", "Limits of the whole result")}</h4>
          <ul>
            {global.map((l) => (
              <li key={l} className="wb-reason-limit">
                <span className="wb-reason-id is-limit">{nodes[l]!.id}</span>
                <p>{nodes[l]!.s.text}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
