#!/usr/bin/env python3
"""飞书文档同步工具 - 在飞书文档和本地 Markdown 之间双向同步"""

import json
import re
import sys
import os
import requests
from pathlib import Path
from urllib.parse import quote, unquote

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_DIR = Path(
    os.environ.get("FEISHU_GROUP_MEETING_HOME", "~/.config/feishu-sync-group-meeting")
).expanduser()
CACHE_DIR = Path(
    os.environ.get("FEISHU_GROUP_MEETING_CACHE", "~/.cache/feishu-sync-group-meeting")
).expanduser()
BASE_URL = "https://open.feishu.cn"

# ─── Block type constants ───
BT_PAGE = 1
BT_TEXT = 2
BT_HEADING1 = 3
BT_HEADING2 = 4
BT_HEADING3 = 5
BT_HEADING4 = 6
BT_HEADING5 = 7
BT_HEADING6 = 8
BT_HEADING7 = 9
BT_HEADING8 = 10
BT_HEADING9 = 11
BT_BULLET = 12
BT_ORDERED = 13
BT_CODE = 14
BT_QUOTE = 15
BT_TODO = 17
BT_DIVIDER = 22
BT_TABLE = 31
BT_TABLE_CELL = 32


# ═══════════════════════════════════════════
#  Auth & API helpers
# ═══════════════════════════════════════════

def _expand_path(raw_path: str, base_dir: Path | None = None) -> Path:
    path = Path(os.path.expandvars(raw_path)).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path


def find_config_file() -> Path | None:
    env_path = os.environ.get("FEISHU_GROUP_MEETING_CONFIG")
    candidates = []
    if env_path:
        candidates.append(_expand_path(env_path))
    candidates.extend([
        SKILL_DIR / "config.json",
        CONFIG_DIR / "config.json",
        Path("~/.feishu-sync-group-meeting/config.json").expanduser(),
    ])
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_config(require_credentials: bool = True) -> dict:
    config_path = find_config_file()
    config = {}
    if config_path:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
        config["_config_path"] = str(config_path)
    else:
        config["_config_path"] = None

    env_overrides = {
        "app_id": "FEISHU_APP_ID",
        "app_secret": "FEISHU_APP_SECRET",
        "wiki_url": "FEISHU_DOC_URL",
        "md_file": "FEISHU_GROUP_MEETING_MD_FILE",
    }
    for key, env_name in env_overrides.items():
        value = os.environ.get(env_name)
        if value:
            config[key] = value

    if require_credentials:
        missing = [
            key for key in ("app_id", "app_secret", "wiki_url")
            if not config.get(key)
        ]
        if missing:
            locations = [
                "$FEISHU_GROUP_MEETING_CONFIG",
                str(SKILL_DIR / "config.json"),
                str(CONFIG_DIR / "config.json"),
            ]
            raise SystemExit(
                "缺少飞书配置字段: "
                + ", ".join(missing)
                + "\n请设置环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET / "
                + "FEISHU_DOC_URL，或创建 config.json。候选位置:\n  "
                + "\n  ".join(locations)
            )
    return config


def resolve_md_path(config: dict) -> Path:
    raw_path = config.get("md_file") or str(CACHE_DIR / "feishu_schedule.md")
    config_path = config.get("_config_path")
    base_dir = Path(config_path).parent if config_path else CONFIG_DIR
    path = _expand_path(raw_path, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_tenant_access_token(app_id, app_secret):
    url = f"{BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取 tenant_access_token 失败: {data}")
    return data["tenant_access_token"]


def api_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def parse_feishu_url(url):
    """解析飞书文档 URL，返回 (url_type, token)
    支持:
      /wiki/{wiki_token}  → ("wiki", token)
      /docx/{document_id} → ("docx", token)
    """
    m = re.search(r"/wiki/([a-zA-Z0-9_-]+)", url)
    if m:
        return "wiki", m.group(1)
    m = re.search(r"/docx/([a-zA-Z0-9_-]+)", url)
    if m:
        return "docx", m.group(1)
    raise ValueError(f"无法解析飞书文档 URL: {url}\n支持格式: /wiki/{{token}} 或 /docx/{{token}}")


