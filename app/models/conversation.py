import json
from app.models.db import get_connection


class ConversationRepository:

    @staticmethod
    def create(user_id, title=None, model_id=None):
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO conversation_history (user_id, title, model_id) VALUES (?,?,?)",
                (user_id, title, model_id)
            )
            return cursor.lastrowid

    @staticmethod
    def update_title(conv_id, title):
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversation_history SET title = ? WHERE id = ?",
                (title, conv_id)
            )
            return True

    @staticmethod
    def get_user_conversations(user_id, limit=50):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT ch.*, am.name as model_name
                   FROM conversation_history ch
                   LEFT JOIN ai_models am ON ch.model_id = am.id
                   WHERE ch.user_id = ?
                   ORDER BY ch.create_at DESC LIMIT ?""",
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(conv_id, user_id=None):
        with get_connection() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT * FROM conversation_history WHERE id = ? AND user_id = ?",
                    (conv_id, user_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM conversation_history WHERE id = ?", (conv_id,)
                ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def delete(conv_id, user_id=None):
        with get_connection() as conn:
            if user_id:
                conn.execute("DELETE FROM conversation_history WHERE id = ? AND user_id = ?",
                             (conv_id, user_id))
            else:
                conn.execute("DELETE FROM conversation_history WHERE id = ?", (conv_id,))
            conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conv_id,))
            return True

    @staticmethod
    def save_message(conversation_id, role, content, msg_type="text", extra=None):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO conversation_messages (conversation_id, role, content, msg_type, extra)
                   VALUES (?,?,?,?,?)""",
                (conversation_id, role, content, msg_type, json.dumps(extra, ensure_ascii=False) if extra else None)
            )
            return True

    @staticmethod
    def get_messages(conversation_id, limit=100):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY id ASC LIMIT ?",
                (conversation_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_recent_messages(conversation_id, limit=20):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM conversation_messages
                   WHERE conversation_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (conversation_id, limit)
            ).fetchall()
            result = [dict(r) for r in rows]
            result.reverse()
            return result
