# Portal image: Next.js standalone server. Brands are baked in; the deployed agents (<slug>/agent.yaml) and platform.yaml are mounted
# (AGENTS_DIR, PLATFORM_FILE) until the catalog moves to the database (P2).
FROM node:26.12.0-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:26.12.0-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:26.12.0-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3100 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
COPY --from=build /app/brands ./brands
USER node
EXPOSE 3100
CMD ["node", "server.js"]
