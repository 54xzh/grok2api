# 项目技术约定

---

## 技术栈
- **后端:** Python / FastAPI
- **部署:** Docker / docker-compose
- **代理能力:** 内置 mihomo（Clash Meta 兼容）+ 管理端点
- **存储:** file（默认）/ mysql / redis（由环境变量控制）

---

## 开发约定
- **编码:** UTF-8
- **命名约定:** Python 使用 snake_case；前端 JS 保持现有风格
- **依赖管理:** 以 `requirements.txt` 与容器镜像为准；如同时存在 `pyproject.toml`，以运行环境为准并在文档中标注差异

---

## 错误与日志
- **策略:** FastAPI 统一异常处理 + 日志记录；管理端点返回 `{"success": bool, ...}` 结构
- **日志目录:** 容器内默认 `/app/logs/`

---

## 测试与流程
- **优先验证:** 订阅更新 / 节点切换 / Clash 启停 / 管理台交互
- **发布前自检:** 更新知识库与 `helloagents/CHANGELOG.md`

