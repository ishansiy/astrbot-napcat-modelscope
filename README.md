---
title: AstrBot NapCat 大肥鱼
sdk: docker
app_port: 7860
---
# AstrBot + NapCat 大肥鱼 · ModelScope

在单个容器中运行 AstrBot、NapCat、Xvfb 和 Nginx，统一通过 7860 访问。此仓库复刻自 [MoYangking/Astrbot-Napcat-huggingface](https://github.com/MoYangking/Astrbot-Napcat-huggingface)，保留 Git 历史与上游关联。魔搭适配版改用官方组件，移除了上游动态路由管理、文件管理器、同步服务和临时代理。

## 包含什么

- AstrBot v4.29.4，NapCat 官方容器中的 QQ NT 和协议端。
- 自定义“大肥鱼”人格，默认中文、短句聊天，任务优先。
- 固定源码提交的 LivingMemory、Proactive Chat 和大肥鱼 QQ 表情/媒体插件；来源见 `deploy/plugins.lock.json`。
- 内部 OneBot 连接预先配好；双方使用相同随机 Token。
- AstrBot 数据、插件、长期记忆与 QQ 登录资料均位于 `/mnt/workspace/dafeiyu`。
- 先构建并验证两个管理界面、AstrBot 登录和重启持久化，再通过 GitHub Actions 发布 GHCR 镜像。

## 魔搭国际站

已部署的私有空间：[打开魔搭国际站](https://www.modelscope.ai/studios/uaa7813d3/astrbot-napcat-dafeiyu)。

创建 **私有 Docker 创空间**，使用免费 CPU 资源。推荐使用本仓库根目录 `Dockerfile` 从锁定的官方组件构建。GHCR 镜像已发布；GitHub 首次发布的镜像默认私有，拉取需要 `read:packages` 凭据。魔搭当前通过同份源码构建，不保存 GitHub 拉取凭据。仅在镜像已设为公开或运行环境已经配置镜像认证时，才可使用：

```dockerfile
FROM ghcr.io/ishansiy/astrbot-napcat-modelscope:latest
```

在创空间 Secrets 设置 `ASTRBOT_ADMIN_PASSWORD`、`NAPCAT_WEBUI_TOKEN`、`ONEBOT_TOKEN`，并可设置 `DEEPSEEK_API_KEY`。普通变量可设置 `OWNER_QQ`（你的聊天主号，非机器人小号）、`TZ=Asia/Shanghai`。

首次启动自动生成配置。已有配置不会被环境变量覆盖；后续修改模型、管理员和白名单，请使用 AstrBot 管理面板。更换 Secrets 不会自动重置已有密码。

| 地址 | 用途 |
| --- | --- |
| `/` | AstrBot 管理面板及网页聊天，用户名 `astrbot` |
| `/napcat/webui/` | NapCat 管理面板，使用 `NAPCAT_WEBUI_TOKEN` 登录并扫描 QQ 二维码 |
| `/healthz` | AstrBot 就绪检查 |

## 首次接入

1. 用 Secrets 中的密码登录 AstrBot，确认“大肥鱼”人格已存在。
2. 如果未提供 `DEEPSEEK_API_KEY`，在“模型提供商”填写自己的推理 API Key，启用模型并设为默认。魔搭部署 Token 不会被当成 DeepSeek Key。
3. 设置管理员 QQ 和访问白名单。`OWNER_QQ` 未提供时，预置哨兵白名单会阻止 QQ 消息触发，网页聊天仍可用。
4. 打开 NapCat 面板，用 QQ 小号扫码；内部 WebSocket 已指向 `ws://127.0.0.1:6199/ws`。
5. LivingMemory 需要在插件配置中选择有效的 Embedding 提供商；默认按会话隔离，不采集未触发的全部群聊。配置前不得把插件已安装视为长期记忆已可用。
6. Proactive Chat 默认关闭。指定私聊会话后再启用，建议间隔 120–240 分钟、免打扰 23–8、最大未回复 1 次。语音、图片转述和视频音轨还需配置相应模型。

免费创空间可能休眠，不能保证全天在线、准时提醒或永久保持 QQ 登录。平台重命名/转移空间可能影响持久化目录，重要资料应另做备份。这里不配置保活流量。

## 本地 Docker

复制 `.env.example` 为 `.env` 并填写，再运行 `docker compose up -d`。只需访问 `http://127.0.0.1:7860`；不需要 privileged、宿主 Docker socket 或额外公开 OneBot 端口。

## 来源与维护

AstrBot 使用其上游 AGPL-3.0 许可；NapCat 和各插件遵循各自上游许可。插件包在构建时取自锁定提交，不包含任何个人账号配置。未对无许可证的上游历史文件重新授权；本仓库保留来源记录。镜像代码及锁定版本均可从本仓库获取。

## 已验证

2026-11-03：GitHub Actions 已通过源码检查、持久化覆盖保护测试、真实容器双面板访问与 AstrBot 登录、重启及删除容器重建后的持久化恢复。镜像源码提交：`e3006046adb172bfe45e669b1b23a1423ec1cfa7`，镜像标签：`sha-e3006046adb1`。

魔搭国际站云端验证：私有空间进入 Running；真实 AstrBot 登录及 NapCat 管理页访问通过。写入临时人格记录后重新部署，确认运行实例创建时间已改变、原密码和记录均保留；测试记录随后删除并回读确认。日志确认知识库与插件数据使用 `/mnt/workspace/dafeiyu/astrbot/`。QQ 尚未扫码，模型和 Embedding 凭据由用户在面板补充，尚未验证真实 QQ 对话。
