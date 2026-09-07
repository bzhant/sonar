"""声呐 Sonar - B站 & 贴吧 舆情分析工具 | LLM驱动采集 + 现代化暗色主题 GUI"""
import os
import sys
import json
import threading
import queue
from datetime import datetime

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from bilibili_collector import BilibiliCollector
from tieba_collector import TiebaCollector
from llm_analyzer import LLMAnalyzer, FunctionCallingNotSupported
import cookie_helper

# ========== 暗色主题配色 ==========
THEME = {
    "bg":           "#0f0f0f",
    "bg_card":     "#1a1a1a",
    "bg_input":    "#222222",
    "bg_hover":    "#2a2a2a",
    "bg_sidebar":  "#161616",
    "border":      "#2a2a2a",
    "text":        "#e0e0e0",
    "text_dim":    "#808080",
    "text_bright": "#ffffff",
    "accent":      "#00d4ff",
    "accent_dim":  "#0099bb",
    "accent_bg":   "#0a2a33",
    "bili_pink":   "#fb7299",
    "tieba_blue":  "#4e6ef2",
    "success":     "#00c853",
    "warning":     "#ffab00",
    "error":       "#ff5252",
    "font":        "Segoe UI",
    "font_mono":   "Cascadia Code",
}

SIDEBAR_W = 180
STATUSBAR_H = 26


