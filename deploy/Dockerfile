# Multi-stage: build Vite SPA, serve with NGINX + /api reverse proxy config baked in image.
FROM node:22-alpine AS vite-build

WORKDIR /app

COPY cales-breathe-v2-vite/package.json cales-breathe-v2-vite/package-lock.json ./
RUN npm ci

COPY cales-breathe-v2-vite/ ./

ARG VITE_API_BASE=http://localhost/api
ENV VITE_API_BASE=${VITE_API_BASE}

ARG VITE_LINE_ADD_FRIEND_URL=https://line.me/R/ti/p/@033ikgzv
ENV VITE_LINE_ADD_FRIEND_URL=${VITE_LINE_ADD_FRIEND_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=vite-build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
