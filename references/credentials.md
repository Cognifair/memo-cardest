# 凭证读取（支持工作区沙箱）

## API 路线：使用、会员与保存（操作凭证前必读）

本文件只在 API 路线读取；TXT 路线不检查会员、不读取凭证、不调用账户 API。

- **选择顺序：本次明确指定的 key → `MAIMEMO_TOKEN` 的 resolver 结果。** 两者同时存在时用本次指定值，默认仅本次使用，不静默覆盖；本次凭证验证失败也不回退旧 key、其他账户或 Web token。来源、账户或使用权限不清楚时先澄清；他人、共享或来源不明的 key 不配置，未澄清前不调用账户。
- 本次未指定 key 时才运行 `python -B scripts/secret_resolver.py MAIMEMO_TOKEN`；只报告找到/未找到与来源类型，不输出值。下面的文件路径是受支持的**读取位置，不授权新建或保存凭证文件**。
- 有本次指定或解析到的可用凭证时，报 `member: pro（本次指定凭证 / 解析到的凭证）`；用户明确说已开通也可据其原话报告。实际请求权限另由当前官方文档的最小只读请求验证。没有可用凭证、也没有明确会员状态时，才问「学习者的墨墨记忆卡账户已开通专业版，还是未开通？」并等待；明确未开通才报 `member: free（用户原话）`。历史连接、牌组数量和一次只读成功不能单独证明会员或全部写权限。
- 仅当 key 来自本次输入且 `MAIMEMO_TOKEN` 尚未设置，按主技能 S0 的提问方式问一次：「要把这个 key 设为用户环境变量 `MAIMEMO_TOKEN` 吗？请确认这是你自己账户的 key——接错后续会操作别人的账户。① 是我自己的 key，设置到用户环境变量 ② 不用，仅本次使用」。用户未回答不保存；已有变量只在明确要求替换时修改。
- 选①且确认是本人 key：通过不回显、不把值放进命令参数或历史的安全通道写用户级环境变量，成功只报 `token_env: set`；无安全通道则让用户在系统环境变量界面自行设置，失败如实报告，本次仍可使用已选值。选②不落盘，报 `token_env: session_only`。**新 key 的持久化仅允许这项明确授权的用户环境变量操作**，不因沙箱受限而自动改写凭证文件。
- 不向 tutuji、GitHub、表格渲染器或第三方 TTS 发送 key；不写入技能、状态、日志、Git、截图或示例。API 只读验证与写入步骤见 [api-workflow.md](api-workflow.md)。

## 默认凭证解析

Windows 用户级环境变量只影响**新启动**的进程。DSH / Codex 启动后再 `setx`，当前进程不会自动看见，所以只读 `$env:MAIMEMO_TOKEN` 会得到空值；这不是“需要完全权限”。

统一用 `scripts/secret_resolver.py`，按以下顺序读取：

1. **进程环境变量**（恰好继承了就用）；
2. **Windows 用户级环境变量**（`HKCU\Environment`）；
3. `%LOCALAPPDATA%\MaimemoSecrets\<小写名>`；
4. `<工作区>\.memo-secrets\<小写名>`，并向上查找最多 3 层父目录。

支持的名字：

| 变量 | 文件名 |
|---|---|
| `MAIMEMO_TOKEN` | `maimemo_token` |
| `MINERU_TOKEN` | `mineru_token` |
| `MARKJI_TOKEN` | `markji_token`（通常改用 MR 的浏览器捕获，不落盘） |

## 检查（不显示值）

```powershell
python -B scripts\secret_resolver.py MAIMEMO_TOKEN
python -B scripts\secret_resolver.py MINERU_TOKEN
```

成功只打印 `found via <来源>`；失败打印检查过的位置。**绝不会打印 token。**

## 读取已有工作区文件

兼容读取项目根目录中的以下文件；这里不是保存新 key 的授权。管理已有文件时需排除 Git 并限定权限：

```text
<workspace>\.memo-secrets\maimemo_token
<workspace>\.memo-secrets\mineru_token
```

`.gitignore`：

```text
.memo-secrets/
```

文件只放 token 本身，不要加 `NAME=`、引号或说明。文件权限只给当前 Windows 用户：

```powershell
icacls .memo-secrets\maimemo_token /inheritance:r /grant:r "$env:USERNAME:(R)"
```

## 用户数据目录

也兼容读取下列已有文件；不作为保存新 key 的默认或兜底位置：

```text
%LOCALAPPDATA%\MaimemoSecrets\maimemo_token
%LOCALAPPDATA%\MaimemoSecrets\mineru_token
```

工作区模式只要能读该目录即可；如果沙箱拦截用户目录，就退回工作区 `.memo-secrets`。

## 用户级环境变量（可选）

```powershell
[Environment]::SetEnvironmentVariable('MAIMEMO_TOKEN', '<token>', 'User')
```

- 不要用会记录历史的命令写入 token；
- 写入后新进程才继承；已运行的 DSH/Codex 仍要用 resolver 读注册表；
- 不要把 token 写进聊天、日志、技能文件或 Git。

## 代码里怎么用

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from secret_resolver import SecretNotFound, get_secret

try:
    token, source = get_secret("MAIMEMO_TOKEN")
except SecretNotFound as exc:
    raise SystemExit(str(exc)) from None
```

不要把 `token` 或 `source` 中的文件内容写进日志；只记录“来源类型”。

## 安全边界

- 文件方案是**明文落盘**；只放在仅当前用户可读的路径，并纳入 `.gitignore`；
- token 有有效期；失效后重新生成/配置，不复用旧值；
- MR 的 Web token 是短时会话凭证，优先用 `capture_token.py` 捕获，不建议长期保存；
- 任何方案都不把 token 放进命令参数、聊天、截图或提交历史。
