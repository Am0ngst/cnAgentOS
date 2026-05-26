# 后台管理控制器
import tornado.web
import json
from app.controllers.base import BaseHandler
from app.models.user import UserRepository
from app.models.rbac import RoleRepository

class AdminLoginHandler(tornado.web.RequestHandler):
    """管理员登录页面"""
    def get(self):
        self.render("admin/login.html", error=None)
    
    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "")
        
        if not username or not password:
            return self.render("admin/login.html", error="用户名或密码不能为空")
        
        # 验证管理员账号 (admin/admin888)
        if username == "admin" and password == "admin888":
            self.set_secure_cookie("admin_user", username)
            self.redirect("/admin/dashboard")
        elif UserRepository.verify_user(username, password):
            # 普通用户也可以登录后台
            self.set_secure_cookie("admin_user", username)
            self.redirect("/admin/dashboard")
        else:
            self.render("admin/login.html", error="用户名或密码错误")

class AdminLogoutHandler(BaseHandler):
    """管理员退出"""
    def post(self):
        self.clear_cookie("admin_user")
        self.redirect("/admin/login")

class AdminBaseHandler(BaseHandler):
    """后台管理基础处理器"""
    def get_current_user(self):
        return self.get_secure_cookie("admin_user")

    def get_login_url(self):
        return "/admin/login"

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
