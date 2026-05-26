import json
from app.models.db import get_connection


class SentimentRepository:

    @staticmethod
    def create_analysis(title, analysis_type='comprehensive', data_source=None,
                        prompt=None, result=None, risk_level='low', risk_score=0,
                        keywords=None, summary=None, model_used=None, tokens_used=0,
                        status='completed'):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO sentiment_analysis (title, analysis_type, data_source,
                   prompt, result, risk_level, risk_score, keywords, summary,
                   model_used, tokens_used, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (title, analysis_type, data_source, prompt, result,
                 risk_level, risk_score, keywords, summary, model_used, tokens_used,
                 status)
            )
            return cursor.lastrowid

    @staticmethod
    def get_analyses(page=1, per_page=20):
        offset = (page - 1) * per_page
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM sentiment_analysis").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM sentiment_analysis ORDER BY create_at DESC LIMIT ? OFFSET ?",
                (per_page, offset)
            ).fetchall()
            return [dict(r) for r in rows], total

    @staticmethod
    def get_analysis_by_id(analysis_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sentiment_analysis WHERE id = ?", (analysis_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_recent_analyses(limit=5):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sentiment_analysis ORDER BY create_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def delete_analysis(analysis_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM sentiment_reports WHERE analysis_id = ?", (analysis_id,))
            conn.execute("DELETE FROM sentiment_analysis WHERE id = ?", (analysis_id,))
            return True

    @staticmethod
    def get_risk_distribution():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT risk_level, COUNT(*) as cnt FROM sentiment_analysis GROUP BY risk_level"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_report(analysis_id=None, report_type='daily', title='', content=None, chart_data=None):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO sentiment_reports (analysis_id, report_type, title, content, chart_data)
                   VALUES (?,?,?,?,?)""",
                (analysis_id, report_type, title, content, chart_data)
            )
            return cursor.lastrowid

    @staticmethod
    def get_reports(page=1, per_page=20):
        offset = (page - 1) * per_page
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM sentiment_reports").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM sentiment_reports ORDER BY create_at DESC LIMIT ? OFFSET ?",
                (per_page, offset)
            ).fetchall()
            return [dict(r) for r in rows], total

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_conversations = conn.execute("SELECT COUNT(*) FROM conversation_history").fetchone()[0]
            total_messages = conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0]
            total_watch = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()[0]
            total_models = conn.execute("SELECT COUNT(*) FROM ai_models WHERE status=1").fetchone()[0]
            total_analyses = conn.execute("SELECT COUNT(*) FROM sentiment_analysis").fetchone()[0]

            high_risk = conn.execute(
                "SELECT COUNT(*) FROM sentiment_analysis WHERE risk_level='high'"
            ).fetchone()[0]
            medium_risk = conn.execute(
                "SELECT COUNT(*) FROM sentiment_analysis WHERE risk_level='medium'"
            ).fetchone()[0]
            low_risk = conn.execute(
                "SELECT COUNT(*) FROM sentiment_analysis WHERE risk_level='low'"
            ).fetchone()[0]

            daily_conversations = conn.execute(
                "SELECT COUNT(*) FROM conversation_history WHERE date(create_at)=date('now')"
            ).fetchone()[0]
            daily_watch = conn.execute(
                "SELECT COUNT(*) FROM watch_data WHERE date(create_at)=date('now')"
            ).fetchone()[0]

            recent_keywords = conn.execute(
                "SELECT keywords FROM sentiment_analysis WHERE keywords IS NOT NULL ORDER BY create_at DESC LIMIT 20"
            ).fetchall()

            return {
                "total_users": total_users,
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "total_watch": total_watch,
                "total_models": total_models,
                "total_analyses": total_analyses,
                "high_risk": high_risk,
                "medium_risk": medium_risk,
                "low_risk": low_risk,
                "daily_conversations": daily_conversations,
                "daily_watch": daily_watch,
                "recent_keywords": [r[0] for r in recent_keywords if r[0]]
            }

    @staticmethod
    def get_trend_data():
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT date(create_at) as day,
                       COUNT(*) as cnt
                   FROM conversation_history
                   WHERE create_at >= date('now','-6 days')
                   GROUP BY date(create_at) ORDER BY day"""
            ).fetchall()
            chat_days = {r['day']: r['cnt'] for r in rows}

            rows = conn.execute(
                """SELECT date(create_at) as day,
                       COUNT(*) as cnt
                   FROM watch_data
                   WHERE create_at >= date('now','-6 days')
                   GROUP BY date(create_at) ORDER BY day"""
            ).fetchall()
            watch_days = {r['day']: r['cnt'] for r in rows}

            rows = conn.execute(
                """SELECT date(create_at) as day,
                       COUNT(*) as cnt
                   FROM sentiment_analysis
                   WHERE create_at >= date('now','-6 days')
                   GROUP BY date(create_at) ORDER BY day"""
            ).fetchall()
            analysis_days = {r['day']: r['cnt'] for r in rows}

            import datetime
            days = []
            chat_data = []
            watch_data_list = []
            analysis_data = []
            for i in range(6, -1, -1):
                d = datetime.date.today() - datetime.timedelta(days=i)
                ds = d.isoformat()
                days.append((d.month, d.day))
                chat_data.append(chat_days.get(ds, 0))
                watch_data_list.append(watch_days.get(ds, 0))
                analysis_data.append(analysis_days.get(ds, 0))

            return {
                "days": [f"{m}/{d}" for m, d in days],
                "chat": chat_data,
                "watch": watch_data_list,
                "analysis": analysis_data
            }

    @staticmethod
    def get_user_activity():
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT date(cm.create_at) as day,
                       COUNT(*) as msg_count,
                       COUNT(DISTINCT ch.user_id) as user_count
                   FROM conversation_messages cm
                   LEFT JOIN conversation_history ch ON cm.conversation_id = ch.id
                   WHERE cm.create_at >= date('now', '-6 days')
                   GROUP BY date(cm.create_at) ORDER BY day"""
            ).fetchall()
            import datetime
            result = {"days": [], "messages": [], "users": []}
            day_map = {r['day']: r for r in rows}
            for i in range(6, -1, -1):
                d = datetime.date.today() - datetime.timedelta(days=i)
                ds = d.isoformat()
                result["days"].append(f"{d.month}/{d.day}")
                r = day_map.get(ds, {})
                result["messages"].append(r.get("msg_count", 0) if isinstance(r, dict) else 0)
                result["users"].append(r.get("user_count", 0) if isinstance(r, dict) else 0)
            return result

    @staticmethod
    def get_top_keywords(limit=10):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT keyword, COUNT(*) as cnt
                   FROM watch_data
                   WHERE keyword IS NOT NULL AND keyword != ''
                   GROUP BY keyword ORDER BY cnt DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [{"keyword": r['keyword'], "count": r['cnt']} for r in rows]

    @staticmethod
    def get_model_usage():
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT ch.model_id, am.name, COUNT(*) as call_count
                   FROM conversation_history ch
                   LEFT JOIN ai_models am ON ch.model_id = am.id
                   WHERE ch.model_id IS NOT NULL
                   GROUP BY ch.model_id ORDER BY call_count DESC"""
            ).fetchall()
            result = []
            for r in rows:
                name = r['name'] or f"模型#{r['model_id']}"
                result.append({"model_id": r['model_id'], "name": name, "count": r['call_count']})
            return result
