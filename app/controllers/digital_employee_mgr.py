import json
import tornado.web
import tornado.gen
import requests
from app.controllers.admin import AdminBaseHandler
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.ai_model import AIModelRepository
from app.models.api_interface import ApiInterfaceRepository
from app.models.conversation import ConversationRepository
from app.models.user import UserRepository


class DigitalEmployeeHandler(AdminBaseHandler):
    """数字员工管理页面"""
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        per_page = 20
        data_list, total = DigitalEmployeeRepository.get_page(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        models = AIModelRepository.get_all(status=1)
        apis = ApiInterfaceRepository.get_all(status=1)
        self.render("admin/digital_employees.html",
                    title="数字员工",
                    username=self.current_user.decode('utf-8'),
                    active_menu="digital_employees",
                    data_list=data_list,
                    data_json=json.dumps(data_list, ensure_ascii=False),
                    models=models,
                    apis=apis,
                    page=page,
                    total_pages=total_pages,
                    total=total)


class DigitalEmployeeCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = self.get_body_argument("name", "").strip()
        alias = self.get_body_argument("alias", "").strip()
        emp_type = self.get_body_argument("emp_type", "普通").strip()
        model_id = self.get_body_argument("model_id", "").strip() or None
        api_id = self.get_body_argument("api_id", "").strip() or None
        system_prompt = self.get_body_argument("system_prompt", "").strip() or None
        params_key = self.get_body_argument("params_key", "").strip() or None
        params_label = self.get_body_argument("params_label", "").strip() or None
        params_placeholder = self.get_body_argument("params_placeholder", "").strip() or None
        description = self.get_body_argument("description", "").strip() or None
        sort_order = int(self.get_body_argument("sort_order", "0"))

        if not name or not alias:
            return self.write({"success": False, "message": "名称和别名不能为空"})

        params_config = None
        if params_key:
            params_config = {
                "param_key": params_key,
                "param_label": params_label or "参数",
                "required": True,
                "placeholder": params_placeholder or ""
            }

        eid = DigitalEmployeeRepository.create(
            name, alias, emp_type,
            int(model_id) if model_id else None,
            int(api_id) if api_id else None,
            system_prompt, params_config, description, sort_order
        )
        if eid:
            self.write({"success": True, "message": "创建成功", "id": eid})
        else:
            self.write({"success": False, "message": "别名已存在"})


class DigitalEmployeeUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        eid = self.get_body_argument("id", "")
        if not eid:
            return self.write({"success": False, "message": "参数错误"})

        kwargs = {}
        for f in ["name", "alias", "emp_type", "system_prompt", "description"]:
            v = self.get_body_argument(f, "").strip()
            if v:
                kwargs[f] = v

        mid = self.get_body_argument("model_id", "").strip()
        aid = self.get_body_argument("api_id", "").strip()
        so = self.get_body_argument("sort_order", "").strip()
        st = self.get_body_argument("status", "").strip()

        if mid:
            kwargs["model_id"] = int(mid)
        else:
            kwargs["model_id"] = None
        if aid:
            kwargs["api_id"] = int(aid)
        else:
            kwargs["api_id"] = None
        if so:
            kwargs["sort_order"] = int(so)
        if st:
            kwargs["status"] = int(st)

        pk = self.get_body_argument("params_key", "").strip()
        if pk:
            kwargs["params_config"] = {
                "param_key": pk,
                "param_label": self.get_body_argument("params_label", "").strip() or "参数",
                "required": True,
                "placeholder": self.get_body_argument("params_placeholder", "").strip() or ""
            }
        else:
            kwargs["params_config"] = None

        DigitalEmployeeRepository.update(int(eid), **kwargs)
        self.write({"success": True, "message": "更新成功"})


class DigitalEmployeeDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        eid = self.get_body_argument("id", "")
        if eid:
            DigitalEmployeeRepository.delete(int(eid))
            self.write({"success": True, "message": "删除成功"})
        else:
            self.write({"success": False, "message": "参数错误"})


class DigitalEmployeeDispatchHandler(AdminBaseHandler):
    """数字员工调度：根据@alias 分发给AI模型或API接口"""
    @tornado.web.authenticated
    def post(self):
        alias = self.get_body_argument("alias", "").strip()
        message = self.get_body_argument("message", "").strip()
        conversation_id = self.get_body_argument("conversation_id", "").strip() or None

        if not alias:
            return self.write({"success": False, "message": "请指定数字员工别名"})

        emp = DigitalEmployeeRepository.get_by_alias(alias)
        if not emp:
            return self.write({"success": False, "message": f"未找到数字员工 @{alias}"})

        if emp["emp_type"] == "AI":
            return self._handle_ai(emp, message, conversation_id)
        else:
            return self._handle_api(emp, message)

    def _handle_ai(self, emp, message, conversation_id=None):
        if not emp.get("api_key"):
            return self.write({"success": False, "message": "请先在模型管理中配置默认模型"})

        try:
            admin_username = self.current_user.decode('utf-8')
            admin_user = UserRepository.get_user_by_username(admin_username)
            user_id = admin_user["id"] if admin_user else 0

            if not conversation_id:
                title = message[:30] + ("..." if len(message) > 30 else "")
                conversation_id = ConversationRepository.create(user_id, title, emp.get("model_id"))
            else:
                conversation_id = int(conversation_id)

            ConversationRepository.save_message(conversation_id, "user", message, "text")

            from openai import OpenAI
            client = OpenAI(api_key=emp["api_key"], base_url=emp["base_url"])
            messages = []
            if emp.get("system_prompt"):
                messages.append({"role": "system", "content": emp["system_prompt"]})
            history_msgs = ConversationRepository.get_recent_messages(conversation_id, 30)
            for m in history_msgs:
                role = "assistant" if m["role"] == "assistant" else "user"
                messages.append({"role": role, "content": m["content"]})
            response = client.chat.completions.create(
                model=emp["model_code_name"] or emp.get("model_name", ""),
                messages=messages,
                extra_body={"thinking": {"type": "enabled"}}
            )
            reply = response.choices[0].message.content
            usage = response.usage
            AIModelRepository.add_token_log(
                emp["model_id"],
                usage.prompt_tokens, usage.completion_tokens
            )
            ConversationRepository.save_message(conversation_id, "assistant", reply, "text")
            self.write({"success": True, "data": {"reply": reply, "type": "AI", "from": emp["alias"],
                        "conversation_id": conversation_id}})
        except Exception as e:
            self.write({"success": False, "message": f"AI调用失败: {str(e)[:200]}"})

    def _handle_api(self, emp, message):
        api_url = emp.get("api_url")
        if not api_url:
            return self.write({"success": False, "message": "该数字员工未关联API接口"})

        pc = emp.get("params_config")
        url = api_url
        if isinstance(pc, dict) and pc.get("param_key"):
            if message:
                url = f"{api_url}?{pc['param_key']}={message}"
            elif pc.get("required"):
                return self.write({"success": False, "message": f"请输入{pc.get('param_label','参数')}",
                                   "need_param": True, "placeholder": pc.get("placeholder", "")})

        try:
            resp = requests.get(url, timeout=15)
            data = resp.json()
            self.write({"success": True, "data": data, "type": "API", "from": emp["alias"]})
        except Exception as e:
            self.write({"success": False, "message": f"API调用失败: {str(e)[:200]}"})


class DigitalEmployeeChatSSEHandler(AdminBaseHandler):
    """数字员工AI对话 - SSE流式响应"""
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        alias = self.get_argument("alias", "").strip()
        message = self.get_argument("message", "").strip()
        conversation_id = self.get_argument("conversation_id", "").strip() or None

        if not alias or not message:
            self.set_header("Content-Type", "text/event-stream")
            self.write("data: " + json.dumps({"error": "参数缺失"}, ensure_ascii=False) + "\n\n")
            return self.finish()

        emp = DigitalEmployeeRepository.get_by_alias(alias)
        if not emp or emp["emp_type"] != "AI":
            self.set_header("Content-Type", "text/event-stream")
            self.write("data: " + json.dumps({"error": f"AI数字员工@{alias}不存在"}, ensure_ascii=False) + "\n\n")
            return self.finish()

        admin_username = self.current_user.decode('utf-8')
        admin_user = UserRepository.get_user_by_username(admin_username)
        user_id = admin_user["id"] if admin_user else 0

        if not conversation_id:
            title = message[:30] + ("..." if len(message) > 30 else "")
            conversation_id = ConversationRepository.create(user_id, title, emp.get("model_id"))
        else:
            conversation_id = int(conversation_id)

        ConversationRepository.save_message(conversation_id, "user", message, "text")

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")

        self.write("data: " + json.dumps({"conversation_id": conversation_id}, ensure_ascii=False) + "\n\n")
        yield self.flush()

        try:
            from openai import OpenAI
            client = OpenAI(api_key=emp["api_key"], base_url=emp["base_url"])
            messages = []
            if emp.get("system_prompt"):
                messages.append({"role": "system", "content": emp["system_prompt"]})
            history_msgs = ConversationRepository.get_recent_messages(conversation_id, 30)
            for m in history_msgs:
                role = "assistant" if m["role"] == "assistant" else "user"
                messages.append({"role": role, "content": m["content"]})
            stream = client.chat.completions.create(
                model=emp["model_code_name"] or emp.get("model_name", ""),
                messages=messages,
                stream=True,
                extra_body={"thinking": {"type": "enabled"}}
            )
            full_content = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                    self.write("data: " + json.dumps({"chunk": full_content}, ensure_ascii=False) + "\n\n")
                    yield self.flush()
            ConversationRepository.save_message(conversation_id, "assistant", full_content, "text")
            self.write("data: " + json.dumps({"done": True}, ensure_ascii=False) + "\n\n")
        except Exception as e:
            ConversationRepository.save_message(conversation_id, "system", str(e)[:200], "error")
            self.write("data: " + json.dumps({"error": str(e)[:200]}, ensure_ascii=False) + "\n\n")
        finally:
            self.finish()


class DigitalChatPageHandler(AdminBaseHandler):
    """数字员工对话页面"""
    @tornado.web.authenticated
    def get(self):
        emps = DigitalEmployeeRepository.get_all(status=1)
        self.render("admin/digital_chat.html",
                    title="数字员工对话",
                    username=self.current_user.decode('utf-8'),
                    active_menu="digital_employees",
                    employees=emps)

