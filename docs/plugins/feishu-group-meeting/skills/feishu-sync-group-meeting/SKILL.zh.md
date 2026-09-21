# 飞书群组会

> 本文是 `plugins/feishu-group-meeting/skills/feishu-sync-group-meeting/SKILL.md` 的中文翻译，仅供阅读，不参与 skill 加载。

**frontmatter 字段**

- `name`: `feishu-sync-group-meeting`
- `description`: 管理存放在 Docx/Wiki 文档里的飞书/Lark 群组会日程 —— 把文档拉成 Markdown、查询当前汇报人、轮换每周讲者、调整组会时间、并把改动推回飞书。用于组会讲者查询、日程更新、飞书同步、组会提醒、或每周轮换任务。

---

这个 skill 管理存放在 Docx 或 Wiki 文档里的飞书/Lark 群组会日程。它用随包的 Python 脚本把线上文档拉进本地 Markdown 缓存、编辑或轮换这份缓存、再把改动推回飞书。

当用户要求发提醒或修改日程文档时，不要再问一次确认。拉取最新文档、执行被要求的操作、校验结果、然后直接发送或推送。只在缺少必要信息、目标会话/文档不可用、或被要求的改动有歧义时才提问。

## 配置

首次使用前，用环境变量或本地配置文件配好凭据。

环境变量：

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="..."
export FEISHU_DOC_URL="https://example.feishu.cn/docx/..."
```

配置文件位置，按优先级排列：

1. `FEISHU_GROUP_MEETING_CONFIG`
2. 与 `SKILL.md` 同目录的 `config.json`
3. `~/.config/feishu-sync-group-meeting/config.json`
4. `~/.feishu-sync-group-meeting/config.json`

用 `config.example.json` 作为模版。绝不要打印或暴露 `app_secret`。

绝不要用 `cat`、`sed`、`less` 这类命令直接打印配置文件，因为里面有 `app_secret`。要安全查看配置，用定向读取或脱敏读取：

```bash
# 脱敏总览。
jq 'del(.app_secret)' "$CONFIG_PATH"

# 单个非敏感字段。
jq -r '.test_chat_id' "$CONFIG_PATH"
jq -r '.target_chat_id' "$CONFIG_PATH"
jq -r '.schedule_doc_url' "$CONFIG_PATH"
```

如果缺 `requests`，在 skill 目录下执行：

```bash
python3 -m pip install -r requirements.txt
```

## 命令

在这个 skill 目录下执行命令。在 Claude Code 里，`${CLAUDE_SKILL_DIR}` 就是这个目录；在 Codex 里，相对路径以 `SKILL.md` 所在位置为基准解析。

```bash
# 把最新的飞书文档拉进本地 Markdown 缓存。
python3 scripts/feishu_sync.py pull

# 打印本地缓存路径，用于读取/编辑。
python3 scripts/feishu_sync.py path

# 把本地 Markdown 缓存推回飞书。
python3 scripts/feishu_sync.py push

# 组会结束后轮换一次。
python3 scripts/update_schedule.py

