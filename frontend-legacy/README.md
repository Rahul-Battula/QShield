# QShield dashboard (legacy, zero-build fallback)

This is the original single-file dashboard. It is **no longer the primary UI** —
that is the Vite + React + TypeScript app in [`../frontend/`](../frontend/). This
folder is kept as the fallback the backend serves when `frontend/dist/` has not
been built (for example on a machine with no Node toolchain):
`app.config.frontend_dir()` returns `frontend/dist` when it exists and this
directory otherwise.

Kept out of the Python package on purpose: the backend is a library plus a JSON
API, and this is a separate presentation layer that happens to be served from the
same process for convenience.

## What it is

- `index.html` — the shell: a stylesheet link and three `<script>` tags.
- `styles.css` — the whole design system (one accent, a neutral ramp, muted
  status colours, tabular numerals).
- `app.js` — the application: React 18 with `React.createElement` directly (no
  JSX, no build step), one view per phase (Overview, Discovery, Risk, Threat,
  Benchmark, Migrate), each a thin render over a `/api/...` endpoint.
- `vendor/` — React and ReactDOM (UMD), vendored so the page has no external
  dependency and works offline. No `npm install`, no bundler.

## Running it

The backend serves this directory:

```
python -m app.api          # then open http://127.0.0.1:8000/
```

`app.api` locates this folder through `app.config.frontend_dir()`,
which honours the `QSHIELD_FRONTEND` environment variable if you keep the files
somewhere else.

## Changing it

Edit `app.js` or `styles.css` and reload the browser — there is no build step.
If you replace this with a bundled framework later, point `QSHIELD_FRONTEND`
(or `frontend_dir()`) at the build output directory and keep the `/api`
contract.
