# Build context is the repo root (see docker-compose.prod.yml), so this stage
# can reach frontend/ while the conf below lives under docker/.

# ---- stage 1: compile the SPA to static files -----------------------------
FROM node:20-slim AS build
WORKDIR /app

# Lockfile first so this layer caches on dependency changes, not source edits.
# npm ci (not install) installs exactly what the lockfile pins and fails loudly
# if it has drifted from package.json — that is what you want in a release
# build, where a silent minor-version bump is a real risk.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# tsc runs first via the build script, so a type error fails the image build
# instead of shipping.
RUN npm run build

# ---- stage 2: serve ---------------------------------------------------------
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
