#!/bin/sh
set -e

# 验证必填参数
if [ -z "${TELEGRAM_API_ID}" ] || [ -z "${TELEGRAM_API_HASH}" ]; then
  echo "错误：缺少 TELEGRAM_API_ID 或 TELEGRAM_API_HASH"
  echo "请在 docker-compose.yml 中配置这些参数"
  exit 1
fi

# 端口配置
PUBLIC_PORT="${PUBLIC_PORT:-7860}"
TELEGRAM_API_PORT="${TELEGRAM_API_PORT:-8081}"

# 目录配置
WORK_DIR="${TELEGRAM_WORK_DIR:-/tmp/telegram-bot-api-data}"
TEMP_DIR="${TELEGRAM_TEMP_DIR:-/tmp/telegram-bot-api-tmp}"
mkdir -p "$WORK_DIR" "$TEMP_DIR"

VERBOSITY="${TELEGRAM_VERBOSITY:-1}"

# 启动 telegram-bot-api (后台运行)
echo "启动 telegram-bot-api: 127.0.0.1:${TELEGRAM_API_PORT}"
telegram-bot-api \
  --api-id="${TELEGRAM_API_ID}" \
  --api-hash="${TELEGRAM_API_HASH}" \
  --dir="$WORK_DIR" \
  --temp-dir="$TEMP_DIR" \
  --http-ip-address=127.0.0.1 \
  --http-port="${TELEGRAM_API_PORT}" \
  --local \
  --verbosity="$VERBOSITY" \
  &

# 启动代理层 (前台运行)
echo "启动代理层: 0.0.0.0:${PUBLIC_PORT}"
echo "上游地址: http://127.0.0.1:${TELEGRAM_API_PORT}"
exec uvicorn app:app --host 0.0.0.0 --port "${PUBLIC_PORT}"