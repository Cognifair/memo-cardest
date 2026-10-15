# 可选支链清单

本技能的核心功能独立可用；下列能力仅按任务需要调用。安装来源与远端版本源尚未核实，null 不表示已经上架或最新。当前不会联网查版本。授权与执行步骤见 [satellite-framework.md](satellite-framework.md)。

```json
{
  "schema": 1,
  "skill_id": "memo-cardest",
  "auto_check": false,
  "throttle_hours": 24,
  "allowed_version_hosts": [],
  "satellites": [
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

