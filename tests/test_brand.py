"""Brand rules: one source of truth for colours, mirrored in the Streamlit theme."""

import re
import tomllib

import plotly.io as pio

from reading_tracker import brand, db

CONFIG = db.PROJECT_ROOT / ".streamlit" / "config.toml"
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
BRAND_TONES = {
    brand.REGENT,
    brand.INK,
    brand.SLATE,
    brand.HAZE,
    brand.GOLD,
    brand.BOTTLE,
    brand.PEARL,
    brand.PORCELAIN,
    brand.MIST,
    brand.FROST,
    brand.HAIRLINE,
    brand.FOREST,
}


def test_streamlit_theme_mirrors_brand_py():
    theme = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["theme"]
    assert theme["base"] == "light"
    assert theme["primaryColor"] == brand.REGENT
    assert theme["backgroundColor"] == brand.PEARL
    assert theme["secondaryBackgroundColor"] == brand.MIST
    assert theme["textColor"] == brand.INK
    assert theme["linkColor"] == brand.BOTTLE
    assert theme["borderColor"] == brand.HAIRLINE
    assert theme["orangeColor"] == brand.GOLD
    assert theme["orangeTextColor"] == brand.FOREST  # text on gold is deep


def test_theme_uses_only_brand_colours():
    assert set(HEX.findall(CONFIG.read_text(encoding="utf-8"))) <= BRAND_TONES


def test_theme_is_locked_to_light():
    theme = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["theme"]
    assert "light" not in theme and "dark" not in theme  # no appearance toggle


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
    assert layout.paper_bgcolor == brand.PEARL
    assert list(layout.colorway)[0] == brand.REGENT
    assert brand.GOLD not in layout.colorway  # gold is a highlight, not a series


def test_finished_and_abandoned_use_the_quiet_pair():
    assert brand.STATUS_COLORS["finished"] == brand.REGENT
    assert brand.STATUS_COLORS["abandoned"] == brand.HAZE


def test_brand_fonts_are_self_hosted_for_streamlit_and_plotly():
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    theme = config["theme"]
    assert config["server"]["enableStaticServing"] is True
    assert theme["font"] == "Jost"
    assert theme["headingFont"] == "Libre Bodoni"
    assert theme["baseFontWeight"] >= 450  # brand.md: no light body weights
    faces = theme["fontFaces"]
    assert {face["family"] for face in faces} == {"Jost", "Libre Bodoni"}
    for face in faces:
        # Streamlit serves app/static/ under the URL prefix app/static/.
        assert (db.PROJECT_ROOT / face["url"]).is_file()
    assert (db.PROJECT_ROOT / "app" / "static" / "fonts" / "OFL.txt").is_file()
    assert brand.FONT_FAMILY.startswith('"Jost"')
    assert brand.HEADING_FONT_FAMILY.startswith('"Libre Bodoni"')
