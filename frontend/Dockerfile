# ── Stage 1: Build ──────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

COPY . .

# Build for production
RUN npm run build

# ── Stage 2: Serve ───────────────────────────────────────────────
FROM node:20-slim AS runner

WORKDIR /app

COPY --from=builder /app/.output /app/.output

EXPOSE 3000

ENV NODE_ENV=production
ENV NITRO_HOST=0.0.0.0
ENV NITRO_PORT=3000

CMD ["node", "/app/.output/server/index.mjs"]
