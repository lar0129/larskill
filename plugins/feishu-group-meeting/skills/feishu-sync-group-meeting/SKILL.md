---
name: feishu-sync-group-meeting
description: Manage a Feishu/Lark group meeting schedule by pulling a docx/wiki document to Markdown, querying current presenters, rotating weekly speakers, rescheduling meeting time, and pushing updates back to Feishu. Use for group meeting speaker queries, schedule updates, Feishu sync, meeting reminders, or weekly rotation tasks.
---

# Feishu Group Meeting

This skill manages a Feishu/Lark group meeting schedule stored in a Docx or Wiki document. It uses bundled Python scripts to pull the live document into a local Markdown cache, edit or rotate that cache, and push changes back to Feishu.

When the user asks to send a reminder or modify the schedule document, do not ask for another confirmation. Pull the latest document, perform the requested action, validate the result, and send or push directly. Ask a question only when required information is missing, the target chat/document is unavailable, or the requested change is ambiguous.

## Setup

Before first use, configure credentials with either environment variables or a local config file.

Environment variables:

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="..."
export FEISHU_DOC_URL="https://example.feishu.cn/docx/..."
```

Config file locations, in priority order:

1. `FEISHU_GROUP_MEETING_CONFIG`
2. `config.json` beside this `SKILL.md`
3. `~/.config/feishu-sync-group-meeting/config.json`
4. `~/.feishu-sync-group-meeting/config.json`

Use `config.example.json` as the template. Never print or expose `app_secret`.

Never print config files directly with commands such as `cat`, `sed`, or `less`, because they contain `app_secret`. To inspect config safely, use targeted or redacted reads:

```bash
# Redacted overview.
jq 'del(.app_secret)' "$CONFIG_PATH"

# Single non-secret fields.
jq -r '.test_chat_id' "$CONFIG_PATH"
jq -r '.target_chat_id' "$CONFIG_PATH"
jq -r '.schedule_doc_url' "$CONFIG_PATH"
```

If `requests` is missing, run this from the skill directory:

```bash
python3 -m pip install -r requirements.txt
```

## Commands

Run commands from this skill directory. In Claude Code, `${CLAUDE_SKILL_DIR}` is this directory; in Codex, resolve relative paths from this `SKILL.md`.

```bash
# Pull latest Feishu document into the local Markdown cache.
python3 scripts/feishu_sync.py pull

# Print the local cache path for reading/editing.
python3 scripts/feishu_sync.py path

# Push the local Markdown cache back to Feishu.
python3 scripts/feishu_sync.py push

# Rotate once after a meeting ends.
python3 scripts/update_schedule.py

