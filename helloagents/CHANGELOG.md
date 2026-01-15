# Changelog

本文件记录项目所有重要变更。
格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 修复
- 修复内置 Clash 节点切换可能出现 404 的问题（自动发现可切换代理组，并确保 `GLOBAL` 选择组存在）
- 修复 Base64 URI 订阅中 `hysteria2://` 节点无法导入的问题（解析 hysteria2 节点并合并到 Clash YAML）
- 修复 Docker 启动时未写入 Clash PID 导致停止不稳定的问题（写入 `clash.pid`，并在后端优先按 PID 结束）
- 修复管理台启停 Clash 后节点列表刷新逻辑错误的问题

