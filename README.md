# 墨卡大师 Memo-Cardest v1.14.8

[![License: MIT](https://img.shields.io/github/license/Cognifair/memo-cardest?color=2f6f4f&label=license)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-4b5563)
![Agent](https://img.shields.io/badge/agent-Codex%20%7C%20Claude%20Code%20%7C%20WorkBuddy%20%7C%20DSH-4b5563)

**你写一张样卡，它把整份材料按这个口径做完。**

墨墨记忆卡（Markji）的制卡技能：拆知识点、设计题面、写卡片正文、按章节排版，最后走官方 OpenAPI 直接写回，或导出一份 UTF-8 TXT 由客户端导入。扫描件和大 PDF 可以先交给 [Memo-MinerUOCR](https://github.com/Cognifair/memo-mineruocr) 识别成 Markdown，再进入制卡流程。

调用名 `$memo-cardest` · [宣传页](https://moka-master.app.workbuddy.host/?sharecode=ZYHGDS4GEB) · [变更记录](CHANGELOG.md)

它不复刻「手写一张好卡」这件事。Anki 社区那种卡——题面聚焦、只引导一个答案、难度落在合意困难那一段——是人的判断，不是模型的判断。所以这里换了个做法：**你把标准做进一张样卡，它负责把标准复制到剩下的每一张上。**

## 能做什么（直接这样说）

| 你想做什么 | 直接说 | 谁执行 |
|---|---|---|
| 做卡、改卡、操作牌组 | “把这些材料做成卡” | `memo-cardest` |
| **批量删除卡片** | “把这些卡批量删掉” | **`memo-cardest` 内置 DELETE 章流程** |
| 表格 | “这张表做成表格卡” | `memo-canvas` |
| 图像重绘 | “这张公式图/化学结构/流程图保留或重画” | `memo-canvas` |
| 生成 TXT 自己导入 | “生成 TXT，不碰 API” | `memo-txt` |
| 扫描件 / PDF OCR | “先 OCR 再制卡” | `memo-mineruocr` |
| 卡片互链 / 目录跳转 | “给这两张卡加双向链接” | `memo-cardlink`（卡跳跳） |
| Anki 图片挖空迁墨 | “把 Anki 卡迁到墨墨” | `memo-ankigo`（迁墨） |
| 墨墨产品使用问题 | “这个设置在哪” | `memo-qahelper` |

批量删除不是独立技能，是主技能内置流程；表格由 G1.5、图像重绘由 G1.4.1 强制触发 `memo-canvas`；两者同时命中时一次调用、分开提问、逐项回报。

## 30 秒判断要不要装

| 你的情况 | 结论 |
|---|---|
| 已经有一张（或几张）自己认可的样卡，想按这个口径批量出 | 主用法。样卡决定题型、挖空粒度和解释的写法 |
| 有材料，但还没定样卡，愿意先做一张 | 装。先做一张样卡，再往下批量 |
| 已经在 Anki 里做图片挖空，想搬成墨墨原生遮罩 | 装，再配 [迁墨 Memo-AnkiGo](https://github.com/Cognifair/memo-ankigo) |
| 只想生成一份 TXT 自己导入，不碰 API | 装。不需要会员即可导入，也不需要 API key；但字数上限按账号区分（专业版 5000 / 非专业版 2000） |

## 长什么样

一张样卡，加三张同款。材料里的一句话：

> 立方和公式：a³ + b³ = (a + b)(a² − ab + b²)

**不这么写**：把整条公式挖空。你练的是符号的形状，换个字母就断。

**这么写**，拆成三张：

| 题面 | 答案面 |
|---|---|
| a³ + b³ 分解后的两个因式分别是什么？ | (a + b) 和 (a² − ab + b²) |
| 第二个因式里为什么是 −ab，而不是 +ab？ | 展开时 a·(−ab) 与 b·(a²) 的交叉项要正好抵消；写成 +ab 就消不掉 |
| 已知 a + b = 3、ab = 2，求 a³ + b³。 | 9。（a² − ab + b² = (a+b)² − 3ab = 3） |

这三张定下来之后，整章的题型、挖空粒度、解释怎么写、章节怎么切，都照它们走。

<!-- 截图位：把成品卡截图放到 docs/images/ 后，把下面这行注释换成真正的图片引用
![成品卡示例](docs/images/card-demo.png)
建议至少两张：一张客户端里的挖空卡，一张带表格的卡。
-->

## 为什么是样卡，不是自动生成

一张手写的好卡要同时满足三件事：题面聚焦、只引导一个答案、难度落在「合意困难」那一段。这三件事靠的是写卡人几千次复习攒出来的判断——只有复习到第三个月，才知道这张卡 cue 不 cue 得住。

模型目前做不到。Memory Machines 的实验（Kirkby 与 Matuschak）让前沿模型把划线和原文直接变成记忆卡，评分分布是这样的：

| 模型 | T0 跑偏 | T1 看着合理、几个月后失效 | T2 需打磨 | T3 可直接复习 |
|---|---|---|---|---|
| Opus 4.5 | 11% | 39% | 21% | 29% |
| Gemini 3 Pro | 12% | 34% | 28% | 26% |
| GPT-5.2 | 10% | 26% | 29% | 35% |

只有四分之一到三分之一能直接进复习，另有两到三成要打磨一遍才敢用。最要命的是 T1——读起来像回事，复习到第三个月才发现它 cue 不住——模型自己也识别不出来：判别「这张卡扛不扛得住」最高 64–67%，从四个候选里挑最好的，仍有 30–40% 挑中坏的那个。

所以这里把判断交回给你：**用一张样卡把「什么算好」定死，模型只负责复刻。** 报告原文见 [memory-machines.com/report](https://memory-machines.com/report)。

## 安装

技能就是一堆本地文件，没有安装包，也不需要联网。把仓库放进你客户端的技能目录即可：

| 客户端 | 技能目录 |
|---|---|
| DSH | `~/.agents/skills` |
| Codex | `~/.codex/skills` |
| Claude Code | `~/.claude/skills` |
| WorkBuddy | `~/.workbuddy/skills` |

### 路线 A：git clone（推荐）

能自动更新，也能被技能自带的同步检查识别。

```text
git clone https://github.com/Cognifair/memo-cardest.git <技能目录>/memo-cardest
```

### 路线 B：下载 ZIP

在仓库页 `Code → Download ZIP`，解压成 `<技能目录>/memo-cardest`（目录名要和 `SKILL.md` 里的 `name` 一致）。能用，但自带的同步检查会返回 `skipped: not_a_git_checkout`，只能手动更新。

### 装完之后

- **重启客户端**。Codex / WorkBuddy 只在启动时扫描技能目录，运行中的会话不会重新加载；DSH 会热加载，能看到即时变化。
- 在对话里说 `$memo-cardest`，或者直接说「帮我做几张卡」——技能的描述里已经写了触发词。

### 支链（可选）

支链是独立仓库，不随本仓库分发。缺了只降级，不影响主流程。

<details>
<summary>展开：支链的 clone 命令</summary>

```text
git clone https://github.com/Cognifair/memo-mineruocr.git
git clone https://github.com/Cognifair/memo-canvas.git
git clone https://github.com/Cognifair/memo-txt.git
git clone https://github.com/Cognifair/memo-ankigo.git
git clone https://github.com/Cognifair/memo-qahelper.git
```

克隆后用 `python -B scripts/check_updates.py inventory` 确认每项都有 `.git`；不建议 `--depth 1`，浅克隆在 `pull` 时偶尔需要完整历史。

</details>

## 第一次使用会发生什么

1. **问你要不要自动同步。** 三选一：仅这次同步 / 以后自动帮我同步（需要开启完全权限）/ 不需要。选过的选择会被记住，之后不再重复问。
2. **问两类问题。** 交付路线走官方 API 还是导出 TXT；以及章节怎么切、样式来源：你发一张样卡（推荐）/ 用目标牌组首卡 / 按工具箱默认 / 自己描述。用户没回答不往下推进。
3. **开工。** 先检查源文件有没有文字层：图片版/扫描件会先问你要不要 OCR，不会自己跑一套 OCR；没有文字层时不会假装已经读懂。遇到真实表格或公式图/化学结构/流程图会强制先调用 `memo-canvas`（墨兰迪）；走 API 路线时，每张卡写完都会回读比对，回读结果和写入状态一起报给你。

最小示例：

> 使用 `$memo-cardest`，把这份复习材料制作成墨墨记忆卡，保持完整知识覆盖。

正常首次任务先出现同步三选一；TXT 路线不读取 API 凭证、不碰 API key，但仍会问一次专业版/非专业版，用来确定单卡字数上限。

## 为什么还要分步提问

这不是流程冗余，也不是把决策推回给用户。

墨卡大师不要求你一开始就写一份“完美提示词”，也不要求你凭有限的记忆，把所有样式、章节、表格、OCR、字数和交付方式一次说清。它选择在少数会影响成品的节点上，一步步问清楚，把你的模糊想法细化成可执行的约束：

- 你要模仿哪张样卡、章节怎么切；
- 走 API 还是 TXT、账号是不是专业版；
- 源文件有没有文字层、要不要 OCR；
- 有没有表格、公式图、化学结构或流程图要交给墨兰迪；
- 单卡内容会不会超过平台字数上限。

已经明确回答过的不重复问；单张卡、明确的 TXT 请求等场景会跳过不必要的问题。

我们试过合并问题、减少提问，让模型根据上下文自己补。结果是模型开始猜风格、猜章节、猜表格和图片怎么处理，越多细节交给模型猜，越容易偏离你的真实需求。所以这里的选择是：

> **在影响成品的少数节点上问清楚，而不是一开始要求用户写出完美提示词，剩下的靠模型自觉。**

这些问题是为了收敛需求，不是为了拖长流程；如果某个问题不影响本次成品，就不应该问。

## 桌面端可选：Memo Studio

[Memo Studio](https://github.com/Cognifair/Memo-Studio-DSH) 是 **DSH 桌面端插件**，不是技能；npm 包名是 `memo-studio-dsh`，旧本地 link 名 `dsh-memo-skill-island` 继续兼容：

- 顶部一枚胶囊，点开是技能指南；
- 干活时显示状态、等待选择、上传进度；
- 只读状态，不执行制卡、上传或账户操作；
- 不能放进 `skills` 目录，也不适用于 Codex / Claude Code。

当前安装方式：

1. 到 [最新 Release](https://github.com/Cognifair/Memo-Studio-DSH/releases/latest) 下载 `install.cmd` 和 `install.ps1`；
2. 双击 `install.cmd`，脚本会下载正式版、校验 `SHA256SUMS.txt`、解压到固定目录；
3. 把脚本复制的命令粘贴到 DSH 桌面端：
   `plugin_manager install_bundle  target = <脚本输出的 package 路径>`；
4. 没出现胶囊就重启 DSH。

npm 包已发布：`memo-studio-dsh@0.1.9`。可以直接在 DSH 里说「把 memo-studio-dsh 装上」。它是可选项，不装不影响制卡。

两边预留了轻量兼容契约：[companion.json](companion.json)（schema 1），列出 Memo 技能、进度协议根目录和 Studio 下载地址。当前 Studio 只做技能指南和只读进度，**暂不读取 Cardest 版本/状态做检测**；这份契约留给后续对接，不会成为主技能的硬依赖。

## 常见问题

**要买墨墨会员吗？** TXT 路线不需要会员即可导入，但单卡字数上限不同：专业版 5000、非专业版 2000；API 路线用官方 OpenAPI 直接写回，需要对应的专业版授权。

**要 API key 吗？** 只有 API 路线需要。默认读环境变量 `MAIMEMO_TOKEN`，也可以在一次任务里单独指定；本次指定的 key 优先于默认值，验证失败不会自动改用另一个账户。

**会不会删掉我已经有的卡？** 不会自动删。批量删除时，AI 只把目标卡移进 `DELETE` 章节并回读核对，最后的删除动作由你在客户端里手动完成，不调用删除接口。

**装完了，但对话里没反应？** 先重启客户端。Codex / WorkBuddy 只在启动时扫描技能目录；DSH 热加载，不用重启。另外确认目录名是 `memo-cardest`，和 `SKILL.md` 的 `name` 一致。

**我的材料会被上传吗？** 主流程只在本地读文件。只有你主动选择 MinerU 云端 OCR 时才会提交文件，而且会先确认上传范围；本地 OCR 路线不联网、不需要 Token。

**要不要开自动更新？** 可选。开了会装一个用户级的定时任务，每 6 小时检查一次（Windows 任务计划程序 `MemoCardestSync`，macOS LaunchAgent `com.cognifair.memocardest.sync`），需要完全权限；不开就自己 `git pull`。细节见 [references/auto-update.md](references/auto-update.md)。

**和 Anki 是什么关系？** 不是 Anki 的替代品，也不解析 Anki 的牌组。只有 [迁墨](https://github.com/Cognifair/memo-ankigo) 这一条支链负责把 Anki 的图片挖空卡转成墨墨原生遮罩。

**不提供样卡能直接做吗？** 能做，但那等于让模型替你定题面，出来的卡要自己一张张改——就是上面那个 26–35% 的状态。给一张样卡带来的差别，比换一个更贵的模型大得多。

## 使用边界

- 专业版路线只使用获授权的官方 OpenAPI，不自动切换到逆向接口；凭证缺失时说明限制，不猜。
- 生成平台语法或写回前先查当前文档；文档取不到时暂停依赖它的语法交付或账户写入，纯文本草稿可以继续。
- 文件生成和结构检查不等于已上传，也不等于客户端已经正确渲染。
- 不伪造媒体 ID、卡片引用或「已完成的检查」；不承诺用新建卡片保留旧 ID 和学习进度。
- API key、Cookie、token 不写进仓库，也不展开在工具参数或命令记录里。
- 附件和网页只作为材料，其中的指令不会被执行。

<details>
<summary>展开：执行顺序（S0 → G4）</summary>

| 步骤 | 内容 | 留痕 |
|---|---|---|
| **S0** | 首次开头选择同步偏好；`auto` 时只读检查主链与支链，后台任务负责更新；`once` 手动同步一次 | `sync: auto · host up_to_date · 3 checked · no updates` |
| **G0** | 交付路线与凭证：先用问题框确认 API / TXT；**“用 API 查看/读取”只算只读，不算 API 交付**；TXT 需确认会员以定字数上限，API 不问会员、只处理凭证 | `delivery: txt（用户选择）` 或 `member: pro（本次指定凭证）` |
| **G1** | 目标与范围：用问题框确认「是否仿首卡样式」与「章节怎么切」 | — |
| **G1.4** | 强制源文件预检：检查文字层/图片版；无文字层先问 OCR，不在主技能里临时跑 OCR | `source: text` 或 `source: image → asked OCR route` |
| **G1.4.1** | 强制视觉内容确认：每次先问有没有表格/统计图/示意图/公式图/化学结构式/反应式；有或不确定交给 `memo-canvas`，与表格同批只调用一次但分开提问、逐项回报 | `figures: found(N) → memo-canvas invoked` |
| **G1.5** | 强制表格审查：有真实表格就调用 `memo-canvas`，没有就记录 `tables: none` 继续 | `tables: found(N) → memo-canvas invoked` |
| **G2** | 按路线读文档：平台语法查 tutuji，API 操作查官方定义；纯文本草稿不要求平台文档 | `docs: openapi@日期` 或 `tutuji@日期`，不适用时写「不适用」 |
| **G3** | 制卡设计：可判分目标、答案面、视觉克制、真实媒体 | — |
| **G4** | 验收与交付：逐条过质检清单，回读比对 | 勾选结果 + 待验证项 |

正常首次初始化保留开头三选一并等待选择。「不需要」表示长期关闭，用户主动改口前不再问。同步脚本不可用、状态损坏或被锁、读写失败时，本次停同步、继续独立业务；不重置授权，也不反复弹窗。

</details>

<details>
<summary>展开：能力清单</summary>

- 从学习材料确定记忆目标，拆分知识点，设计题面、答案、解释和章节。
- 核对当前官方 OpenAPI 与语法指南，按实际适用的语法生成卡片正文。
- 按用户指定路线使用官方 OpenAPI 或制作 UTF-8 TXT；明确要本地文件时不读取 API 凭证，但仍确认会员状态以决定单卡字数上限。
- 检查学习覆盖度、正文结构、换行与媒体引用；不把接口成功当作客户端渲染验收。
- API 卡片操作提供本地变更清单、逐项状态和独立回读比对；接口字段按实时文档提取，脚本不联网、不读取凭证、不自动重试或续跑。说明见 [卡片变更记录](references/change-journal.md)。
- 需要时配合独立的 OCR、文档导入和表格技能；扩展缺失时说明限制，继续完成可交付部分。
- 批量删除：AI 只把目标卡移入 `DELETE` 章节并回读核对，最后由用户在客户端手动删除该章。
- 开局强制审查真实表格；发现表格就调用 `memo-canvas`，没有才继续普通制卡。
- 每次业务任务开局先做一次同步检查（首次会询问授权）：先检查主技能自身，再按已核实仓库更新支链。
- 旧称 `Memo_Card_Maker` 仅用于识别自然语言意图，不是另一个调用名。

</details>

<details>
<summary>展开：自动同步与状态（可选功能，排查时看）</summary>

自动同步要求主技能和支链都是 git 工作副本；拷贝文件或解压 ZIP 安装时，`sync` 会对相应项返回 `skipped: not_a_git_checkout`。更新只显式拉取清单里的远端分支，核对技能身份和版本后做快进合并，不依赖当前分支的 upstream。旧版本没有主链自更新逻辑时，先手动 `git pull` 一次完成 bootstrap，之后由 S0 接管。

状态目录默认是 `%LOCALAPPDATA%\Codex\MemoFramework`。沙箱不允许写时，脚本会自动 fallback 到 `%TEMP%\MemoFramework`，并尽量从原状态复制 `sync_mode` / `last_sync`，不会误报成「锁被占用」。TEMP 也不可写时用显式目录：

```text
python -B scripts/check_updates.py --state-dir "<workspace>\.memo-state" sync
```

这是每个工作区独立的状态，可能和桌面端的状态分叉。真实并发锁返回 `busy` / `sync_in_progress`；状态目录不可写返回 `error` / `state_dir_not_writable`，不是锁冲突。

安装用户级后台任务（需要完全权限）：Windows 用 `scripts\windows\install_sync_task.ps1`，macOS 用 `scripts/macos/install_sync_agent.sh`。两个平台都是每 6 小时一次，不检测具体 Agent 进程，同步所有已安装的 Memo 根目录。`auto` 模式下 S0 只跑 `check --include-host --manual`，不改技能文件；实际更新由后台任务执行。当前会话不会重载新版本，更新后需重启或新会话。安装失败必须明确报告，不会假装已安装。

</details>

<details>
<summary>展开：执行器命令</summary>

```text
python -B scripts/check_updates.py <命令>
```

| 命令 | 作用 |
|---|---|
| `inventory` / `status` | 本地已装支链 / 当前同步与授权状态（只读，不联网） |
| `sync` | 手动或后台完整同步：未授权返回 `needs_consent`；`auto` / `once` 时检查并更新主技能与支链 |
| `sync-consent once\|auto\|off` | 记录同步授权（仅这次 / 以后自动 / 不需要）；`auto` 的自动更新安装需要完全权限 |
| `check [--manual] [--include-new] [--include-host]` | 只读版本检查；`--include-host` 额外比较主技能本地与远端 HEAD |
| `discover [--manual]` | 只做新技能发现 |
| `complete --task-id <id>` | 记录一次业务交付，返回缺失能力是否需要介绍 |
| `missing --id <支链> --session-id <会话>` | 记录任务中的缺失提醒 |
| `record pitch\|declined\|discovery-notified\|discovery-dismissed` | 记录提醒与拒绝 |

</details>

<details>
<summary>展开：授权与状态</summary>

| 项 | 说明 |
|---|---|
| 默认 | `sync_mode=unset`：首次使用先问，未回答不授权 |
| `once` | 只尝试同步这一次；CLI 在动作前持久化清除 `sync_pending_once`，失败或中断也不自动重用授权 |
| `auto` | 每次任务开局自动同步，不再询问 |
| `off` | 不同步、不追问；用户主动改口才重新授权 |
| 节流 | 启动同步每次执行；独立 `check` 与技能发现按来源间隔 24 小时 |
| 状态位置 | 写入操作系统本地数据目录，**不写回本仓库** |
| 状态隔离 | 每个技能独立；安装副本不携带他人的授权 |
| 异常 | 状态故障不重置授权、不重复询问；更新前检查可写，更新后保存失败返回 `sync_report` 保留实际结果 |

</details>

<details>
<summary>展开：架构与不变量</summary>

| 层 | 文件 | 作用 |
|---|---|---|
| 行为规范 | [SKILL.md](SKILL.md) | S0–G4 执行顺序、留痕要求、支链与更新政策 |
| 参考知识 | `references/*.md` | 按需读取：API、TXT、设计工具箱、表格、质检、支链框架 |
| 执行器 | `scripts/check_updates.py` | 本地盘点、启动同步、版本检查、新技能发现；显式拉取远端分支、核验后仅快进合并 |
| 自动更新 | `scripts/windows/`, `scripts/macos/` | 可选安装用户级定时同步任务 |
| 自带测试 | `scripts/test_check_updates.py` | 离线验证执行器，不访问真实版本源 |
| 行为评测 | [references/behavioral-evals.md](references/behavioral-evals.md) | 初始化、凭证路由、知识覆盖、重复执行与媒体场景 |
| 版本标识 | [version.json](version.json) | 供版本检查读取 |
| 界面配置 | `agents/openai.yaml` | 展示名与默认提示词 |

入口只保留路线选择、强制步骤和安全边界，详细规则按任务读取：

| 任务 | 先读 |
|---|---|
| API 路线 | [references/credentials.md](references/credentials.md) → [references/api-workflow.md](references/api-workflow.md) |
| TXT 路线 | [references/txt-workflow.md](references/txt-workflow.md) |
| 发现表格 | [references/table-decision.md](references/table-decision.md) |
| 批量删除 | [references/batch-delete.md](references/batch-delete.md) |
| 自动更新安装 | [references/auto-update.md](references/auto-update.md) |
| 维护 / 评测 | [references/satellite-framework.md](references/satellite-framework.md)、[references/behavioral-evals.md](references/behavioral-evals.md) |

三条不变量：

1. **主功能自包含。** 任何支链缺失都只降级——说明实际限制，继续完成可交付部分，不让核心流程停摆。
2. **授权先于动作。** 同步默认未授权，首次使用必须先问；新支链发现是另一项独立授权，未经要求不扫描。
3. **更新仅允许快进。** 只对清单内、来源已核实的支链和当前主技能更新，提交 ID 可追溯；工作区脏、远端或分支不符、历史分歧、非 git 仓库一律跳过。主技能更新后当前会话暂停，重启或新会话生效。

</details>

<details>
<summary>展开：网络边界与状态区分</summary>

- 版本清单只向 `allowed_version_hosts` 白名单域名发起 HTTPS GET；当前为 `raw.githubusercontent.com`。
- 6 秒超时；版本清单响应上限 16 KiB；仓库发现时单份技能上限 256 KiB、公开列表上限 2 MB。
- 禁止重定向、禁止 URL 内凭据与查询参数、禁止 IP 字面量与私网解析地址。
- 不带 Token、Cookie 等凭据；不上传卡片、材料、对话或本地技能清单。
- Git 更新核对 `origin` 的唯一有效 URL 与 `repository_url`，显式拉取 `repository_branch`，验证候选技能和版本后只做 fast-forward。

| 状态 | 含义 |
|---|---|
| `publication=public_github_repository` | GitHub 公开仓库已存在、技能头部可读 —— **不等于**平台已上架 |
| `marketplace_status=unverified` | 未核实平台技能市场条目 |
| `not_configured` / `throttled` / `failed` / `partial` | **都不是**「已是最新版」，也不等于「没有新技能」 |

</details>

<details>
<summary>展开：维护与本地验证</summary>

发布新版本时，以下四处保持一致：

- [SKILL.md](SKILL.md) 的 `metadata.version`
- [version.json](version.json) 的 `version`
- `agents/openai.yaml` 展示名里的版本后缀
- [CHANGELOG.md](CHANGELOG.md) 的最新条目

离线测试（只用已有的 Python 3，不需要额外依赖）：

```text
python -B scripts/test_check_updates.py
```

测试不访问真实远端版本源，也不写入使用者的授权状态；包含本地 Git 仓库集成测试，覆盖错误 upstream、候选版本或身份不一致、分支分歧、失败分类与状态读写异常。维护后另按 [行为评测](references/behavioral-evals.md) 执行代表性用户场景并记录实际输出。离线测试通过不代表真实账户写入、TXT 导入或客户端渲染已验证。

</details>

## 目录结构

```text
memo-cardest/
├── SKILL.md                 # 行为规范：S0–G4、留痕、边界
├── references/              # 按需读取的细节文档（API、TXT、表格、质检…）
├── scripts/
│   ├── check_updates.py     # 执行器：盘点、同步、版本检查
│   └── windows|macos/       # 可选的后台同步任务安装脚本
├── agents/openai.yaml       # 展示名与默认提示词
├── version.json             # 版本标识
├── CHANGELOG.md             # 变更记录
└── LICENSE                  # MIT
```

## Memo 系列

<!-- memo-series:begin -->
| 技能 | 职责 |
|---|---|
| [Memo-MinerUOCR](https://github.com/Cognifair/memo-mineruocr) | 扫描件与大 PDF 识别、拆分并合并 Markdown |
| [墨兰迪 Memo-Canvas](https://github.com/Cognifair/memo-canvas) | 表格图片与 LaTeX array 表格制作，扫描图像高清化与忠实重绘 |
| [墨记文档导入 Memo-TXT](https://github.com/Cognifair/memo-txt) | TXT 容器格式、分卡校验与图片回填 |
| [迁墨 Memo-AnkiGo](https://github.com/Cognifair/memo-ankigo) | Anki 图片挖空转墨墨原生遮罩 |
| [Memo-QAhelper](https://github.com/Cognifair/memo-qahelper) | 墨墨记忆卡使用答疑（官方百科与论坛） |
| [卡跳跳 Memo-CardLink](https://github.com/Cognifair/memo-cardlink) | 卡片单向跳转、双向互链与 Card 引用审计（原 Memo-Link） |
<!-- memo-series:end -->

## License

[MIT](LICENSE) © Cognifair

## API 上传进度（本地新增，尚未发布）

上传脚本使用固定 `UploadTask` 模块自动登记会话和清单，支持后台进度、重启后的观察恢复及明确拒绝后的显式有限重试。逐卡状态仍只保存在 change_journal 清单中，未知结果不会自动重发。接入契约见 [upload-progress.md](references/upload-progress.md)，参考实现见 [upload_example.py](scripts/upload_example.py)。