def get_wiki_node(wiki_token, access_token):
    url = f"{BASE_URL}/open-apis/wiki/v2/spaces/get_node"
    resp = requests.get(url, headers=api_headers(access_token),
                        params={"token": wiki_token})
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取 wiki 节点失败: {data}")
    node = data["data"]["node"]
    return node["obj_token"], node["obj_type"]


def resolve_document_id(config_url, access_token):
    """从 URL 解析出 document_id（自动处理 wiki 和 docx 两种格式）"""
    url_type, token = parse_feishu_url(config_url)
    if url_type == "wiki":
        obj_token, obj_type = get_wiki_node(token, access_token)
        if obj_type != "docx":
            raise Exception(f"不支持的文档类型: {obj_type}，仅支持 docx")
        return obj_token
    else:
        # /docx/ URL，token 就是 document_id
        return token


def get_document_info(document_id, access_token):
    url = f"{BASE_URL}/open-apis/docx/v1/documents/{document_id}"
    resp = requests.get(url, headers=api_headers(access_token))
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取文档信息失败: {data}")
    return data["data"]["document"]


def get_document_blocks(document_id, access_token):
    url = f"{BASE_URL}/open-apis/docx/v1/documents/{document_id}/blocks"
    headers = api_headers(access_token)
    all_blocks = []
    page_token = None

    while True:
        params = {"page_size": 500, "document_revision_id": -1}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"获取文档块失败: {data}")
        all_blocks.extend(data["data"]["items"])
        if not data["data"].get("has_more"):
            break
        page_token = data["data"]["page_token"]

    return all_blocks


# ═══════════════════════════════════════════
#  Pull: Feishu blocks → Markdown
# ═══════════════════════════════════════════

def elements_to_md(elements, in_table=False):
    """将飞书 text elements 转换为 Markdown 字符串"""
    if not elements:
        return ""
    parts = []
    for elem in elements:
        if "text_run" in elem:
            tr = elem["text_run"]
            content = tr.get("content", "").rstrip("\n")
            style = tr.get("text_element_style", {})

            link_url = ""
            link_info = style.get("link")
            if link_info:
                link_url = link_info.get("url", "")
                if link_url:
                    try:
                        link_url = unquote(link_url)
                    except Exception:
                        pass

            if link_url:
                # 链接: [text](url)
                parts.append(f"[{content}]({link_url})")
            else:
                # 应用 inline 样式
                if not in_table:
                    if style.get("bold") and style.get("italic"):
                        content = f"***{content}***"
                    elif style.get("bold"):
                        content = f"**{content}**"
                    elif style.get("italic"):
                        content = f"*{content}*"
                    if style.get("strikethrough"):
                        content = f"~~{content}~~"
                    if style.get("inline_code"):
                        content = f"`{content}`"
                parts.append(content)

        elif "mention_doc" in elem:
            md = elem["mention_doc"]
            title = md.get("title", "doc")
            url = md.get("url", "")
            if url:
                try:
                    url = unquote(url)
                except Exception:
                    pass
                parts.append(f"[{title}]({url})")
            else:
                parts.append(title)

        elif "equation" in elem:
            parts.append(f"${elem['equation'].get('content', '')}$")

    return "".join(parts)


def get_cell_text(cell_block, block_map):
    """获取表格单元格的文本内容"""
    children_ids = cell_block.get("children", [])
    parts = []
    for cid in children_ids:
        child = block_map.get(cid)
        if not child:
            continue
        bt = child["block_type"]
        if bt == BT_TEXT:
            elems = child.get("text", {}).get("elements", [])
            parts.append(elements_to_md(elems, in_table=True))
        elif BT_HEADING1 <= bt <= BT_HEADING9:
            level = bt - 2
            elems = child.get(f"heading{level}", {}).get("elements", [])
            parts.append(elements_to_md(elems, in_table=True))
    return " ".join(p for p in parts if p.strip()) if parts else ""


def table_block_to_md(block, block_map):
    """将 table block 转换为 Markdown 表格"""
    table_data = block.get("table", {})
    prop = table_data.get("property", {})
    row_size = prop.get("row_size", 0)
    col_size = prop.get("column_size", 0)
    if row_size == 0 or col_size == 0:
        return ""

    children_ids = block.get("children", [])
    rows = []
    for r in range(row_size):
        row = []
        for c in range(col_size):
            idx = r * col_size + c
            if idx < len(children_ids):
                cell = block_map.get(children_ids[idx])
                row.append(get_cell_text(cell, block_map) if cell else "")
            else:
                row.append("")
        rows.append(row)

    lines = []
    for i, row in enumerate(rows):
        sanitized = [c.replace("\n", " ").strip() if c else "" for c in row]
        lines.append("|" + "|".join(sanitized) + "|")
        if i == 0:
            lines.append("|" + "|".join(["---"] * col_size) + "|")
    return "\n".join(lines)


