/* Design audit — run in the page (browser devtools or an automation `evaluate`). Returns measured facts and
 * 0–100 sub-scores with explicit formulas. Heuristic measurements of the rendered DOM, not user testing. */
(() => {
  // Measure the settled state: suspend transitions so a theme or route change is not caught mid-animation.
  const freeze = document.createElement("style");
  freeze.textContent = "*,*::before,*::after{transition:none!important;animation:none!important}";
  document.head.appendChild(freeze);
  void document.body.offsetHeight;
  try { return measure(); } finally { freeze.remove(); }
  function measure() {
  const vis = (el) => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && +cs.opacity !== 0 &&
      r.bottom > 0 && r.right > 0 && r.top < innerHeight * 4 && !el.closest("[aria-hidden=true]:not(.wb-custom-icon):not(.wb-glyph)") && !el.closest("dialog:not([open])") &&
      // Chrome lays out the content of a closed <details>; only its <summary> is actually visible.
      !(el.closest("details:not([open])") && !el.closest("summary") && el.closest("details:not([open])") !== el);
  };
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (top, bot) => ({ r: top.r * top.a + bot.r * (1 - top.a), g: top.g * top.a + bot.g * (1 - top.a), b: top.b * top.a + bot.b * (1 - top.a), a: 1 });
  const bgOf = (el) => { const stack = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; } } let base = { r: 255, g: 255, b: 255, a: 1 }; if (stack.length && stack[stack.length - 1].a >= 1) base = stack.pop(); for (let i = stack.length - 1; i >= 0; i--) base = blend(stack[i], base); return base; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const root = document.querySelector(".wb") || document.body;
  const all = [...root.querySelectorAll("*")].filter(vis);

  // Fitts: interactive target sizes (WCAG 2.5.5 AAA 44px; 2.5.8 AA 24px)
  const interactive = all.filter((e) => e.matches("button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [tabindex='0']"));
  const sizes = interactive.map((e) => { const target = e.matches("input[type=checkbox], input[type=radio]") && e.closest("label") ? e.closest("label") : e; const r = target.getBoundingClientRect(); return { w: r.width, h: r.height, label: (e.getAttribute("aria-label") || e.textContent || e.tagName).trim().slice(0, 40) }; });
  const t44 = sizes.filter((s) => s.w >= 44 && s.h >= 44).length, t24 = sizes.filter((s) => s.w >= 24 && s.h >= 24).length;
  const small = sizes.filter((s) => s.w < 44 || s.h < 44).map((s) => `${s.label} ${Math.round(s.w)}x${Math.round(s.h)}`);
  const h40 = sizes.filter((s) => s.h >= 40).length;

  // Contrast of text (own text nodes only)
  const texts = all.filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
  let pass = 0, fails = [];
  for (const e of texts) { const cs = getComputedStyle(e); const fg = parse(cs.color); if (!fg) continue; const bg = bgOf(e); const c = ratio(blend(fg, bg), bg); const large = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 700); if (c >= (large ? 3 : 4.5)) pass++; else fails.push(`${e.textContent.trim().slice(0, 30)} ${c.toFixed(2)}`); }

  // Icons: non-text contrast (WCAG 1.4.11, 3:1) and provenance
  const icons = all.filter((e) => e.matches(".wb-custom-icon, svg.lucide, svg[class*=lucide], .wb-glyph"));
  let iconPass = 0;
  for (const e of icons) { const fg = parse(e.classList.contains("wb-custom-icon") ? getComputedStyle(e).backgroundColor : getComputedStyle(e).color); const bg = bgOf(e.parentElement); if (fg && ratio(blend(fg, bg), bg) >= 3) iconPass++; }
  const lucide = all.filter((e) => e.matches("svg.lucide, svg[class*=lucide]")).length;

  // Typography scale and spacing rhythm
  const fontSizes = new Set(texts.map((e) => Math.round(parseFloat(getComputedStyle(e).fontSize) * 2) / 2));
  const weights = new Set(texts.map((e) => getComputedStyle(e).fontWeight));
  const spacing = [];
  for (const e of all) { const cs = getComputedStyle(e); for (const p of ["paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "marginTop", "marginBottom", "rowGap", "columnGap"]) { const v = parseFloat(cs[p]); if (v > 0) spacing.push(v); } }
  const onGrid = spacing.filter((v) => Math.abs(v / 4 - Math.round(v / 4)) < 0.01).length;
  const distinctSpacing = new Set(spacing.map((v) => Math.round(v))).size;
  const radii = new Set(all.map((e) => getComputedStyle(e).borderTopLeftRadius).filter((r) => r !== "0px"));
  const bordered = all.filter((e) => { const cs = getComputedStyle(e); return parseFloat(cs.borderTopWidth) > 0 && parseFloat(cs.borderLeftWidth) > 0 && e.getBoundingClientRect().width > 120; }).length;

  // Alignment: distinct left edges of block-level visible containers in main (fewer = stronger grid)
  const main = document.querySelector("#wb-main") || root;
  const blocks = [...main.querySelectorAll("section, header, form, h1, h2, h3, p, .wb-card, [class*=card]")].filter(vis);
  const lefts = new Set(blocks.map((e) => Math.round(e.getBoundingClientRect().left)));
  // Content insets: where text starts inside each card, relative to the card's left edge. Grid columns are
  // intended alignment lines; a card whose content starts at a different inset is the misalignment.
  const cards = [...main.querySelectorAll(".wb-kpi, .wb-panel, .wb-scope, .wb-sourcebar")].filter(vis);
  const insets = new Set(), starts = [];
  for (const c of cards) {
    // The card's content start line: leftmost content box (text blocks and media), measured inside padding.
    const cl = c.getBoundingClientRect().left;
    let start = Infinity;
    for (const t of c.querySelectorAll(":scope h2, :scope h3, :scope p, :scope strong, :scope img, :scope .wb-card-note, :scope label, :scope .wb-glyph, :scope [class*='-icon'], :scope [class*='symbol']")) {
      if (!vis(t) || t.closest(".recharts-wrapper, table, .wb-ranking")) continue;
      const cs = getComputedStyle(t);
      start = Math.min(start, t.getBoundingClientRect().left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth) - cl);
    }
    if (Number.isFinite(start)) starts.push(start);
  }
  // A content line is a cluster of starts within 3px (a 1px border is not a different alignment line).
  starts.sort((x, y) => x - y);
  for (const v of starts) if (![...insets].some((u) => Math.abs(u - v) <= 3)) insets.add(Math.round(v));
  // Hick–Hyman concerns choosing a command. Data items that are themselves the content (ranking rows, table
  // rows, graph nodes, chart marks) are not commands and are excluded; the raw count is reported too.
  const DATA = ".wb-ranking button, table button, .wb-graph-node, .recharts-wrapper *, .wb-evidence-links button, .wb-narrative button";
  const region = (sel) => { const r = document.querySelector(sel); return r ? [...r.querySelectorAll("button, a[href], select, summary")].filter(vis).filter((e) => !e.matches(DATA)).length : 0; };
  const regionRaw = (sel) => { const r = document.querySelector(sel); return r ? [...r.querySelectorAll("button, a[href], select, summary")].filter(vis).length : 0; };
  const regions = { sidebar: region(".wb-sidebar"), topbar: region(".wb-topbar"), main: region("#wb-main"), main_including_data_items: regionRaw("#wb-main") };
  const H = Object.fromEntries(Object.entries(regions).filter(([k]) => k !== "main_including_data_items").map(([k, n]) => [k, +Math.log2(n + 1).toFixed(2)]));

  const colors = new Set(all.map((e) => getComputedStyle(e).color)).size;
  const score = {
    fitts: Math.round(100 * (0.6 * t44 / sizes.length + 0.4 * t24 / sizes.length)),
    contrast_text: Math.round(100 * pass / Math.max(1, texts.length)),
    contrast_icons: Math.round(100 * iconPass / Math.max(1, icons.length)),
    spacing_rhythm: Math.round(100 * onGrid / Math.max(1, spacing.length)),
    type_scale: Math.max(0, 100 - 8 * Math.max(0, fontSizes.size - 6)),
    hick_main: Math.max(0, Math.round(100 - 12 * Math.max(0, H.main - 4))),
    alignment: Math.max(0, 100 - 15 * Math.max(0, insets.size - 1)),
    icon_originality: Math.round(100 * (icons.length - lucide) / Math.max(1, icons.length)),
  };
  return { viewport: [innerWidth, innerHeight], targets: { n: sizes.length, ge44: t44, ge24: t24, h_ge40: h40, under44: small.slice(0, 40) },
    text: { n: texts.length, pass, fails: fails.slice(0, 10) }, icons: { n: icons.length, lucide, contrast_pass: iconPass },
    type: { sizes: [...fontSizes].sort((a, b) => a - b), weights: [...weights] }, spacing: { n: spacing.length, on4: onGrid, distinct: distinctSpacing },
    radii: [...radii], bordered_boxes: bordered, left_edges: lefts.size, card_insets: [...insets].sort((a, b) => a - b), regions, hick_bits: H, colors, score };
  }
})();
