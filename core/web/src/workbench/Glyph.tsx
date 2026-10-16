import React from "react";
import { GLYPHS } from "./glyphs.generated";

/**
 * Context Layer glyph: one icon of the original Gemini-generated family (assets/glyphs, tools/design/glyphs.py).
 * Strokes use currentColor; the single index dot uses --glyph-dot (brass), the brand's "index sphere".
 * Decorative by default (aria-hidden): every control that shows a glyph also carries a text label or
 * aria-label. Rendered with React.createElement from validated element lists — never raw markup.
 */
export function Glyph({
  name,
  size = 20,
  className = "",
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  const elements = GLYPHS[name];
  if (!elements) return null;
  return (
    <svg
      className={"wb-glyph " + className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {elements.map(([tag, attrs], i) => React.createElement(tag, { key: i, ...attrs }))}
    </svg>
  );
}

/** A named glyph as a component with the size/className signature the screens already use. */
export function glyph(name: string) {
  return function NamedGlyph({ size = 20, className = "" }: { size?: number; className?: string }) {
    return <Glyph name={name} size={size} className={className} />;
  };
}
