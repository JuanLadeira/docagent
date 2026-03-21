FROM node:24-alpine AS builder

RUN apk update && \
    apk add --no-cache git ffmpeg wget curl bash openssl

WORKDIR /evolution

ARG VERSION=2.3.7

RUN wget -qO- "https://github.com/EvolutionAPI/evolution-api/archive/refs/tags/${VERSION}.tar.gz" | \
    tar xz --strip-components=1

RUN npm ci --silent

RUN chmod +x ./Docker/scripts/* && dos2unix ./Docker/scripts/*

COPY ./.env.example ./.env 2>/dev/null || true
RUN ./Docker/scripts/generate_database.sh

RUN npm run build

# ── Runtime ───────────────────────────────────────────────────────────────────

FROM node:24-alpine

RUN apk update && \
    apk add --no-cache tzdata ffmpeg bash openssl

ENV TZ=America/Sao_Paulo
ENV DOCKER_ENV=true

WORKDIR /evolution

COPY --from=builder /evolution/package.json ./package.json
COPY --from=builder /evolution/package-lock.json ./package-lock.json
COPY --from=builder /evolution/node_modules ./node_modules
COPY --from=builder /evolution/dist ./dist
COPY --from=builder /evolution/prisma ./prisma
COPY --from=builder /evolution/manager ./manager
COPY --from=builder /evolution/public ./public
COPY --from=builder /evolution/.env ./.env
COPY --from=builder /evolution/Docker ./Docker
COPY --from=builder /evolution/runWithProvider.js ./runWithProvider.js
COPY --from=builder /evolution/tsup.config.ts ./tsup.config.ts

EXPOSE 8080

ENTRYPOINT ["/bin/bash", "-c", ". ./Docker/scripts/deploy_database.sh && npm run start:prod"]
