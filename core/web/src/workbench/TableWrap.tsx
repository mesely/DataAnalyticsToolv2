import React, { useEffect, useRef, useState } from "react";

/**
 * Horizontally scrollable table container. While its table is wider than the container it becomes a
 * keyboard-focusable, labelled region (WCAG 2.1.1: arrow keys scroll a focused scroll container),
 * so it adds no tab stop on screens where the table already fits. The label is the given text or
 * the table's own caption.
 */
export function TableWrap({
  children,
  className,
  label,
}: {
  children: React.ReactNode;
  className?: string;
  label?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [scrolls, setScrolls] = useState(false);
  const [caption, setCaption] = useState("");
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => {
      setScrolls(el.scrollWidth > el.clientWidth + 1);
      setCaption(el.querySelector("caption")?.textContent?.trim() ?? "");
    };
    check();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(check);
    observer.observe(el);
    const table = el.querySelector("table");
    if (table) observer.observe(table);
    return () => observer.disconnect();
  });
  const name = label || caption;
  return (
    <div
      ref={ref}
      className={"wb-table-wrap" + (className ? " " + className : "")}
      {...(scrolls
        ? { tabIndex: 0, role: "region", ...(name ? { "aria-label": name } : {}) }
        : {})}
    >
      {children}
    </div>
  );
}
