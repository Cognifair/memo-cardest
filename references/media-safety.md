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
## 6. 原题到成卡的反向对账（写入前）

创建卡片／改正文必须在计划每个 item 明确 source_material。非 Word 原始材料写 "non_docx"。原始来源是 Word 的，即使中间转过 PDF/Markdown，也填 {"docx_manifest":"完整绝对路径"}；不得把 OCR、模型改写或解包后的文件当成新来源。纯移动不改变正文，免此项。没有来源声明的旧写卡脚本会停在发送前；要补建计划，不直接编辑已写日志。历史 verified 仅是回读证据，不能追认为已做本检查。

1. 先用前述完整媒体审计核实 Word 原题段落范围，在表格内的段落也算。执行 python scripts/docx_coverage.py 原卷.docx 卡片key 开始段号 结束段号 新清单.json，生成每处实际引用的核对模板。题号、题干、题图、选项、答案和解析使用原题范围；分卡时明确人工核对本卡范围，不为过检查缩短题区。无法可靠定位就暂停。
2. 每个引用在原位置决定去向：picture 填 media_id，需复核的格式另填 reviewed:true；text 填按原图核实的 replacement；decorative 仅限目读确认的装饰对象，填 reviewed:true 和具体 reason；alternate 仅限同段相同内容的图片备用表示。每项均须写 reason。不按扩展名或字节数一刀切。清单顶层 files 是上传接受清单（以实际 media ID 为键，含 decision:accepted、原图 source_sha256 和上传文件 converted_sha256），复用真实上传记录，不编造 ID。
3. 对选项图填 option（A=1、B=2，以此类推）。常见“上排装置、下排 A/B 说明”的 Word 表格按原列自动确定选项；图要对应固定顺序的选项，原选项说明与其中的公式要保留在对应选项，或在题面明确标 A/B/C/D 的各行说明。不能只写“第一张图”等丢掉每项的实验目的。无法确定图文归属先人工核对版面。
4. API 写入登记和回读核验使用同一清单；执行时重新读取原始 DOCX，不能以旧审计 JSON 或图片总数代替。TXT 路线在封装前逐卡执行 python scripts/docx_coverage.py check 清单.json 卡片key 最终单卡正文.txt，退出码非零不交付。检查依赖源文件与清单；语义、公式转写、客户端布局仍须按原图抽查。
