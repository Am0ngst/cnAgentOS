# 功能模块、角色、权限管理模型
import sqlite3
from app.models.db import get_connection

class FunctionRepository:
    """功能模块仓库"""
    
    @staticmethod
    def create(name, code, icon=None, url=None, parent_id=None, sort_order=0, is_menu=1):
        """创建功能"""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO functions (name, code, icon, url, parent_id, sort_order, is_menu)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, code, icon, url, parent_id, sort_order, is_menu)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    
    @staticmethod
    def update(func_id, name=None, code=None, icon=None, url=None, parent_id=None, sort_order=None, status=None):
        """更新功能"""
        try:
            with get_connection() as conn:
                # 构建动态更新SQL
                updates = []
                params = []
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                if code is not None:
                    updates.append("code = ?")
                    params.append(code)
                if icon is not None:
                    updates.append("icon = ?")
                    params.append(icon)
                if url is not None:
                    updates.append("url = ?")
                    params.append(url)
                if parent_id is not None:
                    updates.append("parent_id = ?")
                    params.append(parent_id)
                if sort_order is not None:
                    updates.append("sort_order = ?")
                    params.append(sort_order)
                if status is not None:
                    updates.append("status = ?")
                    params.append(status)
                
                if not updates:
                    return True
                
                params.append(func_id)
                sql = f"UPDATE functions SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)
                return True
        except sqlite3.IntegrityError:
            return False
    
    @staticmethod
    def delete(func_id):
        """删除功能"""
        with get_connection() as conn:
            # 先删除子功能
            conn.execute("DELETE FROM functions WHERE parent_id = ?", (func_id,))
            # 删除权限关联
            conn.execute("DELETE FROM permissions WHERE function_id = ?", (func_id,))
            # 删除功能
            cursor = conn.execute("DELETE FROM functions WHERE id = ?", (func_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_by_id(func_id):
        """根据ID获取功能"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM functions WHERE id = ?",
                (func_id,)
            ).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_all(parent_id=None, status=None):
        """获取所有功能"""
        with get_connection() as conn:
            sql = "SELECT * FROM functions WHERE 1=1"
            params = []
            if parent_id is not None:
                sql += " AND parent_id = ?"
                params.append(parent_id)
            elif parent_id is False:
                sql += " AND parent_id IS NULL"
            if status is not None:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY sort_order ASC, id ASC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_tree():
        """获取功能树"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM functions WHERE status = 1 ORDER BY sort_order ASC, id ASC"
            ).fetchall()

            func_map = {}
            for row in rows:
                func = dict(row)
                func['children'] = []
                func_map[func['id']] = func

            root_funcs = []
            for func in func_map.values():
                if func['parent_id'] is None:
                    root_funcs.append(func)
                elif func['parent_id'] in func_map:
                    func_map[func['parent_id']]['children'].append(func)

            root_funcs.sort(key=lambda x: x['sort_order'])
            for root in root_funcs:
                root['children'].sort(key=lambda x: x['sort_order'])
            return root_funcs
    
    @staticmethod
    def get_page(page=1, per_page=20):
        """分页获取功能"""
        offset = (page - 1) * per_page
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
            rows = conn.execute(
                """
                SELECT f.*, p.name as parent_name 
                FROM functions f 
                LEFT JOIN functions p ON f.parent_id = p.id 
                ORDER BY f.sort_order ASC, f.id ASC 
                LIMIT ? OFFSET ?
                """,
                (per_page, offset)
            ).fetchall()
            return [dict(row) for row in rows], count


class RoleRepository:
    """角色仓库"""
    
    @staticmethod
    def create(name, code, description=None):
        """创建角色"""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO roles (name, code, description) VALUES (?, ?, ?)",
                    (name, code, description)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    
    @staticmethod
    def update(role_id, name=None, description=None, status=None):
        """更新角色"""
        try:
            with get_connection() as conn:
                # 检查是否是系统角色
                role = conn.execute(
                    "SELECT is_system FROM roles WHERE id = ?",
                    (role_id,)
                ).fetchone()
                if role and role['is_system']:
                    return False  # 系统角色不能修改
                
                updates = []
                params = []
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                if status is not None:
                    updates.append("status = ?")
                    params.append(status)
                
                if not updates:
                    return True
                
                params.append(role_id)
                sql = f"UPDATE roles SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)
                return True
        except sqlite3.IntegrityError:
            return False
    
    @staticmethod
    def delete(role_id):
        """删除角色"""
        with get_connection() as conn:
            # 检查是否是系统角色
            role = conn.execute(
                "SELECT is_system FROM roles WHERE id = ?",
                (role_id,)
            ).fetchone()
            if role and role['is_system']:
                return False  # 系统角色不能删除
            
            # 删除权限关联
            conn.execute("DELETE FROM permissions WHERE role_id = ?", (role_id,))
            # 删除角色
            cursor = conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_by_id(role_id):
        """根据ID获取角色"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM roles WHERE id = ?",
                (role_id,)
            ).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_all(status=None):
        """获取所有角色"""
        with get_connection() as conn:
            sql = "SELECT * FROM roles WHERE 1=1"
            params = []
            if status is not None:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY is_system DESC, id ASC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_page(page=1, per_page=20):
        """分页获取角色"""
        offset = (page - 1) * per_page
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM roles ORDER BY is_system DESC, id ASC LIMIT ? OFFSET ?",
                (per_page, offset)
            ).fetchall()
            return [dict(row) for row in rows], count


class PermissionRepository:
    """权限仓库"""
    
    @staticmethod
    def grant(role_id, function_ids):
        """授予权限"""
        with get_connection() as conn:
            for func_id in function_ids:
                try:
                    conn.execute(
                        "INSERT INTO permissions (role_id, function_id) VALUES (?, ?)",
                        (role_id, func_id)
                    )
                except sqlite3.IntegrityError:
                    pass  # 已存在，忽略
            return True
    
    @staticmethod
    def revoke(role_id, function_id=None):
        """撤销权限"""
        with get_connection() as conn:
            if function_id:
                conn.execute(
                    "DELETE FROM permissions WHERE role_id = ? AND function_id = ?",
                    (role_id, function_id)
                )
            else:
                conn.execute(
                    "DELETE FROM permissions WHERE role_id = ?",
                    (role_id,)
                )
            return True
    
    @staticmethod
    def get_role_permissions(role_id):
        """获取角色的权限"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT f.* FROM functions f
                INNER JOIN permissions p ON f.id = p.function_id
                WHERE p.role_id = ? AND f.status = 1
                ORDER BY f.sort_order ASC
                """,
                (role_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_role_permission_ids(role_id):
        """获取角色有权限的功能ID列表"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT function_id FROM permissions WHERE role_id = ?",
                (role_id,)
            ).fetchall()
            return [row['function_id'] for row in rows]
    
    @staticmethod
    def check_permission(role_id, function_code):
        """检查角色是否有某功能权限"""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM permissions p
                INNER JOIN functions f ON p.function_id = f.id
                WHERE p.role_id = ? AND f.code = ? AND f.status = 1
                """,
                (role_id, function_code)
            ).fetchone()
            return row is not None

    @staticmethod
    def get_menu_tree(role_id):
        with get_connection() as conn:
            direct_ids = set()
            for row in conn.execute(
                "SELECT function_id FROM permissions WHERE role_id = ?", (role_id,)
            ).fetchall():
                direct_ids.add(row["function_id"])

            if not direct_ids:
                return []

            all_funcs = conn.execute(
                "SELECT * FROM functions WHERE status=1 ORDER BY sort_order ASC, id ASC"
            ).fetchall()

            func_map = {}
            for row in all_funcs:
                f = dict(row)
                f["children"] = []
                func_map[f["id"]] = f

            expanded_ids = set(direct_ids)
            for fid in direct_ids:
                children = [f for f in func_map.values() if f.get("parent_id") == fid]
                for child in children:
                    expanded_ids.add(child["id"])

            included = []
            for f in func_map.values():
                if f["id"] in expanded_ids:
                    included.append(f)

            roots = []
            result_map = {}
            for f in included:
                if f.get("is_menu"):
                    result_map[f["id"]] = f
                    if f.get("parent_id") is None:
                        roots.append(f)

            for f in result_map.values():
                pid = f.get("parent_id")
                if pid and pid in result_map:
                    result_map[pid]["children"].append(f)

            roots.sort(key=lambda x: x.get("sort_order", 0))
            for r in roots:
                r["children"].sort(key=lambda x: x.get("sort_order", 0))
            return roots
    
    @staticmethod
    def get_all_with_status(role_id):
        """获取所有功能及其权限状态（用于权限配置）"""
        with get_connection() as conn:
            # 获取所有功能
            funcs = conn.execute(
                "SELECT * FROM functions WHERE status = 1 ORDER BY sort_order ASC"
            ).fetchall()
            
            # 获取角色已有权限
            perms = conn.execute(
                "SELECT function_id FROM permissions WHERE role_id = ?",
                (role_id,)
            ).fetchall()
            permission_ids = {p['function_id'] for p in perms}
            
            # 构建树结构并标记权限
            func_map = {}
            root_funcs = []
            
            for row in funcs:
                func = dict(row)
                func['has_permission'] = func['id'] in permission_ids
                func['children'] = []
                func_map[func['id']] = func
                
                if func['parent_id'] is None:
                    root_funcs.append(func)
                elif func['parent_id'] in func_map:
                    func_map[func['parent_id']]['children'].append(func)
            
            return root_funcs
