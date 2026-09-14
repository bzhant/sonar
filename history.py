"""分析历史归档模块 - 每次分析完成后自动保存报告和数据到 ~/.sonar/history/"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime

from config_manager import CONFIG_DIR

HISTORY_DIR = os.path.join(CONFIG_DIR, "history")


def _sanitize(name, maxlen=30):
    """把关键词/模式名清理成适合做文件名的字符串"""
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("_")
    return name[:maxlen] or "untitled"


def save_analysis(mode, keyword, report, usage=None, bili_data=None, tieba_data=None):
    """
    归档一次分析：Markdown 报告（含元信息头）+ 可选的原始数据 JSON。
    :return: 报告文件路径
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    ts = datetime.now()
    base = f"{ts:%Y%m%d_%H%M%S}_{_sanitize(str(mode))}_{_sanitize(str(keyword))}"

    header = [
        f"# {keyword}",
        "",
        f"- 时间: {ts:%Y-%m-%d %H:%M:%S}",
        f"- 模式: {mode}",
    ]
    if usage and usage.get("total_tokens"):
        header.append(f"- LLM 用量: {usage['total_tokens']} tokens"
                      f"（请求 {usage['requests']} 次，输入 {usage['prompt_tokens']} / 输出 {usage['completion_tokens']}）")
    if bili_data:
        header.append(f"- B站: {bili_data.get('total_videos', 0)} 视频, {bili_data.get('total_comments', 0)} 评论")
    if tieba_data:
        header.append(f"- 贴吧: {tieba_data.get('total_posts', 0)} 帖子, {tieba_data.get('total_replies', 0)} 回复")

    md_path = os.path.join(HISTORY_DIR, base + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n\n---\n\n" + (report or ""))

    if bili_data or tieba_data:
        data_path = os.path.join(HISTORY_DIR, base + ".json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump({
                "mode": str(mode),
                "keyword": str(keyword),
                "time": ts.isoformat(),
                "usage": usage,
                "bilibili_data": bili_data,
                "tieba_data": tieba_data,
            }, f, ensure_ascii=False, indent=2)

    return md_path


def open_history_folder():
    """在系统文件管理器中打开历史归档目录"""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(HISTORY_DIR)
    elif sys.platform == "darwin":
        subprocess.call(["open", HISTORY_DIR])
    else:
        subprocess.call(["xdg-open", HISTORY_DIR])
