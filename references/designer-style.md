# Memo Designer 样式桥接

MemoCardest 不再以《墨记工具箱》作为默认设计参考；卡片样式来源改为：

```text
用户样卡 / 目标牌组首卡
→ 有真实样卡：复制真实源码
→ 没有样卡：调用 memo-designer 的对应题型模板
→ 没有对应模板：先要样卡，不凭空造
```

## 题型映射

| 题型 | Memo Designer 规范 | 冻结模板 |
|---|---|---|
| 单词卡 | `memo-designer/card/word.md` | `memo-designer/card/templates/word.txt` |
| 选择题 | `memo-designer/card/choice.md` | `memo-designer/card/templates/choice.txt` |
| 名词解释 | `memo-designer/card/term.md` | `memo-designer/card/templates/term.txt` |

规则：

- 模板样式字节锁死，只换文字或整块删除；
- 不改颜色、不加下划线、不动空格数；
- 公式统一 `[E##…]`，不用 `$…$`；
- 绿色只用于标题术语或指定语义，不铺满；
- 新增题型必须有真实样例，不能凭空造整卡模板；
- `memo-designer/scripts/validate.py` 用于校验模板源码本身；不代表任意生成卡都通过客户端渲染。

## 样式来源留痕

```text
style: sample | deck-first | designer | custom
```

- `designer`：使用 Memo Designer 模板；
- 旧记录 `toolbox` 按 `designer` 兼容，但不再作为默认；
- 用户明确要工具箱旧风格时才读历史参考，并说明是旧风格。

## 调用失败

如果 `memo-designer` 不可用：

```text
停下说明缺少对应题型模板
请用户给样卡
不静默退回工具箱或自创版式
```
