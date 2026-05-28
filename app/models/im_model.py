import json
import os
from app.models.db import get_connection

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "database", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class IMContactRepository:

    @staticmethod
    def get_contacts(user_id):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT c.*, u.username
                   FROM im_contacts c
                   JOIN users u ON c.contact_id = u.id
                   WHERE c.user_id = ?
                   ORDER BY u.username""",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def is_contact(user_id, contact_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM im_contacts WHERE user_id = ? AND contact_id = ?",
                (user_id, contact_id)
            ).fetchone()
            return row is not None

    @staticmethod
    def add_contact(user_id, contact_id, remark=None):
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO im_contacts (user_id, contact_id, remark) VALUES (?,?,?)",
                    (user_id, contact_id, remark)
                )
                conn.execute(
                    "INSERT OR IGNORE INTO im_contacts (user_id, contact_id, remark) VALUES (?,?,?)",
                    (contact_id, user_id, remark)
                )
                return True
        except Exception:
            return False

    @staticmethod
    def remove_contact(user_id, contact_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM im_contacts WHERE user_id = ? AND contact_id = ?", (user_id, contact_id))
            conn.execute("DELETE FROM im_contacts WHERE user_id = ? AND contact_id = ?", (contact_id, user_id))
            return True


class IMFriendRequestRepository:

    @staticmethod
    def send_request(from_user_id, to_user_id, message=None):
        existing = IMFriendRequestRepository.get_pending(from_user_id, to_user_id)
        if existing:
            return None
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO im_friend_requests (from_user_id, to_user_id, message) VALUES (?,?,?)",
                (from_user_id, to_user_id, message)
            )
            return cursor.lastrowid

    @staticmethod
    def get_pending(from_user_id, to_user_id):
        with get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM im_friend_requests
                   WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'""",
                (from_user_id, to_user_id)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_incoming(user_id):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT r.*, u.username as from_username
                   FROM im_friend_requests r
                   JOIN users u ON r.from_user_id = u.id
                   WHERE r.to_user_id = ? AND r.status = 'pending'
                   ORDER BY r.create_at DESC""",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_outgoing(user_id):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT r.*, u.username as to_username
                   FROM im_friend_requests r
                   JOIN users u ON r.to_user_id = u.id
                   WHERE r.from_user_id = ? AND r.status = 'pending'
                   ORDER BY r.create_at DESC""",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def accept(request_id):
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_friend_requests SET status = 'accepted' WHERE id = ?",
                (request_id,)
            )
            row = conn.execute(
                "SELECT from_user_id, to_user_id FROM im_friend_requests WHERE id = ?",
                (request_id,)
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT OR IGNORE INTO im_contacts (user_id, contact_id) VALUES (?,?)",
                    (row["from_user_id"], row["to_user_id"])
                )
                conn.execute(
                    "INSERT OR IGNORE INTO im_contacts (user_id, contact_id) VALUES (?,?)",
                    (row["to_user_id"], row["from_user_id"])
                )
            return True

    @staticmethod
    def get_incoming_count(user_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM im_friend_requests WHERE to_user_id = ? AND status = 'pending'",
                (user_id,)
            ).fetchone()
            return row[0] if row else 0

    @staticmethod
    def reject(request_id):
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_friend_requests SET status = 'rejected' WHERE id = ?",
                (request_id,)
            )
            return True


