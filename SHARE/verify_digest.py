"""verify_digest.py — 存疑待查「强约束」校验（零 AI，纯本地脚本）。

用途：标注/解读完成后跑一遍。若「存疑待查」未标完（原稿里列了 [?] 条目却没在
原文相应位置打 [?]{正确词}），则校验不通过，任务必须重做。

背景：存疑待查随「已标记」游标多次出现，且总是放在该游标**之前**。因此要扫描
全文所有 `## 存疑待查` 区块，把它们当作勘误汇总；原文 = 剔除这些区块与注释行后
的剩余内容。

规则（硬约束）：
  1. 所有「存疑待查」区块里 `[?]` 的个数 ≤ 原文里 `[?]{...}` 的个数。
     即每个列出的存疑条目，都必须在正文对应位置打了 `[?]{正确词}`。
     若某个存疑条目录进来却漏打在原文 → 个数 > 原文 → fail。
  2. 讲稿文件须存在「已标记」游标（否则说明标注未进行，无存疑可校验）。

用法：
  python verify_digest.py "<讲稿文件>"
  通过输出 {"done": true} 且退出码 0；否则列出未过项，输出 {"done": false,...}，
  退出码 1。
"""

import json
import re
import sys
from pathlib import Path

PENDING_HEAD_RE = re.compile(r"^#{2,3}\s*存疑待查")
MARK_LINE_RE = re.compile(r"^\s*(?:<!--\s*)?已标记(?:\s*-->)?\s*$", re.M)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
# 原文里的打标：`[?]` 紧跟 `{正确词}`（允许中间有空白）
TRANSCRIPT_MARK_RE = re.compile(r"\[\?\]\s*\{")


def split_pending(text):
    """把文本切成「原文」与「存疑待查区块列表（原始字符串）」。

    存疑待查区块 = 从 `## 存疑待查` 标题起，到下一个「已标记」游标 / 下一个
    `#`/`##` 标题 / 文末止。多个区块分别返回（随游标多次出现）。
    原文 = 剔除这些区块与注释行后的剩余内容。
    """
    lines = text.splitlines()
    rest = []
    pending_blocks = []
    in_pending = False
    cur = []

    def flush():
        nonlocal in_pending, cur
        if in_pending and cur:
            pending_blocks.append("\n".join(cur))
        in_pending = False
        cur = []

    for line in lines:
        if PENDING_HEAD_RE.match(line):
            flush()
            in_pending = True
            cur = [line]
            continue
        if in_pending:
            # 区块边界：遇到「已标记」游标或新的一级/二级标题，结束当前区块
            if MARK_LINE_RE.match(line) or re.match(r"^#{1,2}\s", line):
                flush()
                rest.append(line)
                continue
            cur.append(line)
            continue
        rest.append(line)
    flush()
    return "\n".join(rest), pending_blocks


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"done": False,
                          "fails": ["用法: python verify_digest.py <讲稿文件>"]},
                         ensure_ascii=False))
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(json.dumps({"done": False, "fails": [f"讲稿文件不存在: {path}"]},
                         ensure_ascii=False))
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    rest, pending_blocks = split_pending(text)
    fails = []

    # 2. 讲稿须有「已标记」游标
    has_mark = bool(MARK_LINE_RE.search(text))
    if not has_mark:
        fails.append("讲稿文件无「已标记」游标（说明标注未进行/未完成）")

    # 1. 存疑待查条目数 ≤ 原文打标数
    #    存疑条目 = 存疑区块里每条 `- ` 开头的条目，兼容两种格式：
    #      - 新格式：含 `[?]`（如 `面向对象基础[?]`：…）
    #      - 旧格式：`- \`原文\` → \`正确\``（如 `- \`李祖镇\` → \`李笃正\``）
    #      纯说明行也算一条（如 `- 课程信息口播矛盾：…`）
    n_pending = 0
    for b in pending_blocks:
        for line in b.splitlines():
            if line.strip().startswith("-"):
                n_pending += 1
    transcript = COMMENT_RE.sub("", rest)  # 原文去掉注释行
    n_transcript = len(TRANSCRIPT_MARK_RE.findall(transcript))
    if n_pending > n_transcript:
        fails.append(
            f"存疑待查有 {n_pending} 条，但原文只打了 {n_transcript} 处 [?]{{...}}"
            "（有的存疑条目漏打在原文，需补上后才能通过）")

    print(json.dumps({"done": not fails, "fails": fails,
                      "n_pending": n_pending, "n_transcript": n_transcript},
                     ensure_ascii=False))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
