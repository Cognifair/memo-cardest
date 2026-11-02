# 源文件预检与 OCR 路线（G1.4）

这是**强制步骤**，位置在 G1.5 表格审查之前。目标是：在模型开始制卡前，确认材料到底能不能读、是不是图片版，以及要不要 OCR。

## 为什么必须先查

`药理学.docx` 的失败案例：

- 文件表面是 `.docx`，实际正文是 99 张截图；
- 文字层只有 10 个字符，图片有 100 个；
- 模型没有先问 OCR，而是自己跑 Windows OCR，质量不够后才补问；
- 用户的原话是“但你没问我啊兄弟”。

所以：**无文字层不是实现细节，是需要用户授权的路线选择。**

## 检查

本地文件先运行：

```text
python -B scripts/inspect_source.py "<文件路径>"
```

输出字段：

- `text_layer`: `present` / `absent` / `sparse` / `unknown`
- `image_count`
- `recommendation`
- `sample`

判定：

| 结果 | 下一步 |
|---|---|
| `text_layer=present` | 继续 G1.5 |
| `text_layer=sparse` 或 `absent` | 停下来问 OCR 路线 |
| `unknown` 且有图片/扫描特征 | 不要假设；看图或问用户 |
| 纯图片 | 停下来问 OCR 路线 |

PDF 需要 `pypdf`；没有时脚本返回 `unknown`，按“未知”处理，不假装已检查。

## 必须问的问题

```text
这份材料没有文字层 / 是图片版（N 张图）。要 OCR 吗？
① 本地 OCR：不上传、不需要 Token，质量有限
② MinerU 云端：识别更好，需上传并消耗额度；本机 Token 已配置 / 未配置
③ 先不 OCR：换文件，或只做文字部分
```

- 用当前 Agent 的问题框；
- 不要自己跑 Windows OCR 后再补问；
- 不要说“没 Token”之前不检查：先运行
  `python -B <memo-mineruocr>/scripts/secret_resolver.py MINERU_TOKEN`；
- 用户已明确要求 OCR 时，也必须走 `memo-mineruocr`，不要在 cardest 里临时实现 OCR。

## OCR 之后

- 交给 `memo-mineruocr` 完成识别；
- 识别结果仍要回到 G1.5 检查表格；
- OCR 成功不等于知识拆解或语法验收；
- 质量不确定时抽样给用户看，不把 OCR 垃圾直接写卡。

## 留痕

```text
source: text
source: image (99 images) → asked OCR route
source: image → local OCR via memo-mineruocr
source: image → MinerU via memo-mineruocr
```
