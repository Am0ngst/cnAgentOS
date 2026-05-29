# 后台管理控制器
import tornado.web
import json
from app.controllers.base import BaseHandler
from app.models.user import UserRepository
from app.models.rbac import RoleRepository, PermissionRepository

class AdminLoginHandler(tornado.web.RequestHandler):
    """管理员登录页面"""
    def get(self):
        self.render("admin/login.html", error=None)
    
    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "")
        
        if not username or not password:
            return self.render("admin/login.html", error="用户名或密码不能为空")
        
        if username == "admin" and password == "admin888":
            self.set_secure_cookie("admin_user", username)
            self.redirect("/admin/dashboard")
            return

        user = UserRepository.get_user_by_username(username)
        if not user or not UserRepository.verify_user(username, password):
            return self.render("admin/login.html", error="用户名或密码错误")

        role_id = user.get("role_id")
        if not role_id:
            return self.render("admin/login.html", error="您没有后台管理权限，请联系管理员分配角色")

        if not PermissionRepository.check_permission(role_id, "dashboard"):
            return self.render("admin/login.html", error="您没有后台管理权限，请联系管理员")

        self.set_secure_cookie("admin_user", username)
        self.redirect("/admin/dashboard")

class AdminLogoutHandler(BaseHandler):
    """管理员退出"""
    def post(self):
        self.clear_cookie("admin_user")
        self.redirect("/admin/login")


PERMISSION_URL_MAP = [
    ("dashboard", ["/admin/dashboard", "/admin/api/dashboard", "/admin/?", "/admin/api/menu"]),
    ("users", ["/admin/users", "/admin/api/users"]),
    ("roles", ["/admin/roles", "/admin/api/roles"]),
    ("permissions", ["/admin/permissions", "/admin/api/permissions"]),
    ("functions", ["/admin/functions", "/admin/api/functions"]),
    ("api_interfaces", ["/admin/api-interfaces"]),
    ("models", ["/admin/models"]),
    ("digital_employees", ["/admin/digital-employees", "/admin/digital-chat"]),
    ("watch_collect", ["/admin/watch/collect", "/admin/watch/sources", "/admin/watch/execute", "/admin/watch/schedule"]),
    ("watch_data", ["/admin/watch/data", "/admin/watch/deep-crawl"]),
    ("sentiment_dashboard", ["/admin/sentiment/dashboard", "/admin/sentiment/api/stats", "/admin/sentiment/api/earth-texture"]),
    ("sentiment_analysis", ["/admin/sentiment/analysis", "/admin/sentiment/api/analyses", "/admin/sentiment/api/analyze", "/admin/sentiment/api/analysis-delete", "/admin/sentiment/api/chat-data", "/admin/sentiment/api/watch-data"]),
    ("im_groups", ["/admin/im/groups", "/admin/im/api/group-messages", "/admin/im/api/chat-words"]),
    ("im_files", ["/admin/im/files"]),
    ("im_servers", ["/admin/im/servers", "/admin/im/tools"]),
]


def _build_source_map():
    from app.models.db import get_connection
    with get_connection() as conn:
        rows = conn.execute("SELECT id, code, parent_id FROM functions WHERE status=1 AND code IS NOT NULL").fetchall()
    id_to_code = {r["id"]: r["code"] for r in rows}
    code_to_parent = {}
    for r in rows:
        if r["parent_id"] and r["parent_id"] in id_to_code:
            code_to_parent[r["code"]] = id_to_code[r["parent_id"]]
    return code_to_parent

SOURCE_PARENT_MAP = _build_source_map()


def _check_code_with_parents(role_id, code):
    if PermissionRepository.check_permission(role_id, code):
        return True
    cur = code
    for _ in range(5):
        parent = SOURCE_PARENT_MAP.get(cur)
        if not parent:
            return False
        if PermissionRepository.check_permission(role_id, parent):
            return True
        cur = parent
    return False


