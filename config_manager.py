"""配置管理模块 - 存储 Cookie、LLM API 设置等"""
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "bilibili": {
        "cookies": {
            "SESSDATA": "",
            "bili_jct": "",
            "DedeUserID": ""
        }
    },
    "tieba": {
        "cookies": {
            "BDUSS": "",
            "STOKEN": ""
        }
    },
    "llm": {
        "api_base": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat"
    },
    "collect": {
        "bilibili_max_pages": 2,
        "bilibili_comments_per_video": 30,
        "tieba_max_pages": 3,
        "tieba_replies_per_post": 20
    }
}


class ConfigManager:
    """管理应用配置的加载和保存"""

    def __init__(self):
        self.config = {}
        self.load()

    def load(self):
        """从文件加载配置，不存在则用默认配置"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.config = self._deep_copy(DEFAULT_CONFIG)
        else:
            self.config = self._deep_copy(DEFAULT_CONFIG)

    def save(self):
        """保存配置到文件"""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get(self, *keys, default=None):
        """嵌套获取配置值，如 config.get('bilibili', 'cookies', 'SESSDATA')"""
        value = self.config
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def set(self, *keys_and_value):
        """嵌套设置配置值，如 config.set('bilibili', 'cookies', 'SESSDATA', 'xxx')"""
        *keys, value = keys_and_value
        d = self.config
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value

    def get_bilibili_cookie_str(self):
        """获取 B站 Cookie 字符串"""
        cookies = self.get("bilibili", "cookies", default={})
        parts = []
        for k, v in cookies.items():
            if v:
                parts.append(f"{k}={v}")
        return "; ".join(parts)

    def get_tieba_cookie_str(self):
        """获取贴吧 Cookie 字符串"""
        cookies = self.get("tieba", "cookies", default={})
        parts = []
        for k, v in cookies.items():
            if v:
                parts.append(f"{k}={v}")
        return "; ".join(parts)

    def is_bilibili_configured(self):
        return bool(self.get("bilibili", "cookies", "SESSDATA"))

    def is_tieba_configured(self):
        return bool(self.get("tieba", "cookies", "BDUSS"))

    def is_llm_configured(self):
        return bool(self.get("llm", "api_key"))

    @staticmethod
    def _deep_copy(d):
        return json.loads(json.dumps(d))
