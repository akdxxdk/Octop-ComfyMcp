# 更新日志

## [1.0.0] — 2026-10-19

首次整理发布。整套方案已在本机（Windows 11 + RTX 5060 Ti 16GB）端到端实测跑通。

### 新增

- **部署脚本**（`scripts/`）
  - `start-comfyui.bat` —— 参数化 ComfyUI 启动器，支持传参指定 aki 根目录（纯 ASCII，规避 cmd 代码页坑）
  - `start-octop.bat` —— Octop 启动器，支持传参指定 conda 环境
  - `setup-comfymcp-venv.bat` —— 一键创建 comfy-mcp 隔离 venv
  - `setup-connector.py` —— 通过 API 把连接器配置写进 Octop 数据库
  - `verify.py` —— 六项全量验证（登录 / 健康 / Agent / 连接器 / 探针 / ComfyUI）
  - `mcp_call.py` —— MCP 工具直调，调试与模板探查用
  - `make_workflow.py` —— 从官方模板批量生成定制工作流

- **文档**（`docs/`）
  - 完整安装部署流程
  - aki 整合包路径 / 端口切换指南
  - MCP 依赖隔离排障（含根因分析表）
  - MiniMax H3 图生视频实战
  - 常见问题与性能答疑

- **示例工作流**（`workflows/`）
  - `template_raw.json` —— 官方模板原文（Int8 版）
  - `h3_escape_10s.json` —— 10 秒「逃跑穿越」成品工作流

### 实测数据

| 项目 | 结果 |
|---|---|
| Octop | 1.0.2 正式稳定版 |
| ComfyUI | 0.36.0（秋叶 aki 整合包） |
| MCP 工具数 | 39 |
| 视频成品 | 243 帧 @24fps / 10.12s / 864×480 |
| 总耗时 | ~15.7 分钟 |
| 云端花费 | ¥0 |

---

## 版本演进记录

Octop 侧的升级历程（供排障参考）：

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-10-08 | 1.0.2b6 | 初始部署 |
| 2026-10-18 | 1.0.2b9 | 环境损坏修复，补齐子包依赖 |
| 2026-10-19 | **1.0.2** | 正式稳定版；升级后需修复 MCP 依赖隔离 |
