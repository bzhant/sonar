"""Cookie 自动获取模块 - 从浏览器提取 B站/贴吧 Cookie"""
import webbrowser


def get_bilibili_cookies():
    """
    尝试从已登录的浏览器中提取 B站 Cookie。
    支持 Chrome / Edge / Firefox。
    返回 dict（含 SESSDATA, bili_jct, DedeUserID）或 None。
    """
    try:
        import browser_cookie3 as bc
    except ImportError:
        return None

    for loader_name in ("chrome", "edge", "firefox"):
        loader = getattr(bc, loader_name, None)
        if loader is None:
            continue
        try:
            cj = loader(domain_name="bilibili.com")
            cookies = {c.name: c.value for c in cj if c.name in ("SESSDATA", "bili_jct", "DedeUserID")}
            if cookies.get("SESSDATA"):
                return cookies
        except Exception:
            continue
    return None


def get_tieba_cookies():
    """
    尝试从已登录的浏览器中提取贴吧 Cookie。
    返回 dict（含 BDUSS, STOKEN）或 None。
    """
    try:
        import browser_cookie3 as bc
    except ImportError:
        return None

    for loader_name in ("chrome", "edge", "firefox"):
        loader = getattr(bc, loader_name, None)
        if loader is None:
            continue
        try:
            cj = loader(domain_name="tieba.baidu.com")
            cookies = {c.name: c.value for c in cj if c.name in ("BDUSS", "STOKEN")}
            if cookies.get("BDUSS"):
                return cookies
        except Exception:
            continue
    return None


def open_bilibili_login():
    """打开 B站登录页面"""
    webbrowser.open("https://passport.bilibili.com/login")


def open_tieba_login():
    """打开贴吧登录页面"""
    webbrowser.open("https://tieba.baidu.com/index/tbwise/login")


def is_browser_cookie3_available():
    """检查 browser_cookie3 是否可用"""
    try:
        import browser_cookie3  # noqa: F401
        return True
    except ImportError:
        return False
