---
title: CloudPaste TG BotAPI
emoji: 🐢
colorFrom: purple
colorTo: red
sdk: docker
pinned: false
app_port: 7860
---

这是 Hugging Face Space 专用目录。

你要在 HF 部署时：
1) 把本目录里的 `Dockerfile`、`start.sh`、`app.py` 复制到 HF Space 仓库根目录
2) 在 Space 的 Secrets/Variables 里配置：
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `BOT_TOKEN`

然后启动成功后，你就会得到一个对外地址：
- `https://<你的space域名>/tg/...`（默认前缀 `/tg`）
