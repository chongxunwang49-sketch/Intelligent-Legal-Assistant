# 智法通 V2 前端镜像（多阶段：构建 + nginx）
FROM node:20-alpine AS builder
WORKDIR /app
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm config set registry https://registry.npmmirror.com
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 80
HEALTHCHECK --interval=20s --timeout=5s --retries=6 CMD wget -q --spider http://localhost/ || exit 1
ENTRYPOINT ["/start.sh"]
