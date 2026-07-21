---
version: alpha
name: netbox-scribe Interface
description: Project-local visual baseline for any future UI surface.
extends: project-local operational interface baseline
colors:
  background: "#0A0D0B"
  background-elevated: "#0D1117"
  surface: "#111511"
  surface-raised: "#161B22"
  surface-card: "#1C2128"
  border: "#263026"
  border-strong: "#30363D"
  text: "#D8E0D5"
  text-muted: "#A8B995"
  text-bright: "#F0F6EC"
  primary: "#8FAF6A"
  warning: "#C79545"
  danger: "#A3473E"
  info: "#6F9A9A"
typography:
  body:
    fontFamily: Inter, Geist, IBM Plex Sans, system-ui, sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: JetBrains Mono, IBM Plex Mono, SFMono-Regular, Consolas, monospace
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.35
rounded:
  sm: 4px
  md: 6px
  lg: 8px
  xl: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
components:
  page:
    backgroundColor: "{colors.background}"
    textColor: "{colors.text}"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: 12px
  card:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: 12px
---

# netbox-scribe Interface

## Overview

This project uses a low-light operational baseline: graphite surfaces, moss primary actions, amber warnings, muted red danger states, readable typography, and operational density.

Use this file for project-specific deviations only. Keep the common path obvious and dangerous controls explicit.

## Density

Default to dashboard/tool density: compact panels, readable tables/lists/logs, and minimal decorative whitespace. If this project is primarily long-form reading, loosen spacing for prose while keeping controls compact.

## Components

- Primary actions: moss.
- Warning or delayed actions: amber.
- Destructive actions: muted red and visually separated.
- Metadata, timestamps, hostnames, IDs, and logs: monospace only where precision helps scanning.
- Empty, loading, and error states should be styled, not browser defaults.

## Verification

Before merging UI work:

1. Lint this file: `npx -y @google/design.md lint DESIGN.md`.
2. Load the UI in a browser.
3. Check contrast, focus states, empty/loading/error states, and narrow viewport behavior.
4. Run the project's normal test/lint gate.
