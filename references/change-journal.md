# API 卡片变更清单与回读比对（P0）

在 API 创建、修改或移动卡片前读取。TXT 路线不运行，不检查账户或凭证。
`scripts/change_journal.py` 只读写本地 JSON，不联网、不读取 Key、不内置 API 路径、请求体或返回字段映射，也不会自动续跑或重试。
接口字段仍由 Agent 按本次实时官方文档提取。此脚本不代替用户确认、语法验收、写前冲突检查或真实客户端预览。

## 文件与归一化格式

在当前任务的 `work/markji-<任务标识>/` 中保存计划、journal 和临时 GET 快照；不存入技能目录或 Git。文件包含卡片完整正文，是本地明文学习资料，按用户数据保管；结束后告知位置，不默认清理或上传。
不得传入原始 HTTP 响应、请求头、Cookie、Key、带凭证 URL 或任意报错原文。脚本拒绝未定义字段，但这不能识别正文中误粘贴的秘密；输入前仍须检查。

计划示例（所有示例 ID 都是占位符，实际执行必须用已核实的真实 ID）：

```json
{
  "task_id": "lesson-01",
  "account_alias": "本次本人账户A",
  "items": [{
    "key": "source-01/chapter-1/q1",
    "operation": "update",
    "baseline": {
      "deck_id": "真实牌组ID", "chapter_id": "真实章节ID", "card_id": "真实卡片ID",
      "content": "最新GET原文", "grammar_version": 3
    },
    "expected": {
      "deck_id": "真实牌组ID", "chapter_id": "真实章节ID", "card_id": "真实卡片ID",
      "content": "拟写入完整正文", "grammar_version": 3
    }
  }]
}
```

- `key` 是本次任务内唯一、重开会话仍可识别的源材料稳定键；`account_alias` 仅为不含秘密的账户标签，不是账户鉴权或切换保护。
- `create`：`baseline: null`，`expected.card_id: null`，其余字段完整；新 ID 在成功写响应后登记。
- `update`：基线与预期保持牌组、章节、卡片身份不变。若需移动另设计划，不重复登记同一卡片。
- `move`：保持牌组、卡片 ID、正文与语法版本不变，仅改章节。DELETE 章交接仍按原批量删除规则执行。
- 脚本只登记卡片级 create/update/move；牌组、章节和媒体操作仍按现有流程处理，不能把卡片清单报告当作这些操作已验收。
- 所有快照都采用 `deck_id/chapter_id/card_id/content/grammar_version` 五个字段，拒绝缺失和多余字段。GET 未直接返回章节时，必须从本次只读章节成员列表确定；不能用预期章节填充“实际值”。示例版本 3 不是固定平台规范，按实时文档填写。

## 执行顺序

以下命令相对技能目录运行；实际使用绝对的任务文件路径。正文只经 JSON 文件输入，不放命令参数。

```text
python -B scripts/change_journal.py init --journal <任务目录>/journal.json --plan <任务目录>/plan.json
python -B scripts/change_journal.py begin --journal <任务目录>/journal.json --key <稳定键>
```

1. 先确认目标和内容，读取最新基线，再建立清单。清单存在则 `init` 拒绝覆盖；同一卡片不得重复登记。清单不是授权凭证。
2. **发送对应写请求前必须先成功执行 `begin`**，落盘为 `uncertain`（结果不确定）。保存失败或锁冲突就不发送该项。进程在发送前后任意中断，均不再显示为可直接发送的 planned。
3. Agent 按当前文档发送一次获授权请求。成功响应中取得真实卡片 ID 后执行：

```text
python -B scripts/change_journal.py receipt --journal <任务目录>/journal.json --key <稳定键> --card-id <真实卡片ID>
```

`written` 只表示已收到写成功响应，**不表示已回读一致**。更新/移动禁止更换原 ID；创建登记的 ID 不得与其他项重复。

4. Agent 单独 GET 回读，并按当前文档归一化为五字段 JSON（`actual.json`）；不得用写响应、旧缓存、预期值或自造内容代替：

```text
python -B scripts/change_journal.py verify --journal <任务目录>/journal.json --key <稳定键> --snapshot <任务目录>/actual.json
python -B scripts/change_journal.py report --journal <任务目录>/journal.json
```

比对正文（含真实换行、尾部空格、Unicode）、整数语法版本、牌组、章节、卡片 ID。正文差异仅输出长度、SHA-256 和首个差异的 0-based offset / 1-based 行列，不把整篇正文打进终端。完整正文在 journal 的 baseline/expected 中供本地审阅。

脚本只能验证**调用方提供的快照**；不会证明快照来自真实 GET。报告中的 `basis` 明示该限制，Agent 必须保证输入来源。`verified` 仅指这些字段与预期一致，不证明客户端渲染、学习进度、全库新增数量或排序正确；数量和顺序仍按现有流程单独核验。

## 状态、失败与中断

| 状态 | 含义 |
|---|---|
| planned | 清单已记录，尚未开始请求 |
| uncertain | 已开始执行记录，尚无确定写结果；先只读核查 |
| written | 收到写成功响应，等待独立 GET |
| verified | 所提供的 GET 快照五字段全部一致 |
| mismatch | 已比对但存在差异；停止该项，核查原因 |
| failed | 服务端明确拒绝本次写请求 |
| skipped | 尚未发送，由执行者明确跳过 |

- `skip --journal ... --key ...` 只用于 planned。
- `reject --journal ... --key ...` 只用于 uncertain 且已经确认服务端拒绝。超时、断网、响应丢失、回读失败都不等于 failed。
- 更新/移动响应丢失但 ID 已知，可以只读 GET 后 verify；不一致保留 mismatch，不能据此自动再发。
- 创建响应丢失且 ID 未知时，verify 会拒绝；保留 uncertain，人工只读查证。P0 不按标题/正文自动认领对象，不提供自动恢复、重置为 planned 或自动重试功能。
- `verify` 退出码：0 一致；2 差异已保存；1 输入、状态或 I/O 错误。快照字段缺失、GET 失败时不能标 verified。允许再次 GET 后重新 verify，不会执行网络写入。
- `report` 汇总每项和各状态数量，`all_verified` 仅在全部项 verified 时成立；skipped 也不算全部完成。客户端预览始终显示 not_checked，另行报告实际预览结果。
- 同一 journal 修改有排他锁，整文件临时写入后原子替换。遇 `journal_busy` 停止，不删除活动锁；进程崩溃遗留锁需人工确认无执行者后处理。不是多进程任务调度器，也不承诺突然断电下零数据损失。
- 若脚本不可用或记录无法落盘，停止依赖它的账户写入；可继续本地草稿，报告限制，不假装完成了记录。
