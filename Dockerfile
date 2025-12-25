FROM aiogram/telegram-bot-api:latest


RUN apk add --no-cache python3 py3-pip && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir fastapi uvicorn httpx

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app

COPY app.py /app/app.py
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

EXPOSE 7860


ENTRYPOINT ["/app/start.sh"]
