# 视觉任务交接（图表同批）

当 G1.4.1（图像）和 G1.5（表格）同时命中时，给 `memo-canvas` 一次结构化交接，不要连续调用两次。

## 交接格式

```yaml
visual_brief:
  figures:
    - id: fig-1
      type: formula | math-diagram | chemistry | flowchart | other
      count: 1
      source: "第 3 页 / 卡片 A"
  tables:
    - id: table-1
      source: "第 4 页 / 卡片 B"
      style_request: null   # null 表示让 memo-canvas 推荐
  constraints:
    - 不覆盖原图
    - 不把 OCR 文本当作图形还原
    - 逐项回报，不要 all-or-nothing
```

## 必须遵守

1. **一次调用**：图表同批只调用 `memo-canvas` 一次；
2. **分开提问**：
   - 有图片 → 问原样 / 简单高清化 / 精美重绘；
   - 有表格 → 问表格样式或 LaTeX 路线；
   - 只问实际存在的类型，不把两个问题合成一个模糊问题；
3. **逐项回报**：
   - 每张图、每张表分别给状态；
   - 一个失败不把其他项判失败；
   - 不能只回一个“都处理好了”。

## 纯类型

- 纯表格：不触发图片三档询问；
- 纯图像：不触发表格样式询问；
- 只有文字：两者都不触发。

## 失败

- `memo-canvas` 缺失：图表都标“待处理”，不假装完成；
- 某张图重绘失败：保留原图、交付疑点，其他项继续；
- 表格校验失败：单独标表格失败，不覆盖图片结果。

## 留痕

```text
visual: tables+figures → single memo-canvas call
figures: found(N) → memo-canvas invoked
tables: found(N) → memo-canvas invoked
```
