FROM node:20-alpine
RUN npm install -g pnpm
WORKDIR /app
COPY package.json .
RUN pnpm install --no-frozen-lockfile
COPY . .
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
