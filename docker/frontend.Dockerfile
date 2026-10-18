# ---- build the React app ----
FROM node:22-alpine AS build
WORKDIR /app

COPY vero-app/package*.json ./
# Uses the lockfile when it exists (commit it after your first npm install), else installs fresh
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY vero-app/ ./
# The Google Client ID is public. It is baked into the build.
ARG GOOGLE_CLIENT_ID=""
ENV GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
RUN npm run build

# ---- serve with nginx and proxy /api to the backend ----
FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80