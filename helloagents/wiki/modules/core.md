# core

## 目的
提供配置、日志、存储等基础能力，支撑上层 API 与 services。

## 模块概述
- **职责:** setting 管理、storage 管理、日志与异常处理等
- **状态:** ✅稳定
- **最后更新:** 2026-01-15

## 规范

### 需求: 配置可追溯
**模块:** core
配置应有默认值与持久化能力，便于容器/多环境部署。

#### 场景: file 模式启动
前置条件
- `/app/data/` 可写
- 预期结果: 自动生成 `setting.toml` 与 `token.json`（如不存在）

## API接口
无

## 数据模型
见 `wiki/data.md`

## 依赖
无

## 变更历史
后续按 `helloagents/history/` 记录索引补齐。