class IMGroupRepository:

    @staticmethod
    def create(name, owner_id, member_ids=None):
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO im_groups (name, owner_id) VALUES (?,?)",
                (name, owner_id)
            )
            group_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO im_group_members (group_id, user_id, role) VALUES (?,?,'owner')",
                (group_id, owner_id)
            )
            if member_ids:
                for mid in member_ids:
                    try:
                        conn.execute(
                            "INSERT INTO im_group_members (group_id, user_id) VALUES (?,?)",
                            (group_id, int(mid))
                        )
                    except Exception:
                        pass
            return group_id

    @staticmethod
    def get_user_groups(user_id):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT g.*, gm.nickname
                   FROM im_groups g
                   JOIN im_group_members gm ON g.id = gm.group_id
                   WHERE gm.user_id = ?
                   ORDER BY g.id DESC""",
                (user_id,)
            ).fetchall()
            groups = []
            for r in rows:
                g = dict(r)
                member_count = conn.execute(
                    "SELECT COUNT(*) FROM im_group_members WHERE group_id = ?",
                    (g["id"],)
                ).fetchone()[0]
                g["member_count"] = member_count
                members = conn.execute(
                    """SELECT gm.*, u.username
                       FROM im_group_members gm
                       JOIN users u ON gm.user_id = u.id
                       WHERE gm.group_id = ?""",
                    (g["id"],)
                ).fetchall()
                g["members"] = [dict(m) for m in members]
                groups.append(g)
            return groups

    @staticmethod
    def get_by_id(group_id):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM im_groups WHERE id = ?", (group_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def rename_group(group_id, user_id, new_name):
        with get_connection() as conn:
            owner_check = conn.execute(
                "SELECT id FROM im_group_members WHERE group_id = ? AND user_id = ? AND role = 'owner'",
                (group_id, user_id)
            ).fetchone()
            if not owner_check:
                return False
            conn.execute(
                "UPDATE im_groups SET name = ? WHERE id = ?",
                (new_name, group_id)
            )
            return True

    @staticmethod
    def add_members(group_id, member_ids):
        with get_connection() as conn:
            for mid in member_ids:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO im_group_members (group_id, user_id) VALUES (?,?)",
                        (group_id, int(mid))
                    )
                except Exception:
                    pass
            return True

    @staticmethod
    def is_owner(group_id, user_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM im_group_members WHERE group_id = ? AND user_id = ? AND role = 'owner'",
                (group_id, user_id)
            ).fetchone()
            return row is not None

    @staticmethod
    def leave_group(group_id, user_id):
        with get_connection() as conn:
            owner_check = conn.execute(
                "SELECT id FROM im_group_members WHERE group_id = ? AND user_id = ? AND role = 'owner'",
                (group_id, user_id)
            ).fetchone()
            if owner_check:
                return False
            conn.execute(
                "DELETE FROM im_group_members WHERE group_id = ? AND user_id = ?",
                (group_id, user_id)
            )
            return True

    @staticmethod
    def disband_group(group_id, user_id):
        with get_connection() as conn:
            owner_check = conn.execute(
                "SELECT id FROM im_group_members WHERE group_id = ? AND user_id = ? AND role = 'owner'",
                (group_id, user_id)
            ).fetchone()
            if not owner_check:
                return False
            conn.execute("DELETE FROM im_group_messages WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM im_group_members WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM im_groups WHERE id = ?", (group_id,))
            return True

    @staticmethod
    def transfer_owner(group_id, from_user_id, to_user_id):
        with get_connection() as conn:
            owner_check = conn.execute(
                "SELECT id FROM im_group_members WHERE group_id = ? AND user_id = ? AND role = 'owner'",
                (group_id, from_user_id)
            ).fetchone()
            if not owner_check:
                return False
            member_check = conn.execute(
                "SELECT id FROM im_group_members WHERE group_id = ? AND user_id = ?",
                (group_id, to_user_id)
            ).fetchone()
            if not member_check:
                return False
            conn.execute(
                "UPDATE im_group_members SET role = 'member' WHERE group_id = ? AND user_id = ?",
                (group_id, from_user_id)
            )
            conn.execute(
                "UPDATE im_group_members SET role = 'owner' WHERE group_id = ? AND user_id = ?",
                (group_id, to_user_id)
            )
            return True

    @staticmethod
    def get_members(group_id):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT gm.*, u.username
                   FROM im_group_members gm
                   JOIN users u ON gm.user_id = u.id
                   WHERE gm.group_id = ?""",
                (group_id,)
            ).fetchall()
            return [dict(r) for r in rows]


