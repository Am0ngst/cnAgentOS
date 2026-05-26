import sqlite3
from app.models.db import get_connection


class AIModelRepository:

    @staticmethod
    def get_all(status=None):
        with get_connection() as conn:
            sql = "SELECT * FROM ai_models WHERE 1=1"
            params = []
            if status is not None:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY is_default DESC, id ASC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(model_id):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM ai_models WHERE id = ?", (model_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_default():
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM ai_models WHERE is_default = 1 AND status = 1 LIMIT 1").fetchone()
            return dict(row) if row else None

    @staticmethod
    def create(name, code, api_key, base_url, model_name, description=None, is_default=0):
        try:
            with get_connection() as conn:
                if is_default:
                    conn.execute("UPDATE ai_models SET is_default = 0")
                cursor = conn.execute(
                    "INSERT INTO ai_models (name, code, api_key, base_url, model_name, description, is_default) VALUES (?,?,?,?,?,?,?)",
                    (name, code, api_key, base_url, model_name, description, is_default)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    @staticmethod
    def update(model_id, name=None, code=None, api_key=None, base_url=None, model_name=None, description=None, is_default=None, status=None):
        try:
            with get_connection() as conn:
                if is_default:
                    conn.execute("UPDATE ai_models SET is_default = 0")
                updates, params = [], []
                for field, val in [("name", name), ("code", code), ("api_key", api_key),
                                   ("base_url", base_url), ("model_name", model_name),
                                   ("description", description), ("is_default", is_default), ("status", status)]:
                    if val is not None:
                        updates.append(f"{field} = ?")
                        params.append(val)
                if not updates:
                    return True
                params.append(model_id)
                conn.execute(f"UPDATE ai_models SET {', '.join(updates)} WHERE id = ?", params)
                return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete(model_id):
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM ai_models WHERE id = ?", (model_id,))
            return cursor.rowcount > 0

    @staticmethod
    def set_default(model_id):
        with get_connection() as conn:
            conn.execute("UPDATE ai_models SET is_default = 0")
            conn.execute("UPDATE ai_models SET is_default = 1 WHERE id = ?", (model_id,))
            return True

    @staticmethod
    def add_token_log(model_id, prompt_tokens, completion_tokens):
        total = prompt_tokens + completion_tokens
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO token_logs (model_id, prompt_tokens, completion_tokens, total_tokens) VALUES (?,?,?,?)",
                (model_id, prompt_tokens, completion_tokens, total)
            )
            conn.execute(
                "UPDATE ai_models SET total_tokens = total_tokens + ?, total_calls = total_calls + 1 WHERE id = ?",
                (total, model_id)
            )

    @staticmethod
    def get_token_stats(model_id):
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT strftime('%Y-%m-%d', create_at) as day,
                       SUM(prompt_tokens) as prompt_tokens,
                       SUM(completion_tokens) as completion_tokens,
                       SUM(total_tokens) as total_tokens,
                       COUNT(*) as calls
                FROM token_logs WHERE model_id = ?
                GROUP BY day ORDER BY day DESC LIMIT 7
                """,
                (model_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_page(page=1, per_page=6):
        offset = (page - 1) * per_page
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM ai_models").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM ai_models ORDER BY is_default DESC, id ASC LIMIT ? OFFSET ?",
                (per_page, offset)
            ).fetchall()
            return [dict(r) for r in rows], total
