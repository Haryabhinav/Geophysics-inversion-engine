# Agentic Multi-Physics Geophysical Inversion Platform

A two-package monorepo that automates geophysical data inversion across
**13 methods** (TDEM, electrical resistivity, gravity, magnetics,
magnetotellurics, seismic refraction, seismology, radiometrics, borehole
lithology classification, GPR, induced polarization, self-potential, and
geodetic deformation). A Node.js layer ingests noisy field data and streams
it over a WebSocket to a Python FastAPI backend, where a classical solver
(the primary, reliable path — see `JOURNEY.md` Phase 11 for why) or an LLM
agent (Gemini) iteratively fits a forward model until it matches the
observations. A per-method **Interpretation Agent**, and a multi-method
**Joint Interpretation** capstone, then read the numeric result — plus
optional site context and other methods' results — to produce a
natural-language geological interpretation.

See [`spec.md`](./spec.md) for the specification, [`DESIGN.md`](./DESIGN.md) for
the full architecture and data flow, and [`JOURNEY.md`](./JOURNEY.md) for the
**step-by-step story of how it was built** (what we did first, then next, and why).

```
Project1/
├── spec.md                     # Technical specification
├── node-ingestion/             # Step 1 — TypeScript / Fastify ingestion layer
│   ├── src/
│   │   ├── server.ts           # Fastify HTTP server + /ingest/field-data
│   │   ├── ws-client.ts        # Reconnecting WebSocket client (buffered)
│   │   ├── sanitize.ts         # Drops NaN / null / non-finite samples
│   │   ├── methods.ts          # Per-method synthetic-truth generators
│   │   ├── db.ts / siteNotes.ts / chatHistory.ts / siteReports.ts
│   │   │                      # Postgres stores (+ in-memory fallbacks)
│   │   ├── config.ts           # Env-driven config
│   │   └── types.ts            # SensorPayload / AgentJobPayload
│   ├── dashboard/              # React (Next.js) dashboard — see §Dashboard
│   ├── public/                 # GENERATED: dashboard static export (git-ignored)
│   ├── package.json
│   └── tsconfig.json
└── python-agent/               # Step 2 — FastAPI / WebSocket agent backend
    ├── app/
    │   ├── main.py             # FastAPI app + /ws/inversion-stream
    │   ├── agent/methods/      # MethodSpec registry — one file per method
    │   ├── schemas.py          # Pydantic models
    │   └── config.py           # Env-driven settings
    └── requirements.txt
```

## Quick start (Docker)

```bash
cp .env.example .env          # set GEMINI_API_KEY, or keep AGENT_MODE=offline
docker compose up --build     # postgres + sandbox + python-agent + node-ingestion
python simulate_hardware.py   # drive the running stack
```

The converged model is persisted to Postgres and an alert is logged (see
[`DESIGN.md` §8](./DESIGN.md) for the service topology). For running the
services directly (no Docker), see "Running (local)" below.

## Build status

- [x] **Step 1** — Node.js ingestion layer (Fastify, sanitization, resilient WS client)
- [x] **Step 2** — FastAPI WebSocket server (Pydantic validation)
- [x] **Step 3** — LLM sandbox execution tool (`tools/sandbox.py`)
- [x] **Step 4** — Agentic inversion loop (`app/agent/`)
- [x] **Step 5** — End-to-end hardware simulator (`simulate_hardware.py`)
- [x] **Persistence + alerts** — Postgres (`db.ts`) + user alert (`alert.ts`)
- [x] **Containerization** — `docker-compose` with an isolated sandbox container
- [x] **Dashboard** — served web UI with live SSE updates (originally a
      single-file `public/index.html`; superseded below)
- [x] **Interpretation Agent** — reads the converged model + equivalence set +
      an optional site note, produces a natural-language interpretation
      (`app/agent/interpreter.py`, `POST /context/:siteId`) — see `DESIGN.md` §12
- [x] **Multi-physics platform** — 13 methods behind a `MethodSpec` registry
      (ERT, gravity, magnetics, MT, seismic, seismology, radiometrics,
      borehole lithology classification, GPR, IP, SP, Mogi deformation) +
      the multi-method **Joint Interpretation** capstone
      (`POST /sites/:siteId/interpret`) — see `DESIGN.md` §13
