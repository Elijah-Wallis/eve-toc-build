#!/usr/bin/env bash
set -euo pipefail

pm2 start ecosystem.config.js
pm2 save
pm2 startup
