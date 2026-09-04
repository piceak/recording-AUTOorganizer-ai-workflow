"""check_state.py — 讲稿状态检测与路由（零 AI，纯本地脚本）。

用「已标记」文本游标 + state.json(1/2) 判定每门课要做什么：

  原稿末尾不含「已标记」(有未标记新内容) → action=mark   → note-annotate
  原稿已标记 + state=1                    → action=digest → note-digest
  原稿已标记 + state=2                    → action=done   → 不动

「已标记」标记行 = 单独一行的 `<!-- 已标记 -->`（或裸 `已标记`）。
切分点取文件里最后一个「已标记」行，其后的内容 = 未标记段（verbatim，
只把这一段喂给标注模型，省 token）。

用法：
  python check_state.py                              扫描全部课程，输出各 action
  python check_state.py --file <讲稿>               单文件，输出 action + 未标记段
  python check_state.py --file <讲稿> --set-state 1|2  设置状态（标注完=1，笔记完=2）
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYS = Path(__file__).resolve().parent
STATE_PATH = SYS / "state.json"
COURSES_PATH = SYS / "courses.json"
CONFLICT_RE = re.compile(r"conflict|冲突|副本", re.I)

# 单独一行的「已标记」标记：<!-- 已标记 --> 或裸 已标记（含前后空白）
MARK_LINE_RE = re.compile(r"^\s*(?:<!--\s*)?已标记(?:\s*-->)?\s*$")


def read_state():
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def write_state(data):
    STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def course_of(path):
    """课程名 = 父目录名（讲稿文件形如 <课程>/<课程>.md）。"""
    return path.parent.name


def note_file(path):
    return path.with_name(path.stem + "笔记.md")


def split_unmarked(text):
    """在最后一个「已标记」行处切分。返回 (marked, unmarked)。

    marked   = 标记行及其之前的全部内容（已处理部分）。
    unmarked = 标记行之后的原文，逐字 verbatim（供 Edit 精确匹配 + 喂给标注模型）。
    无标记行时：marked="" , unmarked=全文。
    """
    lines = text.splitlines(keepends=True)
    last_mark_idx = None
    for i, line in enumerate(lines):
        if MARK_LINE_RE.match(line):
            last_mark_idx = i
    if last_mark_idx is None:
        return "", text
    marked = "".join(lines[:last_mark_idx + 1])
    unmarked = "".join(lines[last_mark_idx + 1:])
    return marked, unmarked


def context_heading(marked):
    """marked 部分里最后一个 `#`/`##` 标题行，供标注模型判断章节上下文。

    跳过「## 存疑待查」区块——它位于已标记游标之前、且不属于正文章节标题，
    不该被当作上下文返回。无则 None。
    """
    lines = marked.splitlines()
    # 截掉最后一个「存疑待查」标题及其后的内容（那是勘误汇总，不是正文）
    cut = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if re.match(r"^#{1,3}\s*存疑待查", lines[i]):
            cut = i
            break
    for line in reversed(lines[:cut]):
        if re.match(r"^#{1,2}\s+\S", line):
            return line
    return None


def check_file(path, state=None):
    """单文件检测，返回 {file, course, action, ...}。"""
    if state is None:
        state = read_state()
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {"file": str(path), "course": course_of(path), "action": "empty"}

    course = course_of(path)
    marked, unmarked = split_unmarked(text)
    item = {"file": str(path), "course": course}

    # 未标记段有实质内容 → 需标注
    if unmarked.strip():
        item["action"] = "mark"
        item["unmarked_text"] = unmarked
        item["context_heading"] = context_heading(marked)
        return item

    # 已标记且无新内容 → 查 state
    st = state.get(course)
    if st == 1:
        item["action"] = "digest"
    elif st == 2:
        item["action"] = "done"
    else:
        # 已标记但 state 无记录：默认需做笔记（刚标完没记上）
        item["action"] = "digest"
    item["state"] = st
    return item


def set_state(path, value):
    state = read_state()
    course = course_of(path)
    state[course] = value
    write_state(state)
    return {"course": course, "state": value,
            "time": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}


def scan_all(courses_path):
    courses = json.loads(courses_path.read_text(encoding="utf-8"))["courses"]
    state = read_state()
    report = {"mark": [], "digest": [], "done": [], "empty": [],
              "conflicts": [], "errors": []}
    for course in courses:
        folder = ROOT / course
        if not folder.is_dir():
            report["errors"].append({"course": course, "error": "文件夹不存在"})
            continue
        md = folder / f"{course}.md"
        if not md.exists():
            continue
        if CONFLICT_RE.search(md.name):
            report["conflicts"].append({"course": course, "file": str(md)})
            continue
        try:
            item = check_file(md, state)
        except Exception as e:
            report["errors"].append({"course": course, "file": str(md),
                                    "error": str(e)})
            continue
        report[item["action"]].append(item)
    report["pending"] = bool(report["mark"] or report["digest"])
    return report


def notify_toast(items):
    """有需处理的讲稿时弹 Windows 通知；失败静默。"""
    try:
        n = len(items)
        msg = f"检测到 {n} 门课待处理（标注/解读），打开 ZCode 说一声「处理」即可"
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(SYS / "notify.ps1"), "-Message", msg],
            timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="讲稿状态检测与路由")
    ap.add_argument("--file", help="只检单个 .md 讲稿文件")
    ap.add_argument("--set-state", type=int, choices=[1, 2],
                     help="设置状态：1=已标注未笔记，2=已标注已笔记（需配合 --file）")
    ap.add_argument("--courses", default=str(COURSES_PATH),
                    help="课程白名单 JSON 路径")
    args = ap.parse_args()

    if args.set_state is not None:
        if not args.file:
            ap.error("--set-state 需要配合 --file")
        print(json.dumps(set_state(Path(args.file), args.set_state),
                         ensure_ascii=False))
        return

    if args.file:
        print(json.dumps(check_file(Path(args.file)),
                         ensure_ascii=False, indent=2))
        return

    report = scan_all(Path(args.courses))
    (SYS / "last_scan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    pending = report["mark"] + report["digest"]
    if pending:
        notify_toast(pending)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
