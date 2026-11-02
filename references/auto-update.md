# 自动更新安装（可选）

S0 的「② 以后自动帮我同步」会在用户确认后安装一个**用户级后台任务**。它只是更新器，不是常驻服务。

只在用户选择②并准备安装、明确要求卸载或排查后台任务时读取本文件。记录 `sync_mode=auto` 不等于安装成功；已有偏好不触发重新安装。安装以命令退出码及实际结果报告，失败不能声称已安装。

`auto` 模式下 S0 只调用 `check_updates.py check --include-host --manual`：比较版本与 host HEAD，不改技能文件（仍可能写状态 `last_checks`）；实际更新由后台任务执行。只有 `once` 或用户手动执行时，S0 才调用会 fetch/merge 的 `sync`。这里不实现 `plan/apply` 的文件级事务。

## 行为

- Windows：任务计划程序 `MemoCardestSync`，每 6 小时一次；
- macOS：LaunchAgent `com.cognifair.memocardest.sync`，每 6 小时一次 + 登录时；
- 不检测 Agent 进程，任何客户端都可以共用；
- 依次同步四个已安装根目录：
  - `~/.agents/skills`
  - `~/.codex/skills`
  - `~/.claude/skills`
  - `~/.workbuddy/skills`
- 只更新存在的 `memo-cardest` 工作副本；不存在就跳过；
- 更新后当前会话仍加载旧版，需要重启/新会话。

## 安装前提

- 当前客户端必须有**完全权限**，否则写不了 `%LOCALAPPDATA%` / `~/Library`，也注册不了任务；
- 没有完全权限时，S0 必须明确说“自动更新未安装”，不能假装成功；
- 不需要管理员权限（用户级任务）。

## Windows

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\install_sync_task.ps1
```

- 脚本复制到 `%LOCALAPPDATA%\MemoCardest\sync-if-agent.ps1`；
- 注册 `MemoCardestSync`，每 6 小时运行；
- 日志：`%LOCALAPPDATA%\MemoCardest\sync.log`
- 卸载：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\uninstall_sync_task.ps1
```

## macOS

```sh
sh scripts/macos/install_sync_agent.sh
```

- 脚本复制到 `~/Library/Application Support/MemoCardest/sync-if-agent.sh`；
- 注册 `~/Library/LaunchAgents/com.cognifair.memocardest.sync.plist`；
- 每 6 小时 + 登录时运行；
- 日志：`~/Library/Logs/MemoCardest/sync.log`
- 卸载：

```sh
sh scripts/macos/uninstall_sync_agent.sh
```

## 限制

- 任务到点会启动，即使 Agent 没开；这是为了适配任意客户端；
- 任务本身不常驻，跑完退出；空闲时不占内存；
- 如果客户端在更新过程中打开，当前会话不会自动重载新版本；
- 任务只处理公开 `memo-*` 技能，不处理 `Maimemo*` 保密技能；
- 没有 token、没有 API key；更新内容只来自各仓库自己的 GitHub origin。
