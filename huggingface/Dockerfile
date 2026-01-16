FROM aiogram/telegram-bot-api:latest

# 安装 Python 环境和依赖
RUN apk add --no-cache python3 py3-pip && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir starlette uvicorn httpx

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# 复制应用文件
COPY app.py /app/app.py
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# 端口配置
# PUBLIC_PORT: 对外服务端口，默认 7860 (HuggingFace Spaces 标准)
# TELEGRAM_API_PORT: telegram-bot-api 内部端口，默认 8081 (仅 127.0.0.1)
ENV PUBLIC_PORT=7860
ENV TELEGRAM_API_PORT=8081

EXPOSE 7860

ENTRYPOINT ["/app/start.sh"]
