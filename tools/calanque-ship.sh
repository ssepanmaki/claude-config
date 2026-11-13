#!/usr/bin/env bash
# Ships a clean Calanque checkout to prod: R2 bucket, D1/KV ids, remote migrations, build, deploy.
# Usage: calanque-ship.sh <checkout dir>
set -eu
cd "$1"
npx wrangler r2 bucket list | grep -q "name: *calanque-files$" || npx wrangler r2 bucket create calanque-files
node scripts/ensure-d1.mjs
npx wrangler d1 migrations apply DB --remote
npm run build
npx wrangler deploy --var APP_URL:https://calanque.dattruong.com --var CAPTURE_DOMAIN:dattruong.com
