import json
import os
import time
import re
import tornado.web
import tornado.gen
from app.controllers.user_chat import UserBaseHandler
from app.models.user import UserRepository
from app.models.im_model import (
    IMContactRepository, IMFriendRequestRepository, IMGroupRepository,
    IMMessageRepository, UPLOAD_DIR
)
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.ai_model import AIModelRepository
from app.models.db import get_connection

MAX_FILE_SIZE = 50 * 1024 * 1024


class IMIndexHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        if not user:
            return self.redirect("/user/login")
        contacts = IMContactRepository.get_contacts(user["id"])
        groups = IMGroupRepository.get_user_groups(user["id"])
        friends_json = json.dumps([{"id": c["contact_id"], "username": c["username"], "remark": c.get("remark")}
                                   for c in contacts], ensure_ascii=False)
        groups_json = json.dumps([{"id": g["id"], "name": g["name"], "member_count": g["member_count"]}
                                  for g in groups], ensure_ascii=False)
        emps = DigitalEmployeeRepository.get_all(status=1)
        emps_json = json.dumps([{"alias": e["alias"], "name": e["name"], "emp_type": e["emp_type"]}
                                for e in emps], ensure_ascii=False)
        self.render("user/im.html", user=user, friends_json=friends_json,
                    groups_json=groups_json, emps_json=emps_json, employees=emps)


class IMContactListHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        contacts = IMContactRepository.get_contacts(user["id"])
        result = [{"id": c["contact_id"], "username": c["username"], "remark": c.get("remark")}
                  for c in contacts]
        emps = DigitalEmployeeRepository.get_all(status=1)
        for e in emps:
            result.insert(0, {
                "id": -e["id"],
                "username": e["alias"],
                "remark": e["name"],
                "is_employee": True,
                "emp_type": e.get("emp_type"),
                "emp_alias": e["alias"]
            })
        self.write({"success": True, "data": result})


class IMContactRemoveHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        contact_id = int(self.get_body_argument("contact_id", "0"))
        if not contact_id or contact_id == user["id"]:
            return self.write({"success": False, "message": "参数错误"})
        if not IMContactRepository.is_contact(user["id"], contact_id):
            return self.write({"success": False, "message": "不是好友关系"})
        IMContactRepository.remove_contact(user["id"], contact_id)
        self.write({"success": True, "message": "已删除好友"})


class IMUserSearchHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        keyword = self.get_body_argument("keyword", "").strip()
        if not keyword:
            return self.write({"success": True, "data": []})
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id, username FROM users
                   WHERE username LIKE ? AND id != ? AND username != 'admin'
                   ORDER BY username""",
                (f"%{keyword}%", user["id"])
            ).fetchall()
            contact_ids = {c["contact_id"] for c in IMContactRepository.get_contacts(user["id"])}
            result = []
            pending_reqs = IMFriendRequestRepository.get_outgoing(user["id"])
            pending_to_ids = {r["to_user_id"] for r in pending_reqs}
            for r in rows:
                d = dict(r)
                d["is_contact"] = d["id"] in contact_ids
                d["pending"] = d["id"] in pending_to_ids
                result.append(d)
            self.write({"success": True, "data": result})


class IMFriendRequestSendHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        to_user_id = int(self.get_body_argument("user_id", "0"))
        message = self.get_body_argument("message", "").strip() or None
        if not to_user_id or to_user_id == user["id"]:
            return self.write({"success": False, "message": "参数错误"})
        if IMContactRepository.is_contact(user["id"], to_user_id):
            return self.write({"success": False, "message": "已是好友"})
        req_id = IMFriendRequestRepository.send_request(user["id"], to_user_id, message)
        if req_id:
            self.write({"success": True, "message": "好友请求已发送"})
        else:
            self.write({"success": False, "message": "已有待处理的好友请求"})


class IMFriendRequestListHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        incoming = IMFriendRequestRepository.get_incoming(user["id"])
        outgoing = IMFriendRequestRepository.get_outgoing(user["id"])
        self.write({"success": True, "data": {"incoming": incoming, "outgoing": outgoing}})


class IMFriendRequestHandleHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        request_id = int(self.get_body_argument("id", "0"))
        if action == "accept":
            IMFriendRequestRepository.accept(request_id)
            self.write({"success": True, "message": "已接受"})
        elif action == "reject":
            IMFriendRequestRepository.reject(request_id)
            self.write({"success": True, "message": "已拒绝"})
        else:
            self.write({"success": False, "message": "未知操作"})


class IMGroupCreateHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        name = self.get_body_argument("name", "").strip()
        member_ids_str = self.get_body_argument("member_ids", "").strip()
        if not member_ids_str:
            return self.write({"success": False, "message": "请至少选择一位好友"})
        member_ids = [int(x) for x in member_ids_str.split(",") if x.strip().isdigit()]
        member_names = []
        with get_connection() as conn:
            for mid in member_ids:
                row = conn.execute("SELECT username FROM users WHERE id = ?", (mid,)).fetchone()
                if row:
                    member_names.append(row["username"])
        if not name:
            name = "未命名群聊"
        group_id = IMGroupRepository.create(name, user["id"], member_ids)
        IMMessageRepository.send_group(group_id, 0, "system",
            json.dumps({"action": "create", "inviter": user["username"],
                        "member_names": member_names}, ensure_ascii=False))
        self.write({"success": True, "message": "群创建成功", "group_id": group_id, "group_name": name})


class IMGroupInviteHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        group_id = int(self.get_body_argument("group_id", "0"))
        member_ids_str = self.get_body_argument("member_ids", "").strip()
        if not group_id or not member_ids_str:
            return self.write({"success": False, "message": "参数错误"})
        member_ids = [int(x) for x in member_ids_str.split(",") if x.strip().isdigit()]
        IMGroupRepository.add_members(group_id, member_ids)
        member_names = []
        with get_connection() as conn:
            for mid in member_ids:
                row = conn.execute("SELECT username FROM users WHERE id = ?", (mid,)).fetchone()
                if row:
                    member_names.append(row["username"])
        names_str = "、".join(member_names)
        IMMessageRepository.send_group(group_id, 0, "system",
            json.dumps({"action": "invite", "inviter": user["username"],
                        "member_names": member_names}, ensure_ascii=False))
        self.write({"success": True, "message": f"已邀请 {names_str} 加入群聊"})


class IMGroupLeaveHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        group_id = int(self.get_body_argument("group_id", "0"))
        if not group_id:
            return self.write({"success": False, "message": "参数错误"})
        if IMGroupRepository.is_owner(group_id, user["id"]):
            return self.write({"success": False, "message": "群主不能直接退出，请转让群主或解散群聊"})
        ok = IMGroupRepository.leave_group(group_id, user["id"])
        if not ok:
            return self.write({"success": False, "message": "操作失败"})
        IMMessageRepository.send_group(group_id, 0, "system",
            json.dumps({"action": "member_leave", "username": user["username"]}, ensure_ascii=False))
        self.write({"success": True, "message": "已退出群聊"})


class IMGroupTransferHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        group_id = int(self.get_body_argument("group_id", "0"))
        to_user_id = int(self.get_body_argument("to_user_id", "0"))
        if not group_id or not to_user_id:
            return self.write({"success": False, "message": "参数错误"})
        ok = IMGroupRepository.transfer_owner(group_id, user["id"], to_user_id)
        if not ok:
            return self.write({"success": False, "message": "转让失败，仅群主可操作"})
        target_username = ""
        with get_connection() as conn:
            row = conn.execute("SELECT username FROM users WHERE id = ?", (to_user_id,)).fetchone()
            if row:
                target_username = row["username"]
        IMMessageRepository.send_group(group_id, 0, "system",
            json.dumps({"action": "owner_change", "old_owner": user["username"],
                        "new_owner": target_username}, ensure_ascii=False))
        self.write({"success": True, "message": f"已将群主转让给 {target_username}"})


class IMGroupDisbandHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        group_id = int(self.get_body_argument("group_id", "0"))
        if not group_id:
            return self.write({"success": False, "message": "参数错误"})
        ok = IMGroupRepository.disband_group(group_id, user["id"])
        if not ok:
            return self.write({"success": False, "message": "解散失败，仅群主可操作"})
        self.write({"success": True, "message": "群聊已解散"})


class IMGroupRenameHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        group_id = int(self.get_body_argument("group_id", "0"))
        new_name = self.get_body_argument("name", "").strip()
        if not group_id or not new_name:
            return self.write({"success": False, "message": "参数错误"})
        if len(new_name) > 30:
            return self.write({"success": False, "message": "群名称不能超过30个字符"})
        ok = IMGroupRepository.rename_group(group_id, user["id"], new_name)
        if not ok:
            return self.write({"success": False, "message": "仅群主可修改群名称"})
        IMMessageRepository.send_group(group_id, 0, "system",
            json.dumps({"action": "rename", "editor": user["username"],
                        "new_name": new_name}, ensure_ascii=False))
        self.write({"success": True, "message": "群名称已更新", "group_name": new_name})


class IMGroupMembersHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        group_id = int(self.get_argument("group_id", "0"))
        members = IMGroupRepository.get_members(group_id)
        self.write({"success": True, "data": members})


class IMPrivateChatSSEHandler(UserBaseHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def post(self):
        user = self.get_current_user_info()
        peer_id = int(self.get_body_argument("peer_id", "0"))
        message = self.get_body_argument("message", "").strip()
        msg_type = self.get_body_argument("msg_type", "text")
        file_name = self.get_body_argument("file_name", "").strip() or None
        file_size = int(self.get_body_argument("file_size", "0"))
        file_path = self.get_body_argument("file_path", "").strip() or None
        emp_alias = self.get_body_argument("emp_alias", "").strip() or None

        if not peer_id and not emp_alias:
            self._sse_error("参数错误")
            return

        if emp_alias:
            if msg_type == "image" and file_path:
                file_name = os.path.basename(file_path)
            content = file_path if msg_type == "image" else (message or "")
            msg_id = IMMessageRepository.send_private_employee(
                user["id"], emp_alias, msg_type, content, file_name, file_size, file_path
            )
            self.write("data: " + json.dumps({"type": "sent", "id": msg_id, "emp_alias": emp_alias}, ensure_ascii=False) + "\n\n")
            self.flush()

            if msg_type == "text" and message:
                emp = DigitalEmployeeRepository.get_by_alias(emp_alias)
                if emp and emp["emp_type"] == "AI":
                    model = None
                    if emp.get("model_id"):
                        model = AIModelRepository.get_by_id(emp["model_id"])
                    if not model:
                        model = AIModelRepository.get_default()
                    if model:
                        try:
                            context = IMMessageRepository.get_employee_context(user["id"], emp_alias, "private", limit=20)
                            from openai import OpenAI
                            client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
                            msgs = []
                            if emp.get("system_prompt"):
                                msgs.append({"role": "system", "content": emp["system_prompt"]})
                            msgs.extend(context)
                            response = client.chat.completions.create(
                                model=model["model_name"],
                                messages=msgs,
                                extra_body={"thinking": {"type": "enabled"}}
                            )
                            reply = response.choices[0].message.content or "抱歉，我暂时无法回答这个问题。"
                            IMMessageRepository.send_private_employee(
                                0, emp_alias, "text", reply
                            )
                        except Exception as e:
                            err_reply = f"抱歉，服务暂时不可用。"
                            IMMessageRepository.send_private_employee(0, emp_alias, "text", err_reply)
                    else:
                        IMMessageRepository.send_private_employee(
                            0, emp_alias, "text", "抱歉，AI 服务未配置，请联系管理员。"
                        )
                elif emp and emp.get("api_url"):
                    self._handle_emp_api_reply(emp, message, user, emp_alias, "private")
                else:
                    IMMessageRepository.send_private_employee(
                        0, emp_alias, "text", "抱歉，该数字员工暂不可用。"
                    )
            self.finish()
            return

        if not IMContactRepository.is_contact(user["id"], peer_id):
            self._sse_error("你们还不是好友")
            return

        if msg_type == "image" and file_path:
            file_name = os.path.basename(file_path)

        content = file_path if msg_type == "image" else (message or "")
        msg_id = IMMessageRepository.send_private(
            user["id"], peer_id, msg_type, content, file_name, file_size, file_path
        )
        self.write("data: " + json.dumps({"type": "sent", "id": msg_id}, ensure_ascii=False) + "\n\n")
        self.flush()
        self.finish()

    def _sse_error(self, msg):
        self.set_header("Content-Type", "text/event-stream")
        self.write("data: " + json.dumps({"type": "error", "content": msg}, ensure_ascii=False) + "\n\n")
        self.flush()
        self.finish()


class IMPrivatePollHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        peer_id = int(self.get_argument("peer_id", "0"))
        last_id = int(self.get_argument("last_id", "0"))
        rendered_ids_str = self.get_argument("rendered_ids", "")
        emp_alias = self.get_argument("emp_alias", "").strip() or None
        if emp_alias:
            messages = IMMessageRepository.get_employee_private_messages(user["id"], emp_alias)
        else:
            messages = IMMessageRepository.get_private_messages(user["id"], peer_id)
        new_msgs = [m for m in messages if m["id"] > last_id]
        result = []
        for m in new_msgs:
            result.append({
                "id": m["id"], "from_user_id": m["from_user_id"],
                "to_user_id": m["to_user_id"], "msg_type": m["msg_type"],
                "content": m["content"], "file_name": m.get("file_name"),
                "file_path": m.get("file_path"), "file_size": m.get("file_size", 0),
                "from_username": m.get("from_username") or emp_alias or "",
                "is_recalled": m.get("is_recalled", 0),
                "create_at": m["create_at"]
            })
        rendered_ids = [int(x) for x in rendered_ids_str.split(",") if x.strip().isdigit()]
        recalled_ids = IMMessageRepository.get_recalled_private_ids(user["id"], peer_id, rendered_ids)
        self.write({"success": True, "data": result, "recalled_ids": recalled_ids})


class IMGroupPollHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        group_id = int(self.get_argument("group_id", "0"))
        last_id = int(self.get_argument("last_id", "0"))
        rendered_ids_str = self.get_argument("rendered_ids", "")
        messages = IMMessageRepository.get_group_messages(group_id)
        new_msgs = [m for m in messages if m["id"] > last_id]
        result = []
        for m in new_msgs:
            result.append({
                "id": m["id"], "group_id": m["group_id"],
                "from_user_id": m["from_user_id"], "msg_type": m["msg_type"],
                "content": m["content"], "file_name": m.get("file_name"),
                "file_path": m.get("file_path"), "file_size": m.get("file_size", 0),
                "from_username": m["from_username"], "at_employee": m.get("at_employee"),
                "is_recalled": m.get("is_recalled", 0),
                "create_at": m["create_at"]
            })
        rendered_ids = [int(x) for x in rendered_ids_str.split(",") if x.strip().isdigit()]
        recalled_ids = IMMessageRepository.get_recalled_group_ids(group_id, rendered_ids)
        self.write({"success": True, "data": result, "recalled_ids": recalled_ids})


class IMGroupChatSendHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        group_id = int(self.get_body_argument("group_id", "0"))
        message = self.get_body_argument("message", "").strip()
        msg_type = self.get_body_argument("msg_type", "text")
        file_name = self.get_body_argument("file_name", "").strip() or None
        file_size = int(self.get_body_argument("file_size", "0"))
        file_path = self.get_body_argument("file_path", "").strip() or None
        at_employee = self.get_body_argument("at_employee", "").strip() or None

        if msg_type == "image" and file_path:
            file_name = os.path.basename(file_path)

        if msg_type == "image":
            content = file_path
        else:
            content = message

        msg_id = IMMessageRepository.send_group(
            group_id, user["id"], msg_type,
            content, file_name, file_size, file_path, at_employee
        )

        result = {"success": True, "message": "发送成功", "id": msg_id}

        if at_employee:
            emp = DigitalEmployeeRepository.get_by_alias(at_employee)
            if emp and emp["emp_type"] == "AI":
                try:
                    from openai import OpenAI
                    model = AIModelRepository.get_by_id(emp["model_id"]) if emp.get("model_id") else AIModelRepository.get_default()
                    if not model:
                        model = AIModelRepository.get_default()
                    if model:
                        pure_msg = re.sub(r'@\S+\s*', '', message).strip() or message
                        context = IMMessageRepository.get_employee_context(user["id"], at_employee, "group", group_id=group_id, limit=20)
                        client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
                        msgs = []
                        if emp.get("system_prompt"):
                            msgs.append({"role": "system", "content": emp["system_prompt"]})
                        msgs.extend(context)
                        response = client.chat.completions.create(
                            model=model["model_name"],
                            messages=msgs,
                            extra_body={"thinking": {"type": "enabled"}}
                        )
                        reply = response.choices[0].message.content or "抱歉，我暂时无法回答这个问题。"
                        emp_reply_id = IMMessageRepository.send_group(
                            group_id, 0, "text", reply,
                            at_employee=at_employee
                        )
                        result["employee_reply"] = {
                            "id": emp_reply_id, "content": reply,
                            "from_username": f"@{at_employee}",
                            "at_employee": at_employee
                        }
                except Exception as e:
                    error_msg = f"@{at_employee} 调用失败: {str(e)[:100]}"
                    err_id = IMMessageRepository.send_group(
                        group_id, 0, "text", error_msg,
                        at_employee=at_employee
                    )
                    result["employee_reply"] = {
                        "id": err_id, "content": error_msg,
                        "from_username": f"@{at_employee}",
                        "at_employee": at_employee
                    }
            elif emp and emp.get("api_url"):
                try:
                    import requests
                    api_url = emp.get("api_url")
                    pc = emp.get("params_config")
                    url = api_url
                    pure_msg = re.sub(r'@\S+\s*', '', message).strip()
                    if isinstance(pc, dict) and pc.get("param_key"):
                        if pure_msg:
                            url = f"{api_url}?{pc['param_key']}={requests.utils.quote(pure_msg)}"
                    resp = requests.get(url, timeout=15)
                    data = resp.json()
                    from app.controllers.user_chat import build_api_message
                    result_obj = build_api_message(emp, data)
                    if isinstance(result_obj, dict) and result_obj.get("type") == "music" and result_obj.get("cover"):
                        IMMessageRepository.send_group(
                            group_id, 0, "image", result_obj["cover"],
                            file_path=result_obj["cover"],
                            at_employee=at_employee
                        )
                    text = ""
                    if isinstance(result_obj, dict) and result_obj.get("type") == "music":
                        text = f"🎵 {result_obj['name']}\n👤 {result_obj['singer']}"
                        if result_obj.get("music_url"):
                            text += f"\n🔗 {result_obj['music_url']}"
                    elif isinstance(result_obj, dict):
                        text = result_obj.get("text", "")
                    else:
                        text = str(result_obj)
                    if text:
                        emp_reply_id = IMMessageRepository.send_group(
                            group_id, 0, "text", text, at_employee=at_employee
                        )
                        result["employee_reply"] = {
                            "id": emp_reply_id, "content": text,
                            "from_username": f"@{at_employee}",
                            "at_employee": at_employee
                        }
                except Exception:
                    err_id = IMMessageRepository.send_group(
                        group_id, 0, "text", f"@{at_employee} 服务暂时不可用",
                        at_employee=at_employee
                    )
                    result["employee_reply"] = {
                        "id": err_id, "content": f"@{at_employee} 服务暂时不可用",
                        "from_username": f"@{at_employee}",
                        "at_employee": at_employee
                    }

        self.write(result)


class IMFileUploadHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        file_info = self.request.files.get("file", [None])[0]
        if not file_info:
            return self.write({"success": False, "message": "未选择文件"})
        if len(file_info["body"]) > MAX_FILE_SIZE:
            return self.write({"success": False, "message": "文件大小超过50MB限制"})
        ext = os.path.splitext(file_info["filename"])[1].lower() or ""
        safe_name = f"{user['id']}_{int(time.time()*1000)}{ext}"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        with open(file_path, "wb") as f:
            f.write(file_info["body"])
        file_size = len(file_info["body"])
        is_image = ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg")
        msg_type = "image" if is_image else "file"
        relative_path = f"/user/im/files/{safe_name}"
        self.write({
            "success": True,
            "data": {
                "file_name": file_info["filename"],
                "file_size": file_size,
                "file_path": relative_path,
                "msg_type": msg_type
            }
        })


class IMFileDownloadHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self, filename):
        filename = os.path.basename(filename)
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.isfile(file_path):
            self.set_status(404)
            return self.write("文件不存在")
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
            ".svg": "image/svg+xml", ".pdf": "application/pdf",
            ".zip": "application/zip", ".txt": "text/plain"
        }
        self.set_header("Content-Type", content_types.get(ext, "application/octet-stream"))
        self.set_header("Content-Disposition", f'inline; filename="{filename}"')
        with open(file_path, "rb") as f:
            self.write(f.read())


class IMEmployeeListHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        emps = DigitalEmployeeRepository.get_all(status=1)
        result = [{"alias": e["alias"], "name": e["name"], "emp_type": e["emp_type"]} for e in emps]
        self.write({"success": True, "data": result})


class IMPrivateRecallHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        msg_id = int(self.get_body_argument("msg_id", "0"))
        if not msg_id:
            return self.write({"success": False, "message": "参数错误"})
        ok = IMMessageRepository.recall_private(msg_id, user["id"])
        if ok:
            self.write({"success": True, "message": "已撤回"})
        else:
            self.write({"success": False, "message": "撤回失败，可能超时或无权操作"})


class IMGroupRecallHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        msg_id = int(self.get_body_argument("msg_id", "0"))
        if not msg_id:
            return self.write({"success": False, "message": "参数错误"})
        ok = IMMessageRepository.recall_group(msg_id, user["id"])
        if ok:
            self.write({"success": True, "message": "已撤回"})
        else:
            self.write({"success": False, "message": "撤回失败，可能超时或无权操作"})


class IMFriendRequestCountHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        count = IMFriendRequestRepository.get_incoming_count(user["id"])
        self.write({"success": True, "count": count})
