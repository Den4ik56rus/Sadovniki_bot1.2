# Stage 1: Сборка admin-webapp
FROM node:20-alpine AS webapp-build

WORKDIR /app

COPY admin-webapp/package.json admin-webapp/package-lock.json ./
RUN npm ci

COPY admin-webapp/ ./

# Base path = / для серверного деплоя (не /Sadovniki_bot1.2/ как на GitHub Pages)
ENV VITE_BASE_PATH=/
RUN npm run build

# Stage 2: Nginx с собранной статикой
FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx/.htpasswd /etc/nginx/.htpasswd
COPY --from=webapp-build /app/dist /usr/share/nginx/html

EXPOSE 80