def block_to_md(block, block_map):
    """将单个 block 转换为 Markdown"""
    bt = block["block_type"]

    if bt == BT_TEXT:
        elems = block.get("text", {}).get("elements", [])
        return elements_to_md(elems)

    if BT_HEADING1 <= bt <= BT_HEADING9:
        level = bt - 2
        elems = block.get(f"heading{level}", {}).get("elements", [])
        text = elements_to_md(elems)
        return f"{'#' * level} {text}"

    if bt == BT_BULLET:
        elems = block.get("bullet", {}).get("elements", [])
        text = elements_to_md(elems)
        result = f"- {text}"
        for cid in block.get("children", []):
            child = block_map.get(cid)
            if child:
                child_md = block_to_md(child, block_map)
                if child_md:
                    result += "\n" + "\n".join(
                        "    " + line for line in child_md.split("\n")
                    )
        return result

    if bt == BT_ORDERED:
        elems = block.get("ordered", {}).get("elements", [])
        return f"1. {elements_to_md(elems)}"

    if bt == BT_CODE:
        elems = block.get("code", {}).get("elements", [])
        return f"```\n{elements_to_md(elems)}\n```"

    if bt == BT_QUOTE:
        elems = block.get("quote", {}).get("elements", [])
        return f"> {elements_to_md(elems)}"

    if bt == BT_TODO:
        todo = block.get("todo", {})
        elems = todo.get("elements", [])
        done = todo.get("style", {}).get("done", False)
        check = "[x]" if done else "[ ]"
        return f"- {check} {elements_to_md(elems)}"

    if bt == BT_DIVIDER:
        return "---"

    if bt == BT_TABLE:
        return table_block_to_md(block, block_map)

    return None


def blocks_to_markdown(blocks):
    """将所有 blocks 转成完整的 Markdown 文档"""
    block_map = {b["block_id"]: b for b in blocks}

    page_block = next((b for b in blocks if b["block_type"] == BT_PAGE), None)
    if not page_block:
        raise Exception("未找到 page block")

    lines = []
    for cid in page_block.get("children", []):
        block = block_map.get(cid)
        if not block:
            continue
        md = block_to_md(block, block_map)
        if md is not None:
            lines.append(md)

    return "\n\n".join(lines) + "\n"


# ═══════════════════════════════════════════
#  Push: Markdown → Feishu blocks
# ═══════════════════════════════════════════

def parse_inline_md(text):
    """解析 inline Markdown 为飞书 text elements"""
    elements = []
    pos = 0
    n = len(text)

    while pos < n:
        # [text](url)
        m = re.match(r'\[([^\]]*)\]\(([^)]+)\)', text[pos:])
        if m:
            link_text = m.group(1)
            link_url = m.group(2)
            elements.append({
                "text_run": {
                    "content": link_text,
                    "text_element_style": {
                        "link": {"url": quote(link_url, safe="")}
                    }
                }
            })
            pos += m.end()
            continue

        # ***bold italic***
        m = re.match(r'\*\*\*(.+?)\*\*\*', text[pos:])
        if m:
            elements.append({
                "text_run": {
                    "content": m.group(1),
                    "text_element_style": {"bold": True, "italic": True}
                }
            })
            pos += m.end()
            continue

        # **bold**
        m = re.match(r'\*\*(.+?)\*\*', text[pos:])
        if m:
            elements.append({
                "text_run": {
                    "content": m.group(1),
                    "text_element_style": {"bold": True}
                }
            })
            pos += m.end()
            continue

        # *italic*
        m = re.match(r'\*(.+?)\*', text[pos:])
        if m:
            elements.append({
                "text_run": {
                    "content": m.group(1),
                    "text_element_style": {"italic": True}
                }
            })
            pos += m.end()
            continue

        # ~~strikethrough~~
        m = re.match(r'~~(.+?)~~', text[pos:])
        if m:
            elements.append({
                "text_run": {
                    "content": m.group(1),
                    "text_element_style": {"strikethrough": True}
                }
            })
            pos += m.end()
            continue

        # `inline code`
        m = re.match(r'`(.+?)`', text[pos:])
        if m:
            elements.append({
                "text_run": {
                    "content": m.group(1),
                    "text_element_style": {"inline_code": True}
                }
            })
            pos += m.end()
            continue

        # 普通文本 - 读到下一个特殊字符
        next_pos = n
        for pat in [r'\[', r'\*', r'~~', r'`']:
            sm = re.search(pat, text[pos + 1:])
            if sm:
                next_pos = min(next_pos, pos + 1 + sm.start())
        plain = text[pos:next_pos]
        if plain:
            elements.append({
                "text_run": {
                    "content": plain,
                    "text_element_style": {}
                }
            })
        pos = next_pos

    if not elements:
        elements.append({"text_run": {"content": "", "text_element_style": {}}})
    return elements


