这是一个很薄的 Telegram Bot API 代理：
- 容器内启动 `telegram-bot-api --local`（突破官方 Bot API 下载大小限制）
- 对外提供一个 HTTP 入口（默认前缀 `/tg`），供 CloudPaste 之类的项目调用

## Docker Compose

1) 先编辑 `docker-compose.yml`

找到 `environment:`，把 3 个必填项填上：
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `BOT_TOKEN`

2) 启动

在本目录执行：

```bash
docker compose up -d
```

3) 验证

- 健康检查：`http://localhost:7860/` → 应该返回 `{"ok": true}`
- 默认前缀 `/tg`：例如（注意替换成你的 token）：
  - `http://localhost:7860/tg/bot<TOKEN>/getMe`

## /tg 前缀怎么改？

用环境变量 `TELEGRAM_PROXY_PREFIX`：

- 默认：`/tg`
- 不想要前缀：填 `/`（表示直接根路径转发）
- 想换成别的：比如 `/x` 就填 `/x`

改完重启容器即可。

## 持久化怎么开？

`docker-compose.yml` 已经默认挂了一个 named volume 到：

- 容器内：`/var/lib/telegram-bot-api`

这个目录就是 `telegram-bot-api` 的工作目录（缓存文件会在这里），所以：

- 开持久化：容器重启不会丢缓存，预览/下载更稳

## CloudPaste

在 CloudPaste 的 Telegram 存储配置里：

- `bot_api_mode` 选 `self_hosted`
- `api_base_url`：
  - 如果 `TELEGRAM_PROXY_PREFIX=/tg`（默认）：填 `http://<你的机器>:7860/tg`
  - 如果 `TELEGRAM_PROXY_PREFIX=/`（无前缀）：填 `http://<你的机器>:7860`
