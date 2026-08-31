# AFIE Dashboard

A React (Next.js) dashboard for the Agentic Field-Data Inversion Engine —
covers all 13 methods, live run monitoring via SSE, run history, an Upload
Data page (bring your own CSV/JSON/zip, with an opt-in AI Cleaning Agent for
messy data), and the multi-method Joint Interpretation capstone. Built on a
modern production stack (Next.js, TypeScript, Ant Design, Tailwind CSS,
Zustand, TanStack Query) with an independently designed color palette and
typography — no code, tokens, or assets from any employer's proprietary
codebase.

## Running in dev

```bash
cp .env.example .env.development.local   # point NEXT_PUBLIC_API_URL at node-ingestion
npm install
npm run dev                              # http://localhost:3001 (or whatever port is free)
```

> Deliberately **not** `.env.local`: Next also loads `.env.local` during
> `next build`, which would bake this absolute dev URL into the production
> bundle (see `DESIGN.md` §14.4 for the live bug this caused).

Requires `node-ingestion` (and `python-agent`) already running — see the
root `README.md`.

## Building for production

```bash
npm run build   # static export to ./out
```

`node-ingestion`'s own `npm run build` copies `dashboard/out/*` into its
`public/` directory (see `node-ingestion/package.json`), so the whole
dashboard is served by the existing Fastify `@fastify/static` — no second
Node process needed in production.

## Structure

- `pages/` — Overview, Run a Method, Upload Data, History, Site Reports, and
  `/runs` (single-run detail) (Next.js Pages Router). Page names must not
  collide with `node-ingestion`'s API routes — they share one origin, and
  Fastify wins. That is why run detail is `/runs`, not `/results`.
- `lib/uploadParsing.ts` — client-side CSV/JSON/zip parsing for `/upload`.
  Pure functions (no DOM/React), so they're unit-testable directly with
  `tsx`. Submits through the real `POST /ingest/field-data` — the same
  endpoint hardware uses — not a separate upload-specific route.
- `services/cleaning.ts` — calls `POST /clean/raw-data`, the opt-in AI
  Cleaning Agent for messy raw uploads (unlabeled columns, outlier spikes,
  drift, mixed units). Unlike every other LLM-backed feature here, this one
  requires `GEMINI_API_KEY` server-side with no offline fallback — see
  `DESIGN.md` §14.7 for why.
- `components/` — `layout/` (shell/nav), `common/` (badges, stat tiles),
  `charts/` (Recharts wrappers), `method/` (run/model/interpretation display),
  `site/` (site history, note editor, joint report), `upload/` (method
  picker and AI-cleaning report card for `/upload`)
- `services/` — typed API calls (axios)
- `store/` — Zustand store fed by the `/events` SSE stream
- `constants/methods.ts` — display metadata for all 13 methods (formulas,
  references, params) — presentational, mirrors
  `python-agent/app/agent/methods/specs/*.py`
- `lib/theme/` — Ant Design `ConfigProvider` theme (light/dark), driven by
  Tailwind's `resolveConfig` off this project's own token set in
  `tailwind.config.ts`
