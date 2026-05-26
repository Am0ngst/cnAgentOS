import json
import tornado.web
import tornado.gen
import urllib.request
from app.controllers.admin import AdminBaseHandler
from app.models.sentiment_repository import SentimentRepository
from app.models.ai_model import AIModelRepository
from app.models.db import get_connection


class EarthTextureProxyHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        urls = [
            'https://raw.githubusercontent.com/apache/echarts-examples/refs/heads/gh-pages/public/data-gl/asset/earth.jpg',
            'https://echarts.apache.org/examples/data-gl/asset/earth.jpg'
        ]
        img = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=15)
                img = resp.read()
                if len(img) > 1000:
                    break
            except Exception:
                continue
        if img:
            self.set_header('Content-Type', 'image/jpeg')
            self.set_header('Cache-Control', 'public, max-age=86400')
            self.write(img)
        else:
            self.set_status(404)
            self.write({'error': 'earth texture not available'})


class SentimentDashboardHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/sentiment_dashboard.html",
                    title="数智大屏",
                    username=self.current_user.decode('utf-8'),
                    active_menu="sentiment_dashboard")


class SentimentStatsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        stats = SentimentRepository.get_stats()
        stats["trend"] = SentimentRepository.get_trend_data()
        stats["user_activity"] = SentimentRepository.get_user_activity()
        stats["top_keywords"] = SentimentRepository.get_top_keywords(10)
        stats["model_usage"] = SentimentRepository.get_model_usage()
        self.write({"success": True, "data": stats})


class SentimentAnalysisPageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        per_page = 20
        analyses, total = SentimentRepository.get_analyses(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        self.render("admin/sentiment_analysis.html",
                    title="智能舆情",
                    username=self.current_user.decode('utf-8'),
                    active_menu="sentiment_analysis",
                    analyses=analyses,
                    page=page,
                    total_pages=total_pages,
                    total=total)


class SentimentAnalysisListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        per_page = 20
        analyses, total = SentimentRepository.get_analyses(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        self.write({"success": True, "data": analyses, "total": total, "total_pages": total_pages})


class SentimentAnalysisDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        analysis_id = self.get_body_argument("id", "")
        if not analysis_id:
            return self.write({"success": False, "message": "参数错误"})
        SentimentRepository.delete_analysis(int(analysis_id))
        self.write({"success": True, "message": "删除成功"})


class SentimentAIAnalyzeHandler(AdminBaseHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        analyze_type = self.get_argument("type", "comprehensive")
        model_id = self.get_argument("model_id", "")

        model = AIModelRepository.get_default()
        if model_id:
            m = AIModelRepository.get_by_id(int(model_id))
            if m:
                model = m
        if not model:
            self.set_status(400)
            self.write("data: " + json.dumps({"error": "没有可用模型"}, ensure_ascii=False) + "\n\n")
            self.finish()
            return

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("X-Accel-Buffering", "no")

        system_prompt = self._build_prompt(analyze_type)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])

            analysis_title_map = {
                "comprehensive": "综合舆情分析",
                "chat": "用户对话风险分析",
                "watch": "瞭望数据趋势分析",
                "risk": "风险预警评估"
            }
            title = analysis_title_map.get(analyze_type, "智慧舆情分析")

            analysis_id = SentimentRepository.create_analysis(
                title=title,
                analysis_type=analyze_type,
                prompt=system_prompt,
                model_used=model["name"],
                status="processing"
            )

            stream = client.chat.completions.create(
                model=model["model_name"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "请开始分析"}
                ],
                stream=True,
                extra_body={"thinking": {"type": "enabled"}}
            )

            full_content = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                    data = json.dumps({"content": delta.content, "analysis_id": analysis_id},
                                      ensure_ascii=False)
                    self.write(f"data: {data}\n\n")
                    self.flush()

            risk_level, risk_score, keywords, summary = self._parse_result(full_content)

            with get_connection() as conn:
                conn.execute(
                    """UPDATE sentiment_analysis SET result=?, risk_level=?, risk_score=?,
                       keywords=?, summary=?, status='completed' WHERE id=?""",
                    (full_content, risk_level, risk_score, keywords, summary, analysis_id)
                )

            self.write("data: [DONE]\n\n")
            self.flush()
        except Exception as e:
            err_msg = str(e)
            err = json.dumps({"error": err_msg}, ensure_ascii=False)
            self.write(f"data: {err}\n\n")
            self.flush()
            try:
                if 'analysis_id' in dir():
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE sentiment_analysis SET status='failed', result=? WHERE id=?",
                            (err_msg, analysis_id)
                        )
            except Exception:
                pass
        self.finish()

    def _build_prompt(self, analyze_type):
        with get_connection() as conn:
            chat_count = conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0]
            user_count = conn.execute("SELECT COUNT(*) FROM conversation_history").fetchone()[0]

            recent_msgs = conn.execute(
                "SELECT cm.role, cm.content FROM conversation_messages cm ORDER BY cm.create_at DESC LIMIT 30"
            ).fetchall()

            watch_count = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()[0]
            watch_keywords = conn.execute(
                "SELECT keyword, COUNT(*) as cnt FROM watch_data GROUP BY keyword ORDER BY cnt DESC LIMIT 10"
            ).fetchall()

            deep_crawl = conn.execute(
                "SELECT COUNT(*) FROM watch_data WHERE deep_crawl_status=1"
            ).fetchone()[0]

        chat_samples = "\n".join([
            f"[{r['role']}]: {r['content'][:200]}" for r in recent_msgs
        ]) if recent_msgs else "暂无对话数据"

        watch_info = "\n".join([
            f"  关键词「{r['keyword']}」: 采集 {r['cnt']} 条" for r in watch_keywords
        ]) if watch_keywords else "  暂无瞭望数据"

        base_prompt = f"""你是一个专业的智慧舆情分析系统。请根据以下系统数据进行分析。

## 系统数据概览
- 总用户对话数: {user_count}
- 总消息条数: {chat_count}
- 瞭望采集数据: {watch_count} 条
- 深度采集数据: {deep_crawl} 条

## 近期对话样本
{chat_samples}

## 瞭望关键词分布
{watch_info}
"""

        prompts = {
            "comprehensive": base_prompt + """
## 分析任务
请进行全面综合的舆情分析，包括：
1. **整体态势评估**: 系统的整体运行情况
2. **热点话题识别**: 从对话和瞭望数据中识别热点话题
3. **风险指标**: 评估潜在风险
4. **趋势预测**: 对未来趋势的判断
5. **建议措施**: 给出管理建议

请以markdown格式输出，并在末尾用JSON格式标注风险等级和关键词：
```json
{"risk_level": "low|medium|high", "risk_score": 0-100, "keywords": ["关键词1","关键词2"], "summary": "一句话总结"}
```
""",
            "chat": base_prompt + """
## 分析任务
请针对用户对话数据进行风析：
1. **对话主题分布**: 用户主要在讨论什么
2. **情感倾向**: 正面/负面/中性
3. **异常行为检测**: 是否有异常对话模式
4. **用户活跃度**: 用户参与度评估

请以markdown格式输出，并在末尾用JSON格式标注风险等级和关键词：
```json
{"risk_level": "low|medium|high", "risk_score": 0-100, "keywords": ["关键词1","关键词2"], "summary": "一句话总结"}
```
""",
            "watch": base_prompt + """
## 分析任务
请针对瞭望采集数据进行分析：
1. **数据采集概况**: 采集数据的整体状况
2. **关键词趋势**: 热门关键词的变化趋势
3. **数据质量评估**: 采集数据的完整性和质量
4. **信息来源分布**: 不同来源的数据量分布

请以markdown格式输出，并在末尾用JSON格式标注风险等级和关键词：
```json
{"risk_level": "low|medium|high", "risk_score": 0-100, "keywords": ["关键词1","关键词2"], "summary": "一句话总结"}
```
""",
            "risk": base_prompt + """
## 分析任务
请进行风险预警评估：
1. **风险识别**: 识别当前存在的风险点
2. **严重程度**: 评估每个风险的严重程度
3. **影响范围**: 评估风险的潜在影响范围
4. **应急建议**: 给出风险应对建议

请以markdown格式输出，并在末尾用JSON格式标注风险等级和关键词：
```json
{"risk_level": "low|medium|high", "risk_score": 0-100, "keywords": ["关键词1","关键词2"], "summary": "一句话总结"}
```
"""
        }
        return prompts.get(analyze_type, prompts["comprehensive"])

    def _parse_result(self, text):
        risk_level = "low"
        risk_score = 0
        keywords = ""
        summary = ""
        try:
            if "```json" in text:
                json_start = text.rindex("```json") + 7
                json_end = text.index("```", json_start)
                json_str = text[json_start:json_end].strip()
                data = json.loads(json_str)
                risk_level = data.get("risk_level", "low")
                risk_score = float(data.get("risk_score", 0))
                keywords = ",".join(data.get("keywords", []))
                summary = data.get("summary", "")
        except Exception:
            pass
        return risk_level, risk_score, keywords, summary


class SentimentChatDataHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        per_page = int(self.get_argument("per_page", 50))
        offset = (page - 1) * per_page
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0]
            rows = conn.execute(
                """SELECT cm.id, cm.conversation_id, cm.role, cm.content,
                       cm.msg_type, cm.extra, cm.create_at,
                       u.username as user_name
                   FROM conversation_messages cm
                   LEFT JOIN conversation_history ch ON cm.conversation_id = ch.id
                   LEFT JOIN users u ON ch.user_id = u.id
                   ORDER BY cm.create_at DESC LIMIT ? OFFSET ?""",
                (per_page, offset)
            ).fetchall()
            messages = [dict(r) for r in rows]
        self.write({
            "success": True,
            "data": messages,
            "total": total,
            "page": page,
            "per_page": per_page
        })


class SentimentWatchDataHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        per_page = int(self.get_argument("per_page", 50))
        offset = (page - 1) * per_page
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()[0]
            rows = conn.execute(
                """SELECT id, keyword, source_url, title, content,
                       status, deep_crawl_status, create_at
                   FROM watch_data
                   ORDER BY create_at DESC LIMIT ? OFFSET ?""",
                (per_page, offset)
            ).fetchall()
            watch_items = [dict(r) for r in rows]
        self.write({
            "success": True,
            "data": watch_items,
            "total": total,
            "page": page,
            "per_page": per_page
        })
