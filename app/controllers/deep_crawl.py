import json
import time
import re
import tornado.web
import requests
from html import unescape
from app.controllers.admin import AdminBaseHandler
from app.models.watch_source import WatchSourceRepository, WatchDataRepository
from app.models.ai_model import AIModelRepository


def _crawl_page(url, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _extract_text(html):
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text[:8000]
    return text


def _ai_summarize(full_text, title):
    model = AIModelRepository.get_default()
    if not model:
        return None, None, None, None, None

    prompt = f"""请分析以下文章内容，返回JSON格式（不要任何其他文字）：
{{
    "summary": "100字以内的内容摘要",
    "keywords": "5个以内的关键词，逗号分隔",
    "category": "文章分类(如:科技/财经/教育/军事/娱乐/体育/社会/其他)",
    "sentiment": "情感倾向(正面/负面/中性)",
    "entities": "提到的主要人物/机构/地名，逗号分隔"
}}

标题：{title}
正文：{full_text[:3000]}
"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
        response = client.chat.completions.create(
            model=model["model_name"],
            messages=[{"role": "user", "content": prompt}],
            extra_body={"thinking": {"type": "enabled"}}
        )
        reply = response.choices[0].message.content
        if reply is None:
            return None, None, None, None, None
        reply = reply.strip()
        if reply.startswith("```"):
            reply = re.sub(r'^```\w*\n?', '', reply)
            reply = re.sub(r'\n?```$', '', reply)
        result = json.loads(reply)
        return (
            result.get("summary"),
            result.get("keywords"),
            result.get("category"),
            result.get("sentiment"),
            result.get("entities")
        )
    except Exception:
        try:
            response = client.chat.completions.create(
                model=model["model_name"],
                messages=[{"role": "user", "content": prompt}]
            )
            reply = response.choices[0].message.content
            if reply is None:
                return None, None, None, None, None
            reply = reply.strip()
            if reply.startswith("```"):
                reply = re.sub(r'^```\w*\n?', '', reply)
                reply = re.sub(r'\n?```$', '', reply)
            result = json.loads(reply)
            return (
                result.get("summary"),
                result.get("keywords"),
                result.get("category"),
                result.get("sentiment"),
                result.get("entities")
            )
        except Exception:
            return None, None, None, None, None


class DeepCrawlSingleHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        data_id = self.get_body_argument("data_id", "")
        if not data_id or not data_id.isdigit():
            return self.write({"success": False, "message": "参数错误"})

        data_id = int(data_id)
        data = WatchDataRepository.get_by_id(data_id)
        if not data:
            return self.write({"success": False, "message": "数据不存在"})
        if not data.get("url"):
            return self.write({"success": False, "message": "该条数据无URL链接"})

        result = self._do_deep_crawl(data_id, data)
        self.write(result)

    def _do_deep_crawl(self, data_id, data):
        t0 = time.time()
        logs = []

        def log(action, message, status="info"):
            logs.append({"action": action, "message": message, "status": status})
            WatchDataRepository.add_log(data_id, action, message, status)

        log("start", f"开始深度采集: {data.get('title','')[:50]}")
        WatchDataRepository.update_deep_crawl_status(data_id, 1)

        try:
            html = _crawl_page(data["url"])
            log("fetch", f"页面抓取成功，原始大小 {len(html)} 字符")

            full_text = _extract_text(html)
            word_count = len(full_text)
            reading_time = max(1, word_count // 300)
            log("extract", f"正文提取完成，字数: {word_count}，预估阅读时间: {reading_time}分钟")

            ai_summary = None
            keywords = None
            category = None
            sentiment = None
            entities = None

            if word_count > 20:
                log("ai_start", "开始AI智能分析...")
                ai_summary, keywords, category, sentiment, entities = _ai_summarize(
                    full_text, data.get("title", "")
                )
                if ai_summary:
                    log("ai_done", f"AI分析完成: 分类={category}, 情感={sentiment}")
                else:
                    log("ai_skip", "AI分析跳过或失败，保留原始内容", "warning")

            duration = round(time.time() - t0, 2)
            WatchDataRepository.save_detail(
                data_id, full_content=full_text, ai_summary=ai_summary,
                keywords=keywords, category=category, sentiment=sentiment,
                entities=entities, reading_time=f"{reading_time}分钟",
                word_count=word_count, crawl_duration=duration
            )
            WatchDataRepository.update_deep_crawl_status(data_id, 2)
            log("done", f"深度采集完成，耗时 {duration}秒", "success")

            return {
                "success": True,
                "message": f"深度采集完成！耗时 {duration}秒",
                "data": {
                    "word_count": word_count,
                    "reading_time": f"{reading_time}分钟",
                    "ai_summary": ai_summary,
                    "keywords": keywords,
                    "category": category,
                    "sentiment": sentiment,
                    "entities": entities,
                    "duration": duration,
                    "logs": logs
                }
            }

        except requests.exceptions.Timeout:
            WatchDataRepository.update_deep_crawl_status(data_id, 3)
            log("error", "请求超时", "error")
            return {"success": False, "message": "请求超时，请重试"}
        except requests.exceptions.RequestException as e:
            WatchDataRepository.update_deep_crawl_status(data_id, 3)
            log("error", f"网络错误: {str(e)[:100]}", "error")
            return {"success": False, "message": f"网络错误: {str(e)[:100]}"}
        except Exception as e:
            WatchDataRepository.update_deep_crawl_status(data_id, 3)
            log("error", f"采集异常: {str(e)[:100]}", "error")
            return {"success": False, "message": f"采集异常: {str(e)[:100]}"}


class DeepCrawlBatchHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids_str = self.get_body_argument("ids", "")
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        if not ids:
            return self.write({"success": False, "message": "请选择数据"})

        WatchDataRepository.add_log(0, "batch_start", f"开始批量深度采集，共 {len(ids)} 条")

        results = []
        success_count = 0
        fail_count = 0
        skip_count = 0

        for did in ids:
            data = WatchDataRepository.get_by_id(did)
            if not data:
                skip_count += 1
                results.append({"id": did, "status": "skip", "message": "数据不存在"})
                continue
            if not data.get("url"):
                skip_count += 1
                results.append({"id": did, "status": "skip", "message": "无URL"})
                continue
            if data.get("deep_crawl_status") == 2:
                skip_count += 1
                results.append({"id": did, "status": "skip", "message": "已采集"})
                continue

            t0 = time.time()
            WatchDataRepository.add_log(did, "process", f"处理后 ID={did}")
            try:
                html = _crawl_page(data["url"])
                full_text = _extract_text(html)
                word_count = len(full_text)
                reading_time = max(1, word_count // 300)

                ai_summary = keywords = category = sentiment = entities = None
                if word_count > 20:
                    ai_summary, keywords, category, sentiment, entities = _ai_summarize(
                        full_text, data.get("title", "")
                    )

                duration = round(time.time() - t0, 2)
                WatchDataRepository.save_detail(
                    did, full_content=full_text, ai_summary=ai_summary,
                    keywords=keywords, category=category, sentiment=sentiment,
                    entities=entities, reading_time=f"{reading_time}分钟",
                    word_count=word_count, crawl_duration=duration
                )
                WatchDataRepository.update_deep_crawl_status(did, 2)
                WatchDataRepository.add_log(did, "done", f"完成，{word_count}字，{duration}秒", "success")
                success_count += 1
                results.append({"id": did, "status": "success", "word_count": word_count, "duration": duration})
            except Exception as e:
                WatchDataRepository.update_deep_crawl_status(did, 3)
                WatchDataRepository.add_log(did, "error", str(e)[:100], "error")
                fail_count += 1
                results.append({"id": did, "status": "fail", "message": str(e)[:100]})

        stats = WatchDataRepository.get_stats()
        WatchDataRepository.add_log(0, "batch_end", f"批量完成: 成功{success_count} 失败{fail_count} 跳过{skip_count}", "success")

        self.write({
            "success": True,
            "message": f"批量深度采集完成！成功: {success_count}, 失败: {fail_count}, 跳过: {skip_count}",
            "data": {
                "success_count": success_count,
                "fail_count": fail_count,
                "skip_count": skip_count,
                "results": results,
                "stats": stats
            }
        })


class DeepCrawlStatsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        stats = WatchDataRepository.get_stats()
        logs = WatchDataRepository.get_logs(30)
        self.write({"success": True, "data": {"stats": stats, "logs": logs}})


class DeepCrawlDetailHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        data_id = self.get_argument("data_id", "")
        if not data_id or not data_id.isdigit():
            return self.write({"success": False, "message": "参数错误"})
        detail = WatchDataRepository.get_detail(int(data_id))
        if detail:
            self.write({"success": True, "data": detail})
        else:
            self.write({"success": False, "message": "未找到深度采集内容"})