- [x] **React dashboard** — Next.js / TypeScript / Ant Design / Tailwind /
      Zustand / TanStack Query / Recharts, covering all 13 methods, live SSE
      run monitoring, run history, and site reports. Statically exported and
      served by the existing Fastify server — see `DESIGN.md` §14
- [x] **Site Chat Agent + auto-generated Site Reports** — a per-site
      conversational Q&A agent over that site's own run/interpretation
      history (`POST /sites/:siteId/chat`), and an LLM-drafted markdown site
      report with print/PDF export (`POST /sites/:siteId/report`), both
      persisted to Postgres and surfaced as tabs on the Site Reports page —
      see `DESIGN.md` §15

## Dashboard

The Node server serves a **React dashboard** at **http://localhost:3000/** —
covering the whole platform:

| Page | What it does |
|---|---|
| **Overview** | Fleet stats, quick-launch methods, live activity feed |
| **Run a Method** | Pick any of the 13 methods (searchable, grouped by family), see its physics reference and inverted parameters, run a synthetic job, watch it converge live |
| **Upload Data** | `/upload` — submit your OWN field data (CSV/JSON/zip) through the real `POST /ingest/field-data` path. Optional **AI Cleaning Agent** for genuinely messy data (unlabeled columns, outlier spikes, baseline drift, mixed units) — see `DESIGN.md` §14.7. Requires `GEMINI_API_KEY`; there's no offline fallback for this one stage, by design. |
| **History** | Every run, filterable by method / site / status, sortable by misfit |
| **Site Reports** | A site's runs across methods, its free-text site note, and the multi-method **Joint Interpretation** — plus **Chat** (ask questions about the site's own run history) and **Report** (auto-generated markdown report, print/PDF export) tabs |
| **Run detail** | `/runs?jobId=…` — one run in full; deep-linkable. (Named `/runs`, not `/results`, so it doesn't collide with the `GET /results` API on the shared origin.) |

Updates arrive over Server-Sent Events (`GET /events`) — no polling, no page
reload. Charts (observed-vs-predicted, relative-misfit convergence) are
Recharts; the theme is light/dark with a CVD-validated palette. It works with
or without Postgres (falls back to an in-memory store). Endpoints it uses:
`POST /simulate`, `GET /results`, `GET /results/:jobId`, `POST/GET
/context/:siteId`, `POST /sites/:siteId/interpret`, `POST/GET
/sites/:siteId/chat`, `POST/GET /sites/:siteId/report(s)`, `GET /events` (SSE).

The dashboard is a **static export** (`dashboard/out`) copied into
`node-ingestion/public/` at build time and served by the existing
`@fastify/static` — there is **no second Node process** in production. See
[`node-ingestion/dashboard/README.md`](./node-ingestion/dashboard/README.md)
for its structure, and `DESIGN.md` §14 for the design rationale.

> `public/` is a **build artifact** — it is wiped and regenerated by
> `npm run build`. Don't hand-edit it. (The original no-build dashboard it
> replaced is kept for reference in `node-ingestion/legacy/`.)

`/simulate` is **mode-aware**: in `offline` mode it sends a bi-exponential curve
the offline optimizer converges on (**no API key needed** — great for testing
the UI), and with Gemini active it sends a real empymod TDEM curve for the agent
to invert.

> **Gemini free tier** is ~5 requests/min (plus a daily cap). The agent writes a
> **one-shot `scipy` inversion** (fits the model in a single sandbox run), so a
> run needs only ~1–2 API calls — comfortably within the per-minute limit. It
> also retries on 429. A heavy testing session can still hit the daily cap; then
> just use offline mode or wait for the reset.

## Agent modes

The inversion loop (`app/agent/orchestrator.py`) drives a pluggable *modeler*:

- **`GeminiModeler`** — the real agent. Gemini (2.5 Flash) authors `empymod`
  scripts and revises them from the relative-misfit feedback (retries on 429
  rate limits). Requires `GEMINI_API_KEY` and `empymod` installed.
- **`OfflineHeuristicModeler`** — a genuine derivative-free optimizer
  (Nelder–Mead over a reduced synthetic decay model) used as a **test double** so
  the whole pipeline runs with **no API key and no `empymod`**. It emits
  numpy-only code.

