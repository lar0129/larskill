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

You can also load the plugin directory directly while developing:

```bash
claude --plugin-dir "$(pwd)/plugins/feishu-group-meeting"
```
