FROM node:22.12-bookworm-slim

ENV NODE_ENV=production
ENV npm_config_update_notifier=false
ENV npm_config_fund=false
ENV npm_config_audit=false

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    git \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@2026.2.2-3 --no-audit --loglevel=error

RUN useradd -M -u 10001 -d /var/lib/openclaw openclaw \
  && mkdir -p /repo /template /var/lib/openclaw \
  && chown -R openclaw:openclaw /var/lib/openclaw

COPY docker/openclaw/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /repo
ENTRYPOINT ["/entrypoint.sh"]
