# LAR Skill

Portable Codex and Claude Code plugins.

## Included Plugins

- `feishu-group-meeting`: manage a Feishu/Lark group meeting schedule by pulling a Docx/Wiki document to Markdown, querying presenters, rotating weekly speakers, rescheduling meeting time, sending/drafting reminders, and pushing updates back to Feishu.

## Configure Feishu Group Meeting

Copy the template from:

```text
plugins/feishu-group-meeting/skills/feishu-sync-group-meeting/config.example.json
```

Create your private config at one of these locations:

```text
~/.config/feishu-sync-group-meeting/config.json
plugins/feishu-group-meeting/skills/feishu-sync-group-meeting/config.json
```

Or use environment variables:

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="..."
export FEISHU_DOC_URL="https://example.feishu.cn/docx/..."
```

Do not commit `config.json`; it is ignored by `.gitignore`.

## Codex

Add this GitHub repository as a marketplace:

```bash
codex plugin marketplace add lar0129/larskill
```

For local testing:

```bash
git clone git@github.com:lar0129/larskill.git
cd larskill
codex plugin marketplace add "$(pwd)"
```

Then open `/plugins`, choose the `LAR Plugins` marketplace, and install `feishu-group-meeting`.

Update an existing Codex marketplace snapshot after this repository changes:

```bash
codex plugin marketplace upgrade lar-plugins
```

To update all configured Git marketplaces:

```bash
codex plugin marketplace upgrade
```

## Claude Code

After this repository is pushed to GitHub, add and install:

```text
/plugin marketplace add lar0129/larskill
/plugin install feishu-group-meeting@lar-plugins
```

For local testing:

```bash
git clone git@github.com:lar0129/larskill.git
cd larskill
claude plugin marketplace add "$(pwd)"
claude plugin install feishu-group-meeting@lar-plugins
```

Update an existing Claude Code marketplace snapshot after this repository changes:

```text
/plugin marketplace update lar-plugins
```

You can also load the plugin directory directly while developing:

```bash
claude --plugin-dir "$(pwd)/plugins/feishu-group-meeting"
```

## Feishu/Lark Messaging

This skill can use `lark-cli` to interact with Feishu/Lark when the local environment has it configured. For group reminders, initialize `lark-cli`, make sure the app has IM message scopes, and make sure the bot or user identity can access the target chat.

Initialize `lark-cli`:

```bash
lark-cli config init --new
```

Send a group message as the app bot:

```bash
lark-cli im +messages-send --as bot --chat-id oc_xxx --markdown "Meeting reminder"
```

Send as the authorized user instead:

```bash
lark-cli auth login --scope "im:message"
lark-cli im +messages-send --as user --chat-id oc_xxx --markdown "Meeting reminder"
```

Use `--dry-run` first when checking the outgoing message shape:

```bash
lark-cli im +messages-send --as bot --chat-id oc_xxx --markdown "Meeting reminder" --dry-run
```
