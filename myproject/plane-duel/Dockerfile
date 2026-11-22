# 多阶段：builder 装全量依赖，runtime 只带运行所需
FROM node:22-alpine AS builder
RUN corepack enable
WORKDIR /repo
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml tsconfig.base.json ./
COPY packages/shared/package.json packages/shared/
COPY apps/server/package.json apps/server/
COPY apps/client/package.json apps/client/
RUN pnpm install --frozen-lockfile --filter @plane-duel/server... --filter @plane-duel/client...
COPY packages/shared packages/shared
COPY apps/server apps/server
COPY apps/client apps/client
# H5 构建（WS 地址同源：Caddy 把 /ws 反代到服务端）
ARG VITE_WS_URL=
ENV VITE_WS_URL=${VITE_WS_URL}
RUN pnpm -C apps/client build:h5

FROM node:22-alpine AS server
RUN corepack enable
WORKDIR /repo
COPY --from=builder /repo /repo
ENV NODE_ENV=production PORT=8080 HOST=0.0.0.0
EXPOSE 8080
USER node
CMD ["pnpm", "-C", "apps/server", "start"]

FROM caddy:2-alpine AS web
COPY --from=builder /repo/apps/client/dist /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
