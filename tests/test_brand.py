"""Brand rules: one source of truth for colours, mirrored in the Streamlit theme."""

import re
import tomllib

import plotly.io as pio

from reading_tracker import brand, db

CONFIG = db.PROJECT_ROOT / ".streamlit" / "config.toml"
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
BRAND_TONES = {
    brand.ESPRESSO,
    brand.COCOA,
    brand.CLAY,
    brand.OLIVE,
    brand.BARK,
    brand.WHEAT,
    brand.SAND,
    brand.PAPER,
    brand.BODY_INK,
    brand.SOFT_INK,
    brand.FAINT_INK,
    brand.MIST,
    brand.HAIRLINE,
}


def test_streamlit_theme_mirrors_brand_py():
    theme = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["theme"]
    assert theme["base"] == "light"
    assert theme["primaryColor"] == brand.OLIVE
    assert theme["backgroundColor"] == brand.SAND
    assert theme["secondaryBackgroundColor"] == brand.MIST
    assert theme["textColor"] == brand.BODY_INK
    assert theme["borderColor"] == brand.HAIRLINE
    assert theme["orangeColor"] == brand.CLAY


def test_theme_uses_only_brand_colours():
    assert set(HEX.findall(CONFIG.read_text(encoding="utf-8"))) <= BRAND_TONES


def test_no_hex_codes_outside_brand_py():
    code = [
        *(db.PROJECT_ROOT / "src").rglob("*.py"),
        *(db.PROJECT_ROOT / "app").glob("*.py"),
    ]
    offenders = [
        path.name
        for path in code
        if path.name != "brand.py" and HEX.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_plotly_template_is_registered_with_brand_colours():
    name = brand.register_template()
    layout = pio.templates[name].layout
    assert layout.paper_bgcolor == brand.SAND
    assert list(layout.colorway)[0] == brand.OLIVE
    assert brand.CLAY not in layout.colorway  # Clay is a highlight, not a series


def test_finished_and_abandoned_use_the_validated_pair():
    assert brand.STATUS_COLORS["finished"] == brand.OLIVE
    assert brand.STATUS_COLORS["abandoned"] == brand.WARM_NEUTRAL


def test_brand_font_is_self_hosted_for_streamlit_and_plotly():
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    family = "Glacial Indifference"
    assert config["server"]["enableStaticServing"] is True
    assert config["theme"]["font"] == family
    faces = config["theme"]["fontFaces"]
    assert {face["weight"] for face in faces} == {400, 700}  # brand.md: two weights
    for face in faces:
        assert face["family"] == family
        # Streamlit serves app/static/ under the URL prefix app/static/.
        assert (db.PROJECT_ROOT / face["url"]).is_file()
    assert (db.PROJECT_ROOT / "app" / "static" / "fonts" / "OFL.txt").is_file()
    assert brand.FONT_FAMILY.startswith(f'"{family}"')
