FROM node:20-alpine
RUN npm install -g pnpm
WORKDIR /app
COPY package.json .
RUN pnpm install --no-frozen-lockfile
COPY . .

# VITE_API_URL must be baked at build time — Vite replaces import.meta.env.VITE_*
# statically during the build step. Declare it as a build ARG so Railway (and any
# CI) can pass it in. Without this, the bundle falls back to localhost:8000.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN pnpm build
EXPOSE 3000
CMD ["sh", "-c", "node_modules/.bin/vite preview --host 0.0.0.0 --port ${PORT:-3000}"]
