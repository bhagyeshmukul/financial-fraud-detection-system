# Build browser assets with Node, then serve them from an unprivileged Nginx image.
FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

# Final serving stage needs built assets and the gateway, rather than Node tooling.
FROM nginxinc/nginx-unprivileged:1.28-alpine
USER root
RUN apk add --no-cache apache2-utils
COPY deploy/nginx.conf.template /etc/nginx/templates/default.conf.template
# Startup hashes the login password; no plaintext credential is baked into the image.
COPY deploy/auth.sh /docker-entrypoint.d/25-auth.sh
RUN chmod +x /docker-entrypoint.d/25-auth.sh
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
