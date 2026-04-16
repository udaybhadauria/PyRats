FROM node:18-alpine AS builder

WORKDIR /app
COPY . .
RUN npm install
RUN npm run build 2>/dev/null || true

FROM nginx:alpine

# Copy frontend files
COPY --from=builder /app /usr/share/nginx/html

# Copy nginx config
RUN echo 'server { listen 80; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
