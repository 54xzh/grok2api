# models

## 目的
集中维护请求/响应的 Schema 与数据结构定义。

## 模块概述
- **职责:** Pydantic 模型、OpenAI 兼容结构、内部数据结构
- **状态:** ✅稳定
- **最后更新:** 2026-01-15

## 规范

### 需求: Schema 与运行时一致
**模块:** models
Schema 必须与实际返回结构一致，避免客户端解析失败。

#### 场景: 流式输出
前置条件
- 开启流式对话
- 预期结果: `finish_reason` 与 chunk 结构符合 OpenAI 兼容格式

## API接口
无

## 数据模型
无

## 依赖
- core

## 变更历史
后续按 `helloagents/history/` 记录索引补齐。

