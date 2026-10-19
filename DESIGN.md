---
name: Trustworthy News Detector
description: Know Before You Believe. A calm, explainable second look at the news.
colors:
  steel-blue: "#2d6198"
  steel-blue-deep: "#234f7d"
  steel-blue-night: "#4c8ed0"
  harbor-navy: "#10233b"
  slate-ink: "#182433"
  fog-gray: "#647184"
  mist-line: "#dce3ea"
  input-rule: "#cbd6e0"
  focus-blue: "#6995bd"
  paper: "#ffffff"
  paper-soft: "#f5f7f9"
  night-bg: "#0f172a"
  night-surface: "#172033"
  night-line: "#334155"
  night-muted: "#94a3b8"
  pine-green: "#28714d"
  ochre-amber: "#a55d12"
  brick-red: "#a84242"
typography:
  display:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(30px, 4vw, 46px)"
    fontWeight: 800
    lineHeight: 1.12
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Manrope, sans-serif"
    fontSize: "21px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Manrope, sans-serif"
    fontSize: "18px"
    fontWeight: 500
    lineHeight: 1.4
  body:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.14em"
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "24px"
  lg: "32px"
  xl: "64px"
components:
  button-primary:
    backgroundColor: "{colors.steel-blue}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "0 25px"
    height: "53px"
  button-primary-hover:
    backgroundColor: "{colors.steel-blue-deep}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.sm}"
    height: "45px"
  input-frame:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.md}"
    padding: "22px 24px"
  card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "32px"
  status-supported:
    textColor: "{colors.pine-green}"
    rounded: "{rounded.xs}"
    padding: "4px 8px"
  status-needs-verification:
    textColor: "{colors.ochre-amber}"
    rounded: "{rounded.xs}"
    padding: "4px 8px"
  status-contradicted:
    textColor: "{colors.brick-red}"
    rounded: "{rounded.xs}"
    padding: "4px 8px"
---

# Design System: Trustworthy News Detector

## Overview

**Creative North Star: "The Second Look"**

TND should feel like a steady, trustworthy instrument that someone reaches for before believing or sharing a story. It is restrained, clear, and deliberately unsensational. The interface gives the reader space to pause: generous whitespace, a single centered task on the home page, and results laid out as readable evidence rather than as a verdict.

Most of the identity comes from cool neutrals. Navy headings sit on white (or deep slate at night), a single steel blue carries every action, and three muted status hues (pine, ochre, brick) mark claims without shouting. Manrope gives headings a confident, slightly technical voice, and DM Sans keeps body copy plain and readable. Surfaces lift gently off the page on soft cool-tinted shadows.

There are two confirmed rejections. The first is alarmist warning UI: risk reads as measured information, never as a siren. The second is sci-fi "AI" styling: no neon gradients, glowing orbs, or futuristic tech chrome.

**Key Characteristics:**
- Cool-neutral palette with one steel-blue action color
- Muted, desaturated status colors, used only to mark claims and signals
- Manrope headings over DM Sans body, with tight negative tracking on display type
- Gently rounded corners (4–12px) and soft, cool-tinted shadows
- Full light, dark and system theming through shared CSS custom properties

## Colors

A cool, low-chroma palette where blue means "act" and the status hues mean "look closer".

### Primary
- **Steel Blue** (`steel-blue`): the only action color. It covers primary buttons, active nav, overlines, step numbers, links, and the active input tab. In dark theme it brightens to **Night Steel Blue** (`steel-blue-night`).
- **Deep Steel Blue** (`steel-blue-deep`): the hover and pressed state for primary actions.

### Secondary
- **Pine Green** (`pine-green`): supported claims and positive signals.
- **Ochre Amber** (`ochre-amber`): claims that need verification, moderate signals, and the "analysis is incomplete" notice.
- **Brick Red** (`brick-red`): contradicted or high-risk markers and validation errors. It is a muted brick rather than a fire-engine red, on purpose.

