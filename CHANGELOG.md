# 变更记录

遵循语义化版本：修 bug → patch，新增能力 → minor，改变契约 → major。每个版本的说明同时用于 Git tag 与 GitHub Release。

## v1.14.5 — 2026-11-12

影响面：memo-cardest(README.md, CHANGELOG.md)

### 文档

- Memo Studio 的 npm 包已发布为 `memo-studio-dsh@0.1.9`；更新桌面端入口的安装说明和旧本地 link 名兼容说明。

## v1.14.4 — 2026-11-12

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/credentials.md, references/behavioral-evals.md)

### 修复

- 明确“用我的 API 查看/读取/核对/看样卡”只授权只读 GET，不等于 API 交付路线；读取完成后仍要单独问 API 写入还是 TXT。
- 凭证存在、读取成功、看到目标牌组都不能替代 G0 路线确认，也不能授权创建/修改/删除。
- 行为评测新增场景 U：把“用 API 查看”当成 API 交付、跳过路线询问判失败。

## v1.14.3 — 2026-11-09

影响面：memo-cardest(SKILL.md, CHANGELOG.md)

### 变更

- G2 语法边界更新：行内公式 `[E##...]` 由“未验证扩展”改为**已验证可用**——2026-11-09 在真实牌组批量写入并渲染通过；可写在句子中间，只有行首的 `E` 才算独立公式。
- 公式选项、公式挖空、删除线仍不当全局默认，照旧要求最小样卡实测。

## v1.14.2 — 2026-11-07

影响面：memo-cardest(README.md, CHANGELOG.md, companion.json)

### 新增

- 新增 `companion.json`（schema 1）：列出 Memo 系列技能、上传进度协议根目录和 Memo Studio 下载地址，作为两边轻量兼容契约。
- README 明确：Memo Studio 当前只做技能指南和只读进度，暂不读取 Cardest 版本/状态做检测；契约不是主技能硬依赖。

## v1.14.1 — 2026-11-07

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/image-redraw.md)

### 变更

- G1.4.1 从“化学任务才问结构式”改为**每次制卡/改卡先问视觉内容**：表格、统计图/示意图、公式图、化学结构式或反应式。
- 用户回答“有/不确定”时检查材料并交给 `memo-canvas`；回答“没有”时记 `visual: user-none`，但仍执行 G1.5 表格扫描，不能因用户说没有就跳过明显表格/图形。
- 纯语法审查可跳过；用户已经说明过时不再问。

