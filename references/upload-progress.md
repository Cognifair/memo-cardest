# API 上传脚本自动登记与进度（协议 v1）

本流程用于卡片 create/update/move；不扩大账户写入授权，不用于把章节、媒体操作计成卡片成功。插件状态投影迁移不在本协议内。

## 必须接入固定模块

Agent 生成、修改或执行 API 上传脚本时，导入本技能 `scripts/upload_task.py`，按 `scripts/upload_example.py` 接入。模块随上传脚本启动自动登记、上报心跳；**不要另写通知脚本、不要依靠 Agent 口头报告、不要自行维护成功计数**。

先通过 `change_journal.mutate(path, 'init', plan=...)` 建立经确认的完整目标清单；存在的清单只校验和恢复，不覆盖。临时脚本的 API 适配器只负责按当前官方文档实现请求、限速、明确结果分类和独立 GET 归一化，写入生命周期交给 `UploadTask`。

```python
from upload_task import UploadTask, WriteResult

# adapter 的实现来自本次核实的 API 定义。以下代码不是执行授权。
with UploadTask.open(journal_path, execution=adapter.execution_plan) as task:
    outcome = task.execute_write(key, lambda: adapter.send(item), adapter.classify)
    if outcome.kind == 'confirmed':
        current = next(i for i in task.snapshot()['items'] if i['key'] == key)
        task.verify(key, lambda: adapter.fetch_snapshot(current))
```

实际使用参考完整示例，它会用 receipt 后的清单条目及绑定 ID 调用 GET。适配器的 `classify(response)` 返回 `WriteResult('confirmed', real_card_id)`、`WriteResult('rejected')` 或 `WriteResult('uncertain')`。不能仅凭一个任意 HTTP 状态码认定未发生写入；超时、返回丢失、无法解析成功响应、含义不明的 5xx 都不能标明确拒绝。回读失败保留 written/uncertain，不标 verified。

`begin` 必须成功落盘后才调用 send。固定模块不发 HTTP、不读取凭证、不猜 API 字段；回读回调必须实际发起独立 GET，不能返回预期内容、缓存或 POST 响应。章节 GET 如需要 `with_cards=true`，适配器必须显式携带并核验返回的成员关系；缺少列表要报错，不能填假快照。

## 登记和恢复

- 目录（按顺序取第一个可写的，脚本与插件共用这套解析）：
  1. `MEMO_CARDEST_REGISTRY` 指定的目录 —— 只给测试和特殊部署用，普通上传不要设；
  2. `~/.memo-cardest/progress/v1/tasks/<UUID>.json` —— 旧默认目录，能写就用；
  3. `<workspace>/.memo-cardest/progress/v1/tasks/<UUID>.json` —— 沙箱里写不了家目录时的正式回退。
     工作区根取 `MEMO_CARDEST_WORKSPACE`，没有就往上找最近带 `.memo-cardest` 标记的祖先目录，再退回当前目录。
  插件侧同时读这三处，外加旧的 `<workspace>/.progress/tasks`（历史脚本用过），按任务 UUID 去重：
  同一个 UUID 出现在多个目录时只算一条，内容不一致时状态里带 `health.conflict: true`。
