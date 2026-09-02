# GlassBox Frontend

Next.js 15 (App Router) rebuild of the glass trading dashboard, tokens ported 1:1 from
`C:\Users\shrey\Downloads\Glassbox\GlassBox_Complete_v3(1).html` (`tailwind.config.ts` +
`app/globals.css`) and the onboarding flow from the same file's Step 0-3 markup
(`components/onboarding/*`).

## Run

```bash
npm install
cp .env.local.example .env.local   # point at your FastAPI backend
npm run dev
```

Opens on http://localhost:3000.

## Backend contract

- REST: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) — see
  `../backend/openapi.yaml` for the full contract ported from
  `dashboard/DASHBOARD_PRO.py`.
- WebSocket: `NEXT_PUBLIC_WS_URL` (default `ws://localhost:8000/ws/signals`) — consumed by
  `components/SignalTicker.tsx`. Expects newline-delimited JSON frames shaped like
  `{ ticker, signal, agent, timestamp }`.

## Structure

- `app/layout.tsx` — glass chrome shell (nav + fonts), server component.
- `app/page.tsx` — dashboard home; currently one live island (`SignalTicker`).
- `app/onboarding/page.tsx` — 4-step onboarding (`OnboardingFlow`), all client-side state,
  not yet wired to a backend `POST /api/onboarding`.
- `components/onboarding/*` — one component per step (concern, portfolio, verify, alerts),
  faithful to the source mockup's copy and interaction states.
- `lib/queryClient.tsx` — TanStack Query provider, ready for REST reads once endpoints exist.

## Not done yet

- No auth/JWT wiring (Phase 1/4 in the plan).
- Dashboard home only has the signal ticker island — Portfolio/Watchlist/Reports pages from
  Phase 2 aren't built.
- Onboarding doesn't persist — `complete()` in `OnboardingFlow.tsx` just redirects; needs a
  real POST once the backend route exists.
