# 声呐 Sonar 📡

LLM 驱动的 B站 & 贴吧舆情分析工具。接入任意 OpenAI 兼容 API，LLM 通过**函数调用（Function Calling）自主决定采集哪些数据**，最终生成结构化舆情分析报告。

## 功能特性

### 三种分析模式

| 模式 | 说明 |
|------|------|
| 🔍 关键词综合分析 | 输入关键词，LLM 自主搜索 B站视频、抓取评论、检索贴吧帖子，综合分析双平台舆情 |
| 📹 单视频深度分析 | 输入 BV号 / 视频链接，深度分析该视频评论区的**舆论偏向、情绪偏向、主要观点** |
| 📊 B站相关视频概览 | 输入关键词，搜索全站相关视频，LLM 逐个总结每个视频的**观点与情绪倾向**，形成整体舆论图景 |

### 核心能力

- **LLM 自主采集**：通过 OpenAI Function Calling，LLM 像Agent一样自主调用采集工具（搜索、抓评论、查视频详情），按需决定数据量
- **双平台支持**：B站（搜索 / 评论 / 视频详情）+ 贴吧（搜索 / 回复），无需手动爬虫配置
- **自动 Cookie**：一键从本机浏览器提取 B站 / 贴吧 Cookie（基于 browser_cookie3）
- **传统模式回退**：API 不支持函数调用时，自动回退为固定流程采集 + 单轮总结
- **报告导出**：分析报告、原始数据均可导出为文件
- **双 GUI 版本**：
  - `main.py` — Tkinter 暗色主题界面
  - `main_qt.py` — PySide6 苹果质感界面（浅色卡片风格）

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

> Tkinter 版无需 PySide6；运行 `main_qt.py` 需要完整依赖。

### 运行

```bash
# Tkinter 暗色版
python main.py

# PySide6 苹果质感版
python main_qt.py
```

### 配置

1. 打开应用 → **设置页**
2. 填入任意 **OpenAI 兼容 API**（内置预设：DeepSeek / 通义千问 / OpenAI / Moonshot）：
   - API 地址（如 `https://api.deepseek.com/v1`）
   - API Key
   - 模型名（如 `deepseek-chat`，需支持函数调用）
3. 点击「一键获取Cookie」自动从浏览器提取（需已在浏览器登录 B站），贴吧同理
4. 回到主页，选择分析模式，输入关键词或 BV号 → **一键分析**

### 打包为 exe

```bash
pyinstaller --onefile --windowed --name "声呐Sonar" main.py
```

## 项目结构

```
├── main.py               # Tkinter 主程序（暗色主题 GUI）
├── main_qt.py            # PySide6 主程序（苹果质感 GUI）
├── llm_analyzer.py       # LLM 分析核心（函数调用循环 + 三种分析模式）
├── bilibili_collector.py # B站采集（搜索/评论/视频详情，WBI签名）
├── tieba_collector.py    # 贴吧采集（搜索/回复）
├── cookie_helper.py      # 浏览器 Cookie 提取
├── config_manager.py     # 配置持久化
└── requirements.txt      # 依赖清单
```

## 注意事项

- 数据采集依赖 Cookie，评论接口对未登录用户有限制；Cookie 仅保存在本地 `config.json`（已被 .gitignore 排除，不会上传）
- 请合理控制采集频率，本项目仅供学习研究，请勿用于商业用途或恶意刷量
- LLM 分析质量取决于所配置的模型能力，推荐使用支持函数调用的模型

## License

MIT
