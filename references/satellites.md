# 可选支链清单

本技能的核心功能独立可用；下列能力仅按任务需要调用。

**分发渠道是 GitHub 公开仓库**：每项的 `repository_url` 即安装来源，`install_source` 标记来源类型。`marketplace_listing` 恒为 `null`——本项目不走上架平台市场，因此不声称「市场上架」，也不承诺「从市场一键安装」。安装与更新的允许条件见 [satellite-framework.md](satellite-framework.md)。

`version_url` 为 `null` 表示暂无可检查的版本源；未配置不等于已经是最新版。版本检查与新支链发现分别授权、默认关闭。三份 `version.json` 均已于 2026-10-18 逐项核验可读，`allowed_version_hosts` 只放行 `raw.githubusercontent.com`。

**安装必须是 git 工作副本**：自动同步用 `git pull --ff-only`，复制文件或解压 ZIP 装出来的目录没有 `.git`，同步会返回 `skipped: not_a_git_checkout`，看起来已装但永远不会更新。

```json
{
  "schema": 1,
  "skill_id": "memo-cardest",
  "auto_check": false,
  "throttle_hours": 24,
  "allowed_version_hosts": ["raw.githubusercontent.com"],
  "new_skill_discovery": {
    "provider": "github_public",
    "owner": "Cognifair",
    "repo_prefix": "memo-",
    "auto_check": false,
    "max_pages": 3,
    "max_candidates": 10
  },
  "satellites": [
    {
      "id": "memo-mineruocr",
      "name": "Memo-MinerUOCR",
      "capability": "先选择本地非 MinerU OCR 或官网云端，再对扫描材料与大 PDF 拆分识别、整理素材并合并 Markdown",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-mineruocr",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-mineruocr/main/version.json"
    },
    {
      "id": "memo-txtimporter",
      "name": "墨记文档导入 Memo-Txtimporter",
      "capability": "封装与校验 TXT 章节、分卡符和答案线",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-txtimporter",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-txtimporter/main/version.json"
    },
    {
      "id": "memo-table",
      "name": "墨记表格制作 Memo-Table",
      "capability": "制作表格图片或 LaTeX array 表格",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-table",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-table/main/version.json"
    }
  ]
}
```
