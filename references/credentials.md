# 凭证读取（支持工作区沙箱）

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

## 工作区文件（推荐给工作区模式）

在项目根目录：

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

不想放在项目里时：

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
