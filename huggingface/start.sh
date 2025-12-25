#!/bin/sh
set -e

if [ -z "${TELEGRAM_API_ID}" ] || [ -z "${TELEGRAM_API_HASH}" ]; then
  echo "Missing TELEGRAM_API_ID / TELEGRAM_API_HASH"
  exit 1
fi

PUBLIC_PORT="${PORT:-7860}"
UPSTREAM_PORT="${TELEGRAM_UPSTREAM_PORT:-8081}"

WORK_DIR="${TELEGRAM_WORK_DIR:-/tmp/telegram-bot-api-data}"
TEMP_DIR="${TELEGRAM_TEMP_DIR:-/tmp/telegram-bot-api-tmp}"
mkdir -p "$WORK_DIR" "$TEMP_DIR"

VERBOSITY="${TELEGRAM_VERBOSITY:-1}"

telegram-bot-api \
  --api-id="${TELEGRAM_API_ID}" \
  --api-hash="${TELEGRAM_API_HASH}" \
  --dir="$WORK_DIR" \
  --temp-dir="$TEMP_DIR" \
  --http-ip-address=127.0.0.1 \
  --http-port="${UPSTREAM_PORT}" \
  --local \
  --verbosity="$VERBOSITY" \
  &

exec uvicorn app:app --host 0.0.0.0 --port "${PUBLIC_PORT}"