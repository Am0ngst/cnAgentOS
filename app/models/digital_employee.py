import json
from app.models.db import get_connection


class DigitalEmployeeRepository:

    @staticmethod
    def get_all(status=None):
        with get_connection() as conn:
            sql = """SELECT de.*,
                am.name as model_name, am.model_name as model_code_name,
                ai.name as api_name, ai.url as api_url
                FROM digital_employees de
                LEFT JOIN ai_models am ON de.model_id = am.id
                LEFT JOIN api_interfaces ai ON de.api_id = ai.id
                WHERE 1=1"""
            params = []
            if status is not None:
                sql += " AND de.status = ?"
                params.append(status)
            sql += " ORDER BY de.sort_order ASC, de.id ASC"
            rows = conn.execute(sql, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("params_config"):
                    try:
                        d["params_config"] = json.loads(d["params_config"])
                    except Exception:
                        pass
                result.append(d)
            return result

    @staticmethod
    def get_by_id(emp_id):
        with get_connection() as conn:
            row = conn.execute(
                """SELECT de.*,
                   am.name as model_name, am.model_name as model_code_name,
                   ai.name as api_name, ai.url as api_url, ai.code as api_code
                   FROM digital_employees de
                   LEFT JOIN ai_models am ON de.model_id = am.id
                   LEFT JOIN api_interfaces ai ON de.api_id = ai.id
                   WHERE de.id = ?""", (emp_id,)
            ).fetchone()
            if row:
                d = dict(row)
                if d.get("params_config"):
                    try:
                        d["params_config"] = json.loads(d["params_config"])
                    except Exception:
                        pass
                return d
            return None

    @staticmethod
    def get_by_alias(alias):
        with get_connection() as conn:
            row = conn.execute(
                """SELECT de.*,
                   am.name as model_name, am.model_name as model_code_name,
                   am.api_key, am.base_url,
                   ai.name as api_name, ai.url as api_url
                   FROM digital_employees de
                   LEFT JOIN ai_models am ON de.model_id = am.id
                   LEFT JOIN api_interfaces ai ON de.api_id = ai.id
                   WHERE de.alias = ? AND de.status = 1""", (alias,)
            ).fetchone()
            if row:
                d = dict(row)
                if d.get("params_config"):
                    try:
                        d["params_config"] = json.loads(d["params_config"])
                    except Exception:
                        pass
                return d
            return None

    @staticmethod
    def create(name, alias, emp_type, model_id=None, api_id=None,
               system_prompt=None, params_config=None, description=None, sort_order=0):
        try:
            with get_connection() as conn:
                pc_json = json.dumps(params_config, ensure_ascii=False) if isinstance(params_config, dict) else params_config
                cursor = conn.execute(
                    """INSERT INTO digital_employees (name, alias, emp_type, model_id, api_id,
                       system_prompt, params_config, description, sort_order)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (name, alias, emp_type, model_id, api_id,
                     system_prompt, pc_json, description, sort_order)
                )
                return cursor.lastrowid
        except Exception:
            return None

    @staticmethod
    def update(emp_id, **kwargs):
        if not kwargs:
            return True
        if "params_config" in kwargs and isinstance(kwargs["params_config"], dict):
            kwargs["params_config"] = json.dumps(kwargs["params_config"], ensure_ascii=False)
        with get_connection() as conn:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            params = list(kwargs.values()) + [emp_id]
            conn.execute(f"UPDATE digital_employees SET {sets} WHERE id = ?", params)
            return True

    @staticmethod
    def delete(emp_id):
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM digital_employees WHERE id = ?", (emp_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_page(page=1, per_page=20):
        offset = (page - 1) * per_page
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM digital_employees").fetchone()[0]
            rows = conn.execute(
                """SELECT de.*,
                   am.name as model_name,
                   ai.name as api_name
                   FROM digital_employees de
                   LEFT JOIN ai_models am ON de.model_id = am.id
                   LEFT JOIN api_interfaces ai ON de.api_id = ai.id
                   ORDER BY de.sort_order ASC, de.id ASC
                   LIMIT ? OFFSET ?""",
                (per_page, offset)
            ).fetchall()
            return [dict(r) for r in rows], total
