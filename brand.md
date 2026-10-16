# BRAND — personal identity guideline

As applied across the portfolio site, GitHub profile, decks and dashboards.
A warm two-tone system: **espresso ink on a sand ground**, with everything else derived from those
two so nothing ever looks bolted on. Earthy and considered, with generous space and one clay-orange
signal — the register reads handmade and high-end rather than clinical.

Files this kit expects, under `assets/`: `logo.svg` (and a `logo-mono.svg` for one-colour
contexts) · `palette.png` · `icons/` (curated SVGs, see below) · `favicon.svg`.

---

## Palette

The core is two colours — **Espresso** and **Sand**. Every other value is one of those pushed lighter
or darker, plus the warm accents that give the earth palette its life. Eight tones total, same
discipline as a six-plus-two system: enough for any chart or page, few enough to hold in your head.

| Role | Hex | Name | Used for |
|------|-----|------|----------|
| Primary ink | `#2A241E` | **Espresso** | Headings, primary bars, the logo mark, strong ink |
| Deep surface | `#1B1712` | **Cocoa** | Dark hero sections, dark bands, code surfaces |
| Primary accent | `#CB7C5B` | **Clay** | The single loudest signal — CTAs, "look here", the one number that matters |
| Secondary accent | `#5C6449` | **Olive** | Links, active states, the second data tone |
| Supporting | `#7A6A55` | **Bark** | Fourth data tone, captions, metadata, muted UI |
| Tint | `#E0CDA9` | **Wheat** | Bar tracks, unfilled states, quiet fills, tag backgrounds |
| Page | `#E7D8BE` | **Sand** | Warm background of every light surface |
| Raised | `#F1E7D2` | **Paper** | Lighter cards, lifted off Sand with a soft shadow |

Body text sits in a warm near-black `#322A22`, a touch softer than full Espresso — reserve Espresso
`#2A241E` for headings, bars and the mark. Three more earth-biased neutrals: `#6B5F4E` for
soft/secondary body, `#9A8C74` for faint labels, and `#DFCFB2` (**Mist**) for sunken or alternating
sections. Rules and hairlines: `#D8C4A2`.

**Colour carries meaning, consistently.** Clay is the loudest colour — spend it. It should always sit
on the single thing you most want the eye to reach: the primary call to action, the headline metric,
the current step. If Clay means "act here" on one page, it means "act here" on every page. Olive is the
everyday interactive layer; Bark and Wheat are structure and background; Espresso is text and gravity.

**One caution for charts.** Clay is a warm orange, and warm reads as *caution / increase* inside a plot.
Keep Clay for the brand's "look here", never for a data series that means "good" — let Olive, Bark and a
neutral carry the series, and let Clay mark only the point you're calling out.

**Dark mode** is the same palette inverted through its own values, not a separate theme: Cocoa becomes
the page, Sand becomes the text, Bark lifts to `#B3A588` for muted text, Clay brightens to `#D98D6A`
and Olive lifts to `#9BA277` — both keep their roles on the dark ground.

> Don't introduce a ninth colour. Espresso, Olive, Bark and a warm neutral give four sequential data
> tones; Clay is the highlight that pulls one point out. That covers every chart worth making.

---

## Logo

> **Placeholder — no mark yet.** The rules below are the spec the eventual logo should follow;
> until it exists, use the Espresso wordmark of your name/initials as a stand-in (the type system alone
> is enough to look intentional). Drop `logo.svg` / `logo-mono.svg` into `assets/` when ready.

A wordmark or monogram set in **Espresso**, with a single-colour `logo-mono.svg` for when it lands on
Clay, on a photo, or on Cocoa (there, invert to Sand).

- Ship it as SVG. Base64-inline it into single-file decks and dashboards so they stay portable;
  reference the file everywhere else.
- Crop to the bounding box — no baked-in padding. Control spacing with layout, not with transparent pixels.
- Portfolio header: ~28–34px tall. Deck cover: place top-left, ~72–88px tall at 1920×1080.
  Favicon: the monogram alone, never the full wordmark.
- On a flex column, `align-self: flex-start` so it doesn't stretch to the container width.
- Minimum clear space around it equals the height of one letter of the wordmark. Below ~22px, switch
  to the monogram — the full wordmark stops being legible.

---

## Typography — Glacial Indifference

