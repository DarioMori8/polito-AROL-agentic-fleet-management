# Built with the repo root as context (see docker-compose.yml).

# --- STAGE 1: Build the static assets ---
FROM node:20-alpine AS builder
WORKDIR /app

# Copy dependency manifests first for efficient layer caching
COPY frontend/package*.json ./
RUN npm ci

# Copy source files and configuration
COPY frontend/ .

# Build the application with production optimizations
RUN npm run build

# --- STAGE 2: Serve with lightweight, rugged Nginx server ---
FROM nginx:1.25-alpine
WORKDIR /usr/share/nginx/html

# Clean default static assets
RUN rm -rf ./*

# Copy built static files from Stage 1
COPY --from=builder /app/dist .

# Copy custom Nginx configuration to support client-side routing redirects (SPA)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]