def make_text_block(elements):
    return {"block_type": BT_TEXT, "text": {"elements": elements}}


def make_heading_block(level, elements):
    bt = level + 2
    return {"block_type": bt, f"heading{level}": {"elements": elements}}


def make_bullet_block(elements):
    return {"block_type": BT_BULLET, "bullet": {"elements": elements}}


def make_ordered_block(elements):
    return {"block_type": BT_ORDERED, "ordered": {"elements": elements}}


def make_table_block(rows, row_count, col_count):
    """创建空表格块（cells 内容后续通过 fill_table_cells 填充）"""
    return {
        "type": "table",
        "block_type": BT_TABLE,
        "table": {
            "property": {
                "row_size": row_count,
                "column_size": col_count,
                "column_width": [100] + [250] * (col_count - 1)
            },
        },
        "_rows": rows,  # 暂存行数据，创建后填充
    }


def parse_md_table(lines):
    """解析 Markdown 表格行为行列数据"""
    rows = []
    for line in lines:
        line = line.strip()
        if re.match(r'^\|[\s\-:|]+\|$', line) and '-' in line:
            continue
        cells = line.split("|")
        if cells and cells[0].strip() == "":
            cells = cells[1:]
        if cells and cells[-1].strip() == "":
            cells = cells[:-1]
        rows.append([c.strip() for c in cells])

    if not rows:
        return None
    col_count = max(len(r) for r in rows)
    for r in rows:
        while len(r) < col_count:
            r.append("")
    return {"rows": rows, "row_count": len(rows), "col_count": col_count}


def parse_markdown_to_descriptors(md_text):
    """将 Markdown 文本解析为 block 描述列表"""
    lines = md_text.split("\n")
    descriptors = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        if line.strip() == "":
            i += 1
            continue

        # 表格
        if line.strip().startswith("|"):
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            tbl = parse_md_table(table_lines)
            if tbl:
                descriptors.append(("table", tbl))
            continue

        # 标题
        m = re.match(r'^(#{1,9})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            descriptors.append(("heading", level, m.group(2)))
            i += 1
            continue

        # 列表项
        m = re.match(r'^(\s*)- (.*)', line)
        if m:
            text = m.group(2)
            children = []
            i += 1
            while i < n:
                nl = lines[i]
                if nl.strip() == "":
                    i += 1
                    continue
                cm = re.match(r'^(\s{4,})(.*)', nl)
                if cm and not nl.strip().startswith("-") and not nl.strip().startswith("|"):
                    children.append(cm.group(2))
                    i += 1
                else:
                    break
            descriptors.append(("bullet", text, children))
            continue

        # 有序列表
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            descriptors.append(("ordered", m.group(1)))
            i += 1
            continue

        # 分割线
        if re.match(r'^---+\s*$', line):
            descriptors.append(("divider",))
            i += 1
            continue

        # 普通文本
        descriptors.append(("text", line))
        i += 1

    return descriptors


def descriptors_to_blocks(descriptors):
    """将描述列表转换为飞书 API block JSON 列表"""
    blocks = []
    for desc in descriptors:
        kind = desc[0]

        if kind == "text":
            blocks.append(make_text_block(parse_inline_md(desc[1])))

        elif kind == "heading":
            level, text = desc[1], desc[2]
            blocks.append(make_heading_block(level, parse_inline_md(text)))

        elif kind == "bullet":
            text, children = desc[1], desc[2]
            block = make_bullet_block(parse_inline_md(text))
            if children:
                block["children"] = [
                    make_text_block(parse_inline_md(ct)) for ct in children
                ]
            blocks.append(block)

        elif kind == "ordered":
            blocks.append(make_ordered_block(parse_inline_md(desc[1])))

        elif kind == "divider":
            blocks.append({"block_type": BT_DIVIDER, "divider": {}})

        elif kind == "table":
            tbl = desc[1]
            blocks.append(
                make_table_block(tbl["rows"], tbl["row_count"], tbl["col_count"])
            )

    return blocks


# ─── API write operations ───

def delete_document_body(document_id, access_token):
    """删除文档正文的所有子块，返回 (page_block_id, new_revision)"""
    blocks = get_document_blocks(document_id, access_token)
    page_block = next((b for b in blocks if b["block_type"] == BT_PAGE), None)
    if not page_block:
        raise Exception("未找到 page block")

    children = page_block.get("children", [])
    if not children:
        doc_info = get_document_info(document_id, access_token)
        return page_block["block_id"], doc_info["revision_id"]

    doc_info = get_document_info(document_id, access_token)
    revision = doc_info["revision_id"]

    url = (f"{BASE_URL}/open-apis/docx/v1/documents/{document_id}"
           f"/blocks/{page_block['block_id']}/children/batch_delete")
    body = {"start_index": 0, "end_index": len(children)}
    resp = requests.delete(url, headers=api_headers(access_token),
                           json=body, params={"document_revision_id": revision})
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"删除文档块失败: {data}")

    return page_block["block_id"], revision + 1


