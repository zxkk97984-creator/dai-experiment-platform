ARG DAI_FRONTEND_NODE_BASE_IMAGE=node:20-alpine
FROM ${DAI_FRONTEND_NODE_BASE_IMAGE} AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

ARG DAI_FRONTEND_NGINX_BASE_IMAGE=nginx:alpine
FROM ${DAI_FRONTEND_NGINX_BASE_IMAGE}
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
