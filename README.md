# LAR Plugins

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

After this repository is pushed to GitHub, add it as a marketplace:

```bash
codex plugin marketplace add OWNER/lar-plugins
```

For local testing:

```bash
codex plugin marketplace add /home/lianganran/lianganran/lar-plugins
```

Then open `/plugins`, choose the `LAR Plugins` marketplace, and install `feishu-group-meeting`.

## Claude Code

After this repository is pushed to GitHub, add and install:

```text
/plugin marketplace add OWNER/lar-plugins
/plugin install feishu-group-meeting@lar-plugins
```

For local testing:

```bash
claude plugin marketplace add /home/lianganran/lianganran/lar-plugins
claude plugin install feishu-group-meeting@lar-plugins
```

You can also load the plugin directory directly while developing:

```bash
claude --plugin-dir /home/lianganran/lianganran/lar-plugins/plugins/feishu-group-meeting
```