### Neutral
- **Harbor Navy** (`harbor-navy`): headings and the brand mark.
- **Slate Ink** (`slate-ink`): body text.
- **Fog Gray** (`fog-gray`): secondary text, hints, footer, and step descriptions.
- **Mist Line** (`mist-line`) and **Input Rule** (`input-rule`): hairline dividers and card or input borders.
- **Focus Blue** (`focus-blue`): focused input borders and the left rule on evidence blocks.
- **Paper** and **Paper Soft** (`paper`, `paper-soft`): the page and recessed surfaces.
- **Night palette** (`night-bg`, `night-surface`, `night-line`, `night-muted`): dark-theme page, cards, borders, and muted text.

### Named Rules
**The One Action Color Rule.** Steel blue is reserved for things the reader can act on or follow. Never use it decoratively.

**The Measured Risk Rule.** Status colors appear as tinted chips (an 8–10% tint of the hue behind full-strength text), thin rules, or a 3px top border. They never flood a surface. Red is never the dominant color of a screen.

## Typography

**Display Font:** Manrope (with sans-serif)
**Body Font:** DM Sans (with sans-serif)

**Character:** Manrope's geometric, heavy headings give TND a sure footing, and DM Sans keeps the explanatory text neutral and easy to read. Together they say "careful tool", not "news brand".

### Hierarchy
- **Display** (800, `clamp(30px, 4vw, 46px)`, 1.12, −0.035em): page titles such as "Trustworthy News Detector", "Analysis Result" and "About TND".
- **Headline** (700, 21–25px, 1.2–1.3, −0.02em): section headings, legal section titles, and dialog titles.
- **Title** (500, 18px, 1.4): quoted claims inside the results list. Manrope at medium weight sets claims apart from commentary.
- **Body** (400, 16–17px, 1.6): intro copy and input text. Keep intro measures to about 545px.
- **Label** (700, 11–13px, 0.08–0.14em, uppercase): overlines, input tabs, and button text.
- **Score numeral** (800, 67px, −0.07em, Manrope): the risk score only.

### Named Rules
**The Quiet Overline Rule.** Every major section opens with a small uppercase steel-blue overline ("Simple process", "How it helps") above a Manrope heading. Keep the pairing; don't stack two loud levels.

## Layout

Content sits in a centered container, `min(1400px, 100% − 64px)`, under a 92px header with a hairline bottom border. The home page has a single centered column: a hero with large top padding (89px), then an analyzer capped at 860px, then a four-step "How it works" grid. Results stack a risk summary grid (1fr / 1.5fr), detail sections, and the claims list. Legal pages use a 760px reading column.

Spacing is loose and calm, with section gaps of 60–90px and internal card padding of 22–41px. At 700px and below, the header wraps, nav moves to its own row, theme labels collapse to icons, padding tightens, and display type drops to about 32px. The steps grid collapses to one column at 520px.

## Elevation & Depth

TND uses soft lift. Cards, the input frame, and the risk summary float on a faint, cool-tinted ambient shadow. Overlays such as the loading card and the Terms dialog get stronger, deeper shadows. Focus is shown with a 3px translucent steel-blue halo rather than a shadow. In dark theme, shadow color shifts to near-black at 22%.

### Shadow Vocabulary
- **Ambient card** (`box-shadow: 0 8px 24px rgba(21, 43, 67, 0.07)`): input frame, detail sections, claims section, and risk summary.
- **Button lift** (`box-shadow: 0 4px 12px rgba(35, 79, 125, 0.17)`): primary button on hover, paired with a 1px upward shift.
- **Overlay** (`box-shadow: 0 20px 45px rgba(18, 35, 56, 0.22)`, or `0 24px 60px` with the theme shadow color): the loading card and the Terms dialog.
- **Focus halo** (`box-shadow: 0 0 0 3px` steel blue at 10–20%): focused input frame.

