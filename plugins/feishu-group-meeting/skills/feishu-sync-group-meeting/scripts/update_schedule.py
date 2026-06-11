#!/usr/bin/env python3
"""
组会轮转脚本 — 支持双列独立轮转。

读取 feishu_schedule.md，执行一次完整轮转：
  1. 解除上一轮特殊状态（🚫跳过0次 → 重置，😀已讲 → 恢复）
  2. 🚫跳过N次 倒计时（N → N-1，到 0 时该同学本周报告，原讲者悬置）
  3. 若无人归零，正常轮转 😀本周同学
  4. 组会日期 +7 天

表格结构：
  |姓名|Work Report|News|姓名|Showcase Session|
  左侧成员列控制 Work Report 和 News 轮转
  右侧成员列控制 Showcase Session 轮转

Usage:
        python3 update_schedule.py
            # 执行轮转并写入（默认左成员列=0，右成员列=3）

        python3 update_schedule.py --dry-run
            # 仅预览结果，不写入

        python3 update_schedule.py --left-member-col 0 --right-member-col 3
            # 指定从顺序表第 N 列提取左右成员名单（0-based）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_DIR = Path(
    os.environ.get("FEISHU_GROUP_MEETING_HOME", "~/.config/feishu-sync-group-meeting")
).expanduser()
CACHE_DIR = Path(
    os.environ.get("FEISHU_GROUP_MEETING_CACHE", "~/.cache/feishu-sync-group-meeting")
).expanduser()

MARKER_CURRENT = "😀本周同学"
MARKER_DEFERRED = "😀已讲"
MARKER_SKIP_ZERO = "🚫跳过0次(😀本周同学)"
DEFAULT_SKIP_RESET = 11

COL_WR = "Work Report"
COL_NEWS = "News"
COL_SHOWCASE = "Showcase Session"

LEFT_COLUMNS = [COL_WR, COL_NEWS]
RIGHT_COLUMNS = [COL_SHOWCASE]

DEFAULT_LEFT_MEMBER_COL = 0
DEFAULT_RIGHT_MEMBER_COL = 3

WEEKDAY_NAMES: dict[int, str] = {
    0: "周一", 1: "周二", 2: "周三", 3: "周四",
    4: "周五", 5: "周六", 6: "周日",
}


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


def load_config() -> dict:
    config_path = find_config_file()
    config = {}
    if config_path:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
        config["_config_path"] = str(config_path)
    else:
        config["_config_path"] = None

    env_md_file = os.environ.get("FEISHU_GROUP_MEETING_MD_FILE")
    if env_md_file:
        config["md_file"] = env_md_file
    return config


def resolve_schedule_file(raw_path: str | None = None) -> Path:
    config = load_config()
    path_value = raw_path or config.get("md_file") or str(CACHE_DIR / "feishu_schedule.md")
    config_path = config.get("_config_path")
    base_dir = Path(config_path).parent if config_path else CONFIG_DIR
    path = _expand_path(path_value, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

# ---------------------------------------------------------------------------
# Cell state parsing
# ---------------------------------------------------------------------------

_SKIP_N_RE = re.compile(r"🚫跳过(\d+)次")


def parse_cell(value: str) -> tuple[str, int | None]:
    """
    解析单元格值，返回 (类型, 跳过次数)。

    类型:
      'empty'          — 空白
      'current'        — 😀本周同学
      'deferred'       — 😀已讲
      'skip_zero'      — 🚫跳过0次(😀本周同学)
      'skip_n'         — 🚫跳过N次 (N ≥ 1)
      'skip_permanent' — 🚫跳过（无数字，永久跳过）
    """
    v = value.strip()
    if not v:
        return ("empty", None)
    if v == MARKER_CURRENT:
        return ("current", None)
    if v.startswith("😀已讲"):
        return ("deferred", None)
    if v.startswith("🚫跳过0次"):
        return ("skip_zero", 0)
    m = _SKIP_N_RE.match(v)
    if m:
        return ("skip_n", int(m.group(1)))
    if v.startswith("🚫跳过"):
        return ("skip_permanent", None)
    return ("empty", None)


def make_skip_cell(n: int) -> str:
    """生成 🚫跳过N次 格式的单元格文本。"""
    if n == 0:
        return MARKER_SKIP_ZERO
    return f"🚫跳过{n}次"


def parse_markdown_row(line: str) -> list[str]:
    """将 Markdown 行解析为去首尾空管道后的单元格数组。"""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []

    cells = stripped.split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [cell.strip() for cell in cells]


def extract_members_from_table(
    lines: list[str], table_start: int, member_col_idx: int, group_name: str
) -> list[str]:
    """从顺序表的指定列读取成员顺序（按出现顺序）。"""
    if member_col_idx < 0:
        raise ValueError(f"{group_name} 列索引必须 >= 0，当前为 {member_col_idx}")

    members: list[str] = []
    seen: set[str] = set()

    for i in range(table_start + 2, len(lines)):
        stripped = lines[i].strip()
        if not stripped or not stripped.startswith("|"):
            break

        cells = parse_markdown_row(lines[i])
        if member_col_idx >= len(cells):
            continue

        name = cells[member_col_idx].strip()
        if not name:
            continue

        if name in seen:
            raise ValueError(f"{group_name} 成员列存在重复姓名: {name}")
        seen.add(name)
        members.append(name)

    if not members:
        raise ValueError(
            f"未在 {group_name} 成员列（第{member_col_idx}列）读取到任何姓名"
        )
    return members


def load_member_lists(
    lines: list[str],
    table_start: int,
    left_member_col: int,
    right_member_col: int,
) -> tuple[list[str], list[str]]:
    """从顺序表列中加载左右成员顺序。"""
    left_members = extract_members_from_table(
        lines, table_start, left_member_col, "左侧"
    )
    right_members = extract_members_from_table(
        lines, table_start, right_member_col, "右侧"
    )
    return left_members, right_members


# ---------------------------------------------------------------------------
# Table I/O
# ---------------------------------------------------------------------------

def load_schedule(path: Path, left_member_col: int, right_member_col: int):
    """
    解析新表格格式:
      |姓名|Work Report|News|姓名|Showcase Session|

    返回: lines, left_table, right_table, table_start, table_end,
          left_members, right_members
      - left_table:  {left_member_idx: [WR_val, News_val]}
      - right_table: {right_member_idx: [Showcase_val]}
    """
    lines = path.read_text(encoding="utf-8").split("\n")

    table_start: int | None = None
    for i, line in enumerate(lines):
        if "|姓名|" in line:
            table_start = i
            break
    if table_start is None:
        raise ValueError("找不到顺序表（缺少 |姓名| 表头行）")

    left_members, right_members = load_member_lists(
        lines, table_start, left_member_col, right_member_col
    )
    left_index = {name: idx for idx, name in enumerate(left_members)}
    right_index = {name: idx for idx, name in enumerate(right_members)}
    num_left = len(left_members)
    num_right = len(right_members)

    left_table: dict[int, list[str]] = {}
    right_table: dict[int, list[str]] = {}
    table_end = table_start + 2

    for i in range(table_start + 2, len(lines)):
        stripped = lines[i].strip()
        if not stripped or not stripped.startswith("|"):
            table_end = i
            break
        table_end = i + 1

        cells = parse_markdown_row(lines[i])

        if len(cells) < 5:
            continue

        left_name = cells[0].strip()
        wr_val = cells[1].strip()
        news_val = cells[2].strip()
        right_name = cells[3].strip()
        showcase_val = cells[4].strip()

        if left_name in left_index:
            idx = left_index[left_name]
            left_table[idx] = [wr_val, news_val]

        if right_name in right_index:
            idx = right_index[right_name]
            right_table[idx] = [showcase_val]

    # 确保所有成员都有条目
    for i in range(num_left):
        if i not in left_table:
            left_table[i] = ["", ""]
    for i in range(num_right):
        if i not in right_table:
            right_table[i] = [""]

    return (
        lines,
        left_table,
        right_table,
        table_start,
        table_end,
        left_members,
        right_members,
    )


def rebuild_table_lines(
    left_table: dict[int, list[str]],
    right_table: dict[int, list[str]],
    left_members: list[str],
    right_members: list[str],
) -> list[str]:
    """根据 left_table / right_table 重建 Markdown 表格行。"""
    out = [
        "|姓名|Work Report|News|姓名|Showcase Session|",
        "|---|---|---|---|---|",
    ]
    num_left = len(left_members)
    num_right = len(right_members)
    num_rows = max(num_left, num_right)
    for i in range(num_rows):
        left_name = left_members[i] if i < num_left else ""
        left_vals = left_table.get(i, ["", ""])
        wr = left_vals[0]
        news = left_vals[1] if len(left_vals) > 1 else ""

        right_name = right_members[i] if i < num_right else ""
        right_vals = right_table.get(i, [""])
        showcase = right_vals[0]

        out.append(f"|{left_name}|{wr}|{news}|{right_name}|{showcase}|")
    return out


# ---------------------------------------------------------------------------
# Rotation helpers
# ---------------------------------------------------------------------------

def find_indices_by_type(
    table: dict[int, list[str]], num_members: int, col_idx: int, cell_type: str
) -> list[int]:
    """返回某列中指定类型的成员索引（已排序）。"""
    result = []
    for idx in range(num_members):
        vals = table.get(idx, [])
        if col_idx < len(vals):
            ct, _ = parse_cell(vals[col_idx])
            if ct == cell_type:
                result.append(idx)
    return sorted(result)


def reset_skip_value() -> int:
    return DEFAULT_SKIP_RESET


def find_next_valid(
    table: dict[int, list[str]], num_members: int, start: int, col_idx: int
) -> int:
    """从 start 向下寻找下一个空白身位（循环），跳过所有非空单元格。"""
    ptr = (start + 1) % num_members
    for _ in range(num_members):
        vals = table.get(ptr, [])
        cell = vals[col_idx] if col_idx < len(vals) else ""
        if cell.strip() == "":
            return ptr
        ptr = (ptr + 1) % num_members
    raise RuntimeError(f"列索引 {col_idx} 中无可用身位")


# ---------------------------------------------------------------------------
# Rotation core
# ---------------------------------------------------------------------------

def rotate_column(
    table: dict[int, list[str]],
    num_members: int,
    col_idx: int,
    col_name: str,
    members_list: list[str],
) -> None:
    """
    对单列执行一次轮转（就地修改 table）。

    三阶段：
      Phase A — 解除上一轮特殊状态
      Phase B — 🚫跳过N次 倒计时
      Phase C — 正常轮转 或 悬置
    """
    # ── Phase A ──
    phase_a_touched: set[int] = set()

    for idx in find_indices_by_type(table, num_members, col_idx, "skip_zero"):
        table[idx][col_idx] = make_skip_cell(reset_skip_value())
        phase_a_touched.add(idx)

    for idx in find_indices_by_type(table, num_members, col_idx, "deferred"):
        table[idx][col_idx] = MARKER_CURRENT
        phase_a_touched.add(idx)

    # ── Phase B ──
    reached_zero: list[int] = []

    for idx in range(num_members):
        if idx in phase_a_touched:
            continue
        vals = table.get(idx, [])
        if col_idx >= len(vals):
            continue
        ct, n = parse_cell(vals[col_idx])
        if ct != "skip_n" or n is None:
            continue
        if n > 1:
            table[idx][col_idx] = make_skip_cell(n - 1)
        elif n == 1:
            table[idx][col_idx] = MARKER_SKIP_ZERO
            reached_zero.append(idx)

    # ── Phase C ──
    if reached_zero:
        current_indices = find_indices_by_type(table, num_members, col_idx, "current")
        if current_indices:
            table[current_indices[0]][col_idx] = MARKER_DEFERRED
        print(
            f"   {col_name}: "
            f"{', '.join(members_list[i] for i in reached_zero)} 跳过归零，本周报告；"
            f"{members_list[current_indices[0]] if current_indices else '?'} 悬置至下周"
        )
    else:
        _normal_rotate(table, num_members, col_idx, col_name, members_list)


def _normal_rotate(
    table: dict[int, list[str]],
    num_members: int,
    col_idx: int,
    col_name: str,
    members_list: list[str],
) -> None:
    """正常轮转。"""
    current_indices = find_indices_by_type(table, num_members, col_idx, "current")
    if not current_indices:
        print(f"⚠️  {col_name} 列未找到 {MARKER_CURRENT}，跳过轮转")
        return

    if col_name == COL_WR:
        # Work Report: 1 人，向下 1 步
        start = current_indices[0]
        table[start][col_idx] = ""
        new_pos = find_next_valid(table, num_members, start, col_idx)
        table[new_pos][col_idx] = MARKER_CURRENT
    elif col_name == COL_NEWS:
        # News: 2 人，每人向下跳 2 步
        for pos in current_indices:
            table[pos][col_idx] = ""
        new_positions: list[int] = []
        for start in current_indices:
            ptr = start
            for _ in range(2):
                ptr = find_next_valid(table, num_members, ptr, col_idx)
            new_positions.append(ptr)
        for p in new_positions:
            table[p][col_idx] = MARKER_CURRENT
    elif col_name == COL_SHOWCASE:
        # Showcase Session: N 人，每人向下 1 步找到空位
        for pos in current_indices:
            table[pos][col_idx] = ""
        new_positions = []
        for start in current_indices:
            ptr = find_next_valid(table, num_members, start, col_idx)
            new_positions.append(ptr)
        for p in new_positions:
            table[p][col_idx] = MARKER_CURRENT


def rotate(
    left_table: dict[int, list[str]],
    right_table: dict[int, list[str]],
    left_members: list[str],
    right_members: list[str],
) -> None:
    """执行完整轮转：左侧列 + 右侧列各自独立处理。"""
    num_left = len(left_members)
    num_right = len(right_members)

    for col_idx, col_name in enumerate(LEFT_COLUMNS):
        rotate_column(left_table, num_left, col_idx, col_name, left_members)

    for col_idx, col_name in enumerate(RIGHT_COLUMNS):
        rotate_column(right_table, num_right, col_idx, col_name, right_members)


# ---------------------------------------------------------------------------
# Time advancement
# ---------------------------------------------------------------------------

def advance_time_line(line: str) -> str:
    """将 ⌛️暂定本周组会时间 中的日期 +7 天，并更新星期。"""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", line)
    if not m:
        return line
    old_date = datetime.strptime(m.group(1), "%Y-%m-%d")
    new_date = old_date + timedelta(days=7)
    new_weekday = WEEKDAY_NAMES[new_date.weekday()]

    line = line.replace(m.group(1), new_date.strftime("%Y-%m-%d"))
    line = re.sub(r"\[.*?\]", f"[{new_weekday} ]", line, count=1)
    return line


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

def print_rotation_summary(
    left_table: dict[int, list[str]],
    right_table: dict[int, list[str]],
    left_members: list[str],
    right_members: list[str],
) -> None:
    """打印轮转后各环节讲者摘要。"""
    print("✅ 轮转完成，下周安排：")
    num_left = len(left_members)
    num_right = len(right_members)

    for col_idx, col_name in enumerate(LEFT_COLUMNS):
        presenters: list[str] = []
        deferred: list[str] = []
        for idx in range(num_left):
            vals = left_table.get(idx, ["", ""])
            if col_idx < len(vals):
                ct, _ = parse_cell(vals[col_idx])
                name = left_members[idx]
                if ct == "current":
                    presenters.append(name)
                elif ct == "skip_zero":
                    presenters.append(f"{name}(跳过归零)")
                elif ct == "deferred":
                    deferred.append(name)
        line = f"   {col_name}: {', '.join(presenters)}"
        if deferred:
            line += f"  [悬置: {', '.join(deferred)}]"
        print(line)

    for col_idx, col_name in enumerate(RIGHT_COLUMNS):
        presenters = []
        deferred = []
        for idx in range(num_right):
            vals = right_table.get(idx, [""])
            if col_idx < len(vals):
                ct, _ = parse_cell(vals[col_idx])
                name = right_members[idx]
                if ct == "current":
                    presenters.append(name)
                elif ct == "skip_zero":
                    presenters.append(f"{name}(跳过归零)")
                elif ct == "deferred":
                    deferred.append(name)
        line = f"   {col_name}: {', '.join(presenters)}"
        if deferred:
            line += f"  [悬置: {', '.join(deferred)}]"
        print(line)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="组会轮转脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅预览结果，不写入")
    parser.add_argument(
        "--schedule-file",
        help="要轮转的 feishu_schedule.md 路径；默认与 feishu_sync.py 使用同一缓存路径",
    )
    parser.add_argument(
        "--left-member-col",
        type=int,
        default=DEFAULT_LEFT_MEMBER_COL,
        help="左侧成员名单所在列索引（从 0 开始）",
    )
    parser.add_argument(
        "--right-member-col",
        type=int,
        default=DEFAULT_RIGHT_MEMBER_COL,
        help="右侧成员名单所在列索引（从 0 开始）",
    )

    args = parser.parse_args(argv)
    if args.left_member_col < 0 or args.right_member_col < 0:
        parser.error("成员列索引必须 >= 0")
    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args(sys.argv[1:])
    dry_run = args.dry_run
    schedule_file = resolve_schedule_file(args.schedule_file)

    (
        lines,
        left_table,
        right_table,
        table_start,
        table_end,
        left_members,
        right_members,
    ) = load_schedule(
        schedule_file,
        args.left_member_col,
        args.right_member_col,
    )

    print("🔄 执行轮转…")
    rotate(left_table, right_table, left_members, right_members)

    for i, line in enumerate(lines):
        if "⌛️暂定本周组会时间" in line:
            lines[i] = advance_time_line(line)
            break

    new_table = rebuild_table_lines(
        left_table,
        right_table,
        left_members,
        right_members,
    )
    lines = lines[:table_start] + new_table + lines[table_end:]

    content = "\n".join(lines)

    if dry_run:
        print(content)
        print("\n--- DRY RUN: 未写入文件 ---")
    else:
        schedule_file.write_text(content, encoding="utf-8")
        print(f"文件已更新: {schedule_file}")

    print()
    print_rotation_summary(left_table, right_table, left_members, right_members)


if __name__ == "__main__":
    main()
