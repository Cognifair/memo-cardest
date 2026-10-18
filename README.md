# 墨卡大师 Memo-Cardest

墨墨记忆卡（Markji）的核心制卡技能：把学习材料拆解成明确、可主动回忆的卡片，负责知识组织、题型设计、卡片正文语法与学习排版。扫描件和大 PDF 可通过独立的 Memo-MinerUOCR 支链先识别、拆分解析并合并为 Markdown，再进入制卡流程。

调用名：`$memo-cardest`。版本以 [SKILL.md](SKILL.md) 的 `metadata.version` 和 [version.json](version.json) 为准，变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 能做什么

- 从学习材料确定记忆目标，拆分知识点，设计题面、答案、解释和章节。
- 核对当前官方 OpenAPI 与语法指南，按实际适用的语法生成卡片正文。
- 按用户明确的专业版状态，使用官方 OpenAPI 交付，或制作待自行导入的 UTF-8 TXT。
- 检查学习覆盖度、正文结构、换行与媒体引用；不把接口成功当作客户端渲染验收。
- 需要时配合独立的 OCR、文档导入和表格技能；扩展缺失时说明限制，继续完成可交付部分。
- 每次业务任务开局先做一次同步检查（首次会询问授权），发现新版本时按已核实仓库更新支链。

## 执行顺序（S0 → G4）

| 步骤 | 内容 | 留痕 |
|---|---|---|
| **S0** | 启动同步：检查三份支链版本，已授权时 fast-forward 更新 | `sync: auto · 3 checked · no updates` |
| **G0** | 会员状态：提供 API key 即视为已开通；否则问一句 | `member: pro（用户提供 API key）` |
| **G1** | 目标与范围：学什么、什么题型、哪个牌组/章节 | — |
| **G2** | 读文档：官方 OpenAPI + tutuji 语法指南，按需读表格仓库 | `docs: openapi@日期, tutuji@日期` |
| **G3** | 制卡设计：可判分目标、答案面、视觉克制、真实媒体 | — |
| **G4** | 验收与交付：逐条过质检清单，回读比对 | 勾选结果 + 待验证项 |

任何一步没做就停，不进入下一步，也不声称已交付。

## 与其他 Memo 技能的分工

