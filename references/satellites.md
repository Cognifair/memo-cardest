# 可选支链清单

本技能的核心功能独立可用；下列能力仅按任务需要调用。

**由 `memo-series.json` 生成，请勿手改**：新增技能只改清单，再跑 `sync-series`。

**分发渠道是 GitHub 公开仓库**：`repository_url` 即安装来源；`marketplace_listing` 恒为 `null`。

**安装必须是 git 工作副本**：复制文件或解压 ZIP 装出来的目录没有 `.git`，同步会返回 `skipped: not_a_git_checkout`。

```json
{
  "schema": 1,
  "skill_id": "memo-cardest",
  "auto_check": false,
  "throttle_hours": 24,
  "allowed_version_hosts": [
    "raw.githubusercontent.com"
  ],
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
      "capability": "扫描件与大 PDF 识别、拆分并合并 Markdown",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-mineruocr",
      "repository_branch": "main",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-mineruocr/main/version.json"
    },
    {
      "id": "memo-table",
      "name": "墨记表格制作 Memo-Table",
      "capability": "表格图片与 LaTeX array 表格渲染",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-table",
      "repository_branch": "main",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-table/main/version.json"
    },
    {
      "id": "memo-txtimporter",
      "name": "墨记文档导入 Memo-Txtimporter",
      "capability": "TXT 容器格式、分卡校验与图片回填",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-txtimporter",
      "repository_branch": "main",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-txtimporter/main/version.json"
    },
    {
      "id": "memo-ankitransfer",
      "name": "迁墨 Memo-Ankitransfer",
      "capability": "Anki 图片挖空转墨墨原生遮罩",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-ankitransfer",
      "repository_branch": "main",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-ankitransfer/main/version.json"
    },
    {
      "id": "memo-qahelper",
      "name": "Memo-QAhelper",
      "capability": "墨墨记忆卡使用答疑（官方百科与论坛）",
      "install_source": "github_public_repository",
      "repository_url": "https://github.com/Cognifair/memo-qahelper",
      "repository_branch": "main",
      "marketplace_listing": null,
      "version_url": "https://raw.githubusercontent.com/Cognifair/memo-qahelper/main/version.json"
    }
  ]
}
```
