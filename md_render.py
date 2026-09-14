"""轻量 Markdown → Tkinter Text 渲染器（适配暗色主题，无第三方依赖）

支持：标题、粗体、行内代码、代码块、引用、无序/有序列表、
表格（等宽字体对齐）、分隔线。其余语法按普通文本显示。
"""
import re

_INLINE_RE = re.compile(r"(\*\*[^*\n]+\*\*|`[^`\n]+`)")
_TABLE_SEP_RE = re.compile(r"^:?-{2,}:?$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^(\s*)(\d+)[.、]\s+(.*)$")


def _display_width(s):
    """粗略计算显示宽度（CJK 等全角字符按 2 计），用于表格对齐"""
    w = 0
    for ch in s:
        w += 2 if ord(ch) > 0x2E7F else 1
    return w


def _pad(s, width):
    return s + " " * max(0, width - _display_width(s))


def _inline_segments(line):
    """把一行拆成 (文本, 是否加粗, 是否行内代码) 片段"""
    segments = []
    for part in _INLINE_RE.split(line):
        if not part:
            continue
        if len(part) > 4 and part.startswith("**") and part.endswith("**"):
            segments.append((part[2:-2], True, False))
        elif len(part) > 2 and part.startswith("`") and part.endswith("`"):
            segments.append((part[1:-1], False, True))
        else:
            segments.append((part, False, False))
    return segments


def render_markdown(text_widget, markdown_text, theme):
    """把 Markdown 文本渲染进 Text 控件。控件需已处于 normal 状态并清空。"""
    font, mono = theme["font"], theme["font_mono"]
    tags = {
        "md_h1": {"font": (font, 14, "bold"), "foreground": theme["text_bright"],
                  "spacing1": 12, "spacing3": 4},
        "md_h2": {"font": (font, 12, "bold"), "foreground": theme["accent"],
                  "spacing1": 12, "spacing3": 4},
        "md_h3": {"font": (font, 11, "bold"), "foreground": theme["text_bright"],
                  "spacing1": 8, "spacing3": 2},
        "md_bold": {"font": (font, 10, "bold"), "foreground": theme["text_bright"]},
        "md_code": {"font": (mono, 9), "background": theme["bg_input"],
                    "foreground": theme["accent"]},
        "md_codeblock": {"font": (mono, 9), "background": theme["bg_input"],
                         "foreground": theme["text"]},
        "md_quote": {"font": (font, 10, "italic"), "foreground": theme["text_dim"],
                     "lmargin1": 16, "lmargin2": 16},
        "md_bullet": {"foreground": theme["accent"], "font": (font, 10, "bold")},
        "md_table": {"font": (mono, 9), "foreground": theme["text"]},
        "md_hr": {"foreground": theme["border"]},
    }
    for name, cfg in tags.items():
        text_widget.tag_configure(name, **cfg)

    def insert_inline(line, extra_tags=()):
        for seg, bold, code in _inline_segments(line):
            t = list(extra_tags)
            if bold:
                t.append("md_bold")
            if code:
                t.append("md_code")
            text_widget.insert("end", seg, tuple(t))
        text_widget.insert("end", "\n")

    table_buf = []

    def flush_table():
        rows = []
        for ln in table_buf:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if cells and all(_TABLE_SEP_RE.match(c) for c in cells if c):
                continue  # |---|---| 分隔行
            rows.append(cells)
        table_buf.clear()
        if not rows:
            return
        ncols = max(len(r) for r in rows)
        widths = [0] * ncols
        for r in rows:
            for j, c in enumerate(r):
                widths[j] = max(widths[j], _display_width(c))
        for r in rows:
            parts = [_pad(c, widths[j]) for j, c in enumerate(r)]
            text_widget.insert("end", "  " + " | ".join(parts) + "\n", "md_table")

    in_code = False
    for line in markdown_text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_table()
            in_code = not in_code
            continue
        if in_code:
            text_widget.insert("end", line + "\n", "md_codeblock")
            continue
        if line.lstrip().startswith("|") and stripped.endswith("|"):
            table_buf.append(line)
            continue
        flush_table()

        if not stripped:
            text_widget.insert("end", "\n")
            continue
        m = _HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            tag = "md_h1" if level == 1 else "md_h2" if level == 2 else "md_h3"
            text_widget.insert("end", m.group(2), (tag,))
            text_widget.insert("end", "\n")
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            text_widget.insert("end", "─" * 80 + "\n", ("md_hr",))
            continue
        if line.lstrip().startswith(">"):
            insert_inline(line.lstrip()[1:].lstrip(), ("md_quote",))
            continue
        m = _BULLET_RE.match(line)
        if m:
            indent = " " * (len(m.group(1)) // 2 * 2 + 2)
            text_widget.insert("end", indent)
            text_widget.insert("end", "• ", ("md_bullet",))
            insert_inline(m.group(2))
            continue
        m = _NUMBERED_RE.match(line)
        if m:
            text_widget.insert("end", " " * (len(m.group(1)) + 2) + m.group(2) + ". ")
            insert_inline(m.group(3))
            continue
        insert_inline(line)
    flush_table()