### Named Rules
**The Gentle Lift Rule.** Shadows are diffuse and cool-tinted, never hard or black, and no resting shadow exceeds the ambient card value.

## Shapes

Corners are gently rounded and grow with the size of the element: 4px for chips, status labels and small icon buttons; 6px for buttons; 7px for the brand mark; 8–9px for cards and the input frame; 12px for dialogs; fully round for the risk meter, toggles, and the theme switcher. Borders are 1px hairlines. Accents use thicker rules: a 2px underline on the active tab, a 3px top border on the risk summary, a 3px left rule on evidence, and a 4px left rule on the incomplete-analysis notice.

## Components

### Buttons
- **Shape:** gently rounded (6px).
- **Primary:** steel-blue fill, white uppercase DM Sans 700 at 14px with 0.035em tracking, 53px minimum height, 25px side padding. Arrows (→) mark onward actions.
- **Hover / Focus:** deep steel-blue fill, 1px upward lift, and the button-lift shadow. Disabled buttons drop to the border color with muted text and no lift.
- **Secondary / Paste:** white or surface fill, input-rule border, slate text, 45px height, with a paper-soft hover.

### Status chips
- **Style:** 4px corners, 4px × 8px padding, 12px bold text, full-strength hue on a pale tint of the same hue: supported (pine), needs verification (ochre), contradicted (brick).

### Cards / Containers
- **Corner Style:** 8px (9px for the "How it works" step cards).
- **Background:** paper (night-surface in dark theme).
- **Shadow Strategy:** ambient card (see Elevation & Depth).
- **Border:** 1px input-rule. The risk summary adds a 3px status-colored top border.
- **Internal Padding:** 22–41px.

### Inputs / Fields
- **Style:** a large framed area (238px minimum height) with 8px corners, a 1px input-rule border, the ambient card shadow, and a borderless 17px DM Sans field inside. URL and Text tabs sit above as uppercase labels with a 2px steel-blue underline on the active tab.
- **Focus:** the frame border shifts to focus blue and gains the 3px steel-blue halo.
- **Error:** a brick-red 13px message below the frame.

### Navigation
- **Style:** a brand lockup (theme-aware logo image) on the left, and DM Sans 600 14px links in fog gray on the right that turn steel blue on hover or when active. The theme switcher (Light / System / Dark) is a fully rounded pill on paper-soft that shows drawn SVG icons at rest. The selected option lifts onto the surface with a soft shadow, its icon turns and takes the accent color, and its label unfolds beside it (0.22, 1, 0.36, 1 ease-out; static under reduced motion). On mobile, nav wraps to a full-width second row and the switcher stays icon-only.

### Risk Summary (signature)
A two-column card. On the left is a large Manrope score numeral ("/ 100") with a label; on the right is a thin, fully rounded 10px meter. A 3px status-colored top border carries the level. It always comes with an explanatory note, and when analysis is incomplete, an ochre-ruled notice saying so.

## Do's and Don'ts

### Do:
- **Do** route every color through the theme custom properties (`--bg`, `--surface`, `--text`, `--accent`, and so on) so light, dark and system themes stay in sync.
- **Do** keep steel blue as the only action color, and keep status hues as tinted chips, thin rules or borders.
- **Do** pair every score or status with plain-language explanation nearby.
- **Do** keep the soft cool-tinted shadows (`0 8px 24px rgba(21, 43, 67, 0.07)`) for resting cards.
- **Do** open sections with an uppercase steel-blue overline over a Manrope heading.

### Don't:
- **Don't** use alarmist warning styling: no full-bleed red, flashing, siren icons, or danger banners for risk.
- **Don't** use sci-fi "AI" styling: no neon gradients, glowing orbs, grid-glow backgrounds, or futuristic chrome.
- **Don't** hard-code hex values in components that already have a theme token.
- **Don't** use hard or black resting shadows.
