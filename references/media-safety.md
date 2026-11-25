# 媒体安全：DOCX / 图片入卡前的审计

目标是避免“Word 里是标点，卡里变成一张巨大图”，同时不把真正的示意图静默丢掉。

## P0 原则

```text
可疑媒体不自动入卡
原文语义不静默丢失
每个放行的 Pic 都能追溯到来源
```

## 1. 先审计 DOCX

```text
python -B scripts/audit_docx_media.py source.docx \
  --out media_audit.json \
  --assets-dir media_assets
```

输出每个媒体引用：

```text
paragraph_index
relationship_id
target / part
declared_content_type
detected_format
source_sha256
pixel_width / pixel_height
word_display_width_px / word_display_height_px
pixel_per_display_ratio
anchor_text / context_before / context_after
decision: candidate | needs_review
review_reasons
```

判断依据：

- **看实际 media part 的文件头**，不靠 `w:drawing` / `w:pict` 判断格式；
- `wmf` / `emf` → 一律 `needs_review`；
- 声明类型和文件头不一致 → `needs_review`；
- 外部链接、找不到 media part → `needs_review`；
- 普通 PNG/JPEG/GIF/WebP/BMP/TIFF → `candidate`，仍需按锚点复核。

`needs_review` 不自动生成 `[Pic#]`，也不删除原件。

## 2. 处理待审媒体

```text
确认是标点/符号 → 在原段落位置还原为文本
确认是示意图   → 转换 / 重绘后再入卡
无法判断       → 该卡暂缓发布，其余卡继续
```

不能因为“图片太大”直接丢；也不能因为“WMF”直接删。

## 3. 逐引用校验已入卡媒体

```text
python -B scripts/check_media_refs.py cards.json \
  --media-map media_map.json
```

`media_map.json` 每个 file id 记录：

```json
{
  "files": {
    "<file id>": {
      "decision": "accepted",
      "source_file": "figure.png",
      "source_sha256": "...",
      "converted_sha256": "..."
    }
  }
}
```

检查：

- 每个 `[Pic#ID/...]` 都有 media record；
- record 是 `accepted`；
- 来源不是 `.wmf` / `.emf`；
- 原件 hash、转换后 hash 都存在。

同一张图可以复用；**不做 Pic 总数相等校验**。

## 4. 构建阶段

- `needs_review` 媒体不得进入 `[Pic#]`；
- 受影响的卡标记 `hold`，其余卡继续；
- 每一处 `[Pic#]` 写入 `source_sha256` + `converted_sha256`；
- 记录 `anchor_text`，确保图跟随引入句；
- 保存 DOCX hash、转换记录和审计 JSON。

## 5. 验收

用出问题的 Word 原文段落验收：

```text
卡上没有巨大括号
原句标点和题意完整
同段正常插图仍在
真正的 WMF 示意图进入待审清单，没有消失
```

只有对照原始 DOCX、转换记录和卡面内容后，才能把“Word 存成 WMF + 转换放大”写成已确认根因。
