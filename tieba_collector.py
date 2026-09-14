"""贴吧数据采集模块 - 搜索帖子、获取回复"""
import re
import time
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 相邻两次请求的最小间隔（秒），降低触发反爬的概率
MIN_REQUEST_INTERVAL = 1.0


class TiebaCollector:
    """贴吧数据采集器"""

    def __init__(self, cookie_str=""):
        self.cookie_str = cookie_str
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if cookie_str:
            self.session.headers["Cookie"] = cookie_str
        self.min_request_interval = MIN_REQUEST_INTERVAL
        self._last_request_ts = 0.0

    def _get(self, url, params=None):
        """限流 GET 并返回 BeautifulSoup 对象；检测到安全验证页时抛出异常"""
        wait = self._last_request_ts + self.min_request_interval - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.time()
        resp = self.session.get(url, params=params, timeout=15)
        resp.encoding = "utf-8"
        if "安全验证" in resp.text:
            raise Exception("贴吧返回安全验证页（疑似触发反爬），请降低采集频率或配置登录Cookie后重试")
        return BeautifulSoup(resp.text, "html.parser")

    # ========== 搜索帖子 ==========

    def search_posts(self, keyword, page=1):
        """
        全吧搜索帖子
        :param keyword: 搜索关键词
        :param page: 页码
        :return: 帖子信息列表
        """
        url = "https://tieba.baidu.com/f/search/res"
        params = {
            "ie": "utf-8",
            "qw": keyword,
            "pn": page,
        }
        soup = self._get(url, params=params)

        results = []
        posts = soup.find_all("div", class_="s_post")
        for post in posts:
            try:
                # 标题和链接
                title_tag = post.find("span", class_="p_title").find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                # 提取帖子 ID
                post_id = ""
                match = re.search(r"/p/(\d+)", href)
                if match:
                    post_id = match.group(1)

                # 内容摘要
                content_tag = post.find("div", class_="p_content")
                content = content_tag.get_text(strip=True) if content_tag else ""

                # 所属贴吧
                bar_tag = post.find("span", class_="p_forum").find("a") if post.find("span", class_="p_forum") else None
                bar_name = bar_tag.get_text(strip=True) if bar_tag else ""

                # 作者
                author_tag = post.find("a", class_="p_author_name")
                author = author_tag.get_text(strip=True) if author_tag else ""

                # 日期
                date_tag = post.find("span", class_="p_date")
                date_str = date_tag.get_text(strip=True) if date_tag else ""

                # 回复数
                reply_tag = post.find("span", class_="p_reply")
                reply_count = 0
                if reply_tag:
                    reply_text = reply_tag.get_text(strip=True)
                    nums = re.findall(r"\d+", reply_text)
                    if nums:
                        reply_count = int(nums[0])

                results.append({
                    "platform": "tieba",
                    "type": "post",
                    "id": post_id,
                    "title": title,
                    "content": content,
                    "bar": bar_name,
                    "author": author,
                    "reply_count": reply_count,
                    "date": date_str,
                    "url": f"https://tieba.baidu.com/p/{post_id}" if post_id else href,
                })
            except Exception as e:
                print(f"[贴吧] 解析帖子失败: {e}")
                continue
        return results

    # ========== 获取帖子详情和回复 ==========

    def get_post_replies(self, post_id, max_pages=2):
        """
        获取帖子内容和回复
        :param post_id: 帖子 ID
        :param max_pages: 最多翻页数
        :return: dict with "title", "content", "replies"
        """
        title = ""
        main_content = ""
        all_replies = []

        for page in range(1, max_pages + 1):
            try:
                url = f"https://tieba.baidu.com/p/{post_id}"
                params = {"pn": page}
                soup = self._get(url, params=params)

                # 标题
                if not title:
                    title_tag = soup.find("h3", class_="core_title_txt")
                    title = title_tag.get_text(strip=True) if title_tag else ""

                # 所有楼层
                posts = soup.find_all("div", class_="l_post")
                for post in posts:
                    try:
                        # 作者
                        author_tag = post.find("ul", class_="p_author")
                        author = ""
                        if author_tag:
                            name_tag = author_tag.find("a", class_="p_author_name")
                            author = name_tag.get_text(strip=True) if name_tag else ""

                        # 楼层内容
                        content_tag = post.find("div", class_="d_post_content")
                        content = content_tag.get_text(strip=True) if content_tag else ""

                        # 楼层号
                        floor_tag = post.find("div", class_="post-tail-wrap")
                        floor = 0
                        if floor_tag:
                            floor_span = floor_tag.find("span", class_="tail-info")
                            if floor_span:
                                nums = re.findall(r"\d+", floor_span.get_text())
                                if nums:
                                    floor = int(nums[0])

                        # 时间
                        time_tag = post.find("span", class_="tail-info")
                        time_str = ""
                        if time_tag:
                            time_text = time_tag.get_text(strip=True)
                            if re.match(r"\d{4}-\d{2}-\d{2}", time_text):
                                time_str = time_text

                        if content:
                            if not main_content and floor == 1:
                                main_content = content
                            else:
                                all_replies.append({
                                    "platform": "tieba",
                                    "type": "reply",
                                    "id": post_id,
                                    "user": author,
                                    "content": content,
                                    "floor": floor,
                                    "time": time_str,
                                })
                    except Exception:
                        continue

                time.sleep(0.5)
            except Exception as e:
                print(f"[贴吧] 获取帖子{post_id}第{page}页失败: {e}")
                break

        return {
            "title": title,
            "content": main_content,
            "replies": all_replies,
            "reply_count": len(all_replies),
        }

    # ========== 浏览某贴吧 ==========

    def get_bar_posts(self, bar_name, page=1):
        """
        获取某个贴吧的帖子列表
        :param bar_name: 贴吧名
        :param page: 页码
        :return: 帖子列表
        """
        url = f"https://tieba.baidu.com/f"
        params = {
            "kw": bar_name,
            "ie": "utf-8",
            "pn": page,
        }
        soup = self._get(url, params=params)

        results = []
        # 贴吧帖子列表在 class="tl_shadow" 的 li 中
        threads = soup.find_all("li", class_="j_thread_list")
        for thread in threads:
            try:
                title_tag = thread.find("a", class_="j_th_tit")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                post_id = ""
                match = re.search(r"/p/(\d+)", href)
                if match:
                    post_id = match.group(1)

                # 作者
                author_tag = thread.find("span", class_="tb_icon_author")
                author = ""
                if author_tag:
                    author = author_tag.get("title", "").replace("主题作者: ", "")

                # 摘要
                abstract_tag = thread.find("div", class_="threadlist_abs")
                content = abstract_tag.get_text(strip=True) if abstract_tag else ""

                # 回复数
                reply_tag = thread.find("span", class_="threadlist_rep_num")
                reply_count = 0
                if reply_tag:
                    nums = re.findall(r"\d+", reply_tag.get_text())
                    if nums:
                        reply_count = int(nums[0])

                # 日期
                date_tag = thread.find("span", class_="threadlist_reply_date")
                date_str = date_tag.get_text(strip=True) if date_tag else ""

                results.append({
                    "platform": "tieba",
                    "type": "post",
                    "id": post_id,
                    "title": title,
                    "content": content,
                    "bar": bar_name,
                    "author": author,
                    "reply_count": reply_count,
                    "date": date_str,
                    "url": f"https://tieba.baidu.com/p/{post_id}" if post_id else "",
                })
            except Exception:
                continue
        return results

    # ========== 综合采集 ==========

    def collect_keyword_data(self, keyword, max_pages=3, replies_per_post=20):
        """
        综合采集某关键词的数据：搜索帖子 + 获取热门帖子回复
        :return: dict with "posts" and "replies"
        """
        all_posts = []
        all_replies = []

        for page in range(1, max_pages + 1):
            try:
                posts = self.search_posts(keyword, page=page)
                if not posts:
                    break
                all_posts.extend(posts)
                time.sleep(0.5)
            except Exception as e:
                print(f"[贴吧] 搜索第{page}页失败: {e}")
                break

        # 对回复数最多的帖子采集回复
        top_posts = sorted(all_posts, key=lambda x: x.get("reply_count", 0), reverse=True)[:3]
        replies_needed = replies_per_post
        for post in top_posts:
            if replies_needed <= 0 or not post.get("id"):
                break
            try:
                max_pages_replies = 1 if replies_needed <= 20 else 2
                detail = self.get_post_replies(post["id"], max_pages=max_pages_replies)
                all_replies.extend(detail["replies"])
                replies_needed -= len(detail["replies"])
                time.sleep(0.5)
            except Exception as e:
                print(f"[贴吧] 获取帖子{post['id']}回复失败: {e}")

        return {
            "posts": all_posts,
            "replies": all_replies,
            "total_posts": len(all_posts),
            "total_replies": len(all_replies),
        }
