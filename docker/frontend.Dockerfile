# NOT YET BUILD-TESTED — no Docker Desktop available in the dev environment
# this was written in (see PROGRESS.md "Known limitations").

FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
