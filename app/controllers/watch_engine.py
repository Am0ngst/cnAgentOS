import json
import re
import tornado.web
import urllib.parse
import requests
from html import unescape
from app.controllers.admin import AdminBaseHandler
from app.models.watch_source import WatchSourceRepository, WatchDataRepository


class WatchCollectHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = WatchSourceRepository.get_all(status=1)
        self.render("admin/watch_collect.html",
                    title="瞭望采集",
                    username=self.current_user.decode('utf-8'),
                    active_menu="watch_collect",
                    sources=sources)


class WatchSourceManageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = WatchSourceRepository.get_all()
        self.write({"success": True, "data": sources})

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        if action == "create":
            name = self.get_body_argument("name", "").strip()
            code = self.get_body_argument("code", "").strip()
            source_type = self.get_body_argument("source_type", "web").strip()
            url_template = self.get_body_argument("url_template", "").strip()
            page_param = self.get_body_argument("page_param", "").strip() or None
            headers_json = self.get_body_argument("headers_json", "").strip() or None
            cookies = self.get_body_argument("cookies", "").strip() or None
            sort_order = int(self.get_body_argument("sort_order", "0"))
            if not name or not code or not url_template:
                return self.write({"success": False, "message": "必填项不能为空"})
            sid = WatchSourceRepository.create(name, code, source_type, url_template,
                                                page_param, headers_json, cookies, sort_order)
            if sid:
                self.write({"success": True, "message": "创建成功", "id": sid})
            else:
                self.write({"success": False, "message": "编码已存在"})
        elif action == "update":
            sid = self.get_body_argument("id", "")
            if not sid:
                return self.write({"success": False, "message": "参数错误"})
            kwargs = {}
            for f in ["name", "code", "source_type", "url_template", "page_param",
                      "headers_json", "cookies"]:
                v = self.get_body_argument(f, "").strip()
                if v:
                    kwargs[f] = v
            so = self.get_body_argument("sort_order", "")
            st = self.get_body_argument("status", "")
            if so:
                kwargs["sort_order"] = int(so)
            if st:
                kwargs["status"] = int(st)
            WatchSourceRepository.update(int(sid), **kwargs)
            self.write({"success": True, "message": "更新成功"})
        elif action == "delete":
            sid = self.get_body_argument("id", "")
            if not sid:
                return self.write({"success": False, "message": "参数错误"})
            WatchSourceRepository.delete(int(sid))
            self.write({"success": True, "message": "删除成功"})
        elif action == "toggle":
            sid = self.get_body_argument("id", "")
            status = int(self.get_body_argument("status", "1"))
            WatchSourceRepository.update(int(sid), status=status)
            self.write({"success": True, "message": "状态已更新"})


class WatchExecuteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        keyword = self.get_body_argument("keyword", "").strip()
        source_ids = self.get_body_argument("source_ids", "").strip()
        page_count = int(self.get_body_argument("page_count", "1"))

        if not keyword or not source_ids:
            return self.write({"success": False, "message": "请输入关键词并选择采集源"})

        ids = [int(x) for x in source_ids.split(",") if x.strip().isdigit()]
        if not ids:
            return self.write({"success": False, "message": "请选择采集源"})

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://www.baidu.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
        })

        try:
            session.get('https://www.baidu.com/', timeout=10)
        except Exception:
            pass

        total_collected = 0
        debug_info = []
        for sid in ids:
            source = WatchSourceRepository.get_by_id(sid)
            if not source or not source.get("status"):
                continue

            for page in range(page_count):
                pn_value = page * 10
                url = source["url_template"].replace("{keyword}", urllib.parse.quote(keyword))
                pparam = source.get("page_param") or "pn"
                if "{" + pparam + "}" in url:
                    url = url.replace("{" + pparam + "}", str(pn_value))
                elif "{pn}" in url:
                    url = url.replace("{pn}", str(pn_value))

                try:
                    resp = session.get(url, timeout=15, allow_redirects=True)
                    try:
                        resp.encoding = resp.apparent_encoding or 'utf-8'
                    except Exception:
                        resp.encoding = 'utf-8'
                    html = resp.text
                    html_len = len(html)

                    debug_info.append(f"第{page+1}页: HTTP {resp.status_code}, 内容 {html_len} 字节")

                    title_count = html.count('<a ')
                    link_count = html.count('href="http')
                    debug_info.append(f"  包含 {title_count} 个<a>标签, {link_count} 个外链")

                    if "baidu" in source["code"].lower():
                        items = _parse_baidu_news_v2(html)
                        if not items:
                            items = _parse_generic_all(html)
                    else:
                        items = _parse_generic_all(html)

                    debug_info.append(f"  解析到 {len(items)} 条")

                    if items:
                        count = WatchDataRepository.save_batch(
                            sid, keyword, page + 1, items, source["name"]
                        )
                        total_collected += count
                        debug_info.append(f"  入库 {count} 条")
                except Exception as e:
                    debug_info.append(f"  异常: {str(e)[:150]}")
                    self.write({
                        "success": False,
                        "message": f"采集失败({source['name']}): {str(e)[:200]}",
                        "debug": debug_info
                    })
                    return

        self.write({
            "success": True,
            "message": f"采集完成，共采集 {total_collected} 条数据",
            "total": total_collected,
            "debug": debug_info
        })


