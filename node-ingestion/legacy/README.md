# Legacy dashboard (superseded)

`index.html` here is the original **self-contained, no-build dashboard**
(Phase 8 — see `JOURNEY.md`): hand-written HTML/CSS/inline-SVG charts driven
by `EventSource`, served straight out of `node-ingestion/public/`.

It was replaced by the React dashboard in `node-ingestion/dashboard/`
(Phase 13), whose static export is what now populates `public/`. Kept here
because it's a working reference for the SSE contract and the chart shapes,
and because `scripts/copy-dashboard-build.mjs` wipes `public/` on every build.

It is **not served** and **not built**. To look at it, open the file directly
in a browser (the API calls will only resolve if `node-ingestion` is running
on `http://localhost:3000`).
