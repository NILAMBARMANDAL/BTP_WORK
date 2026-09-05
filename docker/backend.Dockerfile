# NOT YET BUILD-TESTED — no Docker Desktop available in the dev environment
# this was written in (see PROGRESS.md "Known limitations"). Written to the
# best of our knowledge of the Node/Express setup in backend/; verify on first
# real Docker build and fix anything that doesn't work rather than trusting
# this blindly.

FROM node:24-slim AS base
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY src ./src

ENV NODE_ENV=production
ENV MONGO_MODE=uri
EXPOSE 4000

CMD ["node", "src/server.js"]