def create_children(document_id, parent_block_id, children, access_token, revision=None):
    """调用 create children API 创建子块，返回 (响应data, 新revision)
    如果未提供 revision，则自动获取（兼容旧调用方式）。
    """
    url = (f"{BASE_URL}/open-apis/docx/v1/documents/{document_id}"
           f"/blocks/{parent_block_id}/children")
    if revision is None:
        doc_info = get_document_info(document_id, access_token)
        revision = doc_info["revision_id"]
    body = {"children": children, "index": -1}
    resp = requests.post(url, headers=api_headers(access_token), json=body,
                         params={"document_revision_id": revision})
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"创建子块失败: {data}")
    return data.get("data", {}), revision + 1


def rows_to_markdown_table(rows: list) -> str:
    """将表格行数据重新转为 Markdown 表格字符串，供 blocks/convert API 使用。"""
    if not rows:
        return ""
    lines = []
    for i, row in enumerate(rows):
        lines.append("|" + "|".join(row) + "|")
        if i == 0:
            lines.append("|" + "|".join(["---"] * len(row)) + "|")
    return "\n".join(lines)


def convert_markdown_to_blocks(markdown: str, access_token: str) -> dict:
    """调用飞书 blocks/convert API 将 Markdown 转换为嵌套 block 结构。
    返回包含 blocks 和 first_level_block_ids 的 dict。
    """
    url = f"{BASE_URL}/open-apis/docx/v1/documents/blocks/convert"
    body = {"content_type": "markdown", "content": markdown}
    resp = requests.post(url, headers=api_headers(access_token), json=body)
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Markdown 转换为 blocks 失败: {data}")
    return data["data"]


def clean_table_blocks(blocks: list) -> list:
    """移除 table block 中只读的 merge_info 字段，避免插入时报错。"""
    for block in blocks:
        if block.get("block_type") == BT_TABLE and "table" in block:
            prop = block["table"].get("property", {})
            prop.pop("merge_info", None)
    return blocks


def create_descendants(document_id: str, parent_block_id: str,
                       children_ids: list, descendants: list,
                       access_token: str, index: int = None):
    """调用 descendant API 一次性插入嵌套块（表格及其单元格内容）。

    注意: index 参数必须放在请求体中，不能作为 URL query 参数，
    否则会被 API 静默忽略。
    """
    url = (f"{BASE_URL}/open-apis/docx/v1/documents/{document_id}"
           f"/blocks/{parent_block_id}/descendant")
    body = {
        "children_id": children_ids,
        "descendants": descendants,
    }
    if index is not None:
        body["index"] = index
    resp = requests.post(url, headers=api_headers(access_token), json=body)
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"创建嵌套块失败: {data}")
    return data.get("data", {})


