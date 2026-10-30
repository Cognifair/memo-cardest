# 变更记录

遵循语义化版本：修 bug → patch，新增能力 → minor，改变契约 → major。每个版本的说明同时用于 Git tag 与 GitHub Release。

## v1.5.2 — 2026-10-30

影响面：memo-cardest(README.md, references/satellites.md)

### 变更

- Memo 系列清单加入「卡跳跳 Memo-CardLink」，同步 README 系列表与 satellites。

## v1.5.1 — 2026-10-30

影响面：memo-cardest(README.md)

### 变更

- README 顶部增加「墨卡大师 · 专业制卡工作流」在线介绍页链接。

## v1.5.0 — 2026-10-28

影响面：memo-cardest(SKILL.md, README.md, references/batch-delete.md)

### 新增

- 批量删除交接流程：官方 OpenAPI 只创建/复用 `DELETE` 章节并把目标卡移入，回读核对后由用户在客户端手动删除该章；AI 不调用删除接口，不做不可逆删除。

## v1.4.11 — 2026-10-28

影响面：memo-cardest(references/satellite-framework.md)

### 变更

- 文档中的发布器名称由 `skill-publisher` 更新为 `maimemo-publisher`，与当前技能名保持一致。

## v1.4.10 — 2026-10-26

影响面：memo-cardest(SKILL.md, references/satellite-framework.md, scripts/check_updates.py, scripts/test_check_updates.py) / memo-txtimporter(SKILL.md, scripts/check_updates.py, scripts/test_check_updates.py)

### 修复

- 状态锁竞争不再误报 `state_lock_failed`：根因是加锁前读取被锁字节，Windows 强制字节锁直接抛 `PermissionError`。改为先用 `os.fstat` 判断文件大小，不读被锁区域。
- 锁获取增加 2 秒退避重试；仍被占用时返回 `status: busy` / `reason: sync_in_progress`，说明“另一个客户端/会话正在同步”，业务继续。
- 新增锁竞争回归测试；S0 与框架文档补充 `busy` 处理。

## v1.4.9 — 2026-10-25

影响面：memo-cardest(SKILL.md, references/txt-workflow.md) / memo-txtimporter(SKILL.md, scripts/finalize_txt.py)

### 修复

- G4 明确 TXT 教程块必须是普通 Markdown，不得用代码块包住；否则 GIF 不会渲染。

## v1.4.8 — 2026-10-25

影响面：memo-cardest(SKILL.md, references/txt-workflow.md) / memo-txtimporter(SKILL.md, scripts/finalize_txt.py)

### 变更

- TXT 路线改为强制调用 `memo-txtimporter`：G0 选中 TXT 后立即调用该技能；删除 cardest 本地的容器格式副本、`import_guide.py` 和 GIF 资产，不再本地兜底。
- G4 增加 TXT 交付自检：最终消息必须包含 `finalize_txt.py` 输出和 `交付自检：导入教程已附`。

## v1.4.7 — 2026-10-25

影响面：memo-cardest(SKILL.md, references/txt-workflow.md, scripts/import_guide.py, references/assets/import-flow-36b59d.gif, references/assets/import-dialog-36b59d.png)

### 修复

- TXT 交付必须附导入教程与动图：新增 `scripts/import_guide.py`，`references/txt-workflow.md` 与 `SKILL.md` 要求交付时运行并把四步 + GIF 绝对路径附在消息末尾，修复“只发文字步骤、没发动图”。

## v1.4.6 — 2026-10-24

影响面：memo-cardest(SKILL.md)

### 变更

- 合并重复的「必须用问题框」规则：S0 定义一次通用交互约束，G0/G1 改为引用；删除重复文字，保留全部实质规则（路线确认、key 持久化询问、G1 两问、未回答不推进）。

## v1.4.5 — 2026-10-24

### 变更

- `behavioral-evals.md` 新增 I–M 五个场景：已明确 API 不重复问路线、TXT 双图按资产回填、OCR 完成但下载失败、无搜索工具时的产品答疑、同名技能多副本。
- 判定边界同步覆盖新增场景；仍要求记录未执行项，不把新增评测当作已通过。

## v1.4.4 — 2026-10-24

### 修复

- 更新器把 `.git` 文件也视为 Git 工作副本（支持 linked worktree），不再只认目录。
- 调用支链时交代本次路线、会员状态与 S0 结果，避免支链重复初始化。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.4.2 — 2026-10-23

