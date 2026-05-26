from app.models.db import get_connection


class ApiInterfaceRepository:

    @staticmethod
    def get_all(status=None):
        with get_connection() as conn:
            sql = "SELECT * FROM api_interfaces WHERE 1=1"
            params = []
            if status is not None:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY id ASC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(api_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM api_interfaces WHERE id = ?", (api_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create(name, code, url, method="GET", resp_format="JSON",
               params_desc=None, example_url=None, qps_limit=None,
               has_token=0, remark=None, tags=None):
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    """INSERT INTO api_interfaces (name, code, url, method, resp_format,
                       params_desc, example_url, qps_limit, has_token, remark, tags)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, code, url, method, resp_format,
                     params_desc, example_url, qps_limit, has_token, remark, tags)
                )
                return cursor.lastrowid
        except Exception:
            return None

    @staticmethod
    def update(api_id, **kwargs):
        if not kwargs:
            return True
        with get_connection() as conn:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            params = list(kwargs.values()) + [api_id]
            conn.execute(f"UPDATE api_interfaces SET {sets} WHERE id = ?", params)
            return True

    @staticmethod
    def delete(api_id):
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM api_interfaces WHERE id = ?", (api_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_page(page=1, per_page=20, keyword=None, tags=None):
        offset = (page - 1) * per_page
        with get_connection() as conn:
            sql = "SELECT * FROM api_interfaces WHERE 1=1"
            params = []
            if keyword:
                sql += " AND (name LIKE ? OR code LIKE ? OR remark LIKE ?)"
                kw = f"%{keyword}%"
                params.extend([kw, kw, kw])
            if tags:
                sql += " AND tags LIKE ?"
                params.append(f"%{tags}%")
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            total = conn.execute(count_sql, params).fetchone()[0]
            sql += " ORDER BY id ASC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows], total
