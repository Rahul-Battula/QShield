# QShield dashboard

The Phase 6 command centre: a **Vite + React 18 + TypeScript** single-page app,
styled with **Tailwind CSS** and charted with **Recharts**. It is a pure
presentation layer over the backend's JSON API — every view is a thin render of
one or more `/api/...` endpoints.

## Layout

- `index.html` — the shell (loads Inter + JetBrains Mono, mounts `#root`).
- `src/main.tsx` — React entry point.
- `src/App.tsx` — the seven tabs (Overview, Discovery, Risk, Threat, Quantum
  Lab, Benchmark, Migrate).
- `src/pages/` — one file per tab.
- `src/components/` — `Layout`, shared `ui` primitives (panels, tables, sliders,
  pills), and the Recharts wrappers in `charts.tsx`.
- `src/lib/` — `api.ts` (typed `get`/`post`) and `hooks.ts` (`useAsync`).
- `tailwind.config.js` — the design tokens (dark "ink" ramp, blue brand accent,
  severity colours).

## Running it

### Served by the backend (normal case)

The backend serves the built app at `/`:

```
npm install        # once
npm run build      # emits ./dist  (committed, so this is optional)
python -m app.api  # then open http://127.0.0.1:8000/
```

`dist/` is committed to the repository so the dashboard runs offline with no
build step. `app.config.frontend_dir()` serves `dist/` when it exists and falls
back to [`../frontend-legacy/`](../frontend-legacy/) otherwise. Override the
location with the `QSHIELD_FRONTEND` environment variable.

Vite is configured with `base: "/static/"` because the backend mounts this build
under `/static`; keep that in `vite.config.ts` if you change the mount point.

### Live dev server

```
python -m app.api        # backend on :8000
npm run dev              # dashboard on :5173, proxies /api -> :8000
```

## After changing the UI

Run `npm run build` and commit the regenerated `dist/` so the offline copy stays
in sync. `npm run build` runs `tsc -b` first, so a type error fails the build.
