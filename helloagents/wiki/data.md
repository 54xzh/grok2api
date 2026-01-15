# 数据模型

## 概述
项目支持多种存储模式（file/mysql/redis）。在 file 模式下，主要数据落盘于 `/app/data/`。

---

## 文件存储（file 模式）

### `setting.toml`
**描述:** 全局与 grok 相关配置（含内置 Clash 配置项：订阅地址、当前节点等）。

### `token.json`
**描述:** Token 数据存储（由 Token 管理器维护）。

### `clash/config.yaml`
**描述:** mihomo（Clash Meta 兼容）配置文件，订阅更新后写入。

### `clash/clash.pid`
**描述:** Clash 进程 PID（用于后端精准 stop）。

