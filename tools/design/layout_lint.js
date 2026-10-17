/* Layout lint — run in the page. Finds the defects a screenshot review catches by eye, as DOM facts:
 *   overflow   text or controls that leave their card / dialog / control box
 *   clipped    boxes that hide content (overflow hidden/clip with scrollWidth > clientWidth), excluding
 *              deliberate scroll regions and ellipsis truncation that carries a title
 *   glyph_misaligned  icon + label pairs whose vertical centres differ by more than 2px
 *   images     broken, distorted (aspect drift > 2% without object-fit) or upscaled beyond 1.05x
 *   near_miss  inside one card or dialog section, direct children whose content starts 2-8px apart (1px is a hairline border) (an
 *              intentional indent is larger; a near miss is a misaligned edge)
 *   narrow_control  a select or text input too narrow for its current value or placeholder
 *   page_overflow  horizontal page scroll
 * Returns counts plus up to 12 samples per finding; heuristic, not a substitute for looking at the page. */
(() => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && +cs.opacity !== 0 &&
      !el.closest("dialog:not([open])") && !(el.closest("details:not([open])") && !el.closest("summary")) &&
      !el.closest(".sr-only, .wb-sr-only, .visually-hidden");
  };
  const name = (el) => `${el.tagName.toLowerCase()}${el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : ""} "${(el.getAttribute("aria-label") || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 32)}"`;
  const CONTAINER = ".wb-kpi, .wb-panel, .wb-card, .wb-scope, .wb-dialog, dialog, .wb-sidebar, .wb-topbar, button, select, input, .wb-badge, .wb-chip, summary";
  const root = document.querySelector(".wb") || document.body;
  const all = [...root.querySelectorAll("*")].filter(vis);
  const out = { overflow: [], clipped: [], glyph_misaligned: [], images: [], near_miss: [], narrow_control: [], page_overflow: document.documentElement.scrollWidth - innerWidth };

  for (const el of all) {
    // A leaf with text, or a control, must stay inside its nearest container (1px tolerance for borders).
    const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (hasText || el.matches("button, select, input, svg.wb-glyph")) {
      const box = el.parentElement && el.parentElement.closest(CONTAINER);
      if (box && !box.matches("svg *")) {
        const a = el.getBoundingClientRect(), b = box.getBoundingClientRect();
        // Content of a scroll region may extend; only report when the region does not scroll.
        const scroller = el.closest("[style*=overflow], .wb-table-wrap, [role=region], .wb-network-canvas");
        if (!scroller || !box.contains(scroller)) {
          // Measure the ink, not the block: a block-level label is as wide as its card even when its text is not.
          let ink = a;
          if (hasText && !el.matches("button, select, input, textarea")) { const range = document.createRange(); range.selectNodeContents(el); ink = range.getBoundingClientRect(); }
          const pad = box.matches(".wb-kpi, .wb-panel, .wb-card, .wb-dialog, dialog") ? parseFloat(getComputedStyle(box).paddingRight) / 2 : 0;
          if (ink.right > b.right - pad + 1 || ink.left < b.left - 1) out.overflow.push(`${name(el)} ${Math.round(ink.right - (b.right - pad))}px past ${name(box)}`);
        }
      }
      if (hasText) {
        const range = document.createRange(); range.selectNodeContents(el);
        const t = range.getBoundingClientRect(), r = el.getBoundingClientRect(), cs = getComputedStyle(el);
        if (t.width > r.width + 1 && cs.overflowX !== "visible" && cs.textOverflow !== "ellipsis") out.clipped.push(`${name(el)} text ${Math.round(t.width)} > box ${Math.round(r.width)}`);
        if (cs.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 1 && !el.title && !el.closest("[title]")) out.clipped.push(`${name(el)} truncated with no title`);
      }
    }
    const cs = getComputedStyle(el);
    if (/hidden|clip/.test(cs.overflowX) && el.scrollWidth > el.clientWidth + 1 && !el.matches("svg, svg *") && cs.textOverflow !== "ellipsis") {
      out.clipped.push(`${name(el)} hides ${el.scrollWidth - el.clientWidth}px`);
    }
  }

  // Icon + label: the glyph and the first text-bearing sibling should share a vertical centre.
  for (const g of root.querySelectorAll("svg.wb-glyph")) {
    if (!vis(g)) continue;
    const host = g.parentElement.matches("i, span") && g.parentElement.childElementCount === 1 ? g.parentElement : g;
    const sib = [...host.parentElement.childNodes].find((n) => n !== host && (n.nodeType === 3 ? n.textContent.trim() : n.nodeType === 1 && n.textContent.trim() && !n.querySelector("svg.wb-glyph")));
    if (!sib) continue;
    const parentCs = getComputedStyle(host.parentElement);
    if (parentCs.flexDirection.startsWith("column") || parentCs.display === "grid" && parentCs.gridTemplateRows !== "none" && host.parentElement.childElementCount > 2) continue;
    let tr;
    // A title + subtitle stack is a group the icon centres on; a single wrapped label aligns on its first line.
    const stacked = sib.nodeType === 1 && [...sib.children].some((ch) => getComputedStyle(ch).display === "block");
    if (stacked) tr = sib.getBoundingClientRect();
    else { const range = document.createRange(); range.selectNodeContents(sib); tr = range.getClientRects()[0]; }
    if (!tr) continue;
    const gr = g.getBoundingClientRect();
    if (gr.bottom <= tr.top + 1 || tr.bottom <= gr.top + 1) continue; // stacked (icon above or below the text), not a row
    const d = (gr.top + gr.height / 2) - (tr.top + tr.height / 2);
    // Multi-line labels align the glyph with the first line, so compare against the first line box only.
    if (Math.abs(d) > 2 && (tr.height < 40 || stacked)) out.glyph_misaligned.push(`${name(host.parentElement)} glyph ${d > 0 ? "+" : ""}${d.toFixed(1)}px`);
  }

  for (const card of root.querySelectorAll(".wb-panel, .wb-kpi, .wb-scope, .wb-dialog-body, .wb-narrative-section, .wb-forecast-result")) {
    if (!vis(card)) continue;
    const starts = [];
    for (const k of card.children) {
      if (!vis(k) || k.matches("svg, img, .recharts-responsive-container, .wb-chart, .wb-network-layout, table, hr")) continue;
      const cs = getComputedStyle(k);
      if (cs.position === "absolute") continue;
      // A boxed child (own background or border) aligns by its box edge; an unboxed one by where its content starts.
      const bg = cs.backgroundColor.match(/[\d.]+/g), boxed = (bg && (bg.length < 4 || +bg[3] > 0.05)) || parseFloat(cs.borderLeftWidth) > 0 && cs.borderLeftColor !== "rgba(0, 0, 0, 0)";
      starts.push([k.getBoundingClientRect().left + (boxed ? 0 : parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth)), k]);
    }
    for (let i = 0; i < starts.length; i++) for (let j = i + 1; j < starts.length; j++) {
      const d = Math.abs(starts[i][0] - starts[j][0]);
      if (d >= 2 && d <= 8) out.near_miss.push(`${name(card)}: ${name(starts[i][1])} vs ${name(starts[j][1])} ${d.toFixed(1)}px`);
    }
  }

  const ctx = document.createElement("canvas").getContext("2d");
  for (const ctl of root.querySelectorAll("select, input[type=text], input[type=search], input:not([type])")) {
    if (!vis(ctl)) continue;
    const cs = getComputedStyle(ctl);
    ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const text = ctl.tagName === "SELECT" ? (ctl.selectedOptions[0]?.textContent || "") : (ctl.value || ctl.placeholder || "");
    const room = ctl.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    if (text && ctx.measureText(text).width > room + 1) out.narrow_control.push(`${name(ctl)} "${text.slice(0, 24)}" needs ${Math.round(ctx.measureText(text).width)}px, has ${Math.round(room)}px`);
  }

  for (const img of root.querySelectorAll("img")) {
    if (!vis(img)) continue;
    const r = img.getBoundingClientRect(), cs = getComputedStyle(img);
    if (img.loading === "lazy" && !img.complete) continue; // not requested yet; the browser loads it on approach
    if (!img.complete || img.naturalWidth === 0) { out.images.push(`${img.src.split("/").pop()} broken`); continue; }
    const drift = Math.abs(r.width / r.height - img.naturalWidth / img.naturalHeight) / (img.naturalWidth / img.naturalHeight);
    if (drift > 0.02 && !/cover|contain/.test(cs.objectFit)) out.images.push(`${img.src.split("/").pop()} aspect drift ${(100 * drift).toFixed(1)}%`);
    const up = (r.width * devicePixelRatio) / img.naturalWidth;
    if (up > 1.05) out.images.push(`${img.src.split("/").pop()} upscaled ${up.toFixed(2)}x`);
  }
  const uniq = (a) => [...new Set(a)];
  return Object.fromEntries(Object.entries(out).map(([k, v]) => [k, Array.isArray(v) ? { n: uniq(v).length, samples: uniq(v).slice(0, 12) } : v]));
})();