### 修复

- 修正 G2 的表格参考链接：`Cognifair/maimemo-table` → `Cognifair/memo-table`（旧仓库停更，会把人引到过期内容）。
- README 安装清单补齐系列 6 个仓库，作为聚合安装入口。
- README 的「Memo 系列」表与 `references/satellites.md` 改由 `memo-series.json` 生成（`sync-series`），不再手写跨技能清单。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.4.1 — 2026-10-23

### 变更

- 支链展示名统一为「**迁墨 Memo-Ankitransfer**」（`memo-ankitransfer` 的正式展示名），同步到 `references/satellites.md` 的 `name` 字段、`SKILL.md` 支链段落与 `README.md` 支链表。
- 支链 ID、`repository_url`、`version_url` 均未变，不影响已安装副本的同步与版本检查。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.4.0 — 2026-10-23

### 新增

- 支链清单新增 `memo-ankitransfer`（Anki 图片挖空 → 墨墨图片遮罩，免导出直连本机 Anki，生成位置预览）；`references/satellites.md` 补入 `repository_url` 与已核验的 `version_url`，`allowed_version_hosts` 无需变更。
- `SKILL.md` 支链段落补充 Anki 支链的用途与边界：转换/预览不授权写卡，写入仍需目标牌组、章节与凭证，且逐张回读后才算交付。

### 变更

- `SKILL.md` 不再写死「三个支链」，同步范围以清单为准，避免新增支链后文案与实际不一致。
- `references/satellite-framework.md` 与 `README.md` 同步更新支链数量、GitHub 仓库与 `git clone` 安装示例。

### 核实

- 2026-10-23 实测 `https://raw.githubusercontent.com/Cognifair/memo-ankitransfer/main/version.json` 返回 `200` 与 `text/plain`，`id` / `version` / `updated_at` 字段齐全（`memo-ankitransfer` `v1.1.1`），按现有白名单可直接用于版本检查。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.9 — 2026-10-23

### 修复

- G0 新增交付路线问题框：写卡/改卡前必须确认「官方 API」还是「TXT」，即使消息里提到“接入 API”也要确认一次；用户已明确回答或明确只要 TXT 时跳过。
- 不再靠“提到 API”直接推断路线，避免跳过 TXT/API 选择。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.8 — 2026-10-23

### 新增

- G1 增加两个问题框提问：① 是否模仿用户牌组第一张卡的样式（可自由填写差异）；② 先按材料猜测章节切分，给 2–4 个基于实际结构的选项，并留一个自由填写项。
- 两个问题都要求使用交互式问题框；用户已说明或只做单张卡时跳过。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.7 — 2026-10-19

### 修复

- 恢复首次同步提问的硬性要求：**必须用交互式问题框**，不得只写文字就结束回合或直接终止对话；文字提问仅在确实没有控件时使用。SKILL.md 与支链框架同步改回。
- 恢复 API key 写入用户环境变量的可执行方法（`setx` / 用户级环境变量 API），保留“不要回显”和“只配置本人 key”的约束；记录命令历史的环境提醒用户本人执行。
- 技能描述补回“开工先做启动同步（首次问三档）”。

### 测试

- 56 项离线测试保持通过（本次为文档与描述改动）。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.6 — 2026-10-19

### 修复

- 保留首次开头三选一与等待选择；明确“不需要”为长期关闭，统一无回答时的规则。脚本不可用、状态损坏/被锁或保存失败时停止同步、继续独立业务，不重置授权、不反复提问。
- 凭证优先级改为本次明确指定的 key 优先，环境变量仅作默认；鉴权失败不自动回退旧账户。明确 TXT/本地制卡不再询问会员或读取凭证；安全保存凭证时不展开到命令记录。
- 更新显式选择清单指定的远端与分支，候选技能身份和版本匹配后才快进；更新后验证版本与 HEAD，避免跟随错误 upstream 或误报成功。
- 更新失败进入 `failed` 并返回 `partial`，Git 超时/不可用按支链报告。同步前验证状态可写并持久化消费一次授权；结束保存失败时返回实际同步结果，避免丢失已更新事实。
- 文档检查按交付路线执行，同一任务复用已核对文档；纯文本问答草稿不依赖平台文档。同步说明、界面提示和 README 保持一致。