The brand face is **Glacial Indifference** (Alfredo Marco Pradil, [SIL OFL](https://openfontlicense.org),
free and self-hostable). A geometric sans with circular bowls and a single-story *a* — Futura-adjacent,
but softer and calmer. It carries the whole identity: elegant and high-end without ornament, and it's
the face you first reached for, so the brand is built around it rather than a substitute.

**It ships two weights only — Regular and Bold.** So hierarchy is *not* a fine weight gradient; it comes
from the **Bold-vs-Regular contrast, size, and letterspacing**. That's the classic geometric-type
discipline: confident size jumps, and generous tracking on uppercase where a geometric face is at its
best. One family throughout — never a second typeface for emphasis.

Self-host the woff in the repo (`assets/fonts/` — see `glacial-indifference.css`) and inline it as a
data URI in single-file decks so they stay portable:

```
--sans: "Glacial Indifference", system-ui, -apple-system, "Segoe UI", sans-serif;
--mono: "JetBrains Mono", "IBM Plex Mono", ui-monospace, "Consolas", monospace;
```

**Fallback:** General Sans (also kept in `assets/fonts/`, weights 200–700) is the drop-in substitute if
a surface ever needs true mid-weights — dense dashboards, long-form UI — where two weights feel blunt.
Same geometric-humanist lane, so it degrades gracefully.

The scale, top to bottom — two weights, doing a lot with size and tracking:

| Role | Weight | Tracking | Case / colour |
|------|--------|----------|---------------|
| Eyebrow / small caps | Bold | +0.15em | UPPERCASE, in Olive or Clay |
| Display / H1 | Bold | −0.03em | Sentence, in Espresso `#2A241E` |
| H2 / H3 | Bold | −0.01em | Sentence, in Espresso `#2A241E` |
| Body | Regular | 0 | Sentence, in Body ink `#322A22` |
| Soft body / captions | Regular | 0 | in `#6B5F4E` |
| Faint labels | Regular | +0.02em | in `#9A8C74` |

Eyebrows and section kickers are the brand voice: uppercase, letterspaced, in Olive or Clay —
never a monospace standing in for small caps.

**Monospace appears only where character alignment carries meaning** — code blocks, token/hash chips,
tabular figures in a data table, terminal output. Turn on `font-variant-numeric: tabular-nums` for any
column of numbers so digits line up. Never set running prose in mono.

### Paragraph spacing

Set spacing on the elements, not with blank lines. A simple, consistent scale (rem so it tracks the
base size):

| Element | Space before | Space after |
|---------|--------------|-------------|
| Display / H1 | — | 0.5rem |
| H2 / H3 | 1.5rem | 0.5rem |
| Body, all sizes | — | 1rem |
| Lists, captions | — | 0.75rem |

Spacing *between* sections, cards and grid cells is layout, not paragraph spacing — set it separately
(a section gap of 4–6rem, a card gap of 1.5rem) and don't conflate the two.

---

## Icons

Use one open, MIT-licensed stroke set so the whole system shares a single line weight and corner
radius — **[Lucide](https://lucide.dev)** is the recommended default (1000+ icons, 24px grid, 2px
stroke, consistent geometry). [Phosphor](https://phosphoricons.com) is a fine alternative if you want
optional filled weights. Pick one and stay in it; mixing two icon families reads as loudly as mixing
two typefaces.

Restate every icon in **Espresso** `#2A241E` (or Sand on dark surfaces). Keep the source stroke width —
don't outline-and-fill. Ship them as inline SVG so they inherit `currentColor` and recolour for free.

A starter set for a data / engineering portfolio (Lucide names):

| Icon | Depicts | Used for |
|------|---------|----------|
| `line-chart` | trend line | analysis, results, dashboards |
| `database` | stacked discs | data sources, storage, pipelines |
| `git-branch` | branch | repos, versioning, the GitHub profile |
| `terminal` | prompt | CLI tools, code, "how it's built" |
| `flask-conical` | flask | experiments, research, work-in-progress |
| `layers` | stacked planes | stack, architecture, modules |
| `cpu` | chip | models, compute, ML sections |
| `book-open` | open book | writing, notes, documentation |
| `mail` | envelope | contact |
| `github` | mark | profile link (brand mark, keep its own geometry) |
| `linkedin` | mark | profile link |
| `arrow-up-right` | out-arrow | external links, "view project" |

**Sizing.** 20–24px inline with text, 28–36px in cards and nav, 40–48px as a section marker.
Stroke icons hold up small better than detailed glyphs — but keep the stroke visually ~2px at every size
(scale the viewBox, not the stroke).

**Restraint.** One icon per section header, one per card at most. Icons label sections; they don't
decorate. The test: if removing the icon costs the layout nothing, it was decoration — cut it.

---

## Do and don't

- **Do** derive everything from Espresso and Sand. Two colours plus one warm accent should feel like the
  whole brand; the rest is structure.
- **Do** keep Clay scarce and semantic — one accent moment per view. If everything is highlighted,
  nothing is.
- **Do** self-host the type and icons in the repo so the site, the deck and the GitHub README all render
  identically and offline.
- **Do** build hierarchy from weight and tracking within one family.
- **Don't** introduce a colour outside the eight, charts included — and keep Clay off "positive" data series.
- **Don't** put Sand or pale text on Wheat, Clay or Olive fills — use Espresso or Cocoa for
  numerals and labels on those.
- **Don't** add a second typeface for emphasis, or let a monospace stand in for small caps.
- **Don't** mix two icon families, or fill a stroke set to "match" a filled one.
- **Don't** stretch or pad the logo — crop to the box and space it with layout.
