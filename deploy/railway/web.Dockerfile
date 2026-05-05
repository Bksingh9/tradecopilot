# Railway-specific Web Dockerfile.
#
# Mirrors frontend/Dockerfile but uses repo-root-relative paths (Railway's
# build context is always the repo root regardless of RAILWAY_DOCKERFILE_PATH).
# All other deploy targets (compose, Render, Fly, DO, AWS) keep using
# frontend/Dockerfile unchanged.

FROM node:20-alpine AS builder
WORKDIR /app
ENV CI=true

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ .
ARG VITE_API_BASE=""
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
