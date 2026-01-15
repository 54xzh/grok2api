# API 手册

## 概述
对外提供 OpenAI 兼容 API，并提供管理端点用于配置、Token 与内置 Clash 控制。

## 认证方式
- **OpenAI兼容 API:** 使用 `Authorization: Bearer <token>`（具体以项目实现为准）
- **管理端点:** 管理员登录后通过会话校验（`verify_admin_session`）

---

## 接口列表

### OpenAI 兼容

#### POST `/v1/chat/completions`
**描述:** 创建聊天对话（支持流式与非流式）。

#### GET `/v1/models`
**描述:** 获取模型列表。

#### GET `/images/{img_path}`
**描述:** 获取图片资源。

---

### 管理端点 - 内置 Clash

#### GET `/api/clash/status`
**描述:** 获取 Clash 运行状态与当前节点。

#### GET `/api/clash/proxies`
**描述:** 获取节点列表与当前节点。

#### POST `/api/clash/select`
**描述:** 切换节点。

#### POST `/api/clash/update`
**描述:** 更新订阅并写入 Clash 配置。

#### POST `/api/clash/start`
**描述:** 启动 Clash 进程。

#### POST `/api/clash/stop`
**描述:** 停止 Clash 进程。