# 预览轮换结果但不写入。
python3 scripts/update_schedule.py --dry-run
```

默认缓存路径：`~/.cache/feishu-sync-group-meeting/feishu_schedule.md`。

## 工作流

1. 拉取：`python3 scripts/feishu_sync.py pull`。
2. 从 `python3 scripts/feishu_sync.py path` 读出缓存路径。
3. 回答用户的查询，或只编辑被要求的那一行/那一节日程。
4. 校验表格标记和成员顺序仍然有效。
5. 对用户要求的状态变更操作，校验后直接推送，不要再要一次确认。

## 日程规则

日程表在同一个 Markdown 表格里有两套互相独立的成员顺序：

- 左侧成员列：控制 `Work Report` 和 `News`。
- 右侧成员列：控制 `Showcase Session`。
- 两份成员名单可能包含相同的人但顺序不同；两侧各自独立轮换。

严格的状态标记：

| 标记 | 含义 |
|---|---|
| `😀本周同学` | 当前汇报人 |
| `🚫跳过` | 永久跳过 |
| `🚫跳过N次` | 再跳过 N 周 |
| `🚫跳过0次(😀本周同学)` | 跳过计数归零；这位同学本周汇报 |
| `😀已讲` | 被延后的当前标记；下一次轮换时恢复 |

如果目标列里出现多个 `😀本周同学` 标记：

- 对于"谁来汇报"这类直接查询：报出所有被标记的汇报人，并说明日程存在歧义。
- 对于提醒：把该环节所有被标记的汇报人都列出来。
- 不要擅自挑一个汇报人。

组会时间行的格式：

```text
⌛️暂定本周组会时间：[周X]YYYY-MM-DD HH:MM–HH:MM
```

换讲名单的格式：

```text
A同学[ ] 和 B同学[✅] 交换
```

`[✅]` 表示这位同学已经完成了换来的那次汇报。`[ ]` 表示还没有。一旦双方都是 `[✅]`，立刻删掉这一行换讲记录。

## 查询当前汇报人

触发条件：用户问本周 Work Report、News 或 Showcase Session 由谁汇报。

步骤：

1. 先拉取。
2. 读本地缓存。
3. 确定看哪一侧：Work Report/News 用左侧成员列；Showcase Session 用右侧成员列。
4. 特殊状态优先：如果目标列里同时出现 `🚫跳过0次(😀本周同学)` 和 `😀已讲`，则由 `🚫跳过0次(😀本周同学)` 那位同学本周汇报。
5. 否则找出所有 `😀本周同学` 标记。如果没有标记，就报告目标列没有当前汇报人并停止。如果有多个标记，报出所有被标记的汇报人并说明日程存在歧义，不要挑一个。如果恰好有一个标记，把那位同学当作名义汇报人。
6. 只检查提到这位名义汇报人的换讲行。如果没有任何换讲行提到他们，就停止：名义汇报人即为最终结论。
7. 如果有换讲行提到他们，推断最终汇报人：
   - 双方都是 `[ ]`：由换讲对方汇报。
   - 名义汇报人 `[✅]`、对方 `[ ]`：由对方来还这次。
   - 名义汇报人 `[ ]`、对方 `[✅]`：由名义汇报人来还这次。
8. 当特殊状态或换讲改变了最终汇报人时，解释原因。如果换讲状态存在歧义，就问清最终应该由谁汇报。

## 组会后轮换

触发条件：用户说组会结束了，或要求更新下周轮换。

只跑脚本；不要手动编辑表格。

```bash
python3 scripts/feishu_sync.py pull
python3 scripts/update_schedule.py
python3 scripts/feishu_sync.py push
```

轮换脚本会处理左右两侧的独立轮换、跳过计数、`😀已讲`、`🚫跳过0次(😀本周同学)`、以及组会日期 +7 天。

## 调整组会时间

触发条件：用户要求改组会日期或时间。

步骤：

1. 先拉取。
2. 只编辑本地缓存里的 `⌛️暂定本周组会时间` 那一行。
3. 保持规定的格式。
4. 确保 `周X` 与实际日期一致。
5. 如果用户只给了日期，保留原来的时间段。
6. 如果用户只给了时间段，保留原来的日期。
7. 校验后推送。

纯粹的时间调整不要跑轮换脚本。

## 提醒

触发条件：用户要求发一条组会提醒。

被要求发提醒时，不要在发送前再问确认。拉取最新日程、确定当前组会时间和汇报人、拟好提醒、直接发到配置好的会话。如果缺少必要的会话配置，就说清缺哪个字段，并把确切的消息内容起草出来。

使用当前环境可用的飞书/Lark 消息工具。如果环境提供 `message` 工具，优先用它。如果消息工具不可用，就起草提醒文本，不要假装已经发出去了。

在 Codex 或 `lark-cli` 环境下，用这个命令发提醒：

```bash
lark-cli im +messages-send \
  --as bot \
  --chat-id "$CHAT_ID" \
  --text "$REMINDER_TEXT" \
  --json
```

测试提醒的 `CHAT_ID` 必须是 `test_chat_id`。正式提醒的 `CHAT_ID` 必须是 `target_chat_id`。

建议的配置字段：

- `target_chat_id`：正式群会话 ID。
- `test_chat_id`：测试群会话 ID。
- `schedule_doc_url`：给人看的日程文档链接。

如果用户说这是测试，发到 `test_chat_id`；否则发到 `target_chat_id`。

提醒内容应包含：

- 下一次暂定的组会时间。
- Work Report、News 和 Showcase Session 的当前汇报人。
- 日程文档链接。
- 相关时附上换讲细节。
- 会前提醒要明确提示 Showcase Session 的汇报人准备好演示/内容。
- Emoji 标签与示例格式一致：`📢`、`⌛️`、`👤`、`📰`、`🎯`、`📋`。

提醒示例：

```text
📢 本周组会提醒
⌛️ 时间：2026-05-15（周五）11:00–13:00
👤 Work Report：黄天宇
📰 News：黄炜、魏靖霖
🎯 Showcase Session：蒋哲
请负责 Showcase Session 的同学（蒋哲）提前准备好展示内容～
📋 组会安排目录：<可访问的链接>
```
