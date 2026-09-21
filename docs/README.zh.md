# larskill

> 本文是根目录 `README.md` 的中文翻译，仅供阅读。命令和路径以英文原文为准。

可移植的 Codex 与 Claude Code 插件。

## 包含的插件

- `feishu-group-meeting`：管理飞书/Lark 群组会日程 —— 把 Docx/Wiki 文档拉成 Markdown、查询本周汇报人、轮换每周讲者、调整组会时间、发送或起草提醒、并把改动推回飞书。
- `talk-like-a-human`：写人能快速读懂并且信得过的回复。结论先行，把圈内行话换成读者本来就有的词，一句话一个意思，只有内容真的有结构时才用项目符号和表格，保留确切的数字和名字，并用用户的语言回复。无需配置。
- `bug-verifier`：给它一份 bug 文档和一份源码目录。它会读被指控的代码和触发用的测试，追查那个坏状态是否能从公开入口用调用者可控的参数到达，并给出一个结论：确认缺陷、潜伏缺陷、不是缺陷、或未定。对真缺陷，它会产出一份 issue 报告（确切的 `file:line`、代码片段、复现、预期 vs 实际、修复方案）和一份理解指南（模块职责、设计意图、不变量、陌生概念、历史沿革）。无需配置。

## 配置 Feishu Group Meeting

从这里复制模版：

```text
plugins/feishu-group-meeting/skills/feishu-sync-group-meeting/config.example.json
```

在以下位置之一创建你自己的私有配置：

```text
~/.config/feishu-sync-group-meeting/config.json
plugins/feishu-group-meeting/skills/feishu-sync-group-meeting/config.json
```

或者使用环境变量：

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="..."
export FEISHU_DOC_URL="https://example.feishu.cn/docx/..."
```

不要提交 `config.json`；它已经被 `.gitignore` 忽略。

## Codex

把这个 GitHub 仓库加为 marketplace，然后安装 `feishu-group-meeting`：

```bash
codex plugin marketplace add lar0129/larskill
codex plugin add feishu-group-meeting@larskill
codex plugin add talk-like-a-human@larskill
codex plugin add bug-verifier@larskill
```

本地测试：

```bash
git clone git@github.com:lar0129/larskill.git
cd larskill
codex plugin marketplace add "$(pwd)"
codex plugin add feishu-group-meeting@larskill
```

也可以打开 `/plugins`，选择 `larskill` marketplace，然后安装 `feishu-group-meeting`。

这个仓库有变更后，更新已有的 Codex marketplace 快照：

```bash
codex plugin marketplace upgrade larskill
```

更新所有已配置的 Git marketplace：

```bash
codex plugin marketplace upgrade
```

## Claude Code

这个仓库推到 GitHub 之后，添加 marketplace 并安装 `feishu-group-meeting`：

```text
/plugin marketplace add lar0129/larskill
/plugin install feishu-group-meeting@larskill
/plugin install talk-like-a-human@larskill
/plugin install bug-verifier@larskill
```

本地测试：

```bash
git clone git@github.com:lar0129/larskill.git
cd larskill
claude plugin marketplace add "$(pwd)"
claude plugin install feishu-group-meeting@larskill
```

这个仓库有变更后，更新已有的 Claude Code marketplace 快照：

```text
/plugin marketplace update larskill
```

开发时也可以直接加载插件目录：

```bash
claude --plugin-dir "$(pwd)/plugins/feishu-group-meeting"
```

## 飞书/Lark 消息发送

当本地环境配置好 `lark-cli` 时，这个 skill 可以用它与飞书/Lark 交互。要发群提醒，需要先初始化 `lark-cli`、确保应用具备 IM 消息权限、并确保机器人或用户身份能访问目标会话。

初始化 `lark-cli`：

```bash
lark-cli config init --new
```

以应用机器人身份发群消息：

```bash
lark-cli im +messages-send --as bot --chat-id oc_xxx --markdown "Meeting reminder"
```

改为以已授权用户身份发送：

```bash
lark-cli auth login --scope "im:message"
lark-cli im +messages-send --as user --chat-id oc_xxx --markdown "Meeting reminder"
```

想先确认外发消息的形态时，先用 `--dry-run`：

```bash
lark-cli im +messages-send --as bot --chat-id oc_xxx --markdown "Meeting reminder" --dry-run
```
