import type { NextConfig } from 'next';

// Static export: this dashboard is a pure client that talks to the
// node-ingestion Fastify API (no server-side rendering or API routes of its
// own needed). `npm run build` emits plain HTML/CSS/JS into `out/`, which is
// copied into node-ingestion's `public/` and served by its existing
// `@fastify/static` — no second Node process to run in production.
const nextConfig: NextConfig = {
  output: 'export',
  reactStrictMode: true,
  images: { unoptimized: true }, // next/image's optimizer needs a server; static export has none
  trailingSlash: true, // so `/run` resolves to `/run/index.html` under static file serving
  turbopack: { root: process.cwd() }, // avoid misdetecting node-ingestion's lockfile as the workspace root
};

export default nextConfig;
