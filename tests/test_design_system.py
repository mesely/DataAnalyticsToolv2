"""AW-15 design system: the glyph family is original, valid and complete; the CSS scales are settled.

The glyph family is generated from the unedited Gemini outputs in assets/glyphs/; nothing in the web client may
import a stock icon package again. normalize_css and contrast_tones must be fixed points over the shipped CSS,
so a hand edit that leaves the scales (or a light-theme text tone below 4.6:1) fails here instead of in review.
"""
import hashlib
import json
import re
from pathlib import Path

import pytest

from tools.design import contrast_tones, glyphs, normalize_css

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "core/web/src"
FAMILY, SOURCE = glyphs.load()


@pytest.mark.parametrize("name", sorted(FAMILY))
def test_every_glyph_follows_the_grammar(name):
    elements = glyphs.parse(name, FAMILY[name])
    assert 2 <= len(elements) <= 8
    assert sum(1 for tag, attrs in elements if tag == "circle" and attrs.get("className") == "idx") == 1
    assert {tag for tag, _ in elements} <= glyphs.TAGS


def test_generated_module_matches_the_gemini_sources():
    text = (WEB / "workbench/glyphs.generated.ts").read_text()
    shipped = json.loads(re.search(r"export const GLYPHS: Record<string, GlyphElement\[\]> = (\{.*\});\n", text).group(1))
    assert shipped == {n: glyphs.parse(n, svg) for n, svg in FAMILY.items()}
    assert json.loads(re.search(r"export const GLYPH_SOURCE: Record<string, string> = (\{.*\});\n", text).group(1)) == SOURCE


def test_widget_css_matches_the_gemini_sources():
    assert glyphs.CSS_OUT.read_text() == glyphs.widget_css(FAMILY)
    app = (WEB / "app.css").read_text()
    assert app.index('@import "./workbench/glyphs.generated.css"') < app.index('@import "./workbench/workbench.css"')


def test_every_named_glyph_exists():
    used = set(re.findall(r'glyph\("([a-z_]+)"\)', (WEB / "workbench/BrandIcons.tsx").read_text()))
    assert used and used <= set(FAMILY), used - set(FAMILY)


def test_no_stock_icon_package_remains():
    pkg = json.loads((ROOT / "core/package.json").read_text())
    assert not any("lucide" in d for k in ("dependencies", "devDependencies") for d in pkg.get(k, {}))
    for f in WEB.rglob("*.ts*"):
        assert "lucide" not in f.read_text(), f
    assert [p.name for p in (WEB / "workbench/assets").glob("*.svg")] == ["brand.svg"]


def test_glyph_sources_are_in_the_asset_manifest():
    manifest = {e["path"]: e for e in json.loads((ROOT / "docs/evidence/ASSET_MANIFEST.json").read_text())}
    for f in sorted(glyphs.SRC.glob("gemini-batch-*.json")):
        entry = manifest[str(f.relative_to(ROOT))]
        assert entry["kind"] == "original-gemini-glyph-source"
        assert entry["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    for path in manifest:
        assert (ROOT / path).exists(), path


def test_css_sits_on_the_design_scales():
    css = normalize_css.CSS.read_text()
    assert normalize_css.normalize(css) == css
    # Fluid or relative sizes escape the px scale (5.2vw rendered 20.5px on a 390px phone).
    assert not re.findall(r"(?:font-size|margin|padding)[a-z-]*:[^;]*(?:\d(?:rem|em|vw)\b|clamp\()", css)


def test_light_theme_text_contrast_block_is_current():
    css = contrast_tones.CSS.read_text()
    rendered, _ = contrast_tones.render(css)
    assert rendered == css
    block = css[css.index(contrast_tones.BEGIN):]
    for tone in re.findall(r"--tone-[0-9a-f]{6}: #([0-9a-f]{6});", block):
        assert min(contrast_tones.ratio(tone, s) for s in contrast_tones.SURFACES) >= 4.6
