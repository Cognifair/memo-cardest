# G1.3 页序检查：先核序，再进 G1.4

凡需要按页连续阅读的多页材料，都要逐页核对。PDF 第几页是扫描序号，不是印刷页码。先看源文件数量与类型；同册按一份材料处理，不同册分别核对，切勿跨册数字排序。原件只读，各步骤用工作目录，已存在的输出不覆盖。

**整理输入。** PDF 直接使用；成组扫描图片或多帧 TIFF 先运行 `python scripts/folio_bundle.py 新目录 图1 图2 …`（大量图片可用 `--list 清单.txt`），从新目录的 bundle.pdf 开始，保留 source-map.json 回查原文件和帧。输入顺序只是原扫描顺序。固定版式 DOCX 等先按实际排版导为 PDF，不从媒体文件名或 XML 中的图片个数推测书页。内容本来不分页的笔记、普通流式文本及已确认单页可不适用。

**逐页取证。** 以下命令均以主技能为基准；把文件和目录换为实际路径。依赖 PyMuPDF，生成总览／处理图片需 Pillow；无视觉路线另需本地 Tesseract 及 eng 数据。缺能力就说明并换可核验的路线，不用页索引补读数。

```text
python -B scripts/folio_read.py 原件.pdf 取证目录 --mode visual
python -B scripts/folio_gate.py finalize 原件.pdf 取证目录/evidence.json 判定目录
```

- 两种模式都先逐页读页边文字层。视觉模型使用 visual，打开 overview 图，按图上的 **SCAN 序号**录入印刷数字；模糊时放大对应 crops 原图。无视觉能力使用 `--mode ocr`，由本地 Tesseract 处理文字层读不到的页。若已证实页码位置，可指定 `--box 左 上 右 下`（相对坐标 0–1，可重复），不要把书眉章号、正文题号当作页码。文字层的数字与印刷内容不符时，使用 `--all-crops` 复核。
- `needs_review`（退出码 2）只产生疑点清单，不产生可供 G1.4 使用的凭据。先核对清单中的页和相邻边界。如扫描序号 7 位于 56 与 58 之间，**只有实际读到 57 才能写 57**。模型读图可完成核对，不要求用户逐页点确认；不能读图时先换裁区复扫，只请用户判剩余疑点。
- 确认读数写入 review.json，例如 `{"source_sha256":"取证中的原件哈希","readings":[{"scan":7,"number":57,"reason":"扫描页 7 右下角可见 57"}]}`。视觉模式下每个未读页都需有实际读数。带 `--review review.json` 重跑 finalize，指定**新的判定目录**。
- 封面无号、罗马数字、重复编号、材料本来是非连续节选等，不删页也不硬补。若可从卷名／目录／上下页内容逐页确定顺序，用特殊复核清单：`{"source_sha256":"…","reason":"说明特殊编页及核实依据","order":[{"scan":1,"section":"卷首","label":"封面","reason":"实际所见"}, …]}`。order 必须按最终顺序列全，每页一次、带依据，同一节数字标签须递增。无法确定就停在 G1.3；实际缺页不能靠重排恢复。
- 通过时读取 finalize 输出的 **input 和 receipt**：顺序正确为原件；错序为逐页复核后的 ordered.pdf。page-map.csv 记录原扫描页、印刷页、最终位置。保留原件、工作输入和凭据，直到下游完成；源文件内容改变则重做。**不可单凭文字回复、手填 passed、文件名或旧材料的 receipt 放行。**

**G1.4 和下游都读取同一个已核准的输入。** 先检查正文，再按 G1.4 选择路线；这些是按需选择的命令，不是要依次运行全部命令。

```text
python -B scripts/inspect_source.py 实际输入.pdf --folio-receipt 判定目录/receipt.json
python -B scripts/use_source.py text 实际输入.pdf 逐页正文.json --folio-receipt 判定目录/receipt.json
python -B scripts/use_source.py prepare 实际输入.pdf 本地分片目录 --folio-receipt 判定目录/receipt.json
python -B scripts/use_source.py local 实际输入.pdf 本地识别结果目录 --folio-receipt 判定目录/receipt.json
```

text 供直接拆题，保留实际阅读页序；复杂版式仍须抽查。只有选定 OCR 路线才运行对应命令：prepare 仅调用同级 Memo-MinerUOCR 离线准备任务，不提交；后续提交和费用仍按支链授权。local 只调用已配置的本地 mineru CLI；没有引擎就按支链说明处理。不要绕过主技能入口，另把未核序原件交给外部 CLI。独立使用 MinerU 不受此主技能约束。正式识别后需抽查换序边界的题号与续答归属，再切题。
