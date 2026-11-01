# 只跑抓取后端：不需要 Xvfb / VNC / noVNC，Cookie 由插件配置写入
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium fonts-noto-cjk ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir --timeout 120 --retries 5 -i $PIP_INDEX \
        'aiohttp>=3.10,<4' 'playwright>=1.50,<2'
RUN useradd -m -u 1000 browser && mkdir -p /app /cookies && chown browser:browser /app /cookies
WORKDIR /app
COPY scraper.py ./
USER browser
ENV XDG_CACHE_HOME=/tmp/x-cache
EXPOSE 6081
ENTRYPOINT ["/usr/bin/tini", "--", "python", "/app/scraper.py"]
