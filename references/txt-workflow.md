# TXT 路线：交给 Memo-Txtimporter

选 TXT 后**立即调用** `memo-txtimporter` 技能（`skill` 工具，name=memo-txtimporter）。cardest 不本地封装 TXT、不复制容器格式、不自己写导入教程。

## 交接内容

- 牌组名称/简介、章节映射、卡片正文（原生 Markji 语法）、顺序与卡片数。
- 媒体：只引用已验证的既有媒体 ID；否则交纯文本 + 独立媒体清单，正文不留伪造 ID、文件路径或占位 Pic。
- 旧卡更新：TXT 不保留旧 ID、链接或学习进度，先说明；需要覆盖时让用户提供当前产品支持的格式并先备份。

## 由 txtimporter 负责

- `references/container-format.md`：容器格式与样本证据；
- `scripts/lint_txt.py`：结构校验；
- `scripts/finalize_txt.py`：交付尾注（四步 + GIF + 5000 / 无总量限制说明 + `交付自检：导入教程已附`）；
- `references/import-guide.md` / `.html`：图文指南。

## 边界

- 未安装 txtimporter 或调用失败：**停止 TXT 交付**，告知安装方式；不要本地兜底复制格式或教程。
- 不索要密钥、不调账户 API、不替用户导入；导入结果由用户确认。
- 交付消息必须原样包含 `finalize_txt.py` 的输出；缺教程或自检标记就标「未完成」。
- 用户明确说“不用教程”时才省略，并说明这次省略了。
- 具体按钮以当前官方说明或用户客户端为准，不凭历史截图编造。
