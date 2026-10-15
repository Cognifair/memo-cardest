# 支链与只读更新框架（Codex 适配）

来源：用户提供的 skill-skeleton.zip。保留“主功能自包含、支链按需提醒、授权后只读查版本”的设计；框架的上架或审核声明不是 Codex 官方保证。不复制其不适用的 WorkBuddy 路径、顶层版本字段或工具名。

## 先完成本职工作

核心业务不依赖支链：能完成的部分继续完成，缺失扩展不得让核心流程停摆；不能把未完成的扩展宣称已交付。只使用本技能的实际支链清单，不因清单中的可选能力扩大任务范围。

每次业务执行先读取 [satellites.md](satellites.md)，用下述 inventory 查看本地已装状态。清单的 JSON 块是唯一机器配置，增删支链只改清单，不在此硬编码名字。

所有命令以本技能目录为工作目录；Python 使用已有可用运行时。状态、版本检查均不安装依赖或执行远端代码。

    python scripts/check_updates.py inventory
    python scripts/check_updates.py status

inventory/status 只读，不创建状态，不联网。安装、维护、审查或测试技能本身不算业务任务完成，不应在这些任务里强行推销支链或询问更新授权。

## 缺失能力提醒与一次性介绍

- 仅当用户任务确实需要某项可选能力、且该支链未装时，任务中提醒一次。用 missing --id 支链ID --session-id 当前聊天ID 防止同聊天重复提醒。不要在输出中暴露内部聊天ID。
- 说明缺什么、哪些核心结果仍可交付，不替用户授权安装，不把代装做成默认项、推荐项或自动动作。用户未回应或拒绝后不追问。
- 推荐措辞：“这项扩展需要「支链名」。当前可先完成……；你也可以在平台技能市场查找该技能。”可以说明能接受用户明确的代装请求，但不要生成看似出自用户的安装指令。
- 全部支链都未装、首次业务任务已经交付时，可在回复末尾一次性介绍清单中的缺失能力。只如实复述清单能力，不宣称全能，不列已安装项；用普通文字，不打断主任务。
- 实际介绍后执行 record pitch --task-id 当前任务ID。用户说“不用/以后再说”则 record declined --task-id 当前任务ID，此后不再介绍或主动询问；用户以后主动改口仍可处理。
- 用户明确要求安装后，先说明技能名、来源与能力；只有环境确实提供平台技能市场安装能力且对应条目已核实时才代装。marketplace_listing 为 null 表示尚未核实市场条目，不能声称已上架或可一键安装。
- 不因用户授权框架接入而下载第三方代码。本框架不调用 GitHub 拉取、ZIP 解压安装或执行不明脚本替代市场安装；市场不可用则说明并交用户自行处理。

## 任务结束与更新授权

用稳定且不对外披露的任务ID记录业务交付：

    python scripts/check_updates.py complete --task-id 当前任务ID

按 next_action 处理，不能把调用 complete 当成已经展示过提示：

- pitch：按上一节在末尾介绍；实际展示后才 record pitch。
- ask_update_consent：仅业务任务结束后询问一次，与首次介绍错开。即使支链一开始已装齐，也在第二次业务任务结束后才问，避免永远等不到 pitched。
- check_updates：只有已有 auto_check 授权才执行不带 --manual 的 check。
- none：不附加无关提示。

更新授权选项固定、平级、按以下顺序，无推荐标记、预设选中或倾向性措辞：

1. 仅这次帮我查
2. 以后自动查
3. 不了吧

提问说明：只读取版本清单，不上传卡片、文件内容、对话或凭证。正常网络连接仍会包含 IP、User-Agent 等常规请求元信息，不能保证“零数据外发”。

使用当前环境允许的中性选择控件；没有合适控件时，用普通文字按相同顺序列出选项并等用户回答。不强行使用要求加“推荐”标签的控件，不伪称控件已显示。展示后 record update-asked --task-id 当前任务ID，防止不回应时再次询问；未收到选择视为不检查，不自行记录 auto。

用户明确选择后才执行：

    python scripts/check_updates.py consent once
    python scripts/check_updates.py consent auto
    python scripts/check_updates.py consent off

once/auto 选择后按脚本提示手动检查一次：

    python scripts/check_updates.py check --manual

后续自动场景只能用：

    python scripts/check_updates.py check

--manual 仅用于本次用户明确要求的检查，不能为了绕过 24 小时节流而加上。auto 仅代表以后调用本技能、业务任务结束时顺带检查，不代表已创建定时任务或后台监听；定时检查需另获用户请求并使用产品自动化能力。用户说“以后别查了”立即 consent off；之后主动说“以后自动查”才 consent auto。

## 结果与更新动作

- 明确展示发现更新的“当前版本 → 新版本”。用户选择“更新/先不更新”时同样不给推荐或默认。
- status=up_to_date 只表示 checked 列出的目标已查且未更新；同时有 skipped 时必须说明哪些未覆盖，不能泛称全部最新。
- not_configured 表示没有可检查的版本源/本地版本，不是最新版确认。throttled 是节流跳过；failed/partial 是失败或部分成功，不是无更新。
- 用户显式要求查时如实说明结果和限制；自动场景对无更新、未配置、节流和失败保持安静，不把重复故障变成骚扰。主业务必须继续，发现明确的新版本才告知。
- 更新本地安装代码：仅在有真实平台市场能力、来源已核实且用户明确要求时走平台渠道；自有源只解释用户自行更新方式。本检查器没有下载、安装、覆盖技能或执行远端内容的功能。
- 即使用户选择更新，若市场工具不可用或来源尚未核实，也不能静默改走 GitHub/镜像下载。
- Memo-Publisher 原有“上传本地改动到已确认 GitHub 仓库”是独立流程，不是本框架的“查远端版本/更新本地”。框架授权不能授权提交、推送、建仓、打标签、运行发布器或创建自动化。

## 文件、版本与网络边界

- 配置：[satellites.md](satellites.md)；执行器：../scripts/check_updates.py；根目录 version.json 只含当前技能 id/version/updated_at，供将来经确认的版本源发布使用。
- 支持本地 SKILL.md 的 metadata.version，也兼容旧顶层 version。扫描 ~/.codex/skills、~/.agents/skills 和同级目录；同名优先前者，报告 shadowed，不覆盖或合并副本。
- 默认 auto_check=false、24 小时节流。用户偏好、提醒记录和检查时间写入操作系统本地数据目录 Codex/MemoFramework/技能ID.json，不写回技能仓库，也不进入 Memo-Publisher 的内容指纹。
- 每个主技能有独立本地状态；安装副本不携带他人的授权。状态损坏时停止检查，不擅自重置授权或反复弹窗。
- 当前分发配置的所有 version_url 均为 null、allowed_version_hosts 为空，没有声明任何实际联网更新域名；检查器因此不联网。接入真实源前须用户确认真实 HTTPS version.json URL 与域名白名单，不能从旧仓库名猜地址。
- 有效版本请求仅向显式白名单域名 HTTPS GET，6 秒超时、最多 16 KiB、禁止重定向、URL 内凭证、查询参数、IP 字面量及私网解析地址。只接受匹配技能ID的版本清单，不解释清单中的指令，不读取或发送凭证、Cookie、正文和文件。
- 失败也按目标独立节流；未装支链不联网。无远端清单时不误报“都是最新版本”。

## 发布时的版本一致性

人为升版或原有发布器准备新版本时，metadata.version、version.json.version、界面展示名的版本后缀应保持一致。此状态更新不替代发布授权；自动发布器仍永远排除 memo-publisher 自身。

