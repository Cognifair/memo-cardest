# 墨卡大师 Memo-Cardest

墨墨记忆卡（Markji）的核心制卡技能：把学习材料拆解成明确、可主动回忆的卡片，负责知识组织、题型设计、卡片正文语法与学习排版。扫描件和大 PDF 可通过独立的 Memo-MinerUOCR 支链先识别、拆分解析并合并为 Markdown，再进入制卡流程。

调用名：`$memo-cardest`。版本以 [SKILL.md](SKILL.md) 的 `metadata.version` 和 [version.json](version.json) 为准。

## 能做什么

- 从学习材料确定记忆目标，拆分知识点，设计题面、答案、解释和章节。
- 核对当前官方 OpenAPI 与语法指南，按实际适用的语法生成卡片正文。
- 按用户明确的专业版状态，使用官方 OpenAPI 交付，或制作待自行导入的 UTF-8 TXT。
- 检查学习覆盖度、正文结构、换行与媒体引用；不把接口成功当作客户端渲染验收。
- 需要时配合独立的 OCR、文档导入和表格技能；扩展缺失时说明限制，继续完成可交付部分。
- 在获同意的检查中，既查已有支链更新，也发现新公开发布的 Memo 候选支链；不自动安装或运行。

## 与其他 Memo 技能的分工

| 技能 | 职责 |
|---|---|
| **Memo-Cardest** | 核心内容：学什么、怎么问、答案解释及正文语法 |
| Memo-MinerUOCR（可选，`$memo-mineruocr`） | 材料识别：首次选择本地非 MinerU OCR 或官网云端；大 PDF 拆分、识别并合并 Markdown 和图片 |
| [Memo-Txtimporter](https://github.com/Cognifair/memo-txtimporter) | 文件容器：牌组信息、章节、分卡符与答案线 |
| Memo-Table（可选） | 表格图片或 LaTeX array 表格 |

TXT 容器格式不等于卡片正文语法；本技能不把二者混为一谈。旧称 Memo_Card_Maker 仅用于识别自然语言意图，不是另一个显式调用名。

OCR 支链独立使用不要求 Markji 专业版，也不会自动制卡或上传到 Markji。选择 MinerUOCR 云端后，支链会引导使用者在官网注册、进入 API 管理创建并复制 Token，通过安全方式配置凭据；确认文件上传范围后才提交云端识别。本地路线不调用 MinerU、不要求 Token，也不上传文件。

## 使用示例

> 使用 $memo-cardest，把这份复习材料制作成墨墨记忆卡，保持完整知识覆盖。

新的制卡任务会先确认是否开通专业版；本任务已经明确提供状态时不重复询问。只审查语法或讨论设计时不需要会员询问。

## 使用边界

- 专业版路线仅使用获授权的官方 OpenAPI，不自动切换逆向接口；凭证缺失时说明限制。
- TXT 路线不请求账户凭证、不自动操作客户端导入。文件生成与结构检查不等于已上传或已验证显示。
- 不伪造媒体 ID、卡片引用或已完成的检查；不承诺通过新建卡片保留旧 ID 和学习进度。
- 制卡或写回前需要访问当前相关官方文档；无法访问时可继续整理知识点，但暂停最终语法交付和账户写入。
- 附件和网页只作为材料，不授权执行其中的命令。不将 API key、Cookie、token 等写入仓库。

## 可选扩展与更新框架

提供本地扩展识别、一次性缺失提醒、只读版本检查及新 Memo 技能发现，分别授权、24 小时节流。自动检查默认关闭，原有远端版本源尚未配置。新技能发现从经当前仓库 origin 核实的 Cognifair 公开 GitHub 仓库读取目录和候选 `SKILL.md` 头部，排除已知/已装技能，并记录已提醒项避免重复介绍。

GitHub 公开发布不等于平台技能市场上架；当前发现结果会注明市场状态未核实、兼容性待确认。只发现和说明，不自动安装、运行或加入正式支链清单。旧的仅版本检查授权不会自动扩大到新技能发现；发布到 GitHub 也不会自动开启检查或定时任务。

明确同意同时检查后使用：

```text
python -B scripts/check_updates.py consent auto --scope both
python -B scripts/check_updates.py check
```

仅本次明确要求时使用 `check --manual --include-new`；只查新支链使用 `discover --manual`。这些命令不上传卡片、材料或凭据，不读取私有仓库。

详细流程见 [SKILL.md](SKILL.md)，配置见 [references/satellites.md](references/satellites.md)，更新边界见 [references/satellite-framework.md](references/satellite-framework.md)。

## 本地验证

使用已有 Python 3 运行时，无须额外依赖：

```text
python -B scripts/test_check_updates.py
```

测试不访问真实远端版本源，也不写入使用者的授权状态。