def create_blocks_in_doc(document_id, page_block_id, blocks, access_token,
                         revision=None):
    """在文档中批量创建 blocks。
    普通块使用 create_children API 批量插入；
    表格使用 blocks/convert + descendant API 一次性创建完整嵌套结构（含单元格内容），
    避免逐行插入、逐格填充的 O(rows×cols) API 调用开销。
    """
    if not blocks:
        return

    i = 0
    total = len(blocks)
    while i < total:
        block = blocks[i]

        if block.get("type") == "table":
            rows = block.pop("_rows", [])
            block.pop("type", None)

            table_md = rows_to_markdown_table(rows)
            if table_md:
                convert_data = convert_markdown_to_blocks(table_md, access_token)
                descendants = clean_table_blocks(convert_data.get("blocks", []))
                first_level_ids = convert_data.get("first_level_block_ids", [])
                create_descendants(
                    document_id, page_block_id,
                    first_level_ids, descendants, access_token,
                )
                revision = None

            print(f"  已创建 {i + 1}/{total} 个 blocks (表格)")
            i += 1
        else:
            batch = []
            while i < total and blocks[i].get("type") != "table":
                b = blocks[i]
                b.pop("type", None)
                batch.append(b)
                i += 1

            for j in range(0, len(batch), 50):
                sub = batch[j:j + 50]
                _, revision = create_children(
                    document_id, page_block_id, sub, access_token, revision
                )

            print(f"  已创建 {i}/{total} 个 blocks")


# ═══════════════════════════════════════════
#  Main commands
# ═══════════════════════════════════════════

def cmd_pull(config):
    """从飞书文档拉取到本地 Markdown"""
    print("正在获取 access token...")
    token = get_tenant_access_token(config["app_id"], config["app_secret"])

    print("正在解析文档地址...")
    doc_id = resolve_document_id(config["wiki_url"], token)
    print(f"  document_id: {doc_id}")

    print("正在获取文档块...")
    blocks = get_document_blocks(doc_id, token)
    print(f"  共 {len(blocks)} 个 blocks")

    print("正在转换为 Markdown...")
    md = blocks_to_markdown(blocks)

    md_path = resolve_md_path(config)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(md)
    print(f"已保存到 {md_path}")


def cmd_push(config):
    """从本地 Markdown 推送到飞书文档"""
    md_path = resolve_md_path(config)
    with md_path.open("r", encoding="utf-8") as f:
        md_text = f.read()

    print("正在获取 access token...")
    token = get_tenant_access_token(config["app_id"], config["app_secret"])

    print("正在解析文档地址...")
    doc_id = resolve_document_id(config["wiki_url"], token)

    print("正在解析 Markdown...")
    descriptors = parse_markdown_to_descriptors(md_text)
    blocks = descriptors_to_blocks(descriptors)
    print(f"  解析出 {len(blocks)} 个 blocks")

    print("正在清空文档内容...")
    page_block_id, revision = delete_document_body(doc_id, token)

    print("正在写入新内容...")
    create_blocks_in_doc(doc_id, page_block_id, blocks, token, revision)

    print("推送完成!")


def cmd_debug_pull(config):
    """拉取并打印原始 blocks JSON（调试用）"""
    token = get_tenant_access_token(config["app_id"], config["app_secret"])
    doc_id = resolve_document_id(config["wiki_url"], token)
    blocks = get_document_blocks(doc_id, token)
    print(json.dumps(blocks, ensure_ascii=False, indent=2))


def main():
    usage = """\
用法: python feishu_sync.py <command>

命令:
  pull        从飞书文档拉取到本地 feishu_schedule.md
  push        从本地 feishu_schedule.md 推送到飞书文档
  debug       拉取并打印原始 blocks JSON（调试用）
  path        打印本地 feishu_schedule.md 缓存路径
"""
    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    cmd = sys.argv[1]
    config = load_config(require_credentials=(cmd != "path"))

    if cmd == "pull":
        cmd_pull(config)
    elif cmd == "push":
        cmd_push(config)
    elif cmd == "debug":
        cmd_debug_pull(config)
    elif cmd == "path":
        print(resolve_md_path(config))
    else:
        print(f"未知命令: {cmd}\n")
        print(usage)
        sys.exit(1)


if __name__ == "__main__":
    main()
