import json
import tornado.web
import tornado.gen
from app.controllers.admin import AdminBaseHandler
from app.models.ai_model import AIModelRepository


class ModelEngineHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        per_page = 6
        models, total = AIModelRepository.get_page(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        self.render("admin/models.html",
                    title="模型引擎",
                    username=self.current_user.decode('utf-8'),
                    active_menu="models",
                    models=models,
                    page=page,
                    total_pages=total_pages,
                    total=total)


class ModelCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = self.get_body_argument("name", "").strip()
        code = self.get_body_argument("code", "").strip()
        api_key = self.get_body_argument("api_key", "").strip()
        base_url = self.get_body_argument("base_url", "").strip()
        model_name = self.get_body_argument("model_name", "").strip()
        description = self.get_body_argument("description", "").strip() or None
        is_default = int(self.get_body_argument("is_default", "0"))
        if not all([name, code, api_key, base_url, model_name]):
            return self.write({"success": False, "message": "必填项不能为空"})
        mid = AIModelRepository.create(name, code, api_key, base_url, model_name, description, is_default)
        if mid:
            self.write({"success": True, "message": "模型创建成功", "id": mid})
        else:
            self.write({"success": False, "message": "模型编码已存在"})


class ModelUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        model_id = self.get_body_argument("id", "")
        if not model_id:
            return self.write({"success": False, "message": "参数错误"})
        kwargs = {}
        for f in ["name", "code", "api_key", "base_url", "model_name", "description"]:
            v = self.get_body_argument(f, "").strip()
            if v:
                kwargs[f] = v
        is_default = self.get_body_argument("is_default", "")
        status = self.get_body_argument("status", "")
        if is_default != "":
            kwargs["is_default"] = int(is_default)
        if status != "":
            kwargs["status"] = int(status)
        if AIModelRepository.update(int(model_id), **kwargs):
            self.write({"success": True, "message": "更新成功"})
        else:
            self.write({"success": False, "message": "更新失败，编码可能已存在"})


class ModelDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        model_id = self.get_body_argument("id", "")
        if not model_id:
            return self.write({"success": False, "message": "参数错误"})
        if AIModelRepository.delete(int(model_id)):
            self.write({"success": True, "message": "删除成功"})
        else:
            self.write({"success": False, "message": "删除失败"})


class ModelSetDefaultHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        model_id = self.get_body_argument("id", "")
        if not model_id:
            return self.write({"success": False, "message": "参数错误"})
        AIModelRepository.set_default(int(model_id))
        self.write({"success": True, "message": "已设为默认模型"})


class ModelTokenStatsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        model_id = self.get_argument("id", "")
        if not model_id:
            return self.write({"success": False, "message": "参数错误"})
        stats = AIModelRepository.get_token_stats(int(model_id))
        self.write({"success": True, "data": stats})


class ModelChatHandler(AdminBaseHandler):
    """对话测试（普通响应）"""
    @tornado.web.authenticated
    def post(self):
        model_id = self.get_body_argument("model_id", "")
        message = self.get_body_argument("message", "").strip()
        if not model_id or not message:
            return self.write({"success": False, "message": "参数错误"})
        model = AIModelRepository.get_by_id(int(model_id))
        if not model:
            return self.write({"success": False, "message": "模型不存在"})
        try:
            from openai import OpenAI
            client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
            response = client.chat.completions.create(
                model=model["model_name"],
                messages=[{"role": "user", "content": message}],
                extra_body={"thinking": {"type": "enabled"}}
            )
            content = response.choices[0].message.content
            usage = response.usage
            AIModelRepository.add_token_log(
                int(model_id),
                usage.prompt_tokens,
                usage.completion_tokens
            )
            self.write({"success": True, "content": content,
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens})
        except Exception as e:
            self.write({"success": False, "message": str(e)})


class ModelChatSSEHandler(AdminBaseHandler):
    """SSE流式对话测试"""
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        model_id = self.get_argument("model_id", "")
        message = self.get_argument("message", "").strip()
        if not model_id or not message:
            self.set_status(400)
            return
        model = AIModelRepository.get_by_id(int(model_id))
        if not model:
            self.set_status(404)
            return

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("X-Accel-Buffering", "no")

        try:
            from openai import OpenAI
            client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
            stream = client.chat.completions.create(
                model=model["model_name"],
                messages=[{"role": "user", "content": message}],
                stream=True,
                extra_body={"thinking": {"type": "enabled"}}
            )
            full_content = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                    data = json.dumps({"content": delta.content}, ensure_ascii=False)
                    self.write(f"data: {data}\n\n")
                    self.flush()
            self.write("data: [DONE]\n\n")
            self.flush()
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.write(f"data: {err}\n\n")
            self.flush()
        self.finish()
