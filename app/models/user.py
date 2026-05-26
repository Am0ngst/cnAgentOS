import hashlib
import secrets
import sqlite3

from app.models.db import get_connection

# 密码加密方法
def _hash_password(password:str,salt:bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return dk.hex()

#用户对象类
class UserRepository:
    # 创建用户方法（带角色）
    @staticmethod
    def create_user(username:str,password:str, role_id:int=None) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password,salt)

        try:
            with get_connection() as conn:
                conn.execute(
                    "insert into users(username,password_hash,salt,role_id) values(?,?,?,?)", 
                    (username, password_hash, salt.hex(), role_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    # 通过用户名检索用户信息的方法
    @staticmethod
    def get_user_by_username(username:str):
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT u.*, r.name as role_name, r.code as role_code, r.is_system as role_is_system 
                FROM users u 
                LEFT JOIN roles r ON u.role_id = r.id 
                WHERE u.username = ?
                """, 
                (username,)
            ).fetchone()
        return row

    # 通过ID获取用户信息
    @staticmethod
    def get_user_by_id(user_id:int):
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT u.*, r.name as role_name, r.code as role_code, r.is_system as role_is_system 
                FROM users u 
                LEFT JOIN roles r ON u.role_id = r.id 
                WHERE u.id = ?
                """, 
                (user_id,)
            ).fetchone()
        return dict(row) if row else None

    # 验证用户名和密码的方法
    @staticmethod
    def verify_user(username:str,password:str) -> bool:
        row = UserRepository.get_user_by_username(username)
        if not row:
            return False
        salt = bytes.fromhex(row["salt"])
        return _hash_password(password,salt) == row["password_hash"]

    # 获取用户列表（分页，带角色信息）
    @staticmethod
    def get_users_page(page:int=1, per_page:int=20, search:str=""):
        offset = (page - 1) * per_page
        
        with get_connection() as conn:
            base_sql = """
                FROM users u 
                LEFT JOIN roles r ON u.role_id = r.id 
                WHERE 1=1
            """
            params = []
            
            if search:
                base_sql += " AND u.username LIKE ?"
                params.append(f"%{search}%")
            
            # 获取总数
            count_sql = f"SELECT COUNT(*) {base_sql}"
            total = conn.execute(count_sql, params).fetchone()[0]
            
            # 获取列表
            sql = f"""
                SELECT u.id, u.username, u.create_at, u.role_id,
                       r.name as role_name, r.code as role_code, r.is_system as role_is_system
                {base_sql}
                ORDER BY u.id DESC 
                LIMIT ? OFFSET ?
            """
            params.extend([per_page, offset])
            rows = conn.execute(sql, params).fetchall()
        
        return [dict(row) for row in rows], total

    # 更新用户信息（支持角色）
    @staticmethod
    def update_user(user_id:int, username:str=None, password:str=None, role_id:int=None) -> bool:
        try:
            with get_connection() as conn:
                # 检查是否是admin用户
                user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
                if user and user['username'] == 'admin' and username and username != 'admin':
                    return False  # admin用户名不能修改
                
                updates = []
                params = []
                
                if username is not None:
                    updates.append("username = ?")
                    params.append(username)
                
                if password:
                    salt = secrets.token_bytes(16)
                    password_hash = _hash_password(password, salt)
                    updates.append("password_hash = ?")
                    params.append(password_hash)
                    updates.append("salt = ?")
                    params.append(salt.hex())
                
                if role_id is not None:
                    updates.append("role_id = ?")
                    params.append(role_id)
                
                if not updates:
                    return True
                
                params.append(user_id)
                sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)
            return True
        except sqlite3.IntegrityError:
            return False

    # 删除用户
    @staticmethod
    def delete_user(user_id:int) -> bool:
        with get_connection() as conn:
            # 检查是否是admin用户
            user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
            if user and user['username'] == 'admin':
                return False  # admin用户不能删除
            
            cursor = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            return cursor.rowcount > 0

    # 批量删除用户
    @staticmethod
    def batch_delete_users(user_ids:list) -> int:
        if not user_ids:
            return 0
        
        # 过滤掉admin用户
        placeholders = ','.join(['?' for _ in user_ids])
        with get_connection() as conn:
            # 先找出admin用户的ID
            admin_row = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
            admin_id = admin_row['id'] if admin_row else None
            
            # 过滤admin用户
            filtered_ids = [uid for uid in user_ids if uid != admin_id]
            
            if not filtered_ids:
                return 0
            
            placeholders = ','.join(['?' for _ in filtered_ids])
            cursor = conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", filtered_ids)
            return cursor.rowcount

    # 获取用户总数
    @staticmethod
    def get_user_count() -> int:
        with get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # 检查是否是系统用户（admin）
    @staticmethod
    def is_system_user(user_id:int) -> bool:
        with get_connection() as conn:
            row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
            return row is not None and row['username'] == 'admin'