### 验证

- 56 项离线测试通过，包含本地 Git 集成和状态异常回归，不访问真实账户。
- 新增 8 类制卡行为评测场景；本次独立执行首次初始化、状态读取失败、本地路线、凭证切换、限定条件与完整覆盖、批量续跑共 6 个模拟场景。完整枚举扩展与媒体场景留待执行；未进行真实账户写入、TXT 导入或客户端渲染验收。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.5 — 2026-10-19

### 变更

- G0 明确**只能配置用户自己的 API key**：他人提供的、共享的、来源不明或疑似他人的 key，不得写入本机用户环境变量。
- 设置确认的问题框加入提醒：接错会操作到别人的账户；选项改为「是我自己的 key，设置」/「不用，仅本次使用」。

### 安全

- key 来源存疑时先停下确认；宁可只用本次会话，也不写入环境变量。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.4 — 2026-10-19

### 新增

- G0 确认专业版并拿到 API key 后，用问题框询问是否写入用户环境变量 `MAIMEMO_TOKEN`；同意即设置，之后各会话直接读取，不再反复粘贴。
- 读取顺序固定为：用户级环境变量 → 本次提供的 key；环境变量存在时不再索要 key。

### 安全

- 设置只写用户级变量（`setx`、仅当前 Windows 用户生效），不回显 key；失败则本次继续用内存中的 key。
- 用户级环境变量是唯一允许的持久化位置，且必须经问题框明确同意；不得写入技能、状态、日志或 Git。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.3 — 2026-10-19

### 修复

- 技能描述补上真实触发词：连接墨墨 API、改卡、牌组操作。此前“链接 API key + 改牌组卡片”这类请求匹配不到本技能，Agent 会绕过整个流程。
- SKILL.md 顶部明确适用范围：任何写卡/改卡/牌组/API 请求都必须先走 S0，用户没提技能名也一样。
- S0 增加兜底：脚本不可用时仍须询问同步授权；用户直接给 key 要求改卡也算业务任务；已经动手才发现漏做时立即停下补做并说明。
- 安装文档补充：克隆或升级后必须重启 Codex / WorkBuddy，客户端只在启动时扫描技能目录，运行中的会话不会热更新。

### 测试

- 43 项离线测试保持通过（本次为文档与描述改动）。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.2 — 2026-10-19

### 变更

- 启动同步的首次授权询问**必须通过 Agent 的交互式问题框**（如 `ask_user_question`）发起，并让用户点选三档；不得只在正文写一句问题就结束回合，也不得直接终止对话。
- 用户未选择时不推进任何后续步骤；只有环境确实没有提问控件时，才退回文字提问并明确说明在等选择。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.3.1 — 2026-10-19

### 修复

- `inventory` 新增 `git_checkout` 字段，逐个副本标明是否 git 工作副本。
- `sync` 遇到 `not_a_git_checkout` 时返回 `hint`，明确提示用 `git clone` 重装，不再静默跳过。
- 文档补充「安装方式：必须 git clone」：复制文件或解压 ZIP 装出来的目录永远不会自动更新。

### 测试

- 覆盖 `git_checkout` 报告与 `sync.hint` 提示。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

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

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.2.1 — 2026-10-18

- `memo-table` 新增 `version.json`，三个支链均可做版本检查，`skipped` 不再出现 `version_source_unconfigured`。
- 文档同步说明三份清单的核验结果。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.2.0 — 2026-10-18

- 修复 `install_source` 校验：接受 `github_public_repository` 并校验 `repository_url`（此前整份配置被拒、框架报错）。
- 版本清单接受 GitHub Raw 的 `text/plain`；接入三份清单并限定白名单 `raw.githubusercontent.com`。
- 扫描顺序改为运行副本优先，新增 `copies` 字段，修复版本误报。
- 「仅这次」落盘为 `pending_once`，不再依赖对话记忆。
- 39 项测试通过。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.1.1 — 2026-10-16

- 文档与支链框架修订，发布 1.1.1。

## v1.4.3 — 2026-10-24

### 变更

- 新增 MIT `LICENSE`，README 补 License 说明。

## v1.1.0 — 2026-10-14

- 首个发布版本：制卡主流程、TXT / OCR / 表格支链说明、更新检查框架。
