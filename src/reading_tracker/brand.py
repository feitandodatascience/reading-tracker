"""Brand palette and plotly template, encoded once from brand.md.

Everything visual imports from here (and ``.streamlit/config.toml`` mirrors the
same values for Streamlit's own widgets), so no hex code lives anywhere else.

Colour jobs, per brand.md (the "Regent" brand of the portfolio site):

- Regent green is the first data tone; Haze is its quiet pair (finished vs
  abandoned).
- Antique gold marks the single thing to look at in a view (the current week,
  the book in progress). Never a regular data series, and text on a gold fill
  is Forest, large or bold.
- Pearl is the page; Porcelain marks days without reading in the heatmap.
"""

import plotly.graph_objects as go
import plotly.io as pio

# --- Regent tones (light), from the site's design/tokens.json ------------------------
REGENT = "#0E3B2C"  # primary: headings, first data tone, filled buttons
INK = "#1B2A24"  # body text
SLATE = "#4A5D55"  # secondary text, captions, axis labels
HAZE = "#8A9A93"  # faint labels; also the quiet data tone
GOLD = "#94733A"  # the one accent: "look here"
BOTTLE = "#1A5C43"  # links, eyebrows, the second data tone
PEARL = "#EFF2EF"  # page background
PORCELAIN = "#FAFBFA"  # raised panels
MIST = "#E5EAE6"  # sunken surfaces, widgets
FROST = "#DAE3DD"  # tracks and tints
HAIRLINE = "#CDD7D0"  # rules and grid lines
FOREST = "#0B271D"  # the deepest green: text on gold, hover on green

STATUS_COLORS = {"finished": REGENT, "abandoned": HAZE, "reading": GOLD}

# Font stacks from brand.md: Jost for text, Libre Bodoni for display.
FONT_FAMILY = '"Jost", Futura, "Century Gothic", system-ui, sans-serif'
HEADING_FONT_FAMILY = '"Libre Bodoni", "Bodoni 72", Didot, Georgia, serif'

# Sequential ramp for magnitudes (heatmap): one green hue, light to dark.
# Zero gets Porcelain so days without reading stand apart from short ones.
SEQUENTIAL = [FROST, BOTTLE, REGENT]
HEATMAP_COLORSCALE = [
    [0.0, PORCELAIN],
    [0.001, FROST],
    [0.5, BOTTLE],
    [1.0, REGENT],
]

TEMPLATE_NAME = "reading_tracker"


def plotly_template() -> go.layout.Template:
    """Return the brand plotly template: green ink, recessive grid, no chartjunk."""
    axis = {
        "gridcolor": HAIRLINE,
        "linecolor": HAIRLINE,
        "zerolinecolor": HAIRLINE,
        "tickcolor": HAIRLINE,
        "tickfont": {"color": SLATE},
        "title": {"font": {"color": SLATE}},
        "automargin": True,
        "fixedrange": True,  # no drag or pinch zoom, so a swipe over a chart scrolls
    }
    return go.layout.Template(
        layout={
            "font": {"family": FONT_FAMILY, "color": INK, "size": 13},
            "title": {
                "font": {"family": HEADING_FONT_FAMILY, "color": REGENT, "size": 18}
            },
            # Same as the page, so gaps between marks read as surface.
            "paper_bgcolor": PEARL,
            "plot_bgcolor": PEARL,
            "colorway": [REGENT, HAZE, BOTTLE],
            "xaxis": axis,
            "yaxis": axis,
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "x": 0,
                "font": {"color": SLATE},
            },
            "hoverlabel": {
                "bgcolor": PORCELAIN,
                "bordercolor": HAIRLINE,
                "font": {"family": FONT_FAMILY, "color": REGENT},
            },
            "margin": {"l": 8, "r": 8, "t": 32, "b": 8},
        }
    )


def register_template() -> str:
    """Register the brand template with plotly and return its name."""
    pio.templates[TEMPLATE_NAME] = plotly_template()
    return TEMPLATE_NAME
