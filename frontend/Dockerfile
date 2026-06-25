FROM node:20-alpine
RUN npm install -g pnpm
WORKDIR /app
COPY package.json .
RUN pnpm install --no-frozen-lockfile
COPY . .
EXPOSE 3000
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
