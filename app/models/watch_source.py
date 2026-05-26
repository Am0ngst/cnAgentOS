import json
from app.models.db import get_connection


class WatchSourceRepository:

    @staticmethod
    def get_all(status=None):
        with get_connection() as conn:
            sql = "SELECT * FROM watch_sources WHERE 1=1"
            params = []
            if status is not None:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY sort_order ASC, id ASC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(source_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM watch_sources WHERE id = ?", (source_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create(name, code, source_type, url_template, page_param=None,
               headers_json=None, cookies=None, sort_order=0):
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    """INSERT INTO watch_sources (name, code, source_type,
                       url_template, page_param, headers_json, cookies, sort_order)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (name, code, source_type, url_template, page_param,
                     headers_json, cookies, sort_order)
                )
                return cursor.lastrowid
        except Exception:
            return None

    @staticmethod
    def update(source_id, **kwargs):
        if not kwargs:
            return True
        with get_connection() as conn:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            params = list(kwargs.values()) + [source_id]
            conn.execute(f"UPDATE watch_sources SET {sets} WHERE id = ?", params)
            return True

    @staticmethod
    def delete(source_id):
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM watch_sources WHERE id = ?", (source_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_headers(source_id):
        src = WatchSourceRepository.get_by_id(source_id)
        if src and src.get("headers_json"):
            try:
                return json.loads(src["headers_json"])
            except Exception:
                pass
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class WatchDataRepository:

    @staticmethod
    def save_batch(source_id, keyword, page, items, source_name=""):
        with get_connection() as conn:
            count = 0
            for item in items:
                conn.execute(
                    """INSERT INTO watch_data (source_id, keyword, page, title, url, summary, source_name)
                       VALUES (?,?,?,?,?,?,?)""",
                    (source_id, keyword, page,
                     item.get("title", ""), item.get("url", ""),
                     item.get("summary", ""), source_name)
                )
                count += 1
            return count

    @staticmethod
    def get_page(page=1, per_page=20, keyword=None, source_id=None):
        offset = (page - 1) * per_page
        with get_connection() as conn:
            sql = "SELECT * FROM watch_data WHERE 1=1"
            params = []
            if keyword:
                sql += " AND keyword LIKE ?"
                params.append(f"%{keyword}%")
            if source_id:
                sql += " AND source_id = ?"
                params.append(source_id)
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            total = conn.execute(count_sql, params).fetchone()[0]
            sql += " ORDER BY collect_at DESC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows], total

    @staticmethod
    def delete(data_id):
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM watch_data WHERE id = ?", (data_id,))
            return cursor.rowcount > 0

    @staticmethod
    def batch_delete(ids):
        if not ids:
            return 0
        with get_connection() as conn:
            placeholders = ",".join("?" for _ in ids)
            cursor = conn.execute(
                f"DELETE FROM watch_data WHERE id IN ({placeholders})", ids
            )
            return cursor.rowcount

    @staticmethod
    def get_by_id(data_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM watch_data WHERE id = ?", (data_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_ids(data_ids):
        if not data_ids:
            return []
        with get_connection() as conn:
            ph = ",".join("?" for _ in data_ids)
            rows = conn.execute(
                f"SELECT * FROM watch_data WHERE id IN ({ph})", data_ids
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_deep_crawl_status(data_id, status):
        with get_connection() as conn:
            conn.execute(
                "UPDATE watch_data SET deep_crawl_status = ?, deep_crawl_at = datetime('now') WHERE id = ?",
                (status, data_id)
            )
            return True

    @staticmethod
    def save_detail(data_id, full_content=None, ai_summary=None, keywords=None,
                    category=None, sentiment=None, entities=None,
                    reading_time=None, word_count=0, crawl_duration=0):
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO watch_data_detail
                   (data_id, full_content, ai_summary, keywords, category,
                    sentiment, entities, reading_time, word_count, crawl_duration)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (data_id, full_content, ai_summary, keywords, category,
                 sentiment, entities, reading_time, word_count, crawl_duration)
            )
            return True

    @staticmethod
    def get_detail(data_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM watch_data_detail WHERE data_id = ?", (data_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def add_log(data_id, action, message, status="info", duration=0):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO deep_crawl_log (data_id, action, message, status, duration)
                   VALUES (?,?,?,?,?)""",
                (data_id, action, message, status, duration)
            )
            return True

    @staticmethod
    def get_logs(limit=50):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM deep_crawl_log ORDER BY create_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()[0]
            deep_done = conn.execute(
                "SELECT COUNT(*) FROM watch_data WHERE deep_crawl_status = 2"
            ).fetchone()[0]
            deep_pending = conn.execute(
                "SELECT COUNT(*) FROM watch_data WHERE deep_crawl_status = 0"
            ).fetchone()[0]
            deep_failed = conn.execute(
                "SELECT COUNT(*) FROM watch_data WHERE deep_crawl_status = 3"
            ).fetchone()[0]
            return {
                "total": total,
                "deep_done": deep_done,
                "deep_pending": deep_pending,
                "deep_failed": deep_failed,
                "progress_percent": round(deep_done / total * 100, 1) if total > 0 else 0
            }
