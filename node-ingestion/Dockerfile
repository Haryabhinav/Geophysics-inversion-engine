# ---- build stage: node-ingestion server ----
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
# build:server, not build: the root `build` script also chains the dashboard
# build, which this stage deliberately doesn't copy (it has its own stage
# below) — running it here fails on a missing ./dashboard directory.
RUN npm run build:server

# ---- build stage: React dashboard (static export) ----
FROM node:20-slim AS dashboard-build
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard ./
# Same-origin in production (see next.config.ts) — dashboard is served by
# this very server, so a relative (empty) API base URL is correct here.
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build

# ---- runtime stage ----
FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist
COPY --from=dashboard-build /app/dashboard/out ./public
EXPOSE 3000
CMD ["node", "dist/server.js"]