class AdminBaseHandler(BaseHandler):
    """后台管理基础处理器"""
    def get_current_user(self):
        return self.get_secure_cookie("admin_user")

    def get_login_url(self):
        return "/admin/login"

    def _check_permission(self):
        user = self.current_user
        if not user:
            return True
        username = user.decode("utf-8") if isinstance(user, bytes) else user
        if username == "admin":
            return True

        db_user = UserRepository.get_user_by_username(username)
        if not db_user or not db_user.get("role_id"):
            return False

        role_id = db_user["role_id"]
        path = self.request.path

        required_code = None
        for code, prefixes in PERMISSION_URL_MAP:
            for pfx in prefixes:
                if path == pfx or path.startswith(pfx + "/") or path.startswith(pfx + "?"):
                    required_code = code
                    break
            if required_code:
                break

        if not required_code:
            return False

        return _check_code_with_parents(role_id, required_code)

    def prepare(self):
        if not self._check_permission():
            self.set_status(403)
            self.finish("403 Forbidden: 您无此功能的访问权限")
            return

class AdminIndexHandler(AdminBaseHandler):
    """后台首页重定向"""
    @tornado.web.authenticated
    def get(self):
        self.redirect("/admin/dashboard")

class DashboardHandler(AdminBaseHandler):
    """后台主页"""
    @tornado.web.authenticated
    def get(self):
        self.render("admin/dashboard.html", 
                   title="控制台", 
                   username=self.current_user.decode('utf-8'),
                   active_menu="dashboard")

class UserManageHandler(AdminBaseHandler):
    """用户管理页面"""
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        search = self.get_argument("search", "").strip()
        per_page = 20
        
        users, total = UserRepository.get_users_page(page, per_page, search)
        total_pages = (total + per_page - 1) // per_page
        
        # 获取所有角色（用于下拉选择）
        roles = RoleRepository.get_all(status=1)
        
        self.render("admin/users.html",
                   title="用户管理",
                   username=self.current_user.decode('utf-8'),
                   active_menu="users",
                   users=users,
                   roles=roles,
                   page=page,
                   total_pages=total_pages,
                   total=total)

class UserCreateHandler(AdminBaseHandler):
    """创建用户API"""
    @tornado.web.authenticated
    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", "").strip()
        
        if not username or not password:
            self.write({"success": False, "message": "用户名和密码不能为空"})
            return
        
        # 检查是否创建admin用户（不允许）
        if username == 'admin':
            self.write({"success": False, "message": "admin用户已存在，不能重复创建"})
            return
        
        role_id = int(role_id) if role_id else None
        
        if UserRepository.create_user(username, password, role_id):
            self.write({"success": True, "message": "用户创建成功"})
        else:
            self.write({"success": False, "message": "用户名已存在"})

class UserUpdateHandler(AdminBaseHandler):
    """更新用户API"""
    @tornado.web.authenticated
    def post(self):
        user_id = self.get_body_argument("id", "")
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", "").strip()
        
        if not user_id:
            self.write({"success": False, "message": "参数错误"})
            return
        
        user_id = int(user_id)
        
        # 检查是否是admin用户
        if UserRepository.is_system_user(user_id):
            # admin用户只能修改密码
            if password:
                if UserRepository.update_user(user_id, password=password):
                    self.write({"success": True, "message": "密码修改成功"})
                else:
                    self.write({"success": False, "message": "密码修改失败"})
            else:
                self.write({"success": False, "message": "admin用户只能修改密码"})
            return
        
        # 普通用户更新
        kwargs = {}
        if username:
            kwargs['username'] = username
        if password:
            kwargs['password'] = password
        if role_id:
            kwargs['role_id'] = int(role_id)
        
        if UserRepository.update_user(user_id, **kwargs):
            self.write({"success": True, "message": "用户更新成功"})
        else:
            self.write({"success": False, "message": "用户名已存在或用户不存在"})

class UserDeleteHandler(AdminBaseHandler):
    """删除用户API"""
    @tornado.web.authenticated
    def post(self):
        user_id = self.get_body_argument("id", "")
        if not user_id:
            self.write({"success": False, "message": "参数错误"})
            return
        
        user_id = int(user_id)
        
        # 检查是否是admin用户
        if UserRepository.is_system_user(user_id):
            self.write({"success": False, "message": "admin用户不能删除"})
            return
        
        if UserRepository.delete_user(user_id):
            self.write({"success": True, "message": "删除成功"})
        else:
            self.write({"success": False, "message": "删除失败"})

