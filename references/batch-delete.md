# 批量删除：先移入 DELETE 章，再由用户手动删除

用于用户要清理大量卡片、但官方 OpenAPI 没有“删除卡片”接口的场景。

核心做法：**AI 只创建/复用 `DELETE` 章节并把目标卡移进去；不调用任何删除接口。最后由用户在 Markji 客户端手动删除 `DELETE` 章节，章节里的卡片随之删除。**

这样即使中途出错，卡片也只是被移到 `DELETE` 章，仍可恢复；不会由 AI 直接执行不可逆删除。

## 适用与不适用

适用：

- 用户明确要删除某个牌组里的一批卡片（按标题、关键词或给出的 card_id）；
- 数量较多，逐张在客户端操作不现实；
- 用户接受“先移入 DELETE 章，再由自己删章”的交接方式。

不适用：

- 只删 1–2 张：让用户在客户端手动删更快；
- 删除整个牌组：让用户在客户端删除牌组；
- 用户要求 AI 直接调用删除卡片/章节接口：官方 OpenAPI 不提供，不要用逆向接口绕过；
- 目标不明确、匹配结果有歧义：先停下来确认，不猜。

## 前置确认（缺一不可）

1. 目标牌组 ID / 名称已确认；
2. 目标卡片已确认：优先用用户给出的 card_id；只有标题时，必须按完整标题精确匹配，并列出“匹配到的卡片 + 来源章节 + 数量”让用户确认；
3. 用户明确同意“AI 移入 DELETE 章，最后由我手动删除该章”；
4. 有可用的 `MAIMEMO_TOKEN`，且用户授权本次写入；
5. 知道当前章节列表；`DELETE` 章不存在时新建，已存在时复用（若存在多个，停止确认）。

## 官方 API

Base：`https://open.maimemo.com/open`

| 动作 | 请求 |
|---|---|
| 读章节 | `GET /api/v1/markji/decks/{deck}/chapters` |
| 建 DELETE 章 | `POST /api/v1/markji/decks/{deck}/chapters`，body：`{"deck":"<deck>","name":"DELETE"}` |
| 移卡 | `POST /api/v1/markji/decks/{deck}/chapters/{source_chapter}/cards/move`，body：`{"card_ids":["..."],"to_chapter_id":"<DELETE 章 id>"}` |

- 建章响应取 `data.chapter.id`；
- 移动响应 200/201 视为提交成功，但仍要重新读章节做核对；
- 请求间隔约 0.8–1 秒；429 按 15/30/45 秒退避；
- 不要把 `deck`/`chapter` 放进卡片创建 body 的经验套到所有接口；以实际接口和回读为准。

## 执行步骤

1. **读现状**：拉章节及 `card_ids`，建立 `card_id -> 章节名` 映射；
2. **解析目标**：
   - 有 card_id：直接使用；
   - 只有标题：从卡片正文提取标题（通常是首行 H1），做空白/引号/连字符归一化后精确匹配；
   - 同标题多张卡、标题缺失、匹配不到：列出冲突，停止确认；
3. **出预览**：目标卡数量、来源章节分布、示例标题、`DELETE` 章是新建还是复用；
4. **等用户确认**：明确“移动后需要你手动删除 DELETE 章”；
5. **建/复用 DELETE 章**：已存在则复用；多个同名则停止；
6. **按来源章节分组移动**：每组一次 `cards/move`，记录返回码与数量；
7. **回读核对**：
   - `DELETE` 章卡数 = 计划移动数（扣除原本就在 DELETE 的卡）；
   - 牌组总卡数不变；
   - 来源章节数量按预期减少；
   - 失败项逐条报告，不重复盲发；
8. **交接**：告诉用户“DELETE 章已就绪，请在客户端手动删除该章节；删章会删除其中卡片”，并给出章节名与卡数；
9. **用户删除后复查**（可选）：重新读章节，确认 `DELETE` 消失、总卡数减少、其余章节不受影响。

## 匹配与幂等

- 标题匹配前做 Unicode 引号、全角/半角连字符、连续空白归一化；仍然只做**精确**匹配，不做模糊包含；
- 已在 `DELETE` 章的卡跳过，不重复移动；
- 分批移动失败后先回读，确认哪些已移动，再只补未完成的；
- 不使用“删除后重建”“改正文模拟删除”等替代方案。

## 安全边界

- **AI 不删除卡片、不删除章节**；只创建 `DELETE` 章并移动；
- 不改 `card.content`、媒体、学习进度；
- 不把 token 写进脚本、日志、清单或聊天；
- 不移动未确认的卡；匹配不了就停下；
- 不在非用户指定的牌组上操作；
- 用户未删除 `DELETE` 章之前，卡片仍在牌组里，只是换了章节；这是有意的可恢复状态。

## 最小伪代码

```python
# 1. 读章节
chapters = GET(f"/api/v1/markji/decks/{deck}/chapters")["data"]["chapters"]

# 2. 找/建 DELETE
delete = next((c for c in chapters if c["name"] == "DELETE"), None)
if delete is None:
    delete = POST(f"/api/v1/markji/decks/{deck}/chapters",
                  {"deck": deck, "name": "DELETE"})["data"]["chapter"]

# 3. 按来源章节分组移动（只移动已确认的 card_ids）
for source_chapter, ids in groups.items():
    POST(f"/api/v1/markji/decks/{deck}/chapters/{source_chapter}/cards/move",
         {"card_ids": ids, "to_chapter_id": delete["id"]})
    sleep(1)

# 4. 回读核对；不调用删除接口
# 5. 用户手动删除 DELETE 章
```