def apply_theme(root):
    """配置 ttk 暗色主题样式"""
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=THEME["bg"], foreground=THEME["text"],
                    font=(THEME["font"], 10))
    style.configure("TFrame", background=THEME["bg"])
    style.configure("TLabel", background=THEME["bg"], foreground=THEME["text"])
    style.configure("TLabelDim.TLabel", background=THEME["bg"], foreground=THEME["text_dim"],
                    font=(THEME["font"], 9))
    style.configure("TLabelBold.TLabel", background=THEME["bg"], foreground=THEME["text_bright"],
                    font=(THEME["font"], 11, "bold"))

    # 侧边栏
    style.configure("Sidebar.TFrame", background=THEME["bg_sidebar"])

    # 按钮
    style.configure("Accent.TButton", background=THEME["accent"], foreground="#000000",
                    font=(THEME["font"], 10, "bold"), borderwidth=0, focusthickness=0,
                    padding=(16, 8))
    style.map("Accent.TButton",
              background=[("active", THEME["accent_dim"]), ("disabled", "#333333")],
              foreground=[("disabled", "#666666")])

    style.configure("Secondary.TButton", background=THEME["bg_card"], foreground=THEME["text"],
                    font=(THEME["font"], 10), borderwidth=1, focusthickness=0,
                    padding=(14, 7))
    style.map("Secondary.TButton",
              background=[("active", THEME["bg_hover"]), ("disabled", "#1a1a1a")],
              foreground=[("disabled", "#555555")])

    # 输入框
    style.configure("Dark.TEntry", fieldbackground=THEME["bg_input"], foreground=THEME["text"],
                    borderwidth=1, relief="solid", padding=(8, 6))
    style.map("Dark.TEntry",
              bordercolor=[("focus", THEME["accent"])],
              fieldbackground=[("disabled", "#1a1a1a")])

    # LabelFrame
    style.configure("Card.TLabelframe", background=THEME["bg_card"], bordercolor=THEME["border"],
                    relief="solid", borderwidth=1)
    style.configure("Card.TLabelframe.Label", background=THEME["bg_card"], foreground=THEME["accent"],
                    font=(THEME["font"], 10, "bold"), padding=(12, 6))

    # Notebook
    style.configure("Dark.TNotebook", background=THEME["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("Dark.TNotebook.Tab", background=THEME["bg_card"], foreground=THEME["text_dim"],
                    padding=(20, 10), font=(THEME["font"], 10), borderwidth=0)
    style.map("Dark.TNotebook.Tab",
              background=[("selected", THEME["bg"]), ("active", THEME["bg_hover"])],
              foreground=[("selected", THEME["accent"]), ("active", THEME["text"])])

    # Treeview
    style.configure("Treeview", background=THEME["bg_card"], foreground=THEME["text"],
                    fieldbackground=THEME["bg_card"], borderwidth=0, font=(THEME["font"], 9),
                    rowheight=32)
    style.configure("Treeview.Heading", background=THEME["bg_sidebar"], foreground=THEME["accent"],
                    font=(THEME["font"], 9, "bold"), borderwidth=0, relief="flat", padding=(8, 8))
    style.map("Treeview",
              background=[("selected", THEME["accent_bg"])],
              foreground=[("selected", THEME["accent"])])
    style.map("Treeview.Heading",
              background=[("active", THEME["bg_hover"])])

    # Scrollbar
    style.configure("Dark.Vertical.TScrollbar", background=THEME["bg_card"], borderwidth=0,
                    troughcolor=THEME["bg"], arrowcolor=THEME["text_dim"])
    style.map("Dark.Vertical.TScrollbar",
              background=[("active", THEME["bg_hover"])])

    # Checkbutton
    style.configure("Dark.TCheckbutton", background=THEME["bg"], foreground=THEME["text"],
                    font=(THEME["font"], 10), focusthickness=0)
    style.map("Dark.TCheckbutton",
              background=[("active", THEME["bg_hover"])],
              foreground=[("active", THEME["accent"])])

    # Spinbox
    style.configure("Dark.TSpinbox", fieldbackground=THEME["bg_input"], foreground=THEME["text"],
                    borderwidth=1, relief="solid", arrowcolor=THEME["accent"], padding=(6, 4))

    root.configure(bg=THEME["bg"])


class AnalyzerApp:
    """声呐 Sonar 主应用"""

    def __init__(self, root):
        self.root = root
        self.root.title("声呐 Sonar — B站 & 贴吧 舆情分析")
        self.root.geometry("1280x820")
        self.root.minsize(1100, 750)
        self.root.configure(bg=THEME["bg"])

        self.config = ConfigManager()
        self.message_queue = queue.Queue()

        self.bilibili_data = None
        self.tieba_data = None
        self.analysis_report = ""
        self.current_keyword = ""
        self._current_page = "main"
        self._analyzing = False
        self.analysis_mode = "keyword"  # "keyword" | "single_video" | "bili_overview"

        apply_theme(self.root)
        self._build_ui()
        self._load_config_to_ui()
        self._show_page("main")
        self._poll_queue()

    # ========== 布局 ==========

    def _build_ui(self):
        """构建主界面：左侧边栏 + 右侧内容区 + 底部状态栏"""
        body = tk.Frame(self.root, bg=THEME["bg"])
        body.pack(fill="both", expand=True)

        # ---- 侧边栏 ----
        sidebar = tk.Frame(body, bg=THEME["bg_sidebar"], width=SIDEBAR_W)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(sidebar, bg=THEME["bg_sidebar"], height=70)
        logo_frame.pack(fill="x", pady=(0, 8))
        tk.Label(logo_frame, text="声呐", bg=THEME["bg_sidebar"],
                 fg=THEME["accent"], font=(THEME["font"], 18, "bold")).pack(side="left", padx=20, pady=(22, 0))
        tk.Label(logo_frame, text="Sonar", bg=THEME["bg_sidebar"],
                 fg=THEME["text_dim"], font=(THEME["font"], 9)).pack(side="left", padx=(2, 0), pady=(30, 0))

        sep = tk.Frame(sidebar, bg=THEME["border"], height=1)
        sep.pack(fill="x", padx=16, pady=4)

        # 导航按钮 (2页: 主页 + 设置)
        self.nav_buttons = {}
        nav_items = [
            ("main", "🔍  搜索分析"),
            ("settings", "⚙  设置"),
        ]
        for page_id, label in nav_items:
            btn = tk.Button(
                sidebar, text=label, bg=THEME["bg_sidebar"], fg=THEME["text_dim"],
                activebackground=THEME["bg_hover"], activeforeground=THEME["text_bright"],
                font=(THEME["font"], 10), bd=0, anchor="w", padx=20, pady=11,
                cursor="hand2", relief="flat",
                command=lambda pid=page_id: self._show_page(pid),
            )
            btn.pack(fill="x")
            self.nav_buttons[page_id] = btn

        # 底部版本
        bottom = tk.Frame(sidebar, bg=THEME["bg_sidebar"])
        bottom.pack(side="bottom", fill="y", pady=10)
        tk.Label(bottom, text="v2.0  ·  LLM驱动", bg=THEME["bg_sidebar"],
                 fg=THEME["text_dim"], font=(THEME["font"], 8)).pack(padx=20)
        tk.Label(bottom, text=datetime.now().strftime("%Y-%m-%d"),
                 bg=THEME["bg_sidebar"], fg=THEME["text_dim"],
                 font=(THEME["font"], 8)).pack(padx=20)

        # ---- 内容区 ----
        self.content = tk.Frame(body, bg=THEME["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {}
        self._build_main_page()
        self._build_settings_page()

        # ---- 状态栏 ----
        self.status_var = tk.StringVar(value="● 就绪")
        status_bar = tk.Frame(self.root, bg=THEME["bg_sidebar"], height=STATUSBAR_H)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self.status_var, bg=THEME["bg_sidebar"],
                 fg=THEME["text_dim"], font=(THEME["font"], 8), anchor="w").pack(
            side="left", padx=16, pady=4)

    def _show_page(self, page_id):
        """切换页面"""
        for pid, frame in self.pages.items():
            frame.pack_forget()
        self.pages[page_id].pack(fill="both", expand=True)

        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.config(bg=THEME["accent_bg"], fg=THEME["accent"],
                           activebackground=THEME["accent_bg"],
                           activeforeground=THEME["accent"],
                           font=(THEME["font"], 10, "bold"))
            else:
                btn.config(bg=THEME["bg_sidebar"], fg=THEME["text_dim"],
                           activebackground=THEME["bg_hover"],
                           activeforeground=THEME["text_bright"],
                           font=(THEME["font"], 10))
        self._current_page = page_id

    def _switch_mode(self, mode):
        """切换分析模式，更新 UI 显示"""
        self.analysis_mode = mode
        mode_descs = {
            "keyword": "搜索关键词，分析B站+贴吧舆情",
            "single_video": "输入BV号，分析视频评论区舆论偏向",
            "bili_overview": "搜索关键词，LLM总结相关视频观点与情绪",
        }
        self.mode_desc_var.set(mode_descs.get(mode, ""))

        # 更新模式按钮高亮
        for mid, btn in self.mode_buttons.items():
            if mid == mode:
                btn.config(bg=THEME["accent_bg"], fg=THEME["accent"],
                           activebackground=THEME["accent_bg"],
                           activeforeground=THEME["accent"],
                           font=(THEME["font"], 10, "bold"))
            else:
                btn.config(bg=THEME["bg_card"], fg=THEME["text_dim"],
                           activebackground=THEME["bg_hover"],
                           activeforeground=THEME["text_bright"],
                           font=(THEME["font"], 10))

        # 更新输入卡片标题
        card_text = {"keyword": "关键词", "single_video": "视频链接", "bili_overview": "关键词"}.get(mode, "关键词")
        self.input_card.config(text=f"  {card_text}  ")

        # 切换输入框显示
        if mode == "single_video":
            self.kw_row.pack_forget()
            self.video_row.pack(fill="x", pady=(0, 8), before=self.ctrl_frame)
            # 隐藏贴吧复选框和贴吧参数
            self.tieba_cb.pack_forget()
            self.params_label.pack_forget()
            # 隐藏贴吧相关 spinbox
            self._hide_spinbox(self.tieba_pages_s)
            self._hide_spinbox(self.tieba_replies_s)
        else:
            self.video_row.pack_forget()
            self.kw_row.pack(fill="x", pady=(0, 8), before=self.ctrl_frame)
            if mode == "keyword":
                # 显示贴吧复选框
                self.tieba_cb.pack(side="left", padx=(0, 8), after=self.bili_cb)
                # 重新显示参数
                if not self.params_label.winfo_ismapped():
                    self.params_label.pack(side="left", padx=(20, 6))
                self._show_spinbox(self.tieba_pages_s)
                self._show_spinbox(self.tieba_replies_s)
            elif mode == "bili_overview":
                # 隐藏贴吧复选框
                self.tieba_cb.pack_forget()
                self.params_label.pack(side="left", padx=(20, 6))
                self._hide_spinbox(self.tieba_pages_s)
                self._hide_spinbox(self.tieba_replies_s)

    def _hide_spinbox(self, spinbox):
        """隐藏 spinbox 及其标签"""
        parent = spinbox.master
        parent.pack_forget()

    def _show_spinbox(self, spinbox):
        """显示 spinbox 及其标签"""
        parent = spinbox.master
        if not parent.winfo_ismapped():
            parent.pack(side="left", padx=(8, 0))

    def _build_main_page(self):
        """主页：搜索分析 + 结果展示"""
        page = tk.Frame(self.content, bg=THEME["bg"])
        self.pages["main"] = page

        # ---- 顶部搜索区 ----
        header = tk.Frame(page, bg=THEME["bg"])
        header.pack(fill="x", padx=24, pady=(16, 8))
        tk.Label(header, text="搜索分析", bg=THEME["bg"], fg=THEME["text_bright"],
                 font=(THEME["font"], 18, "bold")).pack(side="left")
        tk.Label(header, text="LLM 自主采集 B站 & 贴吧 数据并生成舆情分析报告",
                 bg=THEME["bg"], fg=THEME["text_dim"],
                 font=(THEME["font"], 10)).pack(side="left", padx=12, pady=(6, 0))

        # ---- 模式选择器 ----
        mode_frame = tk.Frame(page, bg=THEME["bg"])
        mode_frame.pack(fill="x", padx=24, pady=(0, 8))
        self.mode_buttons = {}
        modes = [
            ("keyword", "🔍 关键词综合分析", "搜索关键词，分析B站+贴吧舆情"),
            ("single_video", "📹 单视频深度分析", "输入BV号，分析视频评论区舆论偏向"),
            ("bili_overview", "📊 B站相关视频概览", "搜索关键词，LLM总结相关视频观点与情绪"),
        ]
        for mid, label, desc in modes:
            btn = tk.Button(
                mode_frame, text=label, bg=THEME["bg_card"], fg=THEME["text_dim"],
                activebackground=THEME["bg_hover"], activeforeground=THEME["text_bright"],
                font=(THEME["font"], 10), bd=1, relief="solid",
                padx=16, pady=8, cursor="hand2",
                command=lambda m=mid: self._switch_mode(m),
            )
            btn.pack(side="left", padx=(0, 8))
            self.mode_buttons[mid] = btn

        # ---- 模式描述标签 ----
        self.mode_desc_var = tk.StringVar()
        self.mode_desc_label = tk.Label(mode_frame, textvariable=self.mode_desc_var,
                                        bg=THEME["bg"], fg=THEME["text_dim"],
                                        font=(THEME["font"], 9))
        self.mode_desc_label.pack(side="left", padx=8)

        # ---- 输入卡片 ----
        self.input_card = self._card_frame(page, "关键词")
        self.input_card.pack(fill="x", padx=24, pady=(0, 8))

        self.input_inner = tk.Frame(self.input_card, bg=THEME["bg_card"])
        self.input_inner.pack(fill="x", padx=16, pady=(4, 12))

        # 关键词输入行 (keyword / bili_overview 模式共用)
        self.kw_row = tk.Frame(self.input_inner, bg=THEME["bg_card"])
        self.kw_row.pack(fill="x", pady=(0, 8))
        self.keyword_entry = tk.Entry(
            self.kw_row, bg=THEME["bg_input"], fg=THEME["text_bright"],
            insertbackground=THEME["text_bright"], relief="solid", bd=1,
            font=(THEME["font"], 13), highlightthickness=1,
            highlightcolor=THEME["accent"], highlightbackground=THEME["border"],
        )
        self.keyword_entry.pack(side="left", fill="x", expand=True, ipadx=8, ipady=8)
        self.keyword_entry.bind("<Return>", lambda e: self._start_analysis())
        self.kw_hint = tk.Label(self.kw_row, text="输入关键词", bg=THEME["bg_card"],
                                fg=THEME["text_dim"], font=(THEME["font"], 9))
        self.kw_hint.pack(side="left", padx=(8, 0))

        # BV号输入行 (single_video 模式)
        self.video_row = tk.Frame(self.input_inner, bg=THEME["bg_card"])
        # 不 pack，仅在 single_video 模式显示
        self.video_entry = tk.Entry(
            self.video_row, bg=THEME["bg_input"], fg=THEME["text_bright"],
            insertbackground=THEME["text_bright"], relief="solid", bd=1,
            font=(THEME["font"], 13), highlightthickness=1,
            highlightcolor=THEME["accent"], highlightbackground=THEME["border"],
        )
        self.video_entry.pack(side="left", fill="x", expand=True, ipadx=8, ipady=8)
        self.video_entry.bind("<Return>", lambda e: self._start_analysis())
        tk.Label(self.video_row, text="输入BV号或视频URL", bg=THEME["bg_card"],
                 fg=THEME["text_dim"], font=(THEME["font"], 9)).pack(side="left", padx=(8, 0))

        # 平台选择 + 采集参数
        self.ctrl_frame = tk.Frame(self.input_inner, bg=THEME["bg_card"])
        self.ctrl_frame.pack(fill="x", pady=(0, 4))

        self.bili_var = tk.BooleanVar(value=True)
        self.tieba_var = tk.BooleanVar(value=True)
        self.bili_cb = self._make_checkbox(self.ctrl_frame, "  B站  ", self.bili_var, THEME["bili_pink"])
        self.tieba_cb = self._make_checkbox(self.ctrl_frame, "  贴吧  ", self.tieba_var, THEME["tieba_blue"])

        # 采集参数
        self.params_label = tk.Label(self.ctrl_frame, text="采集深度:", bg=THEME["bg_card"],
                                      fg=THEME["text_dim"], font=(THEME["font"], 10))
        self.params_label.pack(side="left", padx=(20, 6))
        self._make_param_spinbox(self.ctrl_frame, "B站页数", "bili_pages_s", 1, 10, 2)
        self._make_param_spinbox(self.ctrl_frame, "评论数", "bili_comments_s", 0, 100, 30)
        self._make_param_spinbox(self.ctrl_frame, "贴吧页数", "tieba_pages_s", 1, 10, 3)
        self._make_param_spinbox(self.ctrl_frame, "回复数", "tieba_replies_s", 0, 100, 20)

        # 操作按钮
        btn_frame = tk.Frame(self.input_inner, bg=THEME["bg_card"])
        btn_frame.pack(fill="x", pady=(8, 0))
        self.analyze_btn = tk.Button(
            btn_frame, text="🚀  一键分析", bg=THEME["accent"], fg="#000000",
            activebackground=THEME["accent_dim"], activeforeground="#ffffff",
            font=(THEME["font"], 11, "bold"), bd=0, relief="flat",
            padx=28, pady=10, cursor="hand2", command=self._start_analysis,
        )
        self.analyze_btn.pack(side="left", padx=(0, 8))
        self.clear_btn = tk.Button(
            btn_frame, text="清空数据", bg=THEME["bg_input"], fg=THEME["text_dim"],
            activebackground=THEME["bg_hover"], activeforeground=THEME["error"],
            font=(THEME["font"], 10), bd=1, relief="solid",
            padx=18, pady=10, cursor="hand2", command=self._clear_data,
        )
        self.clear_btn.pack(side="left", padx=4)

        # 导出按钮
        tk.Button(btn_frame, text="📄 导出报告", bg=THEME["bg_input"], fg=THEME["text"],
                  activebackground=THEME["bg_hover"], font=(THEME["font"], 9),
                  bd=1, relief="solid", padx=14, pady=8, cursor="hand2",
                  command=self._export_report).pack(side="left", padx=(16, 4))
        tk.Button(btn_frame, text="📦 导出数据", bg=THEME["bg_input"], fg=THEME["text"],
                  activebackground=THEME["bg_hover"], font=(THEME["font"], 9),
                  bd=1, relief="solid", padx=14, pady=8, cursor="hand2",
                  command=self._export_data).pack(side="left", padx=4)

        # 初始化模式
        self._switch_mode("keyword")

        # ---- LLM 活动日志区 ----
        activity_card = self._card_frame(page, "LLM 活动日志")
        activity_card.pack(fill="x", padx=24, pady=(0, 8))

        activity_inner = tk.Frame(activity_card, bg=THEME["bg_card"])
        activity_inner.pack(fill="x", padx=16, pady=(4, 8))

        self.activity_text = scrolledtext.ScrolledText(
            activity_inner, bg=THEME["bg_card"], fg=THEME["text"],
            insertbackground=THEME["text"], font=(THEME["font_mono"], 9),
            relief="flat", bd=0, wrap="word", height=6,
            selectbackground=THEME["accent_bg"], selectforeground=THEME["accent"],
        )
        self.activity_text.pack(fill="x")
        self.activity_text.configure(state="disabled")
        self.activity_text.tag_configure("time", foreground=THEME["text_dim"])
        self.activity_text.tag_configure("tool", foreground=THEME["accent"])
        self.activity_text.tag_configure("result", foreground=THEME["success"])
        self.activity_text.tag_configure("think", foreground=THEME["warning"])
        self.activity_text.tag_configure("error", foreground=THEME["error"])
        self.activity_text.tag_configure("info", foreground=THEME["text"])

        # ---- 数据 + 报告区 (Notebook) ----
        result_card = self._card_frame(page, "数据 & 分析报告")
        result_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        result_inner = tk.Frame(result_card, bg=THEME["bg_card"])
        result_inner.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        notebook = ttk.Notebook(result_inner, style="Dark.TNotebook")
        notebook.pack(fill="both", expand=True)

        # B站视频
        self.bili_tree = self._create_treeview(notebook, "B站视频", [
            ("title", "标题", 300), ("author", "UP主", 100),
            ("play", "播放", 80), ("like", "点赞", 80),
            ("reply", "回复", 80), ("favorites", "收藏", 80),
            ("pubdate", "发布时间", 120),
        ])
        # B站评论
        self.bili_comment_tree = self._create_treeview(notebook, "B站评论", [
            ("user", "用户", 100), ("content", "评论内容", 400),
            ("like", "点赞", 80), ("ctime", "时间", 120),
        ])
        # 贴吧帖子
        self.tieba_tree = self._create_treeview(notebook, "贴吧帖子", [
            ("title", "标题", 300), ("bar", "贴吧", 100),
            ("author", "作者", 100), ("reply_count", "回复数", 80),
            ("date", "日期", 120),
        ])
        # 贴吧回复
        self.tieba_reply_tree = self._create_treeview(notebook, "贴吧回复", [
            ("user", "用户", 100), ("content", "回复内容", 400),
            ("floor", "楼层", 60), ("time", "时间", 120),
        ])
        # 分析报告
        report_frame = tk.Frame(notebook, bg=THEME["bg"])
        notebook.add(report_frame, text="  📊 分析报告  ")
        self.report_text = scrolledtext.ScrolledText(
            report_frame, bg=THEME["bg_card"], fg=THEME["text"],
            insertbackground=THEME["text"], font=(THEME["font"], 10),
            relief="flat", bd=0, wrap="word",
            selectbackground=THEME["accent_bg"], selectforeground=THEME["accent"],
        )
        self.report_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.report_text.configure(state="disabled")

    # ========== 设置页 ==========

    def _build_settings_page(self):
        """设置页：LLM配置 + Cookie配置 + 一键获取Cookie + 运行日志"""
        page = tk.Frame(self.content, bg=THEME["bg"])
        self.pages["settings"] = page

        # 可滚动容器
        canvas = tk.Canvas(page, bg=THEME["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview,
                                  style="Dark.Vertical.TScrollbar")
        scroll_frame = tk.Frame(canvas, bg=THEME["bg"])
        scroll_frame.bind("<Configure>",
                         lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 标题
        tk.Label(scroll_frame, text="设置", bg=THEME["bg"],
                 fg=THEME["text_bright"], font=(THEME["font"], 18, "bold")).pack(
            anchor="w", padx=24, pady=(20, 4))
        tk.Label(scroll_frame, text="配置 LLM API、Cookie 及采集参数", bg=THEME["bg"],
                 fg=THEME["text_dim"], font=(THEME["font"], 10)).pack(
            anchor="w", padx=24, pady=(0, 12))

        # === LLM API 配置 ===
        llm_card = self._card_frame(scroll_frame, "LLM API 配置")
        llm_card.pack(fill="x", padx=24, pady=(0, 12))
        llm_inner = tk.Frame(llm_card, bg=THEME["bg_card"])
        llm_inner.pack(fill="x", padx=16, pady=(4, 12))

        self.llm_base = self._make_entry(llm_inner, "API 地址", "https://api.deepseek.com/v1")
        self.llm_key = self._make_entry(llm_inner, "API Key", "", show="*")
        self.llm_model = self._make_entry(llm_inner, "模型名", "deepseek-chat")

        # 预设按钮
        tk.Label(llm_inner, text="快捷预设", bg=THEME["bg_card"],
                 fg=THEME["text_dim"], font=(THEME["font"], 9)).pack(anchor="w", pady=(8, 4))
        preset_frame = tk.Frame(llm_inner, bg=THEME["bg_card"])
        preset_frame.pack(fill="x")
        for name, base, model in [
            ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
            ("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
            ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
            ("Moonshot", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        ]:
            tk.Button(preset_frame, text=name, bg=THEME["bg_input"], fg=THEME["text_dim"],
                      activebackground=THEME["bg_hover"], activeforeground=THEME["accent"],
                      font=(THEME["font"], 9), bd=1, relief="solid",
                      padx=10, pady=4, cursor="hand2",
                      command=lambda b=base, m=model: self._apply_preset(b, m)).pack(
                side="left", padx=(0, 6))

        tk.Label(llm_inner, bg=THEME["bg_card"], fg=THEME["text_dim"],
                 font=(THEME["font"], 9),
                 text="支持 OpenAI 兼容格式的任意 API。LLM 会通过函数调用自主采集数据并分析。",
                 justify="left", anchor="w").pack(fill="x", pady=(8, 0))

        # === B站 Cookie ===
        bili_card = self._card_frame(scroll_frame, "B站 Cookie")
        bili_card.pack(fill="x", padx=24, pady=(0, 12))
        bili_inner = tk.Frame(bili_card, bg=THEME["bg_card"])
        bili_inner.pack(fill="x", padx=16, pady=(4, 8))

        self.bili_sessdata = self._make_entry(bili_inner, "SESSDATA", "")
        self.bili_jct = self._make_entry(bili_inner, "bili_jct", "")
        self.bili_dedeuid = self._make_entry(bili_inner, "DedeUserID", "")

        # Cookie 获取按钮
        bili_btn_frame = tk.Frame(bili_inner, bg=THEME["bg_card"])
        bili_btn_frame.pack(fill="x", pady=(8, 0))
        tk.Button(bili_btn_frame, text="🔍 一键获取Cookie", bg=THEME["bili_pink"], fg="#ffffff",
                  activebackground="#d65a82", font=(THEME["font"], 9, "bold"),
                  bd=0, relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._get_bilibili_cookie).pack(side="left", padx=(0, 8))
        tk.Button(bili_btn_frame, text="🌐 打开登录页", bg=THEME["bg_input"], fg=THEME["text"],
                  activebackground=THEME["bg_hover"], font=(THEME["font"], 9),
                  bd=1, relief="solid", padx=14, pady=6, cursor="hand2",
                  command=cookie_helper.open_bilibili_login).pack(side="left", padx=4)

        tk.Label(bili_inner, bg=THEME["bg_card"], fg=THEME["text_dim"],
                 font=(THEME["font"], 9),
                 text="点击「一键获取Cookie」自动从浏览器提取（需已登录B站）\n"
                      "或手动: 登录 bilibili.com → F12 → Application → Cookies",
                 justify="left", anchor="w").pack(fill="x", pady=(6, 0))

        # === 贴吧 Cookie ===
        tieba_card = self._card_frame(scroll_frame, "贴吧 Cookie")
        tieba_card.pack(fill="x", padx=24, pady=(0, 12))
        tieba_inner = tk.Frame(tieba_card, bg=THEME["bg_card"])
        tieba_inner.pack(fill="x", padx=16, pady=(4, 8))

        self.tieba_bduss = self._make_entry(tieba_inner, "BDUSS", "")
        self.tieba_stoken = self._make_entry(tieba_inner, "STOKEN", "")

        tieba_btn_frame = tk.Frame(tieba_inner, bg=THEME["bg_card"])
        tieba_btn_frame.pack(fill="x", pady=(8, 0))
        tk.Button(tieba_btn_frame, text="🔍 一键获取Cookie", bg=THEME["tieba_blue"], fg="#ffffff",
                  activebackground="#3a5bd9", font=(THEME["font"], 9, "bold"),
                  bd=0, relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._get_tieba_cookie).pack(side="left", padx=(0, 8))
        tk.Button(tieba_btn_frame, text="🌐 打开登录页", bg=THEME["bg_input"], fg=THEME["text"],
                  activebackground=THEME["bg_hover"], font=(THEME["font"], 9),
                  bd=1, relief="solid", padx=14, pady=6, cursor="hand2",
                  command=cookie_helper.open_tieba_login).pack(side="left", padx=4)

        tk.Label(tieba_inner, bg=THEME["bg_card"], fg=THEME["text_dim"],
                 font=(THEME["font"], 9),
                 text="点击「一键获取Cookie」自动从浏览器提取（需已登录贴吧）\n"
                      "或手动: 登录 tieba.baidu.com → F12 → Application → Cookies",
                 justify="left", anchor="w").pack(fill="x", pady=(6, 0))

        # === 采集参数 ===
        param_card = self._card_frame(scroll_frame, "采集参数")
        param_card.pack(fill="x", padx=24, pady=(0, 12))
        param_inner = tk.Frame(param_card, bg=THEME["bg_card"])
        param_inner.pack(fill="x", padx=16, pady=(4, 12))

        param_row = tk.Frame(param_inner, bg=THEME["bg_card"])
        param_row.pack(fill="x", pady=(4, 0))
        self._make_param_spinbox(param_row, "B站搜索页数", "bili_pages_s2", 1, 10, 2)
        self._make_param_spinbox(param_row, "每视频评论数", "bili_comments_s2", 0, 100, 30)
        param_row2 = tk.Frame(param_inner, bg=THEME["bg_card"])
        param_row2.pack(fill="x", pady=(4, 0))
        self._make_param_spinbox(param_row2, "贴吧搜索页数", "tieba_pages_s2", 1, 10, 3)
        self._make_param_spinbox(param_row2, "每帖子回复数", "tieba_replies_s2", 0, 100, 20)

        tk.Label(param_inner, bg=THEME["bg_card"], fg=THEME["text_dim"],
                 font=(THEME["font"], 9),
                 text="这些参数作为 LLM 工具调用的默认上限。LLM 会根据需要自主决定采集深度。",
                 justify="left", anchor="w").pack(fill="x", pady=(8, 0))

        # === 操作按钮 ===
        btn_frame = tk.Frame(scroll_frame, bg=THEME["bg"])
        btn_frame.pack(fill="x", padx=24, pady=(0, 12))
        tk.Button(btn_frame, text="💾 保存配置", bg=THEME["accent"], fg="#000000",
                  activebackground=THEME["accent_dim"], activeforeground="#ffffff",
                  font=(THEME["font"], 10, "bold"), bd=0, relief="flat",
                  padx=20, pady=9, cursor="hand2",
                  command=self._save_config).pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="测试 B站", bg=THEME["bg_input"], fg=THEME["text"],
                  activebackground=THEME["bg_hover"], font=(THEME["font"], 10),
                  bd=1, relief="solid", padx=16, pady=9, cursor="hand2",
                  command=self._test_bilibili).pack(side="left", padx=4)
        tk.Button(btn_frame, text="测试 贴吧", bg=THEME["bg_input"], fg=THEME["text"],
                  activebackground=THEME["bg_hover"], font=(THEME["font"], 10),
                  bd=1, relief="solid", padx=16, pady=9, cursor="hand2",
                  command=self._test_tieba).pack(side="left", padx=4)
        tk.Button(btn_frame, text="测试 LLM", bg=THEME["bg_input"], fg=THEME["text"],
                  activebackground=THEME["bg_hover"], font=(THEME["font"], 10),
                  bd=1, relief="solid", padx=16, pady=9, cursor="hand2",
                  command=self._test_llm).pack(side="left", padx=4)

        # === 运行日志（次要区域） ===
        log_card = self._card_frame(scroll_frame, "运行日志")
        log_card.pack(fill="x", padx=24, pady=(0, 24))

        log_inner = tk.Frame(log_card, bg=THEME["bg_card"])
        log_inner.pack(fill="x", padx=16, pady=(4, 12))

        self.log_text = scrolledtext.ScrolledText(
            log_inner, bg=THEME["bg_card"], fg=THEME["text"],
            insertbackground=THEME["text"], font=(THEME["font_mono"], 9),
            relief="flat", bd=0, wrap="word", height=10,
            selectbackground=THEME["accent_bg"], selectforeground=THEME["accent"],
        )
        log_inner.pack_propagate(False)
        self.log_text.pack(fill="x")
        self.log_text.configure(state="disabled")
        self.log_text.tag_configure("time", foreground=THEME["text_dim"])
        self.log_text.tag_configure("success", foreground=THEME["success"])
        self.log_text.tag_configure("error", foreground=THEME["error"])
        self.log_text.tag_configure("info", foreground=THEME["accent"])
        self.log_text.tag_configure("warning", foreground=THEME["warning"])

    # ========== UI 辅助方法 ==========

    def _card_frame(self, parent, title):
        """创建卡片式 LabelFrame"""
        frame = tk.LabelFrame(parent, text=f"  {title}  ", bg=THEME["bg_card"],
                              fg=THEME["accent"], font=(THEME["font"], 11, "bold"),
                              bd=1, relief="solid", highlightthickness=0,
                              borderwidth=1, padx=0, pady=0, labelanchor="nw")
        return frame

    def _make_entry(self, parent, label_text, default="", show=None):
        """创建带标签的暗色输入框"""
        row = tk.Frame(parent, bg=THEME["bg_card"])
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text=label_text, bg=THEME["bg_card"], fg=THEME["text_dim"],
                 font=(THEME["font"], 10), width=12, anchor="w").pack(side="left")
        entry = tk.Entry(row, bg=THEME["bg_input"], fg=THEME["text_bright"],
                         insertbackground=THEME["text_bright"], relief="solid", bd=1,
                         font=(THEME["font"], 10), show=show,
                         highlightthickness=1, highlightcolor=THEME["accent"],
                         highlightbackground=THEME["border"])
        entry.pack(side="left", fill="x", expand=True, ipadx=8, ipady=6)
        if default:
            entry.insert(0, default)
        return entry

    def _make_checkbox(self, parent, text, var, accent_color):
        """创建复选框"""
        cb = tk.Checkbutton(parent, text=text, variable=var, bg=THEME["bg_card"],
                            fg=THEME["text"], selectcolor=THEME["bg_input"],
                            activebackground=THEME["bg_card"], activeforeground=accent_color,
                            font=(THEME["font"], 10), bd=0, cursor="hand2",
                            highlightthickness=0)
        cb.pack(side="left", padx=(0, 8))
        return cb

    def _make_param_spinbox(self, parent, label_text, attr_name, from_, to_, default):
        """创建参数 Spinbox"""
        frame = tk.Frame(parent, bg=THEME["bg_card"])
        frame.pack(side="left", padx=(8, 0))
        tk.Label(frame, text=label_text, bg=THEME["bg_card"], fg=THEME["text_dim"],
                 font=(THEME["font"], 9)).pack(side="left")
        sb = tk.Spinbox(frame, from_=from_, to=to_, width=4, bg=THEME["bg_input"],
                        fg=THEME["text_bright"], insertbackground=THEME["text_bright"],
                        font=(THEME["font"], 9), relief="solid", bd=1,
                        highlightthickness=1, highlightcolor=THEME["accent"],
                        highlightbackground=THEME["border"], buttonbackground=THEME["bg_hover"],
                        buttonuprelief="flat", buttondownrelief="flat")
        sb.delete(0, "end")
        sb.insert(0, str(default))
        sb.pack(side="left", padx=(4, 0))
        setattr(self, attr_name, sb)

    def _create_treeview(self, notebook, tab_title, columns):
        """创建暗色主题数据表格"""
        frame = tk.Frame(notebook, bg=THEME["bg"])
        notebook.add(frame, text=f"  {tab_title}  ")

        col_ids = [c[0] for c in columns]
        tree = ttk.Treeview(frame, columns=col_ids, show="headings", selectmode="browse",
                            style="Treeview")
        for col_id, col_name, width in columns:
            tree.heading(col_id, text=col_name)
            tree.column(col_id, width=width, minwidth=50)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview,
                            style="Dark.Vertical.TScrollbar")
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        tree.tag_configure("even", background=THEME["bg_card"])
        tree.tag_configure("odd", background="#1e1e1e")
        return tree

    # ========== 配置读写 ==========

    def _load_config_to_ui(self):
        """从配置文件加载到 UI"""
        self.bili_sessdata.delete(0, "end")
        self.bili_sessdata.insert(0, self.config.get("bilibili", "cookies", "SESSDATA", default=""))
        self.bili_jct.delete(0, "end")
        self.bili_jct.insert(0, self.config.get("bilibili", "cookies", "bili_jct", default=""))
        self.bili_dedeuid.delete(0, "end")
        self.bili_dedeuid.insert(0, self.config.get("bilibili", "cookies", "DedeUserID", default=""))
        self.tieba_bduss.delete(0, "end")
        self.tieba_bduss.insert(0, self.config.get("tieba", "cookies", "BDUSS", default=""))
        self.tieba_stoken.delete(0, "end")
        self.tieba_stoken.insert(0, self.config.get("tieba", "cookies", "STOKEN", default=""))
        self.llm_base.delete(0, "end")
        self.llm_base.insert(0, self.config.get("llm", "api_base", default="https://api.deepseek.com/v1"))
        self.llm_key.delete(0, "end")
        self.llm_key.insert(0, self.config.get("llm", "api_key", default=""))
        self.llm_model.delete(0, "end")
        self.llm_model.insert(0, self.config.get("llm", "model", default="deepseek-chat"))

        # 主页和设置页的 spinbox 都同步
        for sb, key, default in [
            (self.bili_pages_s, "bilibili_max_pages", 2),
            (self.bili_comments_s, "bilibili_comments_per_video", 30),
            (self.tieba_pages_s, "tieba_max_pages", 3),
            (self.tieba_replies_s, "tieba_replies_per_post", 20),
            (self.bili_pages_s2, "bilibili_max_pages", 2),
            (self.bili_comments_s2, "bilibili_comments_per_video", 30),
            (self.tieba_pages_s2, "tieba_max_pages", 3),
            (self.tieba_replies_s2, "tieba_replies_per_post", 20),
        ]:
            sb.delete(0, "end")
            sb.insert(0, str(self.config.get("collect", key, default=default)))

    def _save_config(self):
        """保存 UI 配置到文件"""
        self._update_config_from_ui()
        self.config.save()
        self._log("配置已保存", "success")
        self._show_toast("配置已保存")

    def _apply_preset(self, base, model):
        """应用 LLM 预设"""
        self.llm_base.delete(0, "end")
        self.llm_base.insert(0, base)
        self.llm_model.delete(0, "end")
        self.llm_model.insert(0, model)

    def _update_config_from_ui(self):
        """从 UI 更新配置对象"""
        self.config.set("bilibili", "cookies", "SESSDATA", self.bili_sessdata.get())
        self.config.set("bilibili", "cookies", "bili_jct", self.bili_jct.get())
        self.config.set("bilibili", "cookies", "DedeUserID", self.bili_dedeuid.get())
        self.config.set("tieba", "cookies", "BDUSS", self.tieba_bduss.get())
        self.config.set("tieba", "cookies", "STOKEN", self.tieba_stoken.get())
        self.config.set("llm", "api_base", self.llm_base.get().strip())
        self.config.set("llm", "api_key", self.llm_key.get().strip())
        self.config.set("llm", "model", self.llm_model.get().strip())
        # 从主页 spinbox 读取（设置页的同步显示）
        self.config.set("collect", "bilibili_max_pages", int(self.bili_pages_s.get()))
        self.config.set("collect", "bilibili_comments_per_video", int(self.bili_comments_s.get()))
        self.config.set("collect", "tieba_max_pages", int(self.tieba_pages_s.get()))
        self.config.set("collect", "tieba_replies_per_post", int(self.tieba_replies_s.get()))
        # 同步设置页 spinbox
        for sb_main, sb_settings in [
            (self.bili_pages_s, self.bili_pages_s2),
            (self.bili_comments_s, self.bili_comments_s2),
            (self.tieba_pages_s, self.tieba_pages_s2),
            (self.tieba_replies_s, self.tieba_replies_s2),
        ]:
            sb_settings.delete(0, "end")
            sb_settings.insert(0, sb_main.get())

    def _sync_spinboxes(self):
        """同步主页和设置页的 spinbox 值"""
        for sb_main, sb_settings in [
            (self.bili_pages_s, self.bili_pages_s2),
            (self.bili_comments_s, self.bili_comments_s2),
            (self.tieba_pages_s, self.tieba_pages_s2),
            (self.tieba_replies_s, self.tieba_replies_s2),
        ]:
            sb_settings.delete(0, "end")
            sb_settings.insert(0, sb_main.get())

    # ========== Cookie 一键获取 ==========

    def _get_bilibili_cookie(self):
        """一键获取B站Cookie"""
        self._log("正在从浏览器提取B站Cookie...", "info")
        if not cookie_helper.is_browser_cookie3_available():
            self._log("browser_cookie3 未安装，无法自动获取。请手动填写或安装: pip install browser_cookie3", "error")
            messagebox.showwarning("提示", "browser_cookie3 未安装，无法自动获取Cookie。\n\n请手动填写或运行:\npip install browser_cookie3")
            return

        def _do():
            try:
                cookies = cookie_helper.get_bilibili_cookies()
                if cookies:
                    self.message_queue.put(("cookie_result", "bilibili", cookies))
                else:
                    self.message_queue.put(("cookie_result", "bilibili", None))
            except Exception as e:
                self.message_queue.put(("cookie_result", "bilibili", str(e)))
        threading.Thread(target=_do, daemon=True).start()

    def _get_tieba_cookie(self):
        """一键获取贴吧Cookie"""
        self._log("正在从浏览器提取贴吧Cookie...", "info")
        if not cookie_helper.is_browser_cookie3_available():
            self._log("browser_cookie3 未安装，无法自动获取。请手动填写或安装: pip install browser_cookie3", "error")
            messagebox.showwarning("提示", "browser_cookie3 未安装，无法自动获取Cookie。\n\n请手动填写或运行:\npip install browser_cookie3")
            return

        def _do():
            try:
                cookies = cookie_helper.get_tieba_cookies()
                if cookies:
                    self.message_queue.put(("cookie_result", "tieba", cookies))
                else:
                    self.message_queue.put(("cookie_result", "tieba", None))
            except Exception as e:
                self.message_queue.put(("cookie_result", "tieba", str(e)))
        threading.Thread(target=_do, daemon=True).start()

    # ========== Toast 提示 ==========

    def _show_toast(self, message, toast_type="info"):
        """显示底部 Toast 提示"""
        colors = {"info": THEME["accent"], "success": THEME["success"],
                  "error": THEME["error"], "warning": THEME["warning"]}
        color = colors.get(toast_type, THEME["accent"])

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.configure(bg=color)
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 120
        y = self.root.winfo_y() + self.root.winfo_height() - 80
        toast.geometry(f"240x36+{x}+{y}")
        toast.attributes("-topmost", True)
        tk.Label(toast, text=f"  ✓  {message}", bg=color, fg="#000000",
                 font=(THEME["font"], 10, "bold")).pack(fill="both", expand=True, padx=12, pady=8)
        self.root.after(2000, toast.destroy)

    # ========== 测试连接 ==========

    def _test_bilibili(self):
        self._update_config_from_ui()
        if not self.config.is_bilibili_configured():
            self._log("请先填写 B站 SESSDATA", "error")
            return
        self._log("正在测试B站连接...", "info")

        def _do():
            try:
                collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
                hot = collector.get_hot_searches()
                if hot:
                    self.message_queue.put(("log", f"B站连接成功！热搜: {', '.join(hot[:5])}", "success"))
                    self.message_queue.put(("status", "B站连接正常"))
                else:
                    self.message_queue.put(("log", "B站连接成功（热搜为空）", "success"))
            except Exception as e:
                self.message_queue.put(("log", f"B站连接失败: {e}", "error"))
                self.message_queue.put(("status", "B站连接失败"))
        threading.Thread(target=_do, daemon=True).start()

    def _test_tieba(self):
        self._update_config_from_ui()
        if not self.config.is_tieba_configured():
            self._log("请先填写贴吧 BDUSS", "error")
            return
        self._log("正在测试贴吧连接...", "info")

        def _do():
            try:
                collector = TiebaCollector(self.config.get_tieba_cookie_str())
                posts = collector.get_bar_posts("测试", page=1)
                self.message_queue.put(("log", f"贴吧连接成功！获取到 {len(posts)} 条帖子", "success"))
                self.message_queue.put(("status", "贴吧连接正常"))
            except Exception as e:
                self.message_queue.put(("log", f"贴吧连接失败: {e}", "error"))
                self.message_queue.put(("status", "贴吧连接失败"))
        threading.Thread(target=_do, daemon=True).start()

    def _test_llm(self):
        self._update_config_from_ui()
        if not self.config.is_llm_configured():
            self._log("请先填写 LLM API Key", "error")
            return
        self._log("正在测试LLM连接...", "info")

        def _do():
            try:
                analyzer = LLMAnalyzer(
                    self.config.get("llm", "api_base"),
                    self.config.get("llm", "api_key"),
                    self.config.get("llm", "model"),
                )
                result = analyzer._chat("你是测试助手", "请回复'连接成功'四个字", temperature=0, max_tokens=20)
                self.message_queue.put(("log", f"LLM连接成功！模型回复: {result}", "success"))
                self.message_queue.put(("status", "LLM连接正常"))
            except Exception as e:
                self.message_queue.put(("log", f"LLM连接失败: {e}", "error"))
                self.message_queue.put(("status", "LLM连接失败"))
        threading.Thread(target=_do, daemon=True).start()

    # ========== 核心分析流程（LLM 驱动）==========

    def _start_analysis(self):
        """启动 LLM 驱动的分析流程"""
        if self._analyzing:
            return
        self._update_config_from_ui()

        mode = self.analysis_mode
        if mode == "single_video":
            video_input = self.video_entry.get().strip()
            if not video_input:
                self._log("请输入BV号或视频URL", "error")
                return
            self.current_keyword = video_input
        else:
            keyword = self.keyword_entry.get().strip()
            if not keyword:
                self._log("请输入关键词", "error")
                return
            self.current_keyword = keyword

        if not self.config.is_llm_configured():
            self._log("请先配置 LLM API Key", "error")
            self._show_page("settings")
            return

        use_bili = self.bili_var.get() if mode != "single_video" else True
        use_tieba = self.tieba_var.get() and mode == "keyword"

        if mode != "single_video" and use_bili and not self.config.is_bilibili_configured():
            self._log("B站未配置 Cookie，请在设置页填写", "warning")
        if mode == "keyword" and use_tieba and not self.config.is_tieba_configured():
            self._log("贴吧未配置 Cookie，请在设置页填写", "warning")
        if mode == "single_video" and not self.config.is_bilibili_configured():
            self._log("B站未配置 Cookie，请在设置页填写", "warning")

        self._analyzing = True
        self.analyze_btn.config(state="disabled", text="分析中...")
        self.clear_btn.config(state="disabled")
        self._clear_data()
        self._set_status("● LLM 分析中...")
        self._clear_activity()

        bili_cookie = self.config.get_bilibili_cookie_str() if use_bili else ""
        tieba_cookie = self.config.get_tieba_cookie_str() if use_tieba else ""

        mode_names = {"keyword": "关键词综合分析", "single_video": "单视频深度分析", "bili_overview": "B站相关视频概览"}
        self._activity("开始分析", f"[{mode_names.get(mode, '')}] {self.current_keyword}", "info")

        def _do():
            try:
                analyzer = LLMAnalyzer(
                    self.config.get("llm", "api_base"),
                    self.config.get("llm", "api_key"),
                    self.config.get("llm", "model"),
                )

                def on_tool_call(name, args):
                    desc = self._format_tool_call_desc(name, args)
                    self.message_queue.put(("activity", f"🔍 调用工具: {desc}", "tool"))

                def on_tool_result(name, summary):
                    self.message_queue.put(("activity", f"  ✓ {summary}", "result"))

                def on_thinking(text):
                    if text and len(text) < 200:
                        self.message_queue.put(("activity", f"🤔 {text[:100]}", "think"))

                try:
                    if mode == "keyword":
                        result = analyzer.analyze_agentic(
                            self.current_keyword,
                            bili_cookie=bili_cookie,
                            tieba_cookie=tieba_cookie,
                            use_bilibili=use_bili,
                            use_tieba=use_tieba,
                            on_tool_call=on_tool_call,
                            on_tool_result=on_tool_result,
                            on_thinking=on_thinking,
                        )
                    elif mode == "single_video":
                        result = analyzer.analyze_single_video(
                            self.current_keyword,
                            bili_cookie=bili_cookie,
                            on_tool_call=on_tool_call,
                            on_tool_result=on_tool_result,
                            on_thinking=on_thinking,
                        )
                    elif mode == "bili_overview":
                        result = analyzer.analyze_bili_overview(
                            self.current_keyword,
                            bili_cookie=bili_cookie,
                            on_tool_call=on_tool_call,
                            on_tool_result=on_tool_result,
                            on_thinking=on_thinking,
                        )

                    self.bilibili_data = result.get("bilibili_data")
                    self.tieba_data = result.get("tieba_data")
                    self.analysis_report = result.get("report", "")
                    self.message_queue.put(("data_ready", "bilibili"))
                    if self.tieba_data:
                        self.message_queue.put(("data_ready", "tieba"))
                    self.message_queue.put(("report", self.analysis_report))
                    self.message_queue.put(("activity", "✅ 分析完成！", "result"))
                    self.message_queue.put(("log", f"{mode_names.get(mode, '')}完成", "success"))
                    self.message_queue.put(("done", "complete"))

                except FunctionCallingNotSupported:
                    self.message_queue.put(("activity", "⚠ API不支持函数调用，回退到传统模式", "think"))
                    self.message_queue.put(("log", "API不支持函数调用，使用传统模式", "warning"))
                    if mode == "keyword":
                        bili_data, tieba_data = self._traditional_collect(self.current_keyword, use_bili, use_tieba)
                    elif mode == "single_video":
                        bili_data = self._traditional_collect_single_video(self.current_keyword)
                        tieba_data = None
                    else:
                        bili_data = self._traditional_collect_bili_overview(self.current_keyword)
                        tieba_data = None

                    if bili_data:
                        self.bilibili_data = bili_data
                        self.message_queue.put(("data_ready", "bilibili"))
                    if tieba_data:
                        self.tieba_data = tieba_data
                        self.message_queue.put(("data_ready", "tieba"))
                    self.message_queue.put(("activity", "采集完成，正在分析...", "info"))

                    if mode == "keyword":
                        report = analyzer.analyze_traditional(self.current_keyword, bili_data, tieba_data)
                    else:
                        report = analyzer.analyze_traditional(self.current_keyword, bili_data, None)
                    self.analysis_report = report
                    self.message_queue.put(("report", report))
                    self.message_queue.put(("activity", "✅ 分析完成（传统模式）！", "result"))
                    self.message_queue.put(("log", "传统模式分析完成", "success"))
                    self.message_queue.put(("done", "complete"))

            except Exception as e:
                self.message_queue.put(("activity", f"❌ 分析失败: {e}", "error"))
                self.message_queue.put(("log", f"分析出错: {e}", "error"))
                self.message_queue.put(("done", "error"))

        threading.Thread(target=_do, daemon=True).start()

    def _traditional_collect(self, keyword, use_bili, use_tieba):
        """传统模式采集数据（回退用）"""
        bili_data = None
        tieba_data = None
        bili_max_pages = int(self.bili_pages_s.get())
        bili_comments = int(self.bili_comments_s.get())
        tieba_max_pages = int(self.tieba_pages_s.get())
        tieba_replies = int(self.tieba_replies_s.get())

        if use_bili:
            self.message_queue.put(("activity", "正在采集B站数据...", "info"))
            try:
                collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
                bili_data = collector.collect_keyword_data(
                    keyword, max_pages=bili_max_pages, comments_per_video=bili_comments)
                self.message_queue.put(("activity",
                    f"  ✓ B站: {bili_data['total_videos']}视频, {bili_data['total_comments']}评论", "result"))
            except Exception as e:
                self.message_queue.put(("activity", f"  ❌ B站采集失败: {e}", "error"))

        if use_tieba:
            self.message_queue.put(("activity", "正在采集贴吧数据...", "info"))
            try:
                collector = TiebaCollector(self.config.get_tieba_cookie_str())
                tieba_data = collector.collect_keyword_data(
                    keyword, max_pages=tieba_max_pages, replies_per_post=tieba_replies)
                self.message_queue.put(("activity",
                    f"  ✓ 贴吧: {tieba_data['total_posts']}帖子, {tieba_data['total_replies']}回复", "result"))
            except Exception as e:
                self.message_queue.put(("activity", f"  ❌ 贴吧采集失败: {e}", "error"))

        return bili_data, tieba_data

    def _traditional_collect_single_video(self, video_input):
        """传统模式：单视频采集（回退用）"""
        bvid = BilibiliCollector.resolve_bvid(video_input)
        if not bvid:
            self.message_queue.put(("activity", f"  ❌ 无法解析BV号: {video_input}", "error"))
            return None
        self.message_queue.put(("activity", f"正在获取视频信息: {bvid}...", "info"))
        try:
            collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
            info = collector.get_video_info(bvid)
            self.message_queue.put(("activity",
                f"  ✓ 视频: 《{info['title'][:30]}》 播放:{info['play']}", "result"))
            self.message_queue.put(("activity", "正在获取评论...", "info"))
            comments = []
            for page in range(1, 4):
                try:
                    page_comments = collector.get_video_comments(info["aid"], page=page, ps=20)
                    if not page_comments:
                        break
                    comments.extend(page_comments)
                    if len(comments) >= 60:
                        break
                except Exception:
                    break
            self.message_queue.put(("activity", f"  ✓ 获取到 {len(comments)} 条评论", "result"))
            return {
                "videos": [info],
                "comments": comments,
                "video_info": info,
                "total_videos": 1,
                "total_comments": len(comments),
            }
        except Exception as e:
            self.message_queue.put(("activity", f"  ❌ 视频采集失败: {e}", "error"))
            return None

    def _traditional_collect_bili_overview(self, keyword):
        """传统模式：B站概览采集（回退用）"""
        bili_max_pages = int(self.bili_pages_s.get())
        bili_comments = int(self.bili_comments_s.get())
        self.message_queue.put(("activity", "正在搜索B站相关视频...", "info"))
        try:
            collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
            bili_data = collector.collect_keyword_data(
                keyword, max_pages=bili_max_pages, comments_per_video=bili_comments)
            self.message_queue.put(("activity",
                f"  ✓ B站: {bili_data['total_videos']}视频, {bili_data['total_comments']}评论", "result"))
            return bili_data
        except Exception as e:
            self.message_queue.put(("activity", f"  ❌ B站采集失败: {e}", "error"))
            return None

    def _format_tool_call_desc(self, name, args):
        """格式化工具调用描述"""
        if name == "search_bilibili":
            return f"搜索B站「{args.get('keyword', '?')}」(第{args.get('page', 1)}页)"
        elif name == "get_bilibili_comments":
            return f"获取B站评论(av{args.get('aid', '?')}, 限{args.get('limit', 20)}条)"
        elif name == "get_video_info":
            return f"获取视频详情({args.get('bvid', '?')})"
        elif name == "search_tieba":
            return f"搜索贴吧「{args.get('keyword', '?')}」(第{args.get('page', 1)}页)"
        elif name == "get_tieba_replies":
            return f"获取贴吧回复(帖子{args.get('post_id', '?')})"
        return f"{name}({args})"

    # ========== UI 更新 ==========

    def _log(self, msg, level="info"):
        """写入设置页运行日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{timestamp}] ", "time")
        self.log_text.insert("end", f"{msg}\n", level)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _activity(self, prefix, text, tag="info"):
        """写入主页 LLM 活动日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_text.config(state="normal")
        self.activity_text.insert("end", f"[{timestamp}] ", "time")
        self.activity_text.insert("end", f"{prefix} {text}\n" if prefix else f"{text}\n", tag)
        self.activity_text.see("end")
        self.activity_text.config(state="disabled")

    def _clear_activity(self):
        """清空活动日志"""
        self.activity_text.config(state="normal")
        self.activity_text.delete("1.0", "end")
        self.activity_text.config(state="disabled")

    def _set_status(self, text):
        """更新状态栏"""
        self.status_var.set(text)

    def _set_report(self, text):
        """设置报告内容"""
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", text)
        self.report_text.config(state="disabled")

    def _clear_data(self):
        """清空采集数据"""
        self.bilibili_data = None
        self.tieba_data = None
        self.analysis_report = ""
        self.bili_tree.delete(*self.bili_tree.get_children())
        self.bili_comment_tree.delete(*self.bili_comment_tree.get_children())
        self.tieba_tree.delete(*self.tieba_tree.get_children())
        self.tieba_reply_tree.delete(*self.tieba_reply_tree.get_children())
        self._set_report("")

    def _populate_bilibili_data(self):
        """填充 B站数据到表格"""
        if not self.bilibili_data:
            return
        for i, v in enumerate(self.bilibili_data.get("videos", [])):
            tag = "even" if i % 2 == 0 else "odd"
            self.bili_tree.insert("", "end", values=(
                v.get("title", "")[:50], v.get("author", ""), v.get("play", 0),
                v.get("like", 0), v.get("reply", 0), v.get("favorites", 0),
                v.get("pubdate", "")), tags=(tag,))
        for i, c in enumerate(self.bilibili_data.get("comments", [])):
            tag = "even" if i % 2 == 0 else "odd"
            self.bili_comment_tree.insert("", "end", values=(
                c.get("user", ""), c.get("content", "")[:100],
                c.get("like", 0), c.get("ctime", "")), tags=(tag,))

    def _populate_tieba_data(self):
        """填充贴吧数据到表格"""
        if not self.tieba_data:
            return
        for i, p in enumerate(self.tieba_data.get("posts", [])):
            tag = "even" if i % 2 == 0 else "odd"
            self.tieba_tree.insert("", "end", values=(
                p.get("title", "")[:50], p.get("bar", ""), p.get("author", ""),
                p.get("reply_count", 0), p.get("date", "")), tags=(tag,))
        for i, r in enumerate(self.tieba_data.get("replies", [])):
            tag = "even" if i % 2 == 0 else "odd"
            self.tieba_reply_tree.insert("", "end", values=(
                r.get("user", ""), r.get("content", "")[:100],
                r.get("floor", ""), r.get("time", "")), tags=(tag,))

    def _export_report(self):
        """导出分析报告"""
        if not self.analysis_report:
            self._log("暂无分析报告", "warning")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"声呐报告_{self.current_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        )
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# 关键词「{self.current_keyword}」舆情分析报告\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                f.write(self.analysis_report)
            self._log(f"报告已保存: {filename}", "success")
            self._show_toast("报告已导出", "success")

    def _export_data(self):
        """导出采集数据为 JSON"""
        if not self.bilibili_data and not self.tieba_data:
            self._log("暂无采集数据", "warning")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")],
            initialfile=f"声呐数据_{self.current_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        if filename:
            data = {
                "keyword": self.current_keyword,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bilibili": self.bilibili_data,
                "tieba": self.tieba_data,
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log(f"数据已保存: {filename}", "success")
            self._show_toast("数据已导出", "success")

    # ========== 消息队列轮询 ==========

    def _poll_queue(self):
        """轮询消息队列，处理 UI 更新"""
        try:
            while True:
                msg_type, *msg_parts = self.message_queue.get_nowait()

                if msg_type == "log":
                    msg_data = msg_parts[0] if msg_parts else ""
                    level = msg_parts[1] if len(msg_parts) > 1 else "info"
                    self._log(msg_data, level)

                elif msg_type == "activity":
                    prefix = msg_parts[0] if msg_parts else ""
                    text = msg_parts[1] if len(msg_parts) > 1 else ""
                    tag = msg_parts[2] if len(msg_parts) > 2 else "info"
                    self._activity("", f"{prefix} {text}" if text else prefix, tag)

                elif msg_type == "status":
                    self._set_status(f"● {msg_parts[0]}")

                elif msg_type == "report":
                    self._set_report(msg_parts[0])

                elif msg_type == "data_ready":
                    platform = msg_parts[0]
                    if platform == "bilibili":
                        self._populate_bilibili_data()
                    elif platform == "tieba":
                        self._populate_tieba_data()

                elif msg_type == "cookie_result":
                    platform = msg_parts[0]
                    result = msg_parts[1]
                    if isinstance(result, dict):
                        if platform == "bilibili":
                            self.bili_sessdata.delete(0, "end")
                            self.bili_sessdata.insert(0, result.get("SESSDATA", ""))
                            self.bili_jct.delete(0, "end")
                            self.bili_jct.insert(0, result.get("bili_jct", ""))
                            self.bili_dedeuid.delete(0, "end")
                            self.bili_dedeuid.insert(0, result.get("DedeUserID", ""))
                            self._log("B站Cookie获取成功！", "success")
                            self._show_toast("B站Cookie获取成功", "success")
                        elif platform == "tieba":
                            self.tieba_bduss.delete(0, "end")
                            self.tieba_bduss.insert(0, result.get("BDUSS", ""))
                            self.tieba_stoken.delete(0, "end")
                            self.tieba_stoken.insert(0, result.get("STOKEN", ""))
                            self._log("贴吧Cookie获取成功！", "success")
                            self._show_toast("贴吧Cookie获取成功", "success")
                    elif result is None:
                        name = "B站" if platform == "bilibili" else "贴吧"
                        self._log(f"未找到{name}Cookie，请确保浏览器已登录{name}", "error")
                        messagebox.showwarning("提示", f"未找到{name}Cookie。\n请确保浏览器已登录{name}后重试。")
                    else:
                        name = "B站" if platform == "bilibili" else "贴吧"
                        self._log(f"{name}Cookie获取出错: {result}", "error")

                elif msg_type == "done":
                    self._analyzing = False
                    self.analyze_btn.config(state="normal", text="🚀  一键分析")
                    self.clear_btn.config(state="normal")
                    status = msg_parts[0] if msg_parts else ""
                    if status == "complete":
                        self._set_status("● 完成")
                    elif status == "error":
                        self._set_status("● 出错")

        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    app = AnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
