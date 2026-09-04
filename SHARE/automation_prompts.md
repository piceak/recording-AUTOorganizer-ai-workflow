# 定时自动化 prompt 模板

> 本文件只放**可粘贴到 cron 的 prompt 文本**，供你在 ZCode 里"新建定时自动化"时复制。
> 你自己手动设置两个自动化（本文件不创建、不调度任何 cron）：
>   1. **标注任务**（在前）：处理 `mark` 状态的讲稿。
>   2. **笔记任务**（在其后 20 分钟）：处理 `digest` 状态的讲稿。
>
> 「存疑待查」强约束：`python _system/verify_digest.py "<讲稿>"`，必须 `{"done": true}` 才通过，否则任务重做（补标原文 `[?]{...}`）。
>

---

## 自动化一 · 标注任务（放在前面）

```text
执行本工作区讲稿的标注流程（note-annotate 版，增量模式）。规则见 .agents/skills/note-annotate/SKILL.md，不要中途停下等确认。

步骤：
1. 运行 `python _system/check_state.py` 全量扫描（工作区根目录下，Windows 用 python）。
2. 找到所有 action=mark 的讲稿文件（同目录同名 `.md`，如 `示例课程/示例课程.md`）。若没有 mark，直接结束，什么都不输出、什么都不改。
3. 对每个 mark 的讲稿：
   a. 重新跑 `python _system/check_state.py --file "<讲稿>"`，取 JSON 里的 `unmarked_text`（未标记段，逐字）、`context_heading`、`course`。
   b. 只对 `unmarked_text` 这段标注：重要内容提为 `## 要点标题`；考试相关大区段提为 `# 大标题`；无关口水内容用 `<span style="color:gray">…</span>` 标灰；听写错误/截断处打 `[?]{正确词}`。
   c. 把 `unmarked_text` 用 Edit 替换成"标注后文本 + 空行 + ## 存疑待查 区块（本轮 [?] 条目）+ 空行 + <!-- 已标记 -->"。只加标注，不改原文实质词句。
   d. 跑 `python _system/verify_digest.py "<讲稿>"`，必须 `{"done": true}`；若 false，按 fails 补标后重跑。
   e. 跑 `python _system/check_state.py --file "<讲稿>" --set-state 1`。
   f. 不写笔记文件。
4. 处理完用两三句话极简汇报：标注了哪些文件、标黑多少处、有无 [?] 存疑项。不贴全文。

质量要求（同 note-annotate）：标黑宁精勿滥；大标题只用于明显考试/考点/重点区段；标灰只针对整段无价值（闲聊/签到/语气词）；重点段落里的口语词不逐个标灰；原文一字不改（只加标注与 [?] 纠错）。
```

---

## 自动化二 · 笔记任务（放在标注任务后面 20 分钟）

```text
执行本工作区讲稿的解读做笔记流程（note-digest 版，增量模式）。规则见 .agents/skills/note-digest/SKILL.md，不要中途停下等确认。

步骤：
1. 运行 `python _system/check_state.py` 全量扫描（工作区根目录下，Windows 用 python）。
2. 找到所有 action=digest 的讲稿文件。若没有 digest，直接结束，什么都不输出、什么都不改。
3. 对每个 digest 的讲稿：
   a. 读讲稿文件全文，优先依据 `##` 标黑与 `#` 大标题抓重点；标灰部分不作为重点；汇总所有 `## 存疑待查` 区块的 `[?]` 条目。
   b. 读笔记文件（`<课程>笔记.md`），对照既有笔记区块避免重复。
   c. 把解读结果一次写入笔记文件末尾，标题 `## 📒 解读笔记（YYYY-MM-DD HH:MM）`，六节模板：一句话概括 / 核心概念表 / 要点整理 / 易混·易错 / 自测 / 存疑待查。不改原稿。
   d. 跑 `python _system/verify_digest.py "<讲稿>"`，必须 `{"done": true}`；若 false，说明存疑条目漏打在原文，先回 note-annotate 补标，不要设 state=2。
   e. 跑 `python _system/check_state.py --file "<讲稿>" --set-state 2`。
4. 处理完用两三句话极简汇报：解读了哪些课程、笔记写入哪个文件。不贴全文。

质量要求（同 note-digest）：术语给规范名+白话解释；宁缺毋滥；基于标黑重点，不编造原文没有的内容。
```