# Preview rotation without writing.
python3 scripts/update_schedule.py --dry-run
```

Default cache path: `~/.cache/feishu-sync-group-meeting/feishu_schedule.md`.

## Workflow

1. Pull: `python3 scripts/feishu_sync.py pull`.
2. Read the cache path from `python3 scripts/feishu_sync.py path`.
3. Answer the user's query or edit only the requested schedule line/section.
4. Validate that table markers and member order are still valid.
5. For user-requested state-changing operations, push directly after validation without asking for an extra confirmation.

## Schedule Rules

The schedule table has two independent member orders in one Markdown table:

- Left member column: controls `Work Report` and `News`.
- Right member column: controls `Showcase Session`.
- The member lists may contain the same people in different orders; rotate each side independently.

Strict status markers:

| Marker | Meaning |
|---|---|
| `😀本周同学` | Current presenter |
| `🚫跳过` | Permanently skipped |
| `🚫跳过N次` | Skip for N more weeks |
| `🚫跳过0次(😀本周同学)` | Skip countdown reached zero; this person presents this week |
| `😀已讲` | Deferred current marker; restored by the next rotation |

If a target column contains multiple `😀本周同学` markers:

- For direct "who presents" queries: report all marked presenters and say the schedule is ambiguous.
- For reminders: list all marked presenters for that session.
- Do not silently choose one presenter.

Meeting time line format:

```text
⌛️暂定本周组会时间：[周X]YYYY-MM-DD HH:MM–HH:MM
```

Swap list format:

```text
A同学[ ] 和 B同学[✅] 交换
```

`[✅]` means that person has completed the swapped presentation. `[ ]` means not yet. Delete a swap row immediately once both sides are `[✅]`.

## Query Current Presenter

Trigger: the user asks who presents this week for Work Report, News, or Showcase Session.

Steps:

1. Pull first.
2. Read the local cache.
3. Determine side: Work Report/News use the left member column; Showcase Session uses the right member column.
4. Special state has priority: if the target column contains both `🚫跳过0次(😀本周同学)` and `😀已讲`, the `🚫跳过0次(😀本周同学)` person presents this week.
5. Otherwise find every `😀本周同学` marker. If there are no markers, report that the target column has no current presenter and stop. If there are multiple markers, report all marked presenters and say the schedule is ambiguous; do not pick one. If there is exactly one marker, treat that person as the official presenter.
6. Check only swap rows that mention the official presenter. If none mention them, stop: the official presenter is final.
7. If a swap row mentions them, infer final presenter:
   - Both `[ ]`: the swap counterpart presents.
   - Official presenter `[✅]`, counterpart `[ ]`: counterpart presents as repayment.
   - Official presenter `[ ]`, counterpart `[✅]`: official presenter presents as repayment.
8. Explain the reason when a special state or swap changes the final presenter. If the swap state is ambiguous, ask who the final presenter should be.

## Rotate After Meeting

Trigger: the user says the meeting ended or asks to update next week's rotation.

Only run the scripts; do not manually edit the table.

```bash
python3 scripts/feishu_sync.py pull
python3 scripts/update_schedule.py
python3 scripts/feishu_sync.py push
```

The rotation script handles independent left/right rotations, skip countdowns, `😀已讲`, `🚫跳过0次(😀本周同学)`, and meeting date +7 days.

## Reschedule Meeting

Trigger: the user asks to change the meeting date or time.

Steps:

1. Pull first.
2. Edit only the `⌛️暂定本周组会时间` line in the local cache.
3. Keep the required format.
4. Ensure `周X` matches the actual date.
5. If the user gives only a date, keep the original time range.
6. If the user gives only a time range, keep the original date.
7. Push after validation.

Do not run the rotation script for a pure reschedule.

## Reminders

Trigger: the user asks to send a group meeting reminder.

Do not ask for confirmation before sending a requested reminder. Pull the latest schedule, identify the current meeting time and presenters, compose the reminder, and send it directly to the configured chat. If required chat configuration is missing, state the missing field and draft the exact message instead.

Use the available Feishu/Lark messaging tool for the active environment. If the environment provides a `message` tool, prefer it. If messaging tools are unavailable, draft the reminder text instead of pretending it was sent.

In Codex or `lark-cli` environments, send reminders with:

```bash
lark-cli im +messages-send \
  --as bot \
  --chat-id "$CHAT_ID" \
  --text "$REMINDER_TEXT" \
  --json
```

For test reminders, `CHAT_ID` must be `test_chat_id`. For production reminders, `CHAT_ID` must be `target_chat_id`.

Recommended config fields:

- `target_chat_id`: production group chat ID.
- `test_chat_id`: test group chat ID.
- `schedule_doc_url`: human-facing schedule document URL.

If the user says this is a test, send to `test_chat_id`; otherwise send to `target_chat_id`.

Reminder content should include:

- Next tentative meeting time.
- Current presenters for Work Report, News, and Showcase Session.
- Schedule document URL.
- Swap details when relevant.
- For pre-meeting reminders, explicitly remind Showcase Session presenters to prepare their demo/content.
- Emoji labels matching the example format: `📢`, `⌛️`, `👤`, `📰`, `🎯`, and `📋`.

Example reminder:

```text
📢 本周组会提醒
⌛️ 时间：2026-05-15（周五）11:00–13:00
👤 Work Report：黄天宇
📰 News：黄炜、魏靖霖
🎯 Showcase Session：蒋哲
请负责 Showcase Session 的同学（蒋哲）提前准备好展示内容～
📋 组会安排目录：<可访问的链接>
```
