# Design reference source files

The original HTML mockups this build was implemented against, preserved
here so future work can check exact copy/behavior against the source
instead of depending on files in a local Downloads folder. **Static
reference only** — these are not served by the app and not linked from
any route; nothing here is live.

| File | What it supplied | Built as |
|---|---|---|
| `GlassBox_Complete_v3.html` | Public marketing landing page: hero, demo card, discrepancy stat band, "How it Works" 3-card explainer, social proof, 3-tier pricing, footer | `frontend/app/(marketing)/` — live |
| `GlassBox_Reference.html` | Authenticated app-shell: sidebar nav (active-link indicator, admin/user link groups), topbar, glass design tokens (colors/radii/shadows — identical values to what's already in `frontend/tailwind.config.ts`) | `frontend/components/AppShell.tsx` — live |
| `GlassBox_Pilot_Production.html` | Extends the landing page: Strategy Lenses (investor-archetype cards), "ML Provenance" section, sliding agent/lens marquee banner, 5-star score-review widget. Carries the legal disclaimer for Strategy Lenses (see below) | Phase 11 — see `docs/PROJECT_STATUS.md` |
| `GlassBox_Lenses_Interactive.html` | The exact interactive spec for Strategy Lenses: full 8-persona data (name/firm/strategy/track-record/growth-risk/story quote), 3D CSS carousel mechanics, filter chips, typewriter speech bubble, autoplay/drag/keyboard nav | Phase 11 |

## Strategy Lenses — mandatory disclaimer

`GlassBox_Pilot_Production.html` carries this disclaimer for the 8
investor-archetype "lenses" (modeled on Buffett, Lynch, Griffin, Dalio,
Simons, Englander, Shaw, Soros). **Any implementation of this feature
must ship it prominently, not buried in a footer:**

> These are original AI archetypes inspired by publicly known investment
> philosophies. They are NOT affiliated with, endorsed by, or representing
> any named investor. Portraits are original illustrations, not likenesses.

## Design tokens

All four files share one CSS custom-property palette (`--c-bg`, `--c-teal`,
`--r1`–`--r4`, `--sh-*`, the `--ease` cubic-bezier, etc.) — this is already
ported into `frontend/app/globals.css` and `frontend/tailwind.config.ts`.
Reuse those existing Tailwind classes/utilities when implementing anything
from these files; don't re-port colors from scratch.