def _clean_title(text):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'<em[^>]*>|</em>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = text.replace('&amp;', '&').replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _clean_url(url):
    url = url.replace('&amp;', '&')
    if url.startswith('//'):
        url = 'https:' + url
    return url


def _parse_baidu_news_v2(html):
    items = []
    seen_urls = set()

    strategies = [
        (r'<a[^>]*href="(https?://[^"]*baidu\.com/link\?[^"]*)"[^>]*>(.*?)</a>', 'baidu_link'),
        (r'<h3[^>]*>.*?<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>', 'h3_a'),
        (r'<div[^>]*class="[^"]*result[^"]*"[^>]*>.*?<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>', 'result'),
        (r'<a[^>]*href="(https?://(?!.*baidu\.com)[^"]*)"[^>]*>(.*?)</a>', 'external_link'),
    ]

    for pattern_str, _ in strategies:
        if len(items) >= 30:
            break
        pattern = re.compile(pattern_str, re.DOTALL | re.IGNORECASE)
        for url, title_raw in pattern.findall(html):
            title = _clean_title(title_raw)
            url = _clean_url(url)
            if not title or not url:
                continue
            if len(title) < 6:
                continue
            if 'baidu.com' in title:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            items.append({"title": title[:200], "url": url, "summary": ""})
            if len(items) >= 30:
                break

    if not items:
        items = _extract_all_links(html, seen_urls)

    return items


def _extract_all_links(html, seen_urls=None):
    if seen_urls is None:
        seen_urls = set()
    items = []
    pattern = re.compile(
        r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE
    )
    for url, title_raw in pattern.findall(html):
        title = _clean_title(title_raw)
        url = _clean_url(url)
        if not title or not url:
            continue
        if len(title) < 8:
            continue
        if 'baidu.com' in url:
            continue
        skip_words = ['下一页', '上一页', '首页', '末页', '搜索', '百度', '登录', '注册',
                      '更多', '查看', '点击', '详细', '帮助', '关于', '设为首页', '收藏',
                      'document', 'window', 'javascript', 'function']
        if any(w in title for w in skip_words):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append({"title": title[:200], "url": url, "summary": ""})
        if len(items) >= 30:
            break
    return items


def _parse_generic_all(html):
    return _extract_all_links(html)


class WatchDataHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        keyword = self.get_argument("keyword", "").strip()
        source_id = self.get_argument("source_id", "").strip()
        per_page = 20

        data_list, total = WatchDataRepository.get_page(
            page, per_page, keyword=keyword or None,
            source_id=int(source_id) if source_id.isdigit() else None
        )
        total_pages = (total + per_page - 1) // per_page
        sources = WatchSourceRepository.get_all()

        self.render("admin/watch_data.html",
                    title="数据仓库",
                    username=self.current_user.decode('utf-8'),
                    active_menu="watch_data",
                    data_list=data_list,
                    sources=sources,
                    page=page,
                    total_pages=total_pages,
                    total=total,
                    keyword=keyword,
                    source_id=source_id)


class WatchDataDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        did = self.get_body_argument("id", "")
        if did:
            WatchDataRepository.delete(int(did))
            self.write({"success": True, "message": "删除成功"})
        else:
            self.write({"success": False, "message": "参数错误"})


class WatchDataBatchDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids_str = self.get_body_argument("ids", "")
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        if ids:
            count = WatchDataRepository.batch_delete(ids)
            self.write({"success": True, "message": f"已删除 {count} 条数据"})
        else:
            self.write({"success": False, "message": "请选择数据"})
