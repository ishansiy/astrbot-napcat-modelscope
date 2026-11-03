# 大肥鱼全量备份 · WebDAV

针对魔搭官方持久化目录适配的独立备份插件。设计参考自动备份与 rclone 插件的定时、保留策略；实现改用原生 WebDAV，使地址、用户名、密码可直接在 AstrBot 插件面板配置，无需另配 rclone，也不会按插件所在层级猜测数据根目录。

在「插件 → 大肥鱼全量备份 · WebDAV → 配置」修改服务、目录、凭据、Cron、时区、保留份数和备份范围。密码与恢复密钥默认遮挡。默认每日北京时间 04:00，本地保留 2 份、远程保留 7 份；新安装默认关闭定时和上传，填写恢复密钥与目的地后启用。开启「立即备份一次」并保存，或由管理员发送 `/大肥鱼备份`；用 `/备份状态` 查看进度。后台备份进程在插件配置保存/重载时继续运行，新配置从下次任务生效。

备份 `astrbot/`（数据库、记忆、配置、插件、表情包、知识库及用户文件）、`desktop/`（桌面文件及浏览器资料）、`napcat/`、`qq/` 和初始化凭据文件。Ollama 权重可选，默认不备份；记忆数据库与向量属于 AstrBot 数据，始终随所选范围保存。跳过派生缓存、旧备份、虚拟环境和运行时锁，不跟随符号链接。SQLite 使用在线 backup API，将已提交 WAL 纳入一致性快照，并执行 quick_check。

本地副本默认位于 `/mnt/workspace/dafeiyu/backups/`。ZIP 校验后用 AES-256-GCM 加密，分成默认 64 MB 的文件。每片上传后实际 GET 下载并核对 SHA256，全部通过后才提交 `manifest.json` 并读回目录与清单。只有完整备份计入远程保留数量；清理只处理本插件格式且 installation_id 与当前安装一致的目录，不触碰其他文件。

源 SQLite 已损坏时，只对备份副本执行 SQLite 官方 `.recover --ignore-freelist`，不覆盖源库。所有可读取表的逐行哈希必须与原始快照一致；无法读取的表和恢复情况记录在 `database_recoveries`，原始损坏快照同时保存在加密包的 `_source_database_copies/` 中。恢复不能保证找回源库早已损坏的数据；状态会明确提示该情况。Arch 镜像已校验 `sqlite3` 工具可用。

## 恢复

请另存恢复密钥。更换密钥后，旧备份继续使用旧密钥。下载一个完整备份目录，保留其中的 `manifest.json` 和所有 `part-*.bin`，安装 `cryptography`，执行：

```bash
python restore.py --bundle /path/to/downloaded-backup --key-file /path/to/recovery-key.txt --output /path/to/new-empty-directory
```

恢复工具核对分片、总哈希、AES-GCM、ZIP、每个文件和 SQLite；目标必须为空，不覆盖运行中的服务。Linux root 恢复时还原原 UID/GID 和权限；普通用户恢复时保留当前用户权限。核验后停止服务，把恢复目录中的各数据目录迁入新的持久化根目录，再启动同一部署镜像。

这是整套部署的恢复包，使用随附工具恢复；并非 AstrBot 面板单独的 JSON 导入包。镜像、系统软件和模型权重可重新拉取。备份进程中断或网络失败时，不会把未完成的远程目录标为成功。暂不对所有数据库及正在修改的普通文件提供跨应用的统一事务快照。
