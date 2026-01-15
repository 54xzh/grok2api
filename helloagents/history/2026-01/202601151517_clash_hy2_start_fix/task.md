# 任务清单: 内置 Clash hy2 导入与启动修复
目录: `helloagents/history/2026-01/202601151517_clash_hy2_start_fix/`

> 类型: 轻量迭代  
> 目标: 修复 hysteria2(hy2) 节点导入兼容性，并解决 mihomo 启动崩溃/超时问题。
---

## 1. hysteria2/hy2 订阅解析
- [√] 1.1 在 `app/services/clash.py` 中增强 hysteria2/hy2 URI 解析（支持 `auth_str` 等变体）
- [√] 1.2 修复 `fingerprint` 参数映射（浏览器指纹写入 `client-fingerprint`，避免 mihomo 配置错误）
- [√] 1.3 兼容 URI 列表中 `- hysteria2://...` 等前缀/大小写差异

## 2. 配置落盘与兼容
- [√] 2.1 在写入配置前归一化代理字段（清理 `None` 值；必要时迁移 `fingerprint`→`client-fingerprint`）
- [√] 2.2 写入前执行 `clash -t` 校验，并采用临时文件 + 原子替换避免破坏原配置

## 3. 启动流程与日志
- [√] 3.1 启动前快速校验当前配置，失败时直接返回避免“启动超时”
- [√] 3.2 检测进程提前退出并输出 `clash.log` 尾部，提升可观测性
- [√] 3.3 启动时使用实际配置目录（兼容本地与 Docker）

## 4. 内置 mihomo 升级
- [√] 4.1 更新 `Dockerfile`，将内置 mihomo 版本升级至 `v1.19.18`（可通过 `MIHOMO_VERSION` 覆盖）

## 5. 回归验证
- [√] 5.1 新增 `test/test_clash_hy2.py` 覆盖 hy2 解析与字段归一化的关键用例

## 6. 知识库同步
- [√] 6.1 更新 `helloagents/CHANGELOG.md`
- [√] 6.2 更新 `helloagents/wiki/modules/services.md`（记录 hy2 指纹字段兼容与配置校验策略）

