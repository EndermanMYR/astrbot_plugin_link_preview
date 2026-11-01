FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends chromium xvfb x11vnc novnc openbox fonts-noto-cjk ca-certificates tini && rm -rf /var/lib/apt/lists/*
RUN cp -rL /usr/share/novnc /opt/novnc
RUN pip install --no-cache-dir 'aiohttp>=3.10,<4' 'playwright>=1.50,<2'
RUN useradd -m -u 1000 browser && mkdir -p /app /cookies && chown browser:browser /app /cookies
WORKDIR /app
COPY server.py scraper.py portal.html portal.js portal.css welcome.html start.js start.sh ./
RUN chmod +x /app/start.sh
USER browser
ENV DISPLAY=:99
ENV XDG_CONFIG_HOME=/tmp/x-login-config
ENV XDG_CACHE_HOME=/tmp/x-login-cache
EXPOSE 6080 6081
ENTRYPOINT ["/usr/bin/tini", "--", "/app/start.sh"]