class IMMessageRepository:

    @staticmethod
    def send_private(from_user_id, to_user_id, msg_type, content, file_name=None, file_size=0, file_path=None):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO im_messages (from_user_id, to_user_id, msg_type, content, file_name, file_size, file_path)
                   VALUES (?,?,?,?,?,?,?)""",
                (from_user_id, to_user_id, msg_type, content, file_name, file_size, file_path)
            )
            return cursor.lastrowid

    @staticmethod
    def send_private_employee(from_user_id, emp_alias, msg_type, content, file_name=None, file_size=0, file_path=None):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO im_messages (from_user_id, to_user_id, msg_type, content, file_name, file_size, file_path, emp_alias)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (from_user_id, 0, msg_type, content, file_name, file_size, file_path, emp_alias)
            )
            return cursor.lastrowid

    @staticmethod
    def get_employee_private_messages(user_id, emp_alias, before_id=None, limit=50):
        with get_connection() as conn:
            sql = """SELECT m.*,
                        COALESCE(fu.username, m.emp_alias) as from_username,
                        COALESCE(tu.username, m.emp_alias) as to_username
                   FROM im_messages m
                   LEFT JOIN users fu ON m.from_user_id = fu.id
                   LEFT JOIN users tu ON m.to_user_id = tu.id
                   WHERE m.emp_alias = ?
                     AND ((m.from_user_id = ?) OR (m.to_user_id = ? OR m.from_user_id = 0))"""
            params = [emp_alias, user_id, user_id]
            if before_id:
                sql += " AND m.id < ?"
                params.append(int(before_id))
            sql += " ORDER BY m.id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            result = [dict(r) for r in rows]
            result.reverse()
            return result

    @staticmethod
    def get_employee_context(user_id, emp_alias, chat_type='private', group_id=None, limit=20):
        if chat_type == 'private':
            with get_connection() as conn:
                sql = """SELECT m.*,
                            COALESCE(fu.username, m.emp_alias) as from_username
                       FROM im_messages m
                       LEFT JOIN users fu ON m.from_user_id = fu.id
                       WHERE m.emp_alias = ?
                         AND ((m.from_user_id = ?) OR (m.from_user_id = 0))
                       ORDER BY m.id DESC LIMIT ?"""
                rows = conn.execute(sql, (emp_alias, user_id, limit)).fetchall()
                result = []
                for r in reversed(rows):
                    d = dict(r)
                    if d["from_user_id"] == 0:
                        result.append({"role": "assistant", "content": d["content"]})
                    else:
                        result.append({"role": "user", "content": d["content"]})
                return result
        else:
            with get_connection() as conn:
                sql = """SELECT m.*,
                            COALESCE(u.username, m.at_employee) as from_username
                       FROM im_group_messages m
                       LEFT JOIN users u ON m.from_user_id = u.id
                       WHERE m.group_id = ? AND m.at_employee = ?
                       ORDER BY m.id DESC LIMIT ?"""
                rows = conn.execute(sql, (group_id, emp_alias, limit)).fetchall()
                result = []
                for r in reversed(rows):
                    d = dict(r)
                    if d["from_user_id"] == 0:
                        result.append({"role": "assistant", "content": d["content"]})
                    elif d["from_user_id"] == user_id:
                        result.append({"role": "user", "content": d["content"]})
                    else:
                        content = d["content"] or ""
                        if d.get("at_employee"):
                            result.append({"role": "user", "content": f"@{d['at_employee']} {content}"})
                return result

    @staticmethod
    def get_private_messages(user_id, peer_id, before_id=None, limit=50):
        with get_connection() as conn:
            sql = """SELECT m.*,
                        fu.username as from_username,
                        tu.username as to_username
                   FROM im_messages m
                   JOIN users fu ON m.from_user_id = fu.id
                   JOIN users tu ON m.to_user_id = tu.id
                   WHERE ((m.from_user_id = ? AND m.to_user_id = ?)
                      OR (m.from_user_id = ? AND m.to_user_id = ?))"""
            params = [user_id, peer_id, peer_id, user_id]
            if before_id:
                sql += " AND m.id < ?"
                params.append(int(before_id))
            sql += " ORDER BY m.id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            result = [dict(r) for r in rows]
            result.reverse()
            return result

    @staticmethod
    def get_unread_count(user_id, peer_id):
        return 0

    @staticmethod
    def send_group(group_id, from_user_id, msg_type, content, file_name=None, file_size=0, file_path=None, at_employee=None):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO im_group_messages (group_id, from_user_id, msg_type, content, file_name, file_size, file_path, at_employee)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (group_id, from_user_id, msg_type, content, file_name, file_size, file_path, at_employee)
            )
            return cursor.lastrowid

    @staticmethod
    def get_group_messages(group_id, before_id=None, limit=50):
        with get_connection() as conn:
            sql = """SELECT m.*, u.username as from_username
                       FROM im_group_messages m
                       LEFT JOIN users u ON m.from_user_id = u.id
                       WHERE m.group_id = ?"""
            params = [group_id]
            if before_id:
                sql += " AND m.id < ?"
                params.append(int(before_id))
            sql += " ORDER BY m.id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            result = [dict(r) for r in rows]
            result.reverse()
            return result

    @staticmethod
    def recall_private(msg_id, user_id):
        with get_connection() as conn:
            row = conn.execute(
                """SELECT id FROM im_messages
                   WHERE id = ? AND from_user_id = ? AND is_recalled = 0
                   AND datetime(create_at, '+2 minutes') >= datetime('now')""",
                (msg_id, user_id)
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE im_messages SET is_recalled = 1 WHERE id = ?",
                (msg_id,)
            )
            return True

    @staticmethod
    def recall_group(msg_id, user_id):
        with get_connection() as conn:
            row = conn.execute(
                """SELECT id FROM im_group_messages
                   WHERE id = ? AND from_user_id = ? AND is_recalled = 0
                   AND datetime(create_at, '+2 minutes') >= datetime('now')""",
                (msg_id, user_id)
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE im_group_messages SET is_recalled = 1 WHERE id = ?",
                (msg_id,)
            )
            return True

    @staticmethod
    def get_recalled_private_ids(user_id, peer_id, msg_ids):
        if not msg_ids:
            return []
        with get_connection() as conn:
            placeholders = ','.join('?' for _ in msg_ids)
            sql = f"""SELECT id FROM im_messages
                       WHERE id IN ({placeholders}) AND is_recalled = 1
                       AND ((from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?))"""
            params = list(msg_ids) + [user_id, peer_id, peer_id, user_id]
            rows = conn.execute(sql, params).fetchall()
            return [r["id"] for r in rows]

    @staticmethod
    def get_recalled_group_ids(group_id, msg_ids):
        if not msg_ids:
            return []
        with get_connection() as conn:
            placeholders = ','.join('?' for _ in msg_ids)
            sql = f"""SELECT id FROM im_group_messages
                       WHERE id IN ({placeholders}) AND is_recalled = 1 AND group_id = ?"""
            params = list(msg_ids) + [group_id]
            rows = conn.execute(sql, params).fetchall()
            return [r["id"] for r in rows]


class IMAdminRepository:

    @staticmethod
    def get_all_groups(page=1, per_page=20, keyword=""):
        with get_connection() as conn:
            count_sql = "SELECT COUNT(*) as cnt FROM im_groups"
            data_sql = """SELECT g.*, u.username as owner_name
                          FROM im_groups g
                          LEFT JOIN users u ON g.owner_id = u.id"""
            params = []
            if keyword:
                kw = f"%{keyword}%"
                count_sql += " WHERE g.name LIKE ?"
                data_sql += " WHERE g.name LIKE ?"
                params.append(kw)
            total = conn.execute(count_sql, params).fetchone()["cnt"]
            data_sql += " ORDER BY g.id DESC LIMIT ? OFFSET ?"
            params.extend([per_page, (page - 1) * per_page])
            rows = conn.execute(data_sql, params).fetchall()
            return [dict(r) for r in rows], total

    @staticmethod
    def get_group_members_admin(group_id):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT gm.*, u.username
                   FROM im_group_members gm
                   JOIN users u ON gm.user_id = u.id
                   WHERE gm.group_id = ?""",
                (group_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def disband_group_admin(group_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM im_group_messages WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM im_group_members WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM im_groups WHERE id = ?", (group_id,))
            return True

    @staticmethod
    def ban_group(group_id, reason="", ban_type="mute_all"):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO im_group_bans (group_id, reason, ban_type) VALUES (?,?,?)",
                (group_id, reason, ban_type)
            )
            conn.execute(
                "INSERT INTO im_group_messages (group_id, from_user_id, msg_type, content, at_employee) VALUES (?,0,'system',?,NULL)",
                (group_id, f"群聊已被管理员{reason and '原因: '+reason or '禁言'}")
            )
            return True

    @staticmethod
    def send_announcement(group_id, content):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO im_group_announcements (group_id, content) VALUES (?,?)",
                (group_id, content)
            )
            conn.execute(
                "INSERT INTO im_group_messages (group_id, from_user_id, msg_type, content, at_employee) VALUES (?,0,'system',?,NULL)",
                (group_id, f"📢 群公告：{content}")
            )
            return True

    @staticmethod
    def get_all_files(page=1, per_page=30, keyword=""):
        with get_connection() as conn:
            base = """SELECT id,from_user_id,to_user_id,msg_type,file_name,file_path,file_size,create_at,'private' as source
                        FROM im_messages WHERE msg_type IN ('file','image')"""
            base2 = """SELECT id,group_id as to_user_id,from_user_id,msg_type,file_name,file_path,file_size,create_at,'group' as source
                         FROM im_group_messages WHERE msg_type IN ('file','image')"""
            params = []
            if keyword:
                kw = f"%{keyword}%"
                base += " AND file_name LIKE ?"
                base2 += " AND file_name LIKE ?"
                params = [kw, kw]
            sql = f"SELECT *, COUNT(*) OVER() as total FROM ({base} UNION ALL {base2}) ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([per_page, (page - 1) * per_page])
            rows = conn.execute(sql, params).fetchall()
            if rows:
                total = rows[0]["total"]
            else:
                total = 0
            result = []
            seen = set()
            for r in rows:
                key = r.get("file_path", "")
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                result.append(dict(r))
            return result, total

    @staticmethod
    def delete_file_record(file_id, source):
        with get_connection() as conn:
            table = "im_messages" if source == "private" else "im_group_messages"
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (file_id,))
            return True

    @staticmethod
    def get_all_servers():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM im_chat_servers ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_server(name, host, port, description=""):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO im_chat_servers (name, host, port, description) VALUES (?,?,?,?)",
                (name, host, port, description)
            )
            return True

    @staticmethod
    def update_server(server_id, name, host, port, description):
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_chat_servers SET name=?, host=?, port=?, description=? WHERE id=?",
                (name, host, port, description, server_id)
            )
            return True

    @staticmethod
    def delete_server(server_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM im_chat_servers WHERE id = ?", (server_id,))
            return True

    @staticmethod
    def toggle_server(server_id, is_active):
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_chat_servers SET is_active = 0"
            )
            conn.execute(
                "UPDATE im_chat_servers SET is_active = ? WHERE id = ?",
                (is_active, server_id)
            )
            return True

    @staticmethod
    def get_all_tools(page=1, per_page=30):
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM ai_tools").fetchone()["cnt"]
            rows = conn.execute(
                """SELECT t.*, e.name as employee_name
                   FROM ai_tools t
                   LEFT JOIN digital_employees e ON t.employee_id = e.id
                   ORDER BY t.id DESC LIMIT ? OFFSET ?""",
                (per_page, (page - 1) * per_page)
            ).fetchall()
            return [dict(r) for r in rows], total

    @staticmethod
    def create_tool(name, code, tool_type, description, config, employee_id):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO ai_tools (name, code, tool_type, description, config, employee_id) VALUES (?,?,?,?,?,?)",
                (name, code, tool_type, description, config, employee_id or None)
            )
            return True

    @staticmethod
    def update_tool(tool_id, name, code, tool_type, description, config, employee_id):
        with get_connection() as conn:
            conn.execute(
                "UPDATE ai_tools SET name=?, code=?, tool_type=?, description=?, config=?, employee_id=? WHERE id=?",
                (name, code, tool_type, description, config, employee_id or None, tool_id)
            )
            return True

    @staticmethod
    def delete_tool(tool_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_tools WHERE id = ?", (tool_id,))
            return True

    @staticmethod
    def toggle_tool(tool_id, status):
        with get_connection() as conn:
            conn.execute(
                "UPDATE ai_tools SET status = ? WHERE id = ?",
                (status, tool_id)
            )
            return True

    @staticmethod
    def get_group_messages(group_id, page=1, per_page=50):
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM im_group_messages WHERE group_id=?", (group_id,)
            ).fetchone()["cnt"]
            rows = conn.execute(
                """SELECT m.*, u.username as from_name
                   FROM im_group_messages m
                   LEFT JOIN users u ON m.from_user_id = u.id
                   WHERE m.group_id = ?
                   ORDER BY m.create_at ASC LIMIT ? OFFSET ?""",
                (group_id, per_page, (page - 1) * per_page)
            ).fetchall()
            return [dict(r) for r in rows], total

    @staticmethod
    def get_all_chat_words(limit=300):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT content FROM (
                       SELECT content, create_at FROM im_messages WHERE msg_type='text' AND content IS NOT NULL
                       UNION ALL
                       SELECT content, create_at FROM im_group_messages WHERE msg_type='text' AND content IS NOT NULL
                       UNION ALL
                       SELECT content, create_at FROM conversation_messages WHERE role='user' AND content IS NOT NULL
                   ) ORDER BY create_at DESC LIMIT ?""", (limit,)
            ).fetchall()
            texts = [r["content"] for r in rows if r["content"] and len(r["content"].strip()) > 1]
            return texts
