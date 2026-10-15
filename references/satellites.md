# 可选支链清单

本技能的核心功能独立可用；下列能力仅按任务需要调用。安装来源与远端版本源尚未核实，null 不表示已经上架或最新。版本检查与新支链发现分别授权、默认关闭。新支链源采用现有墨卡大师 Git origin 核实的 Cognifair 公开 GitHub 仓库；这不代表平台市场已上架。授权与执行步骤见 [satellite-framework.md](satellite-framework.md)。

```json
{
  "schema": 1,
  "skill_id": "memo-cardest",
  "auto_check": false,
  "throttle_hours": 24,
  "allowed_version_hosts": [],
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
      "install_source": "platform_marketplace",
      "marketplace_listing": null,
      "version_url": null
    },
    {
      "id": "memo-txtimporter",
      "name": "墨记文档导入 Memo-Txtimporter",
      "capability": "封装与校验 TXT 章节、分卡符和答案线",
      "install_source": "platform_marketplace",
      "marketplace_listing": null,
      "version_url": null
    },
    {
      "id": "memo-table",
      "name": "墨记表格制作 Memo-Table",
      "capability": "制作表格图片或 LaTeX array 表格",
      "install_source": "platform_marketplace",
      "marketplace_listing": null,
      "version_url": null
    }
  ]
}
```

