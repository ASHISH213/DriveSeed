# DESIGN.md: UI/UX and motion spec

Goal: a modern, premium-feeling interface with purposeful animation that stays fast (60 fps), accessible and identical across the main app and the Colab edition. Use the tokens below; do not hard-code colours, sizes or timings in components.

## 1. Principles
1. One primary action per screen (the add box on the dashboard).
2. Every animation explains a change of state (added, progressing, finished, moved).
3. Instant feedback: optimistic updates, skeletons instead of spinners.
4. Calm by default, delightful at key moments (add, complete, play).
5. Keyboard friendly and reduced-motion friendly.

## 2. Design tokens (CSS variables)
Put in `frontend/src/styles/tokens.css` and map into `tailwind.config`.

```css
:root {
  /* colour: dark theme (default) */
  --bg:            #0B0D12;
  --bg-elevated:   #12151C;
  --surface:       rgba(255,255,255,0.04);
  --surface-hover: rgba(255,255,255,0.07);
  --border:        rgba(255,255,255,0.08);
  --text:          #E8EAF0;
  --text-muted:    #9AA3B2;
  --accent-1:      #8B5CF6;   /* violet */
  --accent-2:      #22D3EE;   /* cyan */
  --accent-grad:   linear-gradient(135deg, var(--accent-1), var(--accent-2));
  --success:       #34D399;
  --warning:       #FBBF24;
  --danger:        #F87171;

  /* shape and depth */
  --radius-sm: 8px;  --radius-md: 12px;  --radius-lg: 16px;  --radius-xl: 24px;
  --shadow-1: 0 1px 2px rgba(0,0,0,.4);
  --shadow-2: 0 8px 24px rgba(0,0,0,.35);
  --glow:     0 0 0 1px rgba(139,92,246,.4), 0 0 24px rgba(139,92,246,.25);
  --blur:     saturate(140%) blur(16px);

  /* spacing: 4px grid */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px;

  /* type */
  --font-ui:   "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

:root[data-theme="light"] {
  --bg: #F7F8FB;  --bg-elevated: #FFFFFF;
  --surface: rgba(15,23,42,0.04);  --surface-hover: rgba(15,23,42,0.07);
  --border: rgba(15,23,42,0.10);
  --text: #0F172A;  --text-muted: #5B6475;
}
```
The accent colour is user-selectable (violet default); store it as `--accent-1` and keep `--accent-2` derived or paired.

## 3. Typography
- UI font: Inter. Numbers (speed, size, ETA, percentages): JetBrains Mono with tabular numerals so values do not jitter.
- Scale: 12 / 14 / 16 / 20 / 24 / 32 / 48 px; headings semi-bold, body regular, line height 1.5.

## 4. Motion tokens
Create `frontend/src/lib/motion.ts` and use only these.

| Token | Value | Use |
|---|---|---|
| `duration.fast` | 150 ms | hover, press, toggles |
| `duration.base` | 250 ms | cards, menus, modals |
| `duration.slow` | 400 ms | page and shared-element transitions |
| `ease.out` | `cubic-bezier(0.22, 1, 0.36, 1)` | most transitions |
| `spring.soft` | stiffness 220, damping 26 | cards, list reorder |
| `spring.snappy` | stiffness 400, damping 30 | buttons, small controls |
| `stagger` | 40 ms per item (max 12 items) | list and tree reveals |

Rules: animate only `transform` and `opacity` (plus `filter` sparingly); animations must be interruptible; honour `prefers-reduced-motion` by replacing movement with a quick fade (a single `useReducedMotion` check in the motion helpers).

## 5. Screens and components

**Screens:** Login, Dashboard, File selection (modal), Library, Player, Settings.

**Core components:** `AppShell` (glass header, storage ring), `AddBox`, `TaskCard`, `ProgressBar`, `SpeedSparkline`, `FileTree` (checkboxes), `FolderPicker`, `LibraryGrid/List`, `FileItem`, `ContextMenu`, `CommandPalette`, `PlayerShell`, `StorageRing`, `Toast`, `EmptyState`, `Skeleton`.

## 6. Signature animations
| Moment | Behaviour |
|---|---|
| Paste magnet in `AddBox` | Input border glows with `--glow`; on submit the text morphs into a new `TaskCard` that slides in (layout animation) |
| Fetching metadata | Skeleton shimmer in the card; then the `FileTree` rows reveal with `stagger` |
| Downloading | `ProgressBar` filled with `--accent-grad` plus a moving sheen; speed and ETA use an animated number ticker; `SpeedSparkline` redraws live |
| Uploading to Drive | Small "cloud → Drive" path animation next to the bar while upload progress runs; bar colour shifts slightly to mark the new phase |
| Completed | Checkmark draws itself (SVG path), short confetti burst (≤ 600 ms, ≤ 40 particles), card settles; completion toast |
| Library view switch | Shared-layout animation between list and grid |
| Library items | Staggered entrance, hover lift (`translateY(-2px)` + `--shadow-2`) |
| Open a file | Thumbnail expands into the player (shared-element transition, `duration.slow`) |
| Player | Controls fade after 2.5 s idle; scrub-bar hover preview; double-click/tap skip ripple; ambient backdrop tinted from the poster's dominant colour |
| Storage ring | Animated radial stroke; colour moves success → warning → danger as space fills |
| Toasts | Slide in/out; "Undo" shows a countdown ring |
| Empty and error states | Lottie illustration with a gentle idle loop |
| Page transitions | `AnimatePresence` cross-fade + 8 px slide, `duration.base` |

## 7. Interaction and UX features
- P0: skeleton loading, optimistic UI, undo for delete/move, drag-and-drop to add torrents and to move files.
- P1: command palette (Ctrl/Cmd+K), keyboard shortcuts, right-click menus, marquee multi-select, installable PWA, finish notifications, theme and accent picker.
- P2: onboarding tour, poster/metadata enrichment, picture-in-picture and persistent mini-player.

## 8. States to design for every screen
Loading (skeleton), empty, error (with retry), offline, "Drive almost full", "Drive full", "Drive disconnected", and long-running/paused states.

## 9. Accessibility
Colour contrast at least WCAG AA; visible focus rings (use `--glow`); all controls reachable by keyboard; ARIA labels for icon buttons; player supports space/arrow/F/M/C shortcuts; reduced-motion mode.

## 10. Performance budget
- Initial JS ≤ 250 KB gzipped; player, Lottie and confetti lazy-loaded.
- Largest Contentful Paint ≤ 2.0 s on a mid-range phone over 4G.
- No layout shift from animations; Lighthouse performance ≥ 90.
- Test on a mid-range Android device, not only a desktop.

## 11. Shared with the Colab edition
The built frontend bundle is reused as-is. Components must not assume multi-user features: hide them based on `GET /api/capabilities` (e.g. `{ "torrents": false, "streaming": "drive-handoff", "multiUser": false }`).
