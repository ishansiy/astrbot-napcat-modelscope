ARG ASTRBOT_IMAGE=soulter/astrbot:v4.29.4
ARG NAPCAT_IMAGE=mlikiowa/napcat-docker:latest
FROM ${NAPCAT_IMAGE} AS napcat
FROM ${ASTRBOT_IMAGE}
USER root
ENV DEBIAN_FRONTEND=noninteractive TZ=Asia/Shanghai PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor xvfb unzip jq libnss3 libnotify4 libsecret-1-0 libgbm1 \
    libasound2t64 libgtk-3-0t64 libxss1 libxtst6 libatspi2.0-0t64 \
    libx11-xcb1 libxshmfence1 libdrm2 libxkbcommon0 libxcursor1 libxinerama1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=napcat /opt/QQ /opt/QQ
COPY --from=napcat /app/NapCat.Shell.zip /opt/NapCat.Shell.zip
COPY deploy /opt/dafeiyu
COPY persona /opt/dafeiyu/persona
RUN python /opt/dafeiyu/fetch_plugins.py && \
    uv pip install --system --no-cache -r /opt/plugin-seeds/astrbot_plugin_livingmemory/requirements.txt \
      -r /opt/plugin-seeds/astrbot_plugin_proactive_chat/requirements.txt dashscope imageio-ffmpeg && \
    mkdir -p /app/napcat /app/.config/QQ /AstrBot/data && \
    unzip -q /opt/NapCat.Shell.zip -d /app/napcat && \
    rm /opt/NapCat.Shell.zip && \
    cp /opt/dafeiyu/nginx.conf /etc/nginx/nginx.conf && \
    chmod +x /opt/dafeiyu/entrypoint.sh
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s CMD curl -fsS http://127.0.0.1:7860/healthz || exit 1
ENTRYPOINT ["/bin/bash", "/opt/dafeiyu/entrypoint.sh"]