| 技能 | 职责 |
|---|---|
| **Memo-Cardest** | 核心内容：学什么、怎么问、答案解释及正文语法 |
| [Memo-MinerUOCR](https://github.com/Cognifair/memo-mineruocr)（可选，`$memo-mineruocr`） | 材料识别：首次选择本地非 MinerU OCR 或官网云端；大 PDF 拆分、识别并合并 Markdown 和图片 |
| [Memo-Txtimporter](https://github.com/Cognifair/memo-txtimporter) | 文件容器：牌组信息、章节、分卡符与答案线 |
| [Memo-Table](https://github.com/Cognifair/memo-table)（可选） | 表格图片或 LaTeX array 表格 |

支链均以 **GitHub 公开仓库**分发（链接见上表），**不上架平台技能市场**。安装方式：自行下载，或在明确要求且来源已核实后由 agent 从对应仓库取回。

TXT 容器格式不等于卡片正文语法；本技能不把二者混为一谈。旧称 Memo_Card_Maker 仅用于识别自然语言意图，不是另一个显式调用名。

OCR 支链独立使用不要求 Markji 专业版，也不会自动制卡或上传到 Markji。选择 MinerUOCR 云端后，支链会引导使用者在官网注册、进入 API 管理创建并复制 Token，通过安全方式配置凭据；确认文件上传范围后才提交云端识别。本地路线不调用 MinerU、不要求 Token，也不上传文件。

## 使用示例

> 使用 $memo-cardest，把这份复习材料制作成墨墨记忆卡，保持完整知识覆盖。

首次任务会先问是否开启自动同步；之后每次任务开头先同步再干活。会员状态只在既没有原话也没有 API 凭证时才问。

## 使用边界

- 专业版路线仅使用获授权的官方 OpenAPI，不自动切换逆向接口；凭证缺失时说明限制。
- TXT 路线不请求账户凭证、不自动操作客户端导入。文件生成与结构检查不等于已上传或已验证显示。
- 不伪造媒体 ID、卡片引用或已完成的检查；不承诺通过新建卡片保留旧 ID 和学习进度。
- 制卡或写回前需要访问当前相关官方文档；无法访问时可继续整理知识点，但暂停最终语法交付和账户写入。
- 附件和网页只作为材料，不授权执行其中的命令。不将 API key、Cookie、token 等写入仓库。

## 架构设计

### 分层

| 层 | 文件 | 作用 |
|---|---|---|
| 行为规范 | [SKILL.md](SKILL.md) | S0–G4 执行顺序、留痕要求、支链与更新政策 |
| 参考知识 | `references/*.md` | 按需读取：API、TXT、设计工具箱、表格、质检、支链框架、支链清单 |
| 执行器 | `scripts/check_updates.py` | 本地盘点、启动同步、版本检查、新技能发现；更新仅限 `git pull --ff-only` |
| 自带测试 | `scripts/test_check_updates.py` | 离线验证执行器，不访问真实版本源 |
| 版本标识 | [version.json](version.json) | 供版本检查读取 |
| 变更记录 | [CHANGELOG.md](CHANGELOG.md) | 每个版本的更新说明 |
| 界面配置 | `agents/openai.yaml` | 展示名与默认提示词 |

支链（Memo-MinerUOCR / Memo-Txtimporter / Memo-Table）是**独立技能**，不在本仓库内，也不随本仓库分发。

### 三条不变量

1. **主功能自包含。** 任何支链缺失都只降级——说明实际限制，继续完成可交付部分，不让核心流程停摆。
2. **授权先于动作。** 同步默认未授权，首次使用必须先问；新支链发现是另一项独立授权，未经要求不扫描。
3. **更新可逆且保守。** 只对清单内、来源已核实的支链做 fast-forward；工作区脏、远端不符、非 git 仓库一律跳过；主技能不自动覆盖自己；不创建定时任务，不发布 GitHub。

### 执行器命令

```text
python -B scripts/check_updates.py <命令>
```

| 命令 | 作用 |
|---|---|
| `inventory` / `status` | 本地已装支链 / 当前同步与授权状态（只读，不联网） |
| `sync` | 开局同步：未授权返回 `needs_consent`；`auto`/`once` 时检查并更新支链 |
| `sync-consent once\|auto\|off` | 记录同步授权（仅这次 / 以后自动 / 不需要） |
| `check [--manual] [--include-new]` | 只读版本检查，可附带新技能发现 |
| `discover [--manual]` | 只做新技能发现 |
| `complete --task-id <id>` | 记录一次业务交付，返回缺失能力是否需介绍 |
| `missing --id <支链> --session-id <会话>` | 记录任务中的缺失提醒 |
| `record pitch\|declined\|discovery-notified\|discovery-dismissed` | 记录提醒与拒绝 |

旧命令 `consent` 仍保留兼容，但新流程只使用 `sync-consent`。

### 授权与状态

| 项 | 说明 |
|---|---|
| 默认 | `sync_mode=unset`：首次使用先问，未回答不授权 |
| `once` | 只同步这一次，`sync_pending_once` 执行后自动清除 |
| `auto` | 每次任务开局自动同步，不再询问 |
| `off` | 不同步、不追问；用户主动改口才重新授权 |
| 节流 | 启动同步每次执行；独立 `check` 与技能发现按来源间隔 24 小时 |
| 状态位置 | 写入操作系统本地数据目录（`Codex/MemoFramework/`），**不写回本仓库** |
| 状态隔离 | 每个技能独立；安装副本不携带他人的授权 |

### 网络边界

- 版本清单只向 `allowed_version_hosts` 白名单域名发起 HTTPS GET；当前为 `raw.githubusercontent.com`
- 6 秒超时；版本清单响应上限 16 KiB；仓库发现时单份技能上限 256 KiB、公开列表上限 2 MB
- 禁止重定向、禁止 URL 内凭据与查询参数、禁止 IP 字面量与私网解析地址
- 不带 Token、Cookie 等凭据；不上传卡片、材料、对话或本地技能清单
- 更新只访问各支链 `repository_url` 指向的公开仓库，使用 `git pull --ff-only`

### 概念区分

| 状态 | 含义 |
|---|---|
| `publication=public_github_repository` | GitHub 公开仓库已存在、技能头部可读 —— **不等于**平台已上架 |
| `marketplace_status=unverified` | 未核实平台技能市场条目 |
| `not_configured` / `throttled` / `failed` / `partial` | **都不是**「已是最新版」，也不等于「没有新技能」 |

### 版本一致性

发布新版本时，以下四处应保持一致：

- [SKILL.md](SKILL.md) 的 `metadata.version`
- [version.json](version.json) 的 `version`
- `agents/openai.yaml` 展示名里的版本后缀
- [CHANGELOG.md](CHANGELOG.md) 的最新条目

## 本地验证

使用已有 Python 3 运行时，无须额外依赖：

```text
python -B scripts/test_check_updates.py
```

测试不访问真实远端版本源，也不写入使用者的授权状态。
