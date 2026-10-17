"""Brand palette and plotly template, encoded once from brand.md.

Everything visual imports from here (and ``.streamlit/config.toml`` mirrors the
same values for Streamlit's own widgets), so no hex code lives anywhere else.

Colour jobs, per brand.md and a validated check of the data tones:

- Olive is the everyday data tone; the warm neutral is its pair (finished vs
  abandoned). Olive and Bark are too close to tell apart, so they never pair.
- Clay marks the single thing to look at in a view (the current week, the
  primary action). Never a "good" data series.
- Text on Clay or Olive fills is Espresso, never Sand.
"""

import plotly.graph_objects as go
import plotly.io as pio

# --- the eight brand tones -------------------------------------------------------
ESPRESSO = "#2A241E"  # primary ink: headings, strong marks
COCOA = "#1B1712"  # deep surface
CLAY = "#CB7C5B"  # the one accent: "look here"
OLIVE = "#5C6449"  # interactive layer, first data tone
BARK = "#7A6A55"  # supporting tone, metadata
WHEAT = "#E0CDA9"  # tint: tracks, unfilled states
SAND = "#E7D8BE"  # page background
PAPER = "#F1E7D2"  # raised cards

# --- neutrals named in brand.md ---------------------------------------------------
BODY_INK = "#322A22"
SOFT_INK = "#6B5F4E"
FAINT_INK = "#9A8C74"  # faint labels; also the warm-neutral data tone
MIST = "#DFCFB2"  # sunken sections
HAIRLINE = "#D8C4A2"  # rules and grid lines

WARM_NEUTRAL = FAINT_INK
STATUS_COLORS = {"finished": OLIVE, "abandoned": WARM_NEUTRAL, "reading": CLAY}

# Font stack from brand.md; falls back to the system sans until the
# Glacial Indifference files are self-hosted.
FONT_FAMILY = '"Glacial Indifference", system-ui, -apple-system, "Segoe UI", sans-serif'

# Sequential ramp for magnitudes (heatmap): one warm hue, light to dark.
# Zero gets Paper so days without reading stand apart from short ones.
SEQUENTIAL = [WHEAT, BARK, ESPRESSO]
HEATMAP_COLORSCALE = [
    [0.0, PAPER],
    [0.001, WHEAT],
    [0.5, BARK],
    [1.0, ESPRESSO],
]

TEMPLATE_NAME = "reading_tracker"


def plotly_template() -> go.layout.Template:
    """Return the brand plotly template: warm ink, recessive grid, no chartjunk."""
    axis = {
        "gridcolor": HAIRLINE,
        "linecolor": HAIRLINE,
        "zerolinecolor": HAIRLINE,
        "tickcolor": HAIRLINE,
        "tickfont": {"color": SOFT_INK},
        "title": {"font": {"color": SOFT_INK}},
        "automargin": True,
    }
    return go.layout.Template(
        layout={
            "font": {"family": FONT_FAMILY, "color": BODY_INK, "size": 13},
            "title": {"font": {"color": ESPRESSO, "size": 16}},
            # Same as the page, so gaps between marks read as surface.
            "paper_bgcolor": SAND,
            "plot_bgcolor": SAND,
            "colorway": [OLIVE, WARM_NEUTRAL, ESPRESSO],
            "xaxis": axis,
            "yaxis": axis,
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "x": 0,
                "font": {"color": SOFT_INK},
            },
            "hoverlabel": {
                "bgcolor": PAPER,
                "bordercolor": HAIRLINE,
                "font": {"family": FONT_FAMILY, "color": ESPRESSO},
            },
            "margin": {"l": 8, "r": 8, "t": 32, "b": 8},
        }
    )


def register_template() -> str:
    """Register the brand template with plotly and return its name."""
    pio.templates[TEMPLATE_NAME] = plotly_template()
    return TEMPLATE_NAME
