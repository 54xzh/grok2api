# 任务清单: 内置 Clash 修复（订阅/切换/停止）

目录: `helloagents/history/2026-01/202601150001_clash_builtin_fix/`

> 类型: 轻量迭代  
> 目标: 修复节点切换 404、补齐 hysteria2 节点导入、修复停止按钮失效。

---

## 1. Clash 订阅解析
- [√] 1.1 在 `app/services/clash.py` 中支持 Base64 URI 订阅解析（hysteria2://）并合并到 Clash YAML
- [√] 1.2 确保生成/更新 `proxy-groups.GLOBAL`，避免无可切换的代理组

## 2. 节点切换与状态
- [√] 2.1 在 `app/services/clash.py` 中基于 `/proxies` 自动发现可切换代理组，避免 404
- [√] 2.2 在 `app/services/clash.py` 中自动获取当前节点（不再强依赖固定组名）

## 3. 启停与 PID
- [√] 3.1 在 `docker-entrypoint.sh` 中创建 `/app/data/clash` 并写入 `clash.pid`
- [√] 3.2 在 `app/services/clash.py` 中优先按 PID 结束 Clash，必要时强制 kill

## 4. 管理台交互
- [√] 4.1 在 `app/template/admin.html` 中启动后自动刷新节点列表（停止不刷新）

## 5. 文档更新
- [√] 5.1 创建/更新 `helloagents/wiki/*` 与模块文档，记录修复点与使用方式
- [√] 5.2 更新 `helloagents/CHANGELOG.md`