- 记录协议版本、UUID、业务 task_id、根身份摘要、完整目标数量、按顺序关联的清单路径，以及会话、运行 ID、PID、心跳和生命周期。**不保存逐卡状态或独立成功计数**。
- **登记必须落在插件能发现的位置**。`registry=` 参数只能配合 `allow_custom_registry=True` 用于测试；普通脚本传自定义目录会直接抛 `RegistryUnavailable`，不会静默切到一个宿主看不见的目录再声称进度可用。
- 三处都不可写时，`registry_dir()` 抛 `RegistryUnavailable`，错误里列出试过的路径与处理办法。这发生在**首张卡请求之前**：要么把 `MEMO_CARDEST_REGISTRY` 指到双方都能读写的目录，要么从工作区根目录运行脚本（让回退目录落在工作区里）。不要把登记放在工作区里的任意子目录。
- 会话优先使用明确传入的 session_id，否则读取 DSH 注入的 `DSH_SESSION_ID`，保留 `session-` 前缀；profile 读取 `DSH_PROFILE_DIR`/`DSH_PROFILE`。缺少会话标记为未绑定，不猜测当前窗口。显式跨会话移交使用 `rebind=True`；它不赋予写卡授权。
- 同一根清单自动得到稳定 UUID；续传必须复用登记并恢复同一清单，不能为了重跑重新 init。无记录时传未知 UUID 会拒绝。
- 每 5 秒心跳，插件 15 秒未见心跳标记执行状态未知。后台进程与前台使用相同上下文管理器。必须使用 `with`，或在 finally 中 close；close 不表示成功。
- 同一任务有执行者锁，清单每次变更另有短期锁；不会抢锁、清除残留锁或自动重启上传。崩溃后须先人工确认没有执行者，再处理残留锁。
- 文件采用临时写入、fsync、原子替换。首张卡前登记失败则不写卡；运行中心跳失败会告警，清单仍为事实来源。清单变更失败锁住当前执行器，不能继续发新卡请求。插件离线不会阻塞上传。
- DSH 重启恢复的是观察，不是网络请求。新会话问答不应清除已经登记的任务结果。

## 安全重试和换清单

默认不自动重试写请求。已 verified 不再写；written 执行独立 GET；uncertain 只读核查，未知创建 ID 不自动认领。mismatch 可再次 GET 核验，不能直接重复写。

只有明确拒绝且授权覆盖的重试才使用：

```python
task.retry_rejected(key, send, classify, authorized=True,
                    max_retries=3, retry_after_seconds=retry_after)
```

每次调用只重试一次，历史中已有重试会占用上限；参数不是自动循环开关。必须遵守本次实时频控与 Retry-After，超过上限停止。`pause('rate_limit'|'network_wait'|'paused')` 是上下文管理器，等待时继续心跳，退出后重新采集 ETA 样本。低层 CLI `retry-rejected` 也要求 `--authorize-retry`，只允许 failed→planned。

优先继续同一完整清单。确需换清单时向 open 传已有 `task_uuid`：按根目标 key 关联，account_alias、操作、预期身份/内容须兼容；不得增加根目标集合。明确拒绝项转入新 planned 清单还需 `authorize_successor_retry=True`。未知或已写入条目必须保留绑定 ID 和此前历史，不能借新文件绕过 cannot_resend。旧执行清单被替代后不能再次作为执行入口。

不按文件名相似、标题相同或旧清单数量自动关联。改变预期内容、测试重写等另建任务，不伪装成原任务续传。重复键、重复目标 ID 或关系冲突应停止，插件也会显示关联异常。

## 时间与交付语义

execution 仅接受数值字段 `request_interval_ms`、`concurrency`、`write_requests`、`verify_requests`、`expected_latency_ms`，没有把握则省略，不能把 1.6 秒请求间隔当每张卡耗时。不要把凭证、URL 或原始异常放入登记。

- 上传数来自清单 receipt 历史；失败、跳过、未知不计成功。独立 GET 确认但没有 receipt 的卡片另列“仅回读确认”。
- 核验结果单独统计；全部写完但未回读完是“核验中”。只有全部目标 verified 才是完整核验成功，客户端预览仍待验证。
- 初始完整请求计划可显示配置估算；只有间隔最多给理论下限。实际 ETA 用近期唯一卡片吞吐率，包含网络与限流耗时；暂停、断连、心跳陈旧和样本不足时隐藏。
- 未接入模块的旧脚本只能显示标注的兼容清单或历史报告快照；没有可靠来源就显示进度不可用。**API 写操作（创建/修改/移动卡片）如果绕过 `UploadTask`，Memo Studio 不会出现该任务；这不是插件漏读。此时必须停下说明，或先接上 `UploadTask` 再写，不能事后把“没显示”解释成 Studio 故障。**

## 离线检查

运行 `python -B -m unittest test_change_journal test_upload_task`（scripts 目录）。使用模拟适配器和临时目录，不提供真实 key。插件 tests 使用同一份脱敏协议夹具回放 96 张及 200 张续传样本。离线通过不代表真实 DSH 或 Markji 客户端通过；真实写卡另需明确授权。
