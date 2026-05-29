import json
import tornado.web
from app.controllers.admin import AdminBaseHandler
from app.models.im_model import IMAdminRepository, IMGroupRepository, IMMessageRepository
from app.models.digital_employee import DigitalEmployeeRepository


class IMGroupListPageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/im_groups.html", title="群管理", username=self.current_user.decode('utf-8'))


class IMGroupListAPIHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        keyword = self.get_argument("keyword", "").strip()
        groups, total = IMAdminRepository.get_all_groups(page=page, keyword=keyword)
        self.write({"success": True, "data": groups, "total": total})

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        if action == "disband":
            group_id = int(self.get_body_argument("group_id", "0"))
            IMAdminRepository.disband_group_admin(group_id)
            self.write({"success": True, "message": "群聊已解散"})
        elif action == "ban":
            group_id = int(self.get_body_argument("group_id", "0"))
            reason = self.get_body_argument("reason", "")
            IMAdminRepository.ban_group(group_id, reason)
            self.write({"success": True, "message": "群聊已禁言"})
        elif action == "announce":
            group_id = int(self.get_body_argument("group_id", "0"))
            content = self.get_body_argument("content", "").strip()
            if not content:
                self.write({"success": False, "message": "公告内容不能为空"})
                return
            IMAdminRepository.send_announcement(group_id, content)
            self.write({"success": True, "message": "公告已发送"})
        else:
            self.write({"success": False, "message": "未知操作"})


class IMGroupMembersAPIHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        group_id = int(self.get_argument("group_id", "0"))
        members = IMAdminRepository.get_group_members_admin(group_id)
        self.write({"success": True, "data": members})


class IMGroupMessagesAPIHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        group_id = int(self.get_argument("group_id", "0"))
        page = int(self.get_argument("page", "1"))
        per_page = 50
        msgs, total = IMAdminRepository.get_group_messages(group_id, page, per_page)
        self.write({"success": True, "data": msgs, "total": total})


class IMAllChatWordsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        words = IMAdminRepository.get_all_chat_words(200)
        self.write({"success": True, "data": words})


class IMFilePageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/im_files.html", title="文件管理", username=self.current_user.decode('utf-8'))


class IMFileAPIHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        keyword = self.get_argument("keyword", "").strip()
        files, total = IMAdminRepository.get_all_files(page=page, keyword=keyword)
        result = []
        for f in files:
            result.append({
                "id": f["id"],
                "msg_type": f["msg_type"],
                "file_name": f.get("file_name", ""),
                "file_path": f.get("file_path", ""),
                "file_size": f.get("file_size", 0),
                "create_at": f["create_at"],
                "source": f["source"],
                "from_user_id": f["from_user_id"]
            })
        self.write({"success": True, "data": result, "total": total})

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        if action == "delete":
            file_id = int(self.get_body_argument("id", "0"))
            source = self.get_body_argument("source", "private")
            IMAdminRepository.delete_file_record(file_id, source)
            self.write({"success": True, "message": "文件记录已删除"})
        else:
            self.write({"success": False, "message": "未知操作"})


class IMServerPageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/im_servers.html", title="服务器管理", username=self.current_user.decode('utf-8'))


class IMServerAPIHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        servers = IMAdminRepository.get_all_servers()
        self.write({"success": True, "data": servers})

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        if action == "create":
            name = self.get_body_argument("name", "").strip()
            host = self.get_body_argument("host", "").strip()
            port = int(self.get_body_argument("port", "10086"))
            desc = self.get_body_argument("description", "").strip()
            if not name or not host:
                self.write({"success": False, "message": "名称和地址不能为空"})
                return
            IMAdminRepository.create_server(name, host, port, desc)
            self.write({"success": True, "message": "服务器已创建"})
        elif action == "update":
            sid = int(self.get_body_argument("id", "0"))
            name = self.get_body_argument("name", "").strip()
            host = self.get_body_argument("host", "").strip()
            port = int(self.get_body_argument("port", "10086"))
            desc = self.get_body_argument("description", "").strip()
            IMAdminRepository.update_server(sid, name, host, port, desc)
            self.write({"success": True, "message": "服务器已更新"})
        elif action == "delete":
            sid = int(self.get_body_argument("id", "0"))
            IMAdminRepository.delete_server(sid)
            self.write({"success": True, "message": "服务器已删除"})
        elif action == "toggle":
            sid = int(self.get_body_argument("id", "0"))
            active = int(self.get_body_argument("is_active", "1"))
            IMAdminRepository.toggle_server(sid, active)
            self.write({"success": True, "message": "状态已切换"})
        else:
            self.write({"success": False, "message": "未知操作"})


class IMToolPageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        employees = DigitalEmployeeRepository.get_all(status=1)
        self.render("admin/im_tools.html", employees=employees, title="工具管理", username=self.current_user.decode('utf-8'))


class IMToolAPIHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        tools, total = IMAdminRepository.get_all_tools(page=page)
        self.write({"success": True, "data": tools, "total": total})

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        if action == "create":
            name = self.get_body_argument("name", "").strip()
            code = self.get_body_argument("code", "").strip()
            tool_type = self.get_body_argument("tool_type", "api")
            desc = self.get_body_argument("description", "").strip()
            config = self.get_body_argument("config", "{}")
            employee_id = self.get_body_argument("employee_id", "").strip() or None
            if not name or not code:
                self.write({"success": False, "message": "名称和标识不能为空"})
                return
            IMAdminRepository.create_tool(name, code, tool_type, desc, config, employee_id)
            self.write({"success": True, "message": "工具已创建"})
        elif action == "update":
            tid = int(self.get_body_argument("id", "0"))
            name = self.get_body_argument("name", "").strip()
            code = self.get_body_argument("code", "").strip()
            tool_type = self.get_body_argument("tool_type", "api")
            desc = self.get_body_argument("description", "").strip()
            config = self.get_body_argument("config", "{}")
            employee_id = self.get_body_argument("employee_id", "").strip() or None
            IMAdminRepository.update_tool(tid, name, code, tool_type, desc, config, employee_id)
            self.write({"success": True, "message": "工具已更新"})
        elif action == "delete":
            tid = int(self.get_body_argument("id", "0"))
            IMAdminRepository.delete_tool(tid)
            self.write({"success": True, "message": "工具已删除"})
        elif action == "toggle":
            tid = int(self.get_body_argument("id", "0"))
            status = int(self.get_body_argument("status", "1"))
            IMAdminRepository.toggle_tool(tid, status)
            self.write({"success": True, "message": "状态已切换"})
        else:
            self.write({"success": False, "message": "未知操作"})
