"""B站数据采集模块 - 搜索视频、获取评论、WBI签名"""
import time
import hashlib
import urllib.parse
from datetime import datetime

import requests

# WBI 签名用的重排索引表
WBI_MIXIN_TABLE = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    60, 6, 55, 56, 0, 43, 30, 37, 9, 20, 44, 62, 57, 38, 1, 45,
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    60, 6, 55, 56, 0, 43, 30, 37, 9, 20, 44, 62, 57, 38, 1, 45,
]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT = 15  # 所有请求的超时时间（秒），防止线程被挂起的请求卡死

# WBI 密钥每日轮换，缓存超过该时长后重新获取
WBI_CACHE_TTL = 12 * 3600

# 相邻两次请求的最小间隔（秒），降低触发风控的概率
MIN_REQUEST_INTERVAL = 0.6

# 风控返回码：-412/-509 为接口返回，412/509 为 HTTP 状态码
RISK_CONTROL_CODES = (-412, 412, -509, 509)

# 触发风控后的退避基数（秒），按尝试次数递增
RISK_BACKOFF_BASE = 2


class BilibiliCollector:
    """B站数据采集器"""

    def __init__(self, cookie_str=""):
        self.cookie_str = cookie_str
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if cookie_str:
            self.session.headers["Cookie"] = cookie_str
        self._wbi_keys = None  # 缓存 wbi img_key 和 sub_key
        self._wbi_keys_time = 0.0  # 密钥获取时间，用于过期判断
        self.min_request_interval = MIN_REQUEST_INTERVAL
        self._last_request_ts = 0.0

    # ========== 请求基础设施 ==========

    def _get(self, url, params=None):
        """限流 GET：保证相邻请求不小于最小间隔"""
        wait = self._last_request_ts + self.min_request_interval - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.time()
        return self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)

    def _get_json(self, url, params=None, retries=2):
        """GET 并解析 JSON；触发风控返回码时按指数退避重试。返回原始 data dict（调用方检查 code）"""
        last = {"code": -1, "message": "未知错误"}
        for attempt in range(retries + 1):
            resp = self._get(url, params)
            if resp.status_code in (412, 509):
                last = {"code": resp.status_code, "message": "HTTP状态码异常（疑似风控拦截）"}
            else:
                try:
                    last = resp.json()
                except ValueError:
                    last = {"code": -1, "message": "响应不是有效JSON"}
            if last.get("code") == 0:
                return last
            if last.get("code") in RISK_CONTROL_CODES and attempt < retries:
                time.sleep(RISK_BACKOFF_BASE * (attempt + 1))
                continue
            break
        return last

    # ========== WBI 签名 ==========

    def _get_wbi_keys(self):
        """从导航接口获取 img_key 和 sub_key"""
        if self._wbi_keys and time.time() - self._wbi_keys_time < WBI_CACHE_TTL:
            return self._wbi_keys
        data = self._get_json("https://api.bilibili.com/x/web-interface/nav", retries=1)
        if data.get("code") != 0:
            raise Exception(f"获取WBI密钥失败: {data.get('message', '未知错误')}")
        img_url = data["data"]["wbi_img"]["img_url"]
        sub_url = data["data"]["wbi_img"]["sub_url"]
        img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
        sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
        self._wbi_keys = (img_key, sub_key)
        self._wbi_keys_time = time.time()
        return self._wbi_keys

    def _invalidate_wbi_keys(self):
        """清空缓存的 WBI 密钥（密钥可能已轮换）"""
        self._wbi_keys = None
        self._wbi_keys_time = 0.0

    def _get_mixin_key(self, raw_key):
        """用重排表生成 mixin_key"""
        return "".join(raw_key[i] for i in WBI_MIXIN_TABLE)[:32]

    def _sign_wbi(self, params):
        """对请求参数进行 WBI 签名，返回带 w_rid 和 wts 的新参数字典"""
        img_key, sub_key = self._get_wbi_keys()
        mixin_key = self._get_mixin_key(img_key + sub_key)
        wts = int(time.time())
        params["wts"] = wts
        # 按 key 排序后拼接
        sorted_params = sorted(params.items())
        query = urllib.parse.urlencode(sorted_params)
        w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
        params["w_rid"] = w_rid
        return params

    # ========== 搜索视频 ==========

    def search_videos(self, keyword, page=1, order="totalrank"):
        """
        按关键词搜索视频
        :param keyword: 搜索关键词
        :param page: 页码
        :param order: 排序方式 totalrank/pubdate/play/review/dm
        :return: 视频信息列表
        """
        url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
        for attempt in range(2):
            params = self._sign_wbi({
                "search_type": "video",
                "keyword": keyword,
                "page": page,
                "order": order,
                "page_size": 20,
            })
            data = self._get_json(url, params)
            if data.get("code") == 0:
                break
            if attempt == 0:
                # 签名失败可能是 WBI 密钥已轮换，刷新后重试一次（风控退避已在 _get_json 内处理）
                self._invalidate_wbi_keys()
                continue
            raise Exception(f"B站搜索失败: {data.get('message', '未知错误')}")

        results = []
        for item in data.get("data", {}).get("result", []):
            # 清理标题中的 <em class="keyword"> 高亮标签
            title = item.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
            results.append({
                "platform": "bilibili",
                "type": "video",
                "id": item.get("bvid", ""),
                "aid": item.get("aid", 0),
                "title": title,
                "description": item.get("description", ""),
                "author": item.get("author", ""),
                "mid": item.get("mid", 0),
                "play": item.get("play", 0),
                "danmaku": item.get("video_review", 0),
                "favorites": item.get("favorites", 0),
                "like": item.get("like", 0),
                "coin": item.get("coin", 0),
                "share": item.get("share", 0),
                "reply": item.get("review", 0),
                "pubdate": datetime.fromtimestamp(item.get("pubdate", 0)).strftime("%Y-%m-%d %H:%M") if item.get("pubdate") else "",
                "tag": item.get("tag", ""),
                "cover": item.get("pic", ""),
                "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
            })
        return results

    # ========== 获取视频评论 ==========

    def get_video_comments(self, aid, page=1, ps=20, sort=0):
        """
        获取视频评论
        :param aid: 视频 av 号
        :param page: 页码
        :param ps: 每页数量
        :param sort: 排序方式 0=按时间, 2=按热度
        :return: 评论列表
        """
        params = {
            "type": 1,
            "oid": aid,
            "pn": page,
            "ps": ps,
            "sort": sort,
        }
        url = "https://api.bilibili.com/x/v2/reply"
        data = self._get_json(url, params)

        if data.get("code") != 0:
            if data.get("code") in RISK_CONTROL_CODES:
                raise Exception(f"获取评论被风控拦截(code {data.get('code')})，请降低频率或配置Cookie后重试")
            # 评论区可能关闭等其他情况，返回空列表
            return []

        replies = data.get("data", {}).get("replies") or []
        results = []
        for reply in replies:
            member = reply.get("member", {})
            content = reply.get("content", {})
            results.append({
                "platform": "bilibili",
                "type": "comment",
                "id": reply.get("rpid", 0),
                "user": member.get("uname", ""),
                "content": content.get("message", ""),
                "like": reply.get("like", 0),
                "reply_count": reply.get("rcount", 0),
                "ctime": datetime.fromtimestamp(reply.get("ctime", 0)).strftime("%Y-%m-%d %H:%M") if reply.get("ctime") else "",
            })
        return results

    # ========== 获取视频详情 ==========

    @staticmethod
    def resolve_bvid(input_str):
        """
        从用户输入中提取 BV号。
        支持格式: BV1xx411c7mD / https://www.bilibili.com/video/BV1xx411c7mD / b23.tv短链
        返回 BV号字符串，无法解析时返回 None
        """
        import re
        if not input_str:
            return None
        input_str = input_str.strip()
        # 直接匹配 BV号 (BV后跟10位字母数字)
        match = re.search(r'(BV[0-9a-zA-Z]{10})', input_str)
        if match:
            return match.group(1)
        # av号转BV号太复杂，直接返回None让上层处理
        av_match = re.search(r'av(\d+)', input_str)
        if av_match:
            return av_match.group(0)  # 返回 av123456 格式，get_video_info 会处理
        return None

    def get_video_info(self, bvid):
        """
        获取单个视频详情（标题、简介、标签、UP主、统计数据等）
        :param bvid: BV号 或 av号字符串
        :return: 视频详情 dict
        """
        # 判断是 BV 还是 av
        if bvid.startswith("BV"):
            params = {"bvid": bvid}
        else:
            # av123456 → 123456
            aid = bvid.replace("av", "")
            params = {"aid": aid}

        url = "https://api.bilibili.com/x/web-interface/view"
        data = self._get_json(url, params)

        if data.get("code") != 0:
            raise Exception(f"获取视频详情失败: {data.get('message', '未知错误')}")

        d = data["data"]
        stat = d.get("stat", {})
        owner = d.get("owner", {})

        # 获取标签
        tags = []
        try:
            tag_url = "https://api.bilibili.com/x/tag/archive/tags"
            tag_params = {"bvid": bvid} if bvid.startswith("BV") else {"aid": bvid.replace("av", "")}
            tag_resp = self._get(tag_url, params=tag_params)
            tag_data = tag_resp.json()
            if tag_data.get("code") == 0:
                tags = [t.get("tag_name", "") for t in tag_data.get("data", [])]
        except Exception:
            pass

        return {
            "platform": "bilibili",
            "type": "video_info",
            "id": d.get("bvid", ""),
            "aid": d.get("aid", 0),
            "title": d.get("title", ""),
            "description": d.get("desc", ""),
            "author": owner.get("name", ""),
            "mid": owner.get("mid", 0),
            "play": stat.get("view", 0),
            "danmaku": stat.get("danmaku", 0),
            "like": stat.get("like", 0),
            "coin": stat.get("coin", 0),
            "favorites": stat.get("favorite", 0),
            "share": stat.get("share", 0),
            "reply": stat.get("reply", 0),
            "pubdate": datetime.fromtimestamp(d.get("pubdate", 0)).strftime("%Y-%m-%d %H:%M") if d.get("pubdate") else "",
            "duration": d.get("duration", 0),
            "tags": tags,
            "url": f"https://www.bilibili.com/video/{d.get('bvid', '')}",
        }

    # ========== 获取热搜词 ==========

    def get_hot_searches(self):
        """获取B站热搜榜"""
        url = "https://api.bilibili.com/x/web-interface/search/square"
        data = self._get_json(url, {"limit": 20})
        if data.get("code") != 0:
            return []
        return [item.get("keyword", "") for item in data.get("data", {}).get("trending", {}).get("list", [])]

    # ========== 综合采集 ==========

    def collect_keyword_data(self, keyword, max_pages=2, comments_per_video=30):
        """
        综合采集某关键词的数据：搜索视频 + 获取热门视频评论
        :return: dict with "videos" and "comments"
        """
        all_videos = []
        all_comments = []

        for page in range(1, max_pages + 1):
            try:
                videos = self.search_videos(keyword, page=page)
                if not videos:
                    break
                all_videos.extend(videos)
                time.sleep(0.5)  # 避免请求过快
            except Exception as e:
                print(f"[B站] 搜索第{page}页失败: {e}")
                break

        # 对播放量最高的几个视频采集评论
        top_videos = sorted(all_videos, key=lambda x: x.get("play", 0), reverse=True)[:5]
        comments_needed = comments_per_video
        for video in top_videos:
            if comments_needed <= 0:
                break
            try:
                page = 1
                ps = min(comments_needed, 20)
                comments = self.get_video_comments(video["aid"], page=page, ps=ps)
                all_comments.extend(comments)
                comments_needed -= len(comments)
                time.sleep(0.3)
            except Exception as e:
                print(f"[B站] 获取视频{video['id']}评论失败: {e}")

        return {
            "videos": all_videos,
            "comments": all_comments,
            "total_videos": len(all_videos),
            "total_comments": len(all_comments),
        }
