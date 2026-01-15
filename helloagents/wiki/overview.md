# Grok2API

> 本文件包含项目级别的核心信息。详细的模块文档见 `modules/` 目录。

---

## 1. 项目概述

### 目标与背景
将 Grok 的 Web 调用适配为 OpenAI 兼容接口，并提供管理后台用于 Token/配置管理与运行状态查看。

### 范围
- **范围内:** OpenAI 兼容 API（chat/models/images）、管理后台、内置代理（Clash/mihomo）控制与订阅更新
- **范围外:** 作为通用代理客户端的完整规则/策略管理（仅提供最小可用的全局代理切换）

---

## 2. 模块索引

| 模块名称 | 职责 | 状态 | 文档 |
|---------|------|------|------|
| core | 配置/日志/存储等基础设施 | ✅稳定 | [modules/core.md](modules/core.md) |
| api | OpenAI兼容 API 与管理端点 | ✅稳定 | [modules/api.md](modules/api.md) |
| services | Grok/Token/Clash 等业务服务 | ✅稳定 | [modules/services.md](modules/services.md) |
| models | 数据结构与 Schema | ✅稳定 | [modules/models.md](modules/models.md) |
| template | 管理后台前端模板 | ✅稳定 | [modules/template.md](modules/template.md) |

---

## 3. 快速链接
- [技术约定](../project.md)
- [架构设计](arch.md)
- [API 手册](api.md)
- [数据模型](data.md)
- [变更历史](../history/index.md)

