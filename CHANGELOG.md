# 变更记录

遵循语义化版本：修 bug → patch，新增能力 → minor，改变契约 → major。每个版本的说明同时用于 Git tag 与 GitHub Release。

## v1.3.1 — 2026-10-19

### 修复

- `inventory` 新增 `git_checkout` 字段，逐个副本标明是否 git 工作副本。
- `sync` 遇到 `not_a_git_checkout` 时返回 `hint`，明确提示用 `git clone` 重装，不再静默跳过。
- 文档补充「安装方式：必须 git clone」：复制文件或解压 ZIP 装出来的目录永远不会自动更新。

### 测试

- 覆盖 `git_checkout` 报告与 `sync.hint` 提示。

## v1.3.0 — 2026-10-19

### 新增

- **启动同步（S0）**：每次业务任务的第一步先检查支链版本，再开始制卡。首次使用会先问三档：仅这次同步 / 以后自动帮我同步 / 不需要。
- `sync` 与 `sync-consent` 命令；`auto` 下对清单内支链执行 `git pull --ff-only` 更新。
- 三处留痕要求：`member:`（会员状态来源）、`docs:`（文档读取日期）、验收勾选结果。

### 变更

- SKILL.md 重排为 S0–G4 顺序关卡，支链政策压缩到文末，必读与按需分开。
- 用户提供墨墨 API key 即视为已开通专业版，不再重复询问。
- 主技能不再自动覆盖自己：发现新版本只报告，需用户明确要求。

### 移除

- 任务结束时的更新授权询问，以及 `complete` 的 `ask_update_consent` 分支。

### 安全

- 同步只走清单内已核实的 `repository_url`；工作区不干净、远端不符、非 git 仓库一律跳过。
- 旧状态里的 `auto_check=true` 不自动升级为自动同步（旧授权只查不写）。

### 测试

- 41 项离线测试通过，覆盖同步授权、更新跳过条件与 CLI 全链路。

## v1.2.1 — 2026-10-18

- `memo-table` 新增 `version.json`，三个支链均可做版本检查，`skipped` 不再出现 `version_source_unconfigured`。
- 文档同步说明三份清单的核验结果。

## v1.2.0 — 2026-10-18

- 修复 `install_source` 校验：接受 `github_public_repository` 并校验 `repository_url`（此前整份配置被拒、框架报错）。
- 版本清单接受 GitHub Raw 的 `text/plain`；接入三份清单并限定白名单 `raw.githubusercontent.com`。
- 扫描顺序改为运行副本优先，新增 `copies` 字段，修复版本误报。
- 「仅这次」落盘为 `pending_once`，不再依赖对话记忆。
- 39 项测试通过。

## v1.1.1 — 2026-10-16

- 文档与支链框架修订，发布 1.1.1。

## v1.1.0 — 2026-10-14

- 首个发布版本：制卡主流程、TXT / OCR / 表格支链说明、更新检查框架。
