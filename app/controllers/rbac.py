# 功能管理、角色管理、权限管理控制器
import tornado.web
import json
from app.controllers.admin import AdminBaseHandler
from app.models.rbac import FunctionRepository, RoleRepository, PermissionRepository


class FunctionManageHandler(AdminBaseHandler):
    """功能管理页面"""
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        search = self.get_argument("search", "").strip()
        per_page = 20
        
        functions, total = FunctionRepository.get_page(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        
        # 获取所有父级功能（用于二级联动）
        parent_functions = FunctionRepository.get_all(parent_id=False)
        
        self.render("admin/functions.html",
                   title="功能管理",
                   username=self.current_user.decode('utf-8'),
                   active_menu="functions",
                   functions=functions,
                   parent_functions=parent_functions,
                   page=page,
                   total_pages=total_pages,
                   total=total)


class FunctionCreateHandler(AdminBaseHandler):
    """创建功能API"""
    @tornado.web.authenticated
    def post(self):
        name = self.get_body_argument("name", "").strip()
        code = self.get_body_argument("code", "").strip()
        icon = self.get_body_argument("icon", "").strip() or None
        url = self.get_body_argument("url", "").strip() or None
        parent_id = self.get_body_argument("parent_id", "").strip()
        sort_order = self.get_body_argument("sort_order", "0").strip()
        
        if not name or not code:
            self.write({"success": False, "message": "功能名称和编码不能为空"})
            return
        
        parent_id = int(parent_id) if parent_id else None
        sort_order = int(sort_order) if sort_order else 0
        
        func_id = FunctionRepository.create(name, code, icon, url, parent_id, sort_order)
        if func_id:
            self.write({"success": True, "message": "功能创建成功", "id": func_id})
        else:
            self.write({"success": False, "message": "功能编码已存在"})


class FunctionUpdateHandler(AdminBaseHandler):
    """更新功能API"""
    @tornado.web.authenticated
    def post(self):
        func_id = self.get_body_argument("id", "")
        name = self.get_body_argument("name", "").strip()
        code = self.get_body_argument("code", "").strip()
        icon = self.get_body_argument("icon", "").strip() or None
        url = self.get_body_argument("url", "").strip() or None
        parent_id = self.get_body_argument("parent_id", "").strip()
        sort_order = self.get_body_argument("sort_order", "").strip()
        status = self.get_body_argument("status", "").strip()
        
        if not func_id or not name or not code:
            self.write({"success": False, "message": "参数错误"})
            return
        
        kwargs = {"name": name, "code": code}
        if icon is not None:
            kwargs["icon"] = icon
        if url is not None:
            kwargs["url"] = url
        if parent_id:
            kwargs["parent_id"] = int(parent_id)
        else:
            kwargs["parent_id"] = None
        if sort_order:
            kwargs["sort_order"] = int(sort_order)
        if status:
            kwargs["status"] = int(status)
        
        if FunctionRepository.update(int(func_id), **kwargs):
            self.write({"success": True, "message": "功能更新成功"})
        else:
            self.write({"success": False, "message": "功能编码已存在"})


class FunctionDeleteHandler(AdminBaseHandler):
    """删除功能API"""
    @tornado.web.authenticated
    def post(self):
        func_id = self.get_body_argument("id", "")
        if not func_id:
            self.write({"success": False, "message": "参数错误"})
            return
        
        if FunctionRepository.delete(int(func_id)):
            self.write({"success": True, "message": "删除成功"})
        else:
            self.write({"success": False, "message": "删除失败"})


class FunctionTreeHandler(AdminBaseHandler):
    """获取功能树API"""
    @tornado.web.authenticated
    def get(self):
        tree = FunctionRepository.get_tree()
        self.write({"success": True, "data": tree})


class FunctionParentsHandler(AdminBaseHandler):
    """获取父级功能列表API（用于二级联动）"""
    @tornado.web.authenticated
    def get(self):
        parents = FunctionRepository.get_all(parent_id=False, status=1)
        self.write({"success": True, "data": parents})


class RoleManageHandler(AdminBaseHandler):
    """角色管理页面"""
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        per_page = 20
        
        roles, total = RoleRepository.get_page(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        
        self.render("admin/roles.html",
                   title="角色管理",
                   username=self.current_user.decode('utf-8'),
                   active_menu="roles",
                   roles=roles,
                   page=page,
                   total_pages=total_pages,
                   total=total)


class RoleCreateHandler(AdminBaseHandler):
    """创建角色API"""
    @tornado.web.authenticated
    def post(self):
        name = self.get_body_argument("name", "").strip()
        code = self.get_body_argument("code", "").strip()
        description = self.get_body_argument("description", "").strip() or None
        
        if not name or not code:
            self.write({"success": False, "message": "角色名称和编码不能为空"})
            return
        
        role_id = RoleRepository.create(name, code, description)
        if role_id:
            self.write({"success": True, "message": "角色创建成功", "id": role_id})
        else:
            self.write({"success": False, "message": "角色名称或编码已存在"})


class RoleUpdateHandler(AdminBaseHandler):
    """更新角色API"""
    @tornado.web.authenticated
    def post(self):
        role_id = self.get_body_argument("id", "")
        name = self.get_body_argument("name", "").strip()
        description = self.get_body_argument("description", "").strip() or None
        status = self.get_body_argument("status", "").strip()
        
        if not role_id or not name:
            self.write({"success": False, "message": "参数错误"})
            return
        
        kwargs = {"name": name}
        if description is not None:
            kwargs["description"] = description
        if status:
            kwargs["status"] = int(status)
        
        if RoleRepository.update(int(role_id), **kwargs):
            self.write({"success": True, "message": "角色更新成功"})
        else:
            self.write({"success": False, "message": "系统角色不能修改或角色名称已存在"})


class RoleDeleteHandler(AdminBaseHandler):
    """删除角色API"""
    @tornado.web.authenticated
    def post(self):
        role_id = self.get_body_argument("id", "")
        if not role_id:
            self.write({"success": False, "message": "参数错误"})
            return
        
        if RoleRepository.delete(int(role_id)):
            self.write({"success": True, "message": "删除成功"})
        else:
            self.write({"success": False, "message": "系统角色不能删除"})


class RoleListHandler(AdminBaseHandler):
    """获取角色列表API（用于二级联动）"""
    @tornado.web.authenticated
    def get(self):
        roles = RoleRepository.get_all(status=1)
        self.write({"success": True, "data": roles})


class PermissionManageHandler(AdminBaseHandler):
    """权限管理页面"""
    @tornado.web.authenticated
    def get(self):
        # 获取所有角色
        roles = RoleRepository.get_all(status=1)
        
        # 默认选中第一个非系统角色
        default_role_id = None
        for role in roles:
            if not role['is_system']:
                default_role_id = role['id']
                break
        if not default_role_id and roles:
            default_role_id = roles[0]['id']
        
        # 获取权限树
        permission_tree = []
        if default_role_id:
            permission_tree = PermissionRepository.get_all_with_status(default_role_id)
        
        self.render("admin/permissions.html",
                   title="权限管理",
                   username=self.current_user.decode('utf-8'),
                   active_menu="permissions",
                   roles=roles,
                   default_role_id=default_role_id,
                   permission_tree=permission_tree)


class PermissionGrantHandler(AdminBaseHandler):
    """授予权限API"""
    @tornado.web.authenticated
    def post(self):
        role_id = self.get_body_argument("role_id", "").strip()
        function_ids_str = self.get_body_argument("function_ids", "").strip()
        
        if not role_id:
            self.write({"success": False, "message": "请选择角色"})
            return
        
        function_ids = [int(fid.strip()) for fid in function_ids_str.split(",") if fid.strip()]
        
        # 先清除该角色的所有权限
        PermissionRepository.revoke(int(role_id))
        
        # 重新授予权限
        if function_ids:
            PermissionRepository.grant(int(role_id), function_ids)
        
        self.write({"success": True, "message": "权限设置成功"})


class PermissionGetHandler(AdminBaseHandler):
    """获取角色权限API（用于二级联动）"""
    @tornado.web.authenticated
    def get(self):
        role_id = self.get_argument("role_id", "").strip()
        if not role_id:
            self.write({"success": False, "message": "请选择角色"})
            return
        
        permission_tree = PermissionRepository.get_all_with_status(int(role_id))
        self.write({"success": True, "data": permission_tree})


class MenuHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.current_user
        if not user:
            self.write({"success": True, "data": []})
            return
        username = user.decode("utf-8") if isinstance(user, bytes) else user

        if username == "admin":
            menu_tree = FunctionRepository.get_tree()
        else:
            from app.models.user import UserRepository
            db_user = UserRepository.get_user_by_username(username)
            if not db_user or not db_user.get("role_id"):
                self.write({"success": True, "data": []})
                return
            role_id = db_user["role_id"]
            menu_tree = PermissionRepository.get_menu_tree(role_id)

        self.write({"success": True, "data": menu_tree})