## v1.14.0 — 2026-11-06

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/api-workflow.md, references/behavioral-evals.md, references/change-journal.md, references/image-redraw.md, references/upload-progress.md, scripts/change_journal.py, scripts/upload_task.py, scripts/test_upload_task.py, scripts/test_registry_discovery.py, scripts/fixtures/*)

### 新增

- G1.4.1 化学任务先问「有没有化学结构式或反应式」：有/不确定交给 `memo-canvas`，没有记 `figures: chemistry-none`；不默认化学任务一定有结构，也不把结构只交给 OCR。
- 新增 `scripts/upload_task.py` 上传任务登记与心跳模块：原子登记、恢复、执行者锁、显式 `retry-rejected`、未知结果不重发；`change_journal.py` 增加共享 `mutate()` 与 `retry-rejected` 原子变更。
- 上传进度文档补齐注册目录、心跳、会话绑定、换清单、ETA 与安全重试边界。

### 测试

- 更新器 65、变更清单 31、source inspector 5、resolver 4、upload_task 15、注册发现 5，共 125 项离线测试通过。

## v1.13.5 — 2026-11-04

影响面：memo-cardest(技能名称、调用示例与系列引用) / memo-ankigo / memo-txt

- 将 Anki 迁移技能标识统一为 `memo-ankigo`，TXT 技能标识统一为 `memo-txt`，更新安装路径与系列引用。
- 本次仅调整命名与文档；Anki 历史迁移包格式保持兼容。

## v1.13.4 — 2026-11-04

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/credentials.md, references/behavioral-evals.md)

### 修复

- 明确 API 路线不再询问“专业版/非专业版”：API 可用即按 pro/4500；没有 key 只问/引导配置 key，不把会员状态当 API 前置。
- 凭证说明删除“没有凭证时问会员”的分支；会员问题严格限定在 TXT 路线、仅用于字数上限。
- 行为评测新增场景 S：已选 API 又弹专业版问题判失败。

## v1.13.3 — 2026-11-03

影响面：memo-cardest(README.md, CHANGELOG.md)

### 文档

- 将“为什么问题这么多”改为“为什么还要分步提问”，表达必要收敛，而不是问题数量本身。

## v1.13.2 — 2026-11-03

影响面：memo-cardest(README.md, CHANGELOG.md)

### 文档

- README 新增「为什么问题这么多」：说明分步提问是为了把模糊需求收敛成可执行约束，而不是要求用户一开始写完整提示词、让模型靠自觉补细节。
- 同步修正首次使用说明中的 TXT 会员问题与图表/图像重绘触发描述。

## v1.13.1 — 2026-11-03

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/visual-brief.md, references/behavioral-evals.md)

### 修正

- 明确图表同批的边界：G1.4.1 与 G1.5 只调用一次 `memo-canvas`，但图片三档和表格样式必须分开提问，不能合成一个模糊问题。
- 新增 `references/visual-brief.md`：figures/tables 结构化交接、逐项回报、单项失败不拖累全批。
- 行为评测 R 补充“分开提问 + 逐项回报”，禁止 all-or-nothing。

## v1.13.0 — 2026-11-03

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/image-redraw.md, references/table-decision.md, references/capability-map.md, references/tables.md, references/design-toolbox.md, references/satellite-framework.md, references/behavioral-evals.md)

### 变更

- MEMO-CARDEST: 图表统一路由到墨兰迪，新增图像重绘检查点。

### 新增

- G1.4.1 图像重绘审查：扫描公式、数学图、化学结构、流程图等交给 `memo-canvas`，由它选择原样/高清化/精美重绘。
- 表格与图形同时命中时只调用一次 `memo-canvas`，避免重复询问。

## v1.12.0 — 2026-11-03

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/txt-workflow.md, references/credentials.md, references/capability-map.md, references/behavioral-evals.md)

### 变更

- TXT 路线改为先确认会员状态：专业版单卡上限 5000、非专业版 2000；按更稳的 4500 / 1800 硬上限设计。
- API 路线由可用凭证视为专业版，使用 4500 上限，不重复询问会员。
- G3 增加单卡字数硬/软上限；G4 调用 MT 时交接 `--member pro|free`，由 MT 做同一口径的最终校验。
- 更新 TXT 交接、凭证、能力地图和行为评测，明确“TXT 不读凭证，但仍要确认字数上限”。

## v1.11.0 — 2026-11-02

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/source-preflight.md, references/behavioral-evals.md, scripts/inspect_source.py, scripts/test_inspect_source.py)

### 新增

- G1.4 强制源文件预检：识别 PDF/DOCX/图片的文字层，图片版/无文字层必须先问本地 OCR、MinerU 还是先不 OCR。
- 新增 `scripts/inspect_source.py`：只读检查文字层、图片数量与建议动作；不跑 OCR、不联网。
- OCR 统一交给 `memo-mineruocr`；说 Token 未配置前先用 resolver 核实；OCR 后仍回到 G1.5 检查表格。
- 行为评测新增场景 Q：图片版 docx 未先问 OCR。

## v1.10.1 — 2026-11-02

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md)

### 修复

- G1 样式来源改为显式选择：我发样卡 / 目标牌组首卡 / 工具箱默认 / 自己描述；不再在用户没选时静默 fallback 到工具箱。
- 样卡或首卡读不到源码时停下说明并请用户补样卡，不凭标题猜样式；留痕 `style: sample | deck-first | toolbox | custom`。

## v1.10.0 — 2026-11-02

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/capability-map.md)

### 新增

- README 首屏增加「能做什么（直接这样说）」表，把批量删除、表格、TXT、OCR、卡跳跳、Anki、答疑都放到用户第一眼能看到的位置。
- SKILL 增加能力提示与路由：用户问「你能做什么 / 有哪些功能 / 怎么用」时先回答能力地图，不直接进入 G0 路线提问。
- 首次使用完成同步选择后提示一次能力入口，明确「批量删除是内置能力，不用另装技能」；其他任务不反复播报。
- 新增 `references/capability-map.md`，记录触发说法、执行技能与边界。
- 同步更新 frontmatter description，让批量删除与支线路由更容易被技能发现。

## v1.9.3 — 2026-11-02

影响面：memo-cardest(README.md, CHANGELOG.md)

### 修正

- 「为什么是样卡」补上 T2 那一档：报告首页把 T2+T3 记为 usable（GPT-5.2 为 64.3%），只写 T3 的 26–35% 会让读者以为比原文更悲观。
- 去掉引用里的年份：报告页未写明发布年份，不替它断言。

## v1.9.2 — 2026-11-02

影响面：memo-cardest(README.md, CHANGELOG.md)

### 变更

- 定位改为样卡驱动：首屏一句话改成「你写一张样卡，它把整份材料按这个口径做完」，并说明它不复刻 Anki 社区那种手写卡（题面聚焦、只引导一个答案、合意困难）。
- 新增「为什么是样卡，不是自动生成」一节，引用 Memory Machines 的实测分布（可直接复习只占 26–35%），说明为什么把判断交回给写卡人，而不是让模型从零定题面。
- 撤掉「读完整本书自动出 500 张卡」那条劝退行；「30 秒判断」表改为围绕样卡、支链与 TXT 路线。
- 「长什么样」补一句：样卡定下来后，题型、挖空粒度、解释写法与章节切分都照它走。
- 常见问题补一条「不提供样卡能直接做吗」。

### 测试

- 仅 README 与 CHANGELOG 改动，未动执行器与 SKILL.md；结构自检通过（details/summary 配对、链接可解析、memo-series 块与生成结果一致）。

## v1.9.1 — 2026-11-02

影响面：memo-cardest(README.md, .gitattributes, CHANGELOG.md)

### 变更

- README 按「第一次来的人」重排：首屏给一句话定位、适用与不适用、效果示例和两条安装路线；执行顺序、能力清单、同步与网络边界等技术细节折叠进 details。
- 新增常见问题（会员、API key、删卡、重启、上传、自动更新、与 Anki 的关系）；安装说明改用四个客户端的技能目录，不再要求先读懂状态目录。
- 新增 .gitattributes，把 scripts 标为 vendored、references 标为 documentation，GitHub 侧栏不再把本技能统计成 Python 项目。

### 测试

- 仅文档与仓库元数据改动，未动执行器与 SKILL.md；README 结构自检通过（details/summary 配对、相对链接可解析、memo-series 块与生成结果一致）。
- 100 项离线测试未重跑（无代码变更）。

## v1.9.0 — 2026-11-02

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/auto-update.md, scripts/check_updates.py, scripts/test_check_updates.py)

### 变更

- S0 在 `sync_mode=auto` 下改为只读 `check --include-host --manual`：比较支链版本和主链本地/远端 HEAD，不再由 S0 直接 fetch/merge。
- 实际更新交给 `MemoCardestSync` / LaunchAgent；后台任务未安装时只报告有新版，提示安装或手动 `sync`。
- `once` / 用户手动执行仍使用 `sync`，保留一次性更新路径。
- 新增 `check --include-host`；主链检查通过 `git ls-remote` 只读比较 HEAD，不改技能文件。

### 测试

- updater 65 项、change journal 31 项、resolver 4 项，共 100 项离线测试通过。

## v1.8.0 — 2026-11-02

影响面：memo-cardest(SKILL.md, README.md, scripts/change_journal.py, scripts/test_change_journal.py, references/change-journal.md, references/api-workflow.md, references/quality-and-troubleshooting.md, references/behavioral-evals.md, version.json, agents/openai.yaml, CHANGELOG.md)

### 新增

- P0 本地卡片变更清单：稳定键、完整基线与预期、真实 ID 和逐项状态；排他锁与原子文件替换，拒绝覆盖既有任务。
- P0 写后回读比对：由调用方按实时文档提供独立 GET 的归一化快照，精确检查正文、语法版本与目标身份，输出差异摘要与逐项统计。
- 写前落盘 uncertain，区分写成功和回读一致；不内置 API 路径、不联网、不读凭证、不自动重试或恢复，不改变 TXT 和原客户端预览要求。
- 98 项离线测试通过（新增 31 项，原有 67 项）；两项独立模拟行为检查通过，技能结构校验通过。未测试真实账户、实时接口或客户端渲染。

## v1.7.3 — 2026-11-01

影响面：memo-cardest(SKILL.md, CHANGELOG.md, version.json, agents/openai.yaml)

### 优化

- 将 OCR、Anki 等支链的实现介绍收敛为任务路由，要求先读对应技能；保留上传授权、TXT 缺失即停、强制表格触发与写后回读边界。
- 明确表格判定、交付检查、支链清单、同步框架与行为评测引用的读取时机；不修改自动更新策略、运行时脚本或支链内容。

## v1.7.2 — 2026-11-01

影响面：memo-cardest(SKILL.md, references/batch-delete.md, CHANGELOG.md, version.json, agents/openai.yaml)

### 优化

- 将主入口重复的批量删除操作步骤集中到现有 `references/batch-delete.md`，明确处理前完整阅读；原有匹配、确认、建章、移动、回读及交接流程保持不变。
- 主入口保留禁止不可逆删除、预览确认、仅移动已确认范围及由用户手动删章的安全边界；不修改运行时脚本、授权或后台任务。
- 67 项离线测试、四份本地副本的结构与引用完整性检查通过；未执行真实账户操作或客户端渲染验收。

## v1.7.1 — 2026-11-01

影响面：memo-cardest(SKILL.md, CHANGELOG.md, version.json, agents/openai.yaml, references/api-workflow.md, references/auto-update.md, references/behavioral-evals.md, references/credentials.md, references/satellite-framework.md, references/table-decision.md, references/tables.md, references/txt-workflow.md)

### 优化

- 将凭证处理、TXT 交付及平台更新安装细节集中到现有 reference，主入口保留触发条件、安全边界和必读引用，减少重复说明。
- 统一启动同步、API 路线确认、密钥保存授权及表格技能缺失时的处理规则；不改变核心制卡质量关卡及批量删除边界。
- 不修改运行时脚本；67 项离线测试通过，两组各 20 个模拟决策场景均通过，未观察到核心需求回归（非真实 API 测试）。

## v1.7.0 — 2026-11-01

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/table-decision.md, references/behavioral-evals.md)

### 新增

- G1.5 开局表格审查：材料或待改卡片正文中出现真实表格时，强制调用 `memo-table`，不再让模型自行手写或跳过。
- 增加 `tables: found(N) → memo-table invoked` / `tables: none` / `tables: user-skip` 留痕，并补充场景 N 行为评测。

### 修复

- 修正常见漏触发：模型看到表格但按普通文本直接制卡。

## v1.6.0 — 2026-11-01

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/auto-update.md, scripts/windows/, scripts/macos/)

### 新增

- 自动更新安装器：Windows Task Scheduler 与 macOS LaunchAgent，每 6 小时同步所有已安装的 Memo 根目录。
- 自动更新不检测具体 Agent 进程，适配任意客户端；安装需要完全权限，失败会明确报告未安装。
- 提供安装/卸载脚本、日志位置与限制说明。

### 变更

- S0 的「以后自动帮我同步」现在会走对应平台的安装器，而不是只记录偏好。

## v1.5.6 — 2026-11-01

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md)

### 变更

- S0 首次同步选项明确区分：仅这次同步不安装自动更新；以后自动同步需要开启完全权限才能完成安装。
- 没有完全权限时，S0 明确说明自动更新未安装，不假装已完成；安装后实际更新仍由沙箱外定时任务执行。

## v1.5.5 — 2026-11-01

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/satellite-framework.md, scripts/check_updates.py, scripts/test_check_updates.py)

### 修复

- 解决 workspace-write 下状态目录不可写被误报为“锁被占用”的问题：默认状态目录不可写时自动 fallback 到 `%TEMP%\MemoFramework`，并尽量复制原 `sync_mode` / `last_sync`。
- 新增明确的 `error / state_dir_not_writable`；真实并发锁仍为 `busy / sync_in_progress`，两者不再混淆。
- 支持 `--state-dir <workspace>\.memo-state` 作为显式工作区状态目录；不要求用户开完全权限。

## v1.5.4 — 2026-11-01

影响面：memo-cardest(SKILL.md, README.md, CHANGELOG.md, references/satellite-framework.md, scripts/check_updates.py, scripts/test_check_updates.py)

### 修复

- 解决主链不能自动同步的问题：S0 同步现在会检查当前主技能仓库；仅在 git 工作副本、工作区干净、`main` 分支、GitHub HTTPS origin 且目标可 fast-forward 时更新。
- 主链更新后当前会话暂停，提示重启/新会话；当前会话不继续用旧 SKILL 混杂新脚本。
- 旧版本没有 host 自更新逻辑，需要先手动 `git pull` 一次完成 bootstrap，之后由 S0 接管。

## v1.5.3 — 2026-10-31

影响面：memo-cardest(SKILL.md, scripts/secret_resolver.py, scripts/test_secret_resolver.py, references/credentials.md)

### 修复

- 凭证读取不再只依赖进程环境变量：统一经 `secret_resolver.py` 读取进程环境、Windows 用户级环境、`%LOCALAPPDATA%\MaimemoSecrets` 与工作区 `.memo-secrets`，支持工作区沙箱。

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
