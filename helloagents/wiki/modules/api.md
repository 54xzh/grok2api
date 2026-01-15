# api

## 目的
对外提供 OpenAI 兼容 API，并提供管理后台相关的管理端点。

## 模块概述
- **职责:** 路由注册、请求校验、管理会话校验、调用 services 执行业务逻辑
- **状态:** ✅稳定
- **最后更新:** 2026-01-15

## 规范

### 需求: 管理端点稳定性
**模块:** api
管理端点需返回稳定的 JSON 结构，避免前端因为异常状态码导致的不可用。

#### 场景: Clash 节点切换
前置条件
- 已登录管理后台
- Clash 已启动并可访问 REST API
- 选择一个已存在的节点名称
- 预期结果: 切换成功返回 `success=true`，失败返回 `success=false` 且包含可读的 `error`

## API接口
### POST /api/clash/select
**描述:** 切换 Clash 节点
**输入:** `{ "name": "节点名" }`
**输出:** `{ "success": true/false, ... }`

## 数据模型
无

## 依赖
- services

## 变更历史
后续按 `helloagents/history/` 记录索引补齐。