Selection via `AGENT_MODE` (`auto` | `llm` | `offline`); `auto` uses Gemini when
`GEMINI_API_KEY` is set, otherwise the offline optimizer.

## Running (local)

### Python agent backend

```bash
cd python-agent
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --ws-ping-interval 60 --ws-ping-timeout 120
```

> `--ws-ping-timeout 120`: some methods run a real ~50-70 iteration
> Nelder-Mead search (many real subprocess spawns) that can legitimately
> take over a minute — comfortably longer than uvicorn's default ~20s
> ping timeout, which would otherwise flag the connection as dead and
> reconnect mid-job. See `JOURNEY.md`'s multi-physics expansion phase for
> how this was found live.

### Node.js ingestion layer

```bash
cd node-ingestion
npm install
npm run dev            # API only, on :3000 (serves whatever is in public/)
```

For the **production shape** (dashboard compiled and served by Fastify):

```bash
npm run build          # tsc + Next static export -> public/
npm start              # http://localhost:3000 serves API + dashboard
```

### Dashboard (hot-reload dev loop)

Only needed when working *on* the UI — `npm run build` above is enough to
just use it:

```bash
cd node-ingestion/dashboard
cp .env.example .env.development.local   # points at node-ingestion on :3000
npm install
npm run dev                              # http://localhost:3001
```

Requires `node-ingestion` running too, since the dashboard is a pure client.

> The dev API URL lives in `.env.development.local`, **not** `.env.local`:
> Next loads `.env.local` during `next build` as well, which would bake an
> absolute `http://localhost:3000` into the production bundle that Fastify
> serves same-origin (breaking any other host or port).

### Verify the transport path

```bash
curl -X POST http://localhost:3000/ingest/field-data \
  -H "Content-Type: application/json" \
  -d '{"sensorId":"s1","dataType":"TDEM","timeSteps":[1,2,null,4],"amplitudes":[0.5,0.4,0.3,null]}'
```

## End-to-end run (Step 5)

With both servers running, drive the full pipeline with the simulator:

```bash
python simulate_hardware.py          # posts synthetic TDEM data to Node
```

Flow: hardware → Node.js (sanitize) → WebSocket → FastAPI → agent loop →
sandbox → converged model → back over the WebSocket to Node. The `202` from the
ingestion endpoint is immediate; the converged model arrives asynchronously and
is logged by both services.

To run it without an API key or `empymod`, force the offline optimizer:

```bash
# start the backend in offline mode
AGENT_MODE=offline uvicorn app.main:app --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120
```

Verified offline result (recovering a known bi-exponential truth `a1=10,
tau1=2e-3, a2=2, tau2=2e-2`): **converged to L2 ≈ 0.084 in ~103 iterations**,
recovering `a1≈9.98, tau1≈1.98e-3, a2≈2.04, tau2≈2.01e-2`.

> **Note:** run both servers from their package roots (`python-agent/`,
> `node-ingestion/`) so `app` and `tools` resolve as top-level packages.

## Tests

```bash
# Python (from python-agent/)
pip install -r requirements-dev.txt
pytest                 # all 95 tests (~3.5min, incl. slow + empymod)
pytest -m "not slow"   # fast subset

# Node (from node-ingestion/)
npm test               # Vitest sanitizer + chat/report store tests
npm run typecheck

# Dashboard (from node-ingestion/dashboard/)
npx tsc --noEmit       # typecheck
npx eslint .           # lint
```

Status: **Python 95/95**, **Node 8/8**, dashboard typecheck + lint clean, all
three compile clean. See [`DESIGN.md` §7](./DESIGN.md) for what each test
covers, [`DESIGN.md` §12](./DESIGN.md) for the Interpretation Agent,
[`DESIGN.md` §13](./DESIGN.md) for the multi-physics platform + Joint
Interpretation capstone, [`DESIGN.md` §14](./DESIGN.md) for the dashboard, and
[`DESIGN.md` §15](./DESIGN.md) for the Site Chat Agent + Site Report Generator.

> **Typechecking is not enough on its own.** `tsc` validated an
> `import { Pool } from '@types/pg'` (the type-declaration package, which has
> no runtime `index.js`) right up until the server crashed on startup with
> `ERR_MODULE_NOT_FOUND`. Boot the server as part of any verification pass —
> see `JOURNEY.md` Phase 13.
