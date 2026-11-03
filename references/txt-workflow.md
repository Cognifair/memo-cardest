# TXT 路线：交给 Memo-Txtimporter

选 TXT 后先确认/询问会员状态并记录 `member: pro|free`、`char_limit: 4500|1800`，再调用 `memo-txtimporter`（`skill` 工具，name=memo-txtimporter）。cardest 不本地封装 TXT、不复制容器格式、不自己写导入教程。TXT 的会员问题只用于字数上限，不询问/读取 API 凭证。

这是 TXT 交接、校验与教程呈现的唯一详细说明：选定 TXT 时读取，交付前按此验收；API 路线不因本文件读取 TXT 教程。

## 交接内容

- 牌组名称/简介、章节映射、卡片正文（原生 Markji 语法）、顺序与卡片数。
- `member: pro|free` 与 `char_limit: 4500|1800`；每张卡已按该上限检查。未指定时 MT 按 free/1800 校验。
- 媒体：只引用已验证的既有媒体 ID；否则交纯文本 + 独立媒体清单，正文不留伪造 ID、文件路径或占位 Pic。
- 旧卡更新：TXT 不保留旧 ID、链接或学习进度，先说明；需要覆盖时让用户提供当前产品支持的格式并先备份。

## 由 txtimporter 负责

- `references/container-format.md`：容器格式与样本证据；
- `scripts/lint_txt.py`：结构校验；
- `scripts/finalize_txt.py --member pro|free`：先按 4500/1800 硬上限（4000/1600 软提醒）校验，再输出教程 + GIF + 平台上限/本次上限 + `交付自检：导入教程已附`；按实际脚本输出交付，不另维护步骤数量或教程副本；
- `references/import-guide.md` / `.html`：图文指南。

## 边界

- 未安装 txtimporter 或调用失败：**停止 TXT 交付**，告知安装方式；不要本地兜底复制格式或教程。
- 不索要密钥、不调账户 API、不替用户导入；导入结果由用户确认。
- 交付消息必须原样包含 `finalize_txt.py` 的输出；**按普通 Markdown 粘贴，不要用代码块包住**，否则 GIF 不会显示。缺教程或自检标记就标「未完成」。
- 只有用户明确说“不用教程”时可省略教程，并说明这次省略了；仍需运行校验，不得为省略教程跳过验证，也不得在未附教程时声称“导入教程已附”。
- 具体按钮以当前官方说明或用户客户端为准，不凭历史截图编造。
