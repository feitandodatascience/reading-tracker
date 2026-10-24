# BRAND: Regent

The reading tracker wears the brand of Tung Anh Tran's portfolio site, where its
dashboard is embedded: **deep regent green on a cool pearl ground, with one thread of
antique gold**. Royal and quiet: sturdy type, generous space, one accent per view.

The source of truth for every value below is the site's `design/tokens.json`
(Regent 2.0.0). Here it is encoded once in `src/reading_tracker/brand.py` and mirrored
in `.streamlit/config.toml`.

---

## Palette

| Role | Hex | Name | Used for |
|------|-----|------|----------|
| Primary | `#0E3B2C` | **Regent green** | Headings, the first data tone, filled buttons |
| Text | `#1B2A24` | **Ink** | Body text |
| Muted | `#4A5D55` | **Slate** | Captions, axis labels, metadata |
| Faint | `#8A9A93` | **Haze** | Faint labels; the quiet data tone (abandoned books) |
| Accent | `#94733A` | **Antique gold** | The one "look here" per view: the current week, the demo badge |
| Secondary | `#1A5C43` | **Bottle green** | Links, section eyebrows, the second data tone |
| Page | `#EFF2EF` | **Pearl** | Page and chart background |
| Raised | `#FAFBFA` | **Porcelain** | Raised panels; days without reading in the heatmap |
| Sunken | `#E5EAE6` | **Mist** | Widgets and sunken surfaces |
| Tint | `#DAE3DD` | **Frost** | Tracks, the lightest heatmap step |
| Rule | `#CDD7D0` | **Hairline** | Rules and grid lines |
| Deep | `#0B271D` | **Forest** | Text on gold, hover on green, the goal line |

**Gold is scarce.** It sits on the single thing to look at in a view, never on a
regular data series, and text on a gold fill is Forest, large or bold.

**Charts.** Regent green carries the main series and Haze its quiet pair (finished vs
abandoned). Magnitudes use one green ramp: Frost, Bottle green, Regent green. Charts sit
on Pearl, the same as the page, so gaps between marks read as surface.

**Light only.** The dashboard is locked to the light theme; the site shows it on its pearl
pages. The site's dark values are in `design/tokens.json` if a dark theme is ever added.

> Don't introduce a colour outside this table, charts included.

---

## Typography

- **Libre Bodoni** for headings and display, weight 500: a sturdy Didone, never a
  hairline one.
- **Jost** for text, weight 450 for body and heavier for labels. No light weights.

Both are variable fonts under the [SIL OFL 1.1](https://openfontlicense.org), self-hosted
in `app/static/fonts/` (the Latin subsets from Fontsource, the same files as the site),
because Streamlit serves only `static/` next to the app.

```
heading: "Libre Bodoni", "Bodoni 72", Didot, Georgia, serif
body:    "Jost", Futura, "Century Gothic", system-ui, sans-serif
```

The Latin subsets have no Vietnamese diacritics, so book titles are entered in English.

Section eyebrows are uppercase and bold in Bottle green; headings are sentence case.

---

## Do and don't

- **Do** take every colour from `brand.py`; `tests/test_brand.py` fails on a hex code
  anywhere else.
- **Do** keep gold to one accent moment per view.
- **Don't** put Pearl text on gold, or gold text on a pale fill at body size.
- **Don't** add a second accent colour, a third typeface, or a light font weight.