class UserBatchDeleteHandler(AdminBaseHandler):
    """批量删除用户API"""
    @tornado.web.authenticated
    def post(self):
        ids_str = self.get_body_argument("ids", "")
        if not ids_str:
            self.write({"success": False, "message": "参数错误"})
            return
        
        ids = [int(id.strip()) for id in ids_str.split(",") if id.strip()]
        
        # 过滤掉admin用户
        filtered_ids = [uid for uid in ids if not UserRepository.is_system_user(uid)]
        
        if not filtered_ids:
            self.write({"success": False, "message": "选中的用户包含admin用户，无法删除"})
            return
        
        deleted_count = UserRepository.batch_delete_users(filtered_ids)
        skipped_count = len(ids) - len(filtered_ids)
        
        message = f"成功删除 {deleted_count} 个用户"
        if skipped_count > 0:
            message += f"，跳过 {skipped_count} 个系统用户"
        
        self.write({"success": True, "message": message})

class UserCountHandler(AdminBaseHandler):
    """获取用户数量API"""
    @tornado.web.authenticated
    def get(self):
        count = UserRepository.get_user_count()
        self.write({"count": count})

class UserRolesHandler(AdminBaseHandler):
    """获取用户角色信息API"""
    @tornado.web.authenticated
    def get(self):
        user_id = self.get_argument("id", "").strip()
        if not user_id:
            self.write({"success": False, "message": "参数错误"})
            return
        
        user = UserRepository.get_user_by_id(int(user_id))
        if user:
            self.write({"success": True, "data": user})
        else:
            self.write({"success": False, "message": "用户不存在"})


class DashboardStatsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        from app.models.db import get_connection
        with get_connection() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

            today_private = conn.execute(
                "SELECT COUNT(DISTINCT from_user_id) FROM im_messages WHERE date(create_at)=date('now')"
            ).fetchone()[0]
            today_group = conn.execute(
                "SELECT COUNT(DISTINCT from_user_id) FROM im_group_messages WHERE date(create_at)=date('now')"
            ).fetchone()[0]
            today_chat = conn.execute(
                "SELECT COUNT(DISTINCT ch.user_id) FROM conversation_messages cm LEFT JOIN conversation_history ch ON cm.conversation_id=ch.id WHERE date(cm.create_at)=date('now')"
            ).fetchone()[0]
            active_set = set()
            for uid in conn.execute("SELECT DISTINCT from_user_id FROM im_messages WHERE date(create_at)=date('now')").fetchall():
                active_set.add(uid[0])
            for uid in conn.execute("SELECT DISTINCT from_user_id FROM im_group_messages WHERE date(create_at)=date('now')").fetchall():
                active_set.add(uid[0])
            for row in conn.execute("SELECT DISTINCT ch.user_id FROM conversation_messages cm LEFT JOIN conversation_history ch ON cm.conversation_id=ch.id WHERE date(cm.create_at)=date('now')").fetchall():
                if row[0]:
                    active_set.add(row[0])
            today_active = len(active_set)

            today_msgs = conn.execute(
                "SELECT COUNT(*) FROM im_messages WHERE date(create_at)=date('now')"
            ).fetchone()[0]
            today_msgs += conn.execute(
                "SELECT COUNT(*) FROM im_group_messages WHERE date(create_at)=date('now')"
            ).fetchone()[0]
            today_msgs += conn.execute(
                "SELECT COUNT(*) FROM conversation_messages WHERE date(create_at)=date('now')"
            ).fetchone()[0]

            total_data = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()[0]
            total_data += conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0]
            total_data += conn.execute("SELECT COUNT(*) FROM im_messages").fetchone()[0]
            total_data += conn.execute("SELECT COUNT(*) FROM im_group_messages").fetchone()[0]

            model_count = conn.execute("SELECT COUNT(*) FROM ai_models WHERE status=1").fetchone()[0]
            emp_count = conn.execute("SELECT COUNT(*) FROM digital_employees WHERE status=1").fetchone()[0]
            api_count = conn.execute("SELECT COUNT(*) FROM api_interfaces WHERE status=1").fetchone()[0]
            source_count = conn.execute("SELECT COUNT(*) FROM watch_sources WHERE status=1").fetchone()[0]
            watch_count = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()[0]
            crawl_count = conn.execute("SELECT COUNT(*) FROM watch_data WHERE deep_crawl_status=1").fetchone()[0]

        self.write({
            "success": True,
            "data": {
                "total_users": total_users,
                "today_active": today_active,
                "today_messages": today_msgs,
                "total_data": total_data,
                "model_count": model_count,
                "emp_count": emp_count,
                "api_count": api_count,
                "source_count": source_count,
                "watch_count": watch_count,
                "deep_crawl_count": crawl_count,
            }
        })
