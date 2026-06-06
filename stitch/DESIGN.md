---
name: DevLens
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#c7c4d7'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#c0c1ff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#494bd6'
  secondary: '#adc6ff'
  on-secondary: '#002e6a'
  secondary-container: '#0566d9'
  on-secondary-container: '#e6ecff'
  tertiary: '#ffb783'
  on-tertiary: '#4f2500'
  tertiary-container: '#d97721'
  on-tertiary-container: '#452000'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#ffdcc5'
  tertiary-fixed-dim: '#ffb783'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#703700'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  container-padding-desktop: 32px
  container-padding-mobile: 16px
  gutter: 16px
  stack-gap-sm: 8px
  stack-gap-md: 16px
  stack-gap-lg: 24px
---

## Brand & Style
The design system is engineered for high-density technical assessment and recruitment analytics. It adopts a **Corporate / Modern** aesthetic with a focus on precision, technical authority, and clarity. The interface prioritizes data-heavy layouts while maintaining a sophisticated, calm atmosphere to facilitate complex decision-making.

The visual language utilizes a "Deep Navy" foundation to reduce eye strain during prolonged evaluation sessions. The style avoids unnecessary decoration, relying instead on systematic color-coding and structured information hierarchy to convey developer proficiency at a glance.

## Colors
The palette is rooted in a deep navy spectrum to provide a professional, low-fatigue environment. 

### Semantic Scoring
The most critical aspect of the design system is the 5-tier score band system. These colors must be used consistently across progress bars, score rings, and status badges to indicate developer performance levels:
- **Elite (90-100):** Purple (#a855f7) – Represents top-tier talent.
- **Strong (80-89):** Blue (#3b82f6) – High confidence hires.
- **Good (70-79):** Green (#10b981) – Competent, ready for technical rounds.
- **Moderate (55-69):** Amber (#f59e0b) – Requires further vetting or specific training.
- **Critical (0-54):** Red (#ef4444) – Does not meet minimum technical requirements.

Primary actions use **Indigo (#6366f1)** to differentiate navigational and functional elements from assessment data.

## Typography
This design system utilizes **Inter** for all UI elements to ensure maximum legibility and a neutral, professional tone. A secondary monospaced font, **JetBrains Mono**, is introduced specifically for code snippets, technical IDs, and raw data metrics to emphasize the platform's developer-centric nature.

Hierarchy is maintained through weight and slight shifts in scale rather than drastic size changes, keeping the interface compact. "Label-caps" are used for section headers within cards and property labels to provide clear visual anchors in data-dense views.

## Layout & Spacing
The layout follows a **Fixed Grid** philosophy for dashboard screens to maintain predictable data visualization containers. A 12-column system is used for the main content area, while a persistent 240px sidebar handles primary navigation.

Spacing is tight and systematic, built on a **4px base unit**. Dashboards use 16px gutters between cards to maximize information density without sacrificing clarity. On mobile devices, the layout reflows to a single column with reduced horizontal padding (16px).

## Elevation & Depth
Depth in this design system is achieved through **Tonal Layers** rather than heavy shadows. 

- **Level 0 (Background):** The base application canvas (#0f172a).
- **Level 1 (Cards/Sidebar):** Raised surfaces (#1e293b). These use a subtle 1px border (#334155) to provide definition against the background.
- **Level 2 (Modals/Popovers):** Elevated overlays (#334155) with a soft, 15% opacity black shadow to create separation.

Interactive elements (buttons/active tabs) use a subtle inner glow or a higher-contrast border to signify focus without breaking the flat, technical aesthetic.

## Shapes
The shape language is disciplined and geometric. A standard **8px (0.5rem)** radius is applied to all primary containers and cards, striking a balance between modern friendliness and professional structure.

Buttons and input fields share this 8px radius to maintain consistency. Smaller elements like tags, status chips, and score indicators may use a fully rounded (pill) shape to distinguish them from structural UI components.

## Components
### Buttons & Inputs
- **Primary Button:** Solid Indigo (#6366f1) with white text. 8px radius.
- **Input Fields:** Surface-2 background with a 1px border. Focus state uses a 2px Indigo border and a subtle outer glow.

### Assessment Indicators
- **Progress Bars:** Dual-tone. A dark track (#334155) with a filled portion using the Score Band colors.
- **Score Rings:** Circular gauges with a 4px stroke width. The center of the ring displays the numerical score in a bold font.
- **Status Chips:** Small, pill-shaped badges with low-opacity backgrounds and high-opacity text, color-coded to the performance bands.

### Cards & Navigation
- **Detail Cards:** Used for "Strengths" and "Gaps." These include an icon, a Title-sm heading, and Body-sm description text.
- **Tabbed Interfaces:** Horizontal tabs with a bottom-aligned Indigo indicator for active states. Unselected tabs use a muted gray text color to de-emphasize secondary options.