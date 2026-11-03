---
title: AstrBot NapCat 大肥鱼
sdk: docker
app_port: 7860
---
# Arch Linux XFCE + AstrBot + NapCat 大肥鱼 · ModelScope

在单个容器中运行 Arch Linux、XFCE、Firefox、AstrBot、NapCat 和 Nginx，统一通过 7860 访问。此仓库复刻自 [MoYangking/Astrbot-Napcat-huggingface](https://github.com/MoYangking/Astrbot-Napcat-huggingface)，保留 Git 历史与上游关联。魔搭适配版改用官方组件，移除了上游动态路由管理、文件管理器、同步服务和临时代理。

## 包含什么

- AstrBot v4.29.4，NapCat 官方容器中的 QQ NT 和协议端。
- 自定义“大肥鱼”人格，默认中文、短句聊天，任务优先。
- 固定源码提交的 19 个大肥鱼常用插件，包括 LivingMemory、Proactive Chat、Meme Manager、Memelite、QQ 空间、个人资料、点歌、绘图等；来源、版本与启用默认值见 `deploy/plugins.lock.json`。
- 预装 Ollama，本地 Embedding 模型保存在 `/mnt/workspace/dafeiyu/ollama`；设置 `LOCAL_EMBEDDING_MODEL=bge-m3` 可自动下载模型。免费语音可在 AstrBot 中选择 Edge TTS。
- 内部 OneBot 连接预先配好；双方使用相同随机 Token。
- AstrBot 数据、插件、长期记忆与 QQ 登录资料均位于 `/mnt/workspace/dafeiyu`。
- 先构建并验证两个管理界面、AstrBot 登录和重启持久化，再通过 GitHub Actions 发布 GHCR 镜像。

## 魔搭国际站

已部署的空间：[打开魔搭国际站](https://www.modelscope.ai/studios/uaa7813d3/astrbot-napcat-dafeiyu)。

创建 Docker 创空间，使用免费 CPU 资源；当前部署按用户要求设为公开，各管理入口仍要求登录。推荐使用本仓库根目录 `Dockerfile` 从锁定的官方组件构建。GHCR 镜像已发布；GitHub 首次发布的镜像默认私有，拉取需要 `read:packages` 凭据。魔搭当前通过同份源码构建，不保存 GitHub 拉取凭据。仅在镜像已设为公开或运行环境已经配置镜像认证时，才可使用：

```dockerfile
FROM ghcr.io/ishansiy/astrbot-napcat-modelscope:latest
```

在创空间 Secrets 设置 `ASTRBOT_ADMIN_PASSWORD`、`NAPCAT_WEBUI_TOKEN`、`ONEBOT_TOKEN`、`DESKTOP_PASSWORD`，并可设置 `DEEPSEEK_API_KEY`。普通变量可设置 `OWNER_QQ`（你的聊天主号，非机器人小号）、`TZ=Asia/Shanghai`。

首次启动自动生成配置。已有配置不会被环境变量覆盖；后续修改模型、管理员和白名单，请使用 AstrBot 管理面板。更换 Secrets 不会自动重置已有密码。

| 地址 | 用途 |
| --- | --- |
| `/` | AstrBot 管理面板及网页聊天，用户名 `astrbot` |
| `/napcat/webui/` | NapCat 管理面板，使用 `NAPCAT_WEBUI_TOKEN` 登录并扫描 QQ 二维码 |
| `/desktop/` | XFCE 浏览器桌面，表单登录用户名 `desktop`，密码为 `DESKTOP_PASSWORD` |
| `/healthz` | AstrBot 就绪检查 |

## 首次接入

1. 用 Secrets 中的密码登录 AstrBot，确认“大肥鱼”人格已存在。
2. 如果未提供 `DEEPSEEK_API_KEY`，在“模型提供商”填写自己的推理 API Key，启用模型并设为默认。魔搭部署 Token 不会被当成 DeepSeek Key。
3. 设置管理员 QQ 和访问白名单。`OWNER_QQ` 未提供时，预置哨兵白名单会阻止 QQ 消息触发，网页聊天仍可用。
4. 可使用 QQ 官方机器人接口；也可打开 NapCat 面板，用普通 QQ 小号扫码，内部 WebSocket 已指向 `ws://127.0.0.1:6199/ws`。QQ 空间、戳一戳和修改个人资料等功能需要后一种接入。
5. LivingMemory 需要在插件配置中选择有效的 Embedding 提供商；默认按会话隔离，不采集未触发的全部群聊。配置前不得把插件已安装视为长期记忆已可用。
6. Proactive Chat 默认关闭。指定私聊会话后再启用，建议间隔 120–240 分钟、免打扰 23–8、最大未回复 1 次。语音、图片转述和视频音轨还需配置相应模型。

免费创空间可能休眠，不能保证全天在线、准时提醒或永久保持 QQ 登录。平台重命名/转移空间可能影响持久化目录，重要资料应另做备份。这里不配置保活流量。

## 本地 Docker

复制 `.env.example` 为 `.env` 并填写，再运行 `docker compose up -d`。只需访问 `http://127.0.0.1:7860`；不需要 privileged、宿主 Docker socket 或额外公开 OneBot 端口。

## 来源与维护

AstrBot 使用其上游 AGPL-3.0 许可；NapCat 和各插件遵循各自上游许可。插件包在构建时取自锁定提交，不包含任何个人账号配置。未对无许可证的上游历史文件重新授权；本仓库保留来源记录。镜像代码及锁定版本均可从本仓库获取。

## 已验证

2026-11-03：[GitHub Actions](https://github.com/ishansiy/astrbot-napcat-modelscope/actions/runs/41652038671) 已通过源码检查、密码与配置覆盖保护、真实容器双面板登录、Arch/XFCE 与 Firefox 窗口、完整浏览器 noVNC 登录和连接测试、19 个插件加载与启用状态检查、Ollama 服务检查、表情包从临时目录导入持久化挂载的真实读回检查；重启及删除容器重建后的持久化恢复均通过。镜像源码提交：`580ef48d621c93f352adda336999d80820fdff43`，镜像标签：`sha-580ef48d621c`。表情包上传暂存文件使用 `/tmp`，安装后的资源和配置使用官方持久化目录。

魔搭国际站云端验证：公开空间进入 Running；原 AstrBot 密码有效，人格内容的迁移前后 SHA256 一致；NapCat 管理页、独立桌面密码登录、真实云端桌面 WebSocket 均通过。桌面主目录和机器人数据使用官方 `/mnt/workspace/dafeiyu/`，迁移前的备份留在 `astrbot/backups/`。受限容器无法创建嵌套图像解码沙箱时，桌面启动脚本使用 Glycin 官方的容器内兼容选项；VNC 仍仅监听回环地址。

当前云端使用 QQ 官方机器人接口，用户已确认可正常对话。DeepSeek 聊天模型保持原配置；新增的免费 Edge TTS 已成功合成音频，本地 Ollama bge-m3 Embedding 已实测返回 1024 维向量，LivingMemory 索引检查通过。普通 QQ 小号尚未登录，依赖 NapCat、付费 API 或额外外部服务的插件保留为待启用状态。安装插件不代表其所有外部依赖均已具备。

插件清单参考 [大肥鱼原项目](https://github.com/whyever77/dafeiyu-astrbot) 和 [大肥鱼配置包](https://github.com/zexuanw958-svg/dafeiyu-config-pack)。两项未声明许可证的插件只在用户运行环境按锁定提交下载，不随镜像分发。表情资源包由用户运行环境从上游获取，不包含在本仓库或镜像中。

## Arch 桌面版

系统用户空间来自官方 `archlinux:base` 镜像，使用 pacman 安装并预置 XFCE、Firefox、Thunar 文件管理器、终端、Mousepad 编辑器、中文字体、Git、Node.js、FFmpeg 和 Python 3.12 独立环境。TigerVNC 与 noVNC 提供 1440×900 桌面，无需在自己的电脑安装 VNC 软件。

直接在新窗口打开应用的 `/desktop/`。桌面入口和控制 WebSocket 均校验登录后的签名 Cookie；VNC 原始端口仅监听容器回环地址。桌面以 UID 1000 用户 `desktop` 运行，可在终端通过 sudo 管理容器软件。

桌面主目录 `/home/desktop` 指向 `/mnt/workspace/dafeiyu/desktop`，文件、下载、桌面设置和浏览器配置保存在官方持久化目录；缓存放在临时目录。已有 AstrBot 与 QQ 数据路径保持一致，首次初始化不会重置原密码或配置。

额外安装到系统目录的软件不随容器重建保留；长期需要的软件请加入 Dockerfile 再发布镜像。容器共享魔搭宿主机内核，不提供独立启动的 Arch 内核或完整虚拟机。
