#!/bin/bash
# Mint a fresh long-lived user JWT from the GitHub PAT.
# Run once per ~80 days (TTL is 90).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/.env" ] && set -a && . "$ROOT/.env" && set +a

: "${AACHAT_API_URL:?set in .env}"
: "${AACHAT_OPS_GITHUB_PAT:?set in .env}"
: "${AACHAT_JWT_PATH:=$HOME/.aachat/curation-jwt}"

JWT_PATH="${AACHAT_JWT_PATH/#\~/$HOME}"
mkdir -p "$(dirname "$JWT_PATH")"

echo "Minting JWT from PAT (ttl_days=90)..."
TOKEN=$(curl -fsSX POST "$AACHAT_API_URL/v1/auth/github" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$AACHAT_OPS_GITHUB_PAT\",\"ttl_days\":90}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")

printf '%s' "$TOKEN" > "$JWT_PATH"
chmod 600 "$JWT_PATH"
echo "JWT saved to $JWT_PATH ($(wc -c < "$JWT_PATH") bytes)"
