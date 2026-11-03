ARG ASTRBOT_IMAGE=soulter/astrbot:v4.29.4@sha256:72f341f0ffcf6621ef820277642c5d63955f7beeac3683433ce09cac96379c78
ARG NAPCAT_IMAGE=mlikiowa/napcat-docker@sha256:696e9574a0f6fb2f86cbecba8a32048f2a5823117dc9b13c6c02637ad890fa8b
FROM ${ASTRBOT_IMAGE} AS astrbot
FROM ${NAPCAT_IMAGE} AS napcat
FROM archlinux:base@sha256:ece6c971fec3c532fd508bce299a446deaf469feecbfe7c353e995bc1a5e7bba
ENV TZ=Asia/Shanghai LANG=C.UTF-8 PYTHONUNBUFFERED=1 \
    UV_PYTHON_INSTALL_DIR=/opt/python PATH=/opt/astrbot-venv/bin:$PATH
# Arch requires complete upgrades instead of partial package upgrades.
RUN pacman -Syu --noconfirm --needed \
    ca-certificates curl git uv python nodejs npm base-devel openssl unzip jq \
    nginx supervisor tigervnc dbus xfce4 xfce4-terminal mousepad firefox sudo \
    noto-fonts noto-fonts-cjk ttf-dejavu adwaita-icon-theme xorg-xprop xorg-xwininfo \
    ffmpeg ollama nss libnotify libsecret mesa alsa-lib gtk3 libxss libxtst \
    libx11 libxcb libxkbcommon libxkbcommon-x11 at-spi2-core \
    && pacman -Scc --noconfirm \
    && useradd -m -u 1000 -s /bin/bash desktop \
    && printf 'desktop ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/desktop \
    && chmod 440 /etc/sudoers.d/desktop
COPY --from=astrbot /AstrBot /AstrBot
COPY --from=napcat /opt/QQ /opt/QQ
COPY --from=napcat /app/NapCat.Shell.zip /opt/NapCat.Shell.zip
WORKDIR /AstrBot
RUN uv python install 3.12 && uv venv --python 3.12 /opt/astrbot-venv \
    && uv pip install --python /opt/astrbot-venv/bin/python -r requirements.txt \
    && uv pip install --python /opt/astrbot-venv/bin/python -e . --no-deps \
    && uv pip install --python /opt/astrbot-venv/bin/python socksio pilk websockify==0.13.0 \
    && curl -fL --retry 3 https://github.com/novnc/noVNC/archive/refs/tags/v1.7.0.tar.gz -o /tmp/novnc.tar.gz \
    && mkdir -p /usr/share/novnc \
    && tar -xzf /tmp/novnc.tar.gz --strip-components=1 -C /usr/share/novnc \
    && rm /tmp/novnc.tar.gz
COPY deploy /opt/dafeiyu
COPY persona /opt/dafeiyu/persona
RUN command -v sqlite3 >/dev/null && python /opt/dafeiyu/fetch_plugins.py && \
    python /opt/dafeiyu/install_plugin_deps.py && \
    mkdir -p /app/napcat /app/.config/QQ /AstrBot/data && \
    unzip -q /opt/NapCat.Shell.zip -d /app/napcat && \
    rm /opt/NapCat.Shell.zip && \
    cp /opt/dafeiyu/nginx.conf /etc/nginx/nginx.conf && \
    chmod +x /opt/dafeiyu/*.sh && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=240s CMD curl -fsS http://127.0.0.1:7860/healthz || exit 1
ENTRYPOINT ["/bin/bash", "/opt/dafeiyu/entrypoint.sh"]
