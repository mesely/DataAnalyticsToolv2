"""Public same-origin SVG assets must contain geometry only."""
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
ROOT=Path(__file__).resolve().parents[1]
GENERATED_NAMES = sorted(p.stem for p in (ROOT/"core/web/src/workbench/assets").glob("*.svg"))
@pytest.mark.parametrize("name",GENERATED_NAMES)
def test_generated_navigation_svg_has_no_active_or_external_content(name):
    root=ET.fromstring((ROOT/f"core/web/src/workbench/assets/{name}.svg").read_text())
    assert root.attrib["viewBox"]=="0 0 24 24"
    assert len(list(root)) > 0
    for node in root.iter():
        assert node.tag.split("}")[-1] in {"svg","path","rect","circle","line","polyline","polygon","ellipse","g"}
        for key,value in node.attrib.items():
            assert not key.lower().startswith("on")
            assert "href" not in key.lower()
            assert "url(" not in value.lower()
