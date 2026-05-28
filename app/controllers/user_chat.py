import json
import re
import time
import urllib3
import tornado.web
import tornado.gen
from app.controllers.base import BaseHandler
from app.models.user import UserRepository
from app.models.im_model import IMMessageRepository
from app.models.conversation import ConversationRepository
from app.models.ai_model import AIModelRepository
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.watch_source import WatchDataRepository
from app.models.db import get_connection

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def build_api_message(emp, data):
    code = (emp.get("api_code") or "").lower()
    inner = data.get("data") if isinstance(data, dict) and "data" in data else data
    if "music" in code:
        name = inner.get("song") or inner.get("name") or inner.get("songname") or inner.get("title", "未知歌曲")
        singer = inner.get("singer") or inner.get("author") or inner.get("artistsname") or inner.get("artist", "未知歌手")
        cover = (inner.get("cover") or inner.get("pic") or inner.get("img", "")).strip().strip("`")
        music_url = (inner.get("Music") or inner.get("url") or inner.get("mp3") or inner.get("music_url", "")).strip().strip("`")
        return {"type": "music", "name": name, "singer": singer, "cover": cover, "music_url": music_url}
    if "weather" in code:
        lines = [f"【{emp['name']}】天气查询结果："]
        if isinstance(inner, dict):
            for k, v in inner.items():
                if isinstance(v, (str, int, float)):
                    lines.append(f"• {k}：{v}")
        return {"type": "text", "text": "\n".join(lines)}
    if isinstance(data, str):
        return {"type": "text", "text": str(data)}
    try:
        return {"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}
    except Exception:
        return {"type": "text", "text": str(data)}


class UserBaseHandler(BaseHandler):
    def get_current_user(self):
        return self.get_secure_cookie("username")

    def get_current_user_info(self):
        username = self.get_secure_cookie("username")
        if username:
            return UserRepository.get_user_by_username(username.decode('utf-8'))
        return None

    def get_login_url(self):
        return "/user/login"

    def _handle_emp_api_reply(self, emp, message, user, emp_alias, chat_type="private"):
        import requests
        api_url = emp.get("api_url")
        pc = emp.get("params_config")
        url = api_url
        if isinstance(pc, dict) and pc.get("param_key"):
            if message:
                url = f"{api_url}?{pc['param_key']}={requests.utils.quote(message)}"
            elif pc.get("required"):
                IMMessageRepository.send_private_employee(
                    0, emp_alias, "text",
                    f"请提供{pc.get('param_label', '参数')}，例如：{pc.get('placeholder', '')}"
                )
                return
        try:
            resp = requests.get(url, timeout=15)
            data = resp.json()
            result = build_api_message(emp, data)
            if isinstance(result, dict) and result.get("type") == "music" and result.get("cover"):
                IMMessageRepository.send_private_employee(
                    0, emp_alias, "image", result["cover"],
                    file_path=result["cover"]
                )
            text = ""
            if isinstance(result, dict) and result.get("type") == "music":
                text = f"🎵 {result['name']}\n👤 {result['singer']}"
                if result.get("music_url"):
                    text += f"\n🔗 {result['music_url']}"
            elif isinstance(result, dict):
                text = result.get("text", "")
            else:
                text = str(result)
            if text:
                IMMessageRepository.send_private_employee(0, emp_alias, "text", text)
        except Exception:
            IMMessageRepository.send_private_employee(
                0, emp_alias, "text", f"抱歉，「{emp['name']}」服务暂时不可用，请稍后再试。"
            )


class UserLoginHandler(BaseHandler):
    def get(self):
        self.render("user/login.html", error=None)

    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "")

        if not username or not password:
            return self.render("user/login.html", error="用户名和密码不能为空")

        if not UserRepository.verify_user(username, password):
            return self.render("user/login.html", error="用户名或密码错误")

        user = UserRepository.get_user_by_username(username)
        if not user:
            return self.render("user/login.html", error="用户不存在")

        role_code = user["role_code"] or ""
        if role_code == "super_admin":
            return self.render("user/login.html", error="管理员请从后台登录")

        self.set_secure_cookie("username", username)
        self.redirect("/user/home")


class UserRegisterHandler(BaseHandler):
    def get(self):
        self.render("user/register.html", error=None)

    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "")
        password2 = self.get_body_argument("password2", "")

        if not username or not password:
            return self.render("user/register.html", error="用户名和密码不能为空")
        if len(username) < 2 or len(username) > 20:
            return self.render("user/register.html", error="用户名需2-20个字符")
        if len(password) < 6:
            return self.render("user/register.html", error="密码至少6位")
        if password != password2:
            return self.render("user/register.html", error="两次密码不一致")

        existing = UserRepository.get_user_by_username(username)
        if existing:
            return self.render("user/register.html", error="用户名已存在")

        if UserRepository.create_user(username, password, role_id=2):
            self.set_secure_cookie("username", username)
            self.redirect("/user/home")
        else:
            self.render("user/register.html", error="注册失败，请重试")


class UserLogoutHandler(BaseHandler):
    def post(self):
        self.clear_cookie("username")
        self.redirect("/user/login")


class UserChatHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        if not user:
            return self.redirect("/user/login")

        models = AIModelRepository.get_all(status=1)
        emps = DigitalEmployeeRepository.get_all(status=1)
        conversations = ConversationRepository.get_user_conversations(user["id"], 50)

        self.render("user/chat.html",
                    user=user,
                    models=models,
                    employees=emps,
                    conversations=conversations,
                    conv_id=None,
                    models_json=json.dumps(models, ensure_ascii=False),
                    emps_json=json.dumps(emps, ensure_ascii=False))


class UserChatSSEHandler(UserBaseHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def post(self):
        user = self.get_current_user_info()
        if not user:
            self.set_status(403)
            return

        message = self.get_body_argument("message", "").strip()
        model_id = self.get_body_argument("model_id", "").strip() or None
        conversation_id = self.get_body_argument("conversation_id", "").strip() or None

        if not message:
            self._sse_error("请输入消息内容")
            return

        model = None
        if model_id and model_id.isdigit():
            model = AIModelRepository.get_by_id(int(model_id))
        if not model:
            model = AIModelRepository.get_default()
        if not model:
            self._sse_error("没有可用的AI模型")
            return

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("X-Accel-Buffering", "no")

        if conversation_id and conversation_id.isdigit():
            conv = ConversationRepository.get_by_id(int(conversation_id), user["id"])
            if not conv:
                conversation_id = None

        if not conversation_id:
            title = message[:30] + ("..." if len(message) > 30 else "")
            conversation_id = ConversationRepository.create(user["id"], title, model["id"])
        else:
            conversation_id = int(conversation_id)

        intent = self._detect_intent(message)
        at_emp = self._extract_at_employee(message)
        if not at_emp and intent != "data_query":
            ctx = self._detect_employee_context(conversation_id)
            if ctx:
                at_emp = {"emp": ctx["emp"], "message": message}

        if at_emp:
            yield from self._handle_employee(conversation_id, at_emp, message, model)
        elif intent == "data_query":
            ConversationRepository.save_message(conversation_id, "user", message, "text")
            yield from self._handle_data_query(conversation_id, message, model)
        else:
            ConversationRepository.save_message(conversation_id, "user", message, "text")
            yield from self._handle_general_chat(conversation_id, message, model)

    def _sse_error(self, msg):
        self.set_header("Content-Type", "text/event-stream")
        self.write("data: " + json.dumps({"error": msg}, ensure_ascii=False) + "\n\n")
        self.flush()
        self.finish()

    def _detect_intent(self, message):
        keywords = [
            "最新", "最近", "今天", "昨天", "一共", "多少条", "有多少", "数据",
            "统计", "查询", "列出", "展示", "显示", "告诉我", "查一下",
            "采集到", "深度采集", "数据仓库", "分析"
        ]
        score = sum(1 for k in keywords if k in message)
        return "data_query" if score >= 2 else "general"

    def _extract_at_employee(self, message):
        m = re.match(r'^\s*@(\S+)', message)
        if m:
            alias = m.group(1)
            rest = message[m.end():].strip()
            emp = DigitalEmployeeRepository.get_by_alias(alias)
            if emp:
                return {"emp": emp, "message": rest or message}
        return None

    def _detect_employee_context(self, conversation_id):
        recent = ConversationRepository.get_recent_messages(conversation_id, 6)
        user_at = None
        for m in reversed(recent):
            if m["role"] == "user" and re.match(r'^\s*@(\S+)', m["content"]):
                user_at = m
                break
            if m["role"] == "user" and not m["content"].startswith("@"):
                return None
        if not user_at:
            return None
        alias = re.match(r'^\s*@(\S+)', user_at["content"]).group(1)
        emp = DigitalEmployeeRepository.get_by_alias(alias)
        if not emp:
            return None
        if emp["emp_type"] != "AI":
            return None
        return {"emp": emp}

    @tornado.gen.coroutine
    def _handle_general_chat(self, conversation_id, message, model):
        system_prompt = """你是一个智能助手，名为"问数"。你擅长回答各种问题，也擅长从数据库中检索和分析数据。
请用中文回复，回答简洁清晰，适当使用Markdown格式。

当用户询问数据相关问题时（如"最新一条数据"、"有多少条"、"分析一下"），
你需要生成SQL语句查询数据库。数据库中有以下表：

1. watch_data - 采集数据表
   字段: id, source_id, keyword, title, url, summary, source_name, deep_crawl_status,
         collect_at, create_at
   deep_crawl_status: 0=未采集, 1=采集中, 2=已完成, 3=失败

2. watch_data_detail - AI深度采集详情表
   字段: id, data_id, full_content, ai_summary, keywords, category, sentiment,
         entities, reading_time, word_count, crawl_duration, create_at

3. watch_sources - 数据源表
   字段: id, name, code, source_type, url_template

当需要查询数据时，返回以下JSON格式（不要任何其他文字）：
{"action": "query", "sql": "SELECT ...", "explanation": "查询说明"}

否则正常对话回复即可。"""

        full_content = ""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
            messages = [{"role": "system", "content": system_prompt}]
            history_msgs = ConversationRepository.get_recent_messages(conversation_id, 30)
            for m in history_msgs:
                role = "assistant" if m["role"] == "assistant" else "user"
                cnt = m["content"]
                if cnt.startswith("@") and " " in cnt:
                    cnt = cnt.split(" ", 1)[1] if cnt.split(" ", 1)[0].startswith("@") else cnt
                messages.append({"role": role, "content": cnt})
            messages.append({"role": "user", "content": message})
            stream = client.chat.completions.create(
                model=model["model_name"],
                messages=messages,
                stream=True,
                extra_body={"thinking": {"type": "enabled"}}
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                    data = json.dumps({"type": "chunk", "content": delta.content}, ensure_ascii=False)
                    self.write(f"data: {data}\n\n")
                    self.flush()
                    yield

            if self._is_query_response(full_content):
                query_data = self._execute_ai_query(full_content, model, conversation_id)
                yield from self._stream_query_result(conversation_id, query_data, model)
            else:
                ConversationRepository.save_message(conversation_id, "assistant", full_content, "text")
                self.write("data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n")
                self.flush()
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "invalid" in err_str.lower():
                err_str = "API Key 已失效，请前往后台「模型引擎」更新密钥"
            ConversationRepository.save_message(conversation_id, "system", err_str[:200], "error")
            data = json.dumps({"type": "error", "content": err_str[:200]}, ensure_ascii=False)
            self.write(f"data: {data}\n\n")
            self.flush()
        finally:
            self.finish()

    def _is_query_response(self, content):
        try:
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```\w*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            m = re.search(r'\{[^{}]*"action"\s*:\s*"query"[^{}]*\}', content, re.DOTALL)
            if m:
                content = m.group(0)
            j = json.loads(content)
            return j.get("action") == "query" and "sql" in j
        except Exception:
            return False

    @tornado.gen.coroutine
    def _handle_data_query(self, conversation_id, message, model):
        system_prompt = """你是一个数据分析专家。用户需要从数据库中查询数据，请生成SQL语句。

数据库中有以下表：

1. watch_data - 采集数据表
   字段: id, source_id, keyword, title, url, summary, source_name, deep_crawl_status,
         collect_at(采集时间), create_at
   deep_crawl_status: 0=未采集, 1=采集中, 2=已完成, 3=失败

2. watch_data_detail - AI深度采集详情表
   字段: id, data_id, full_content, ai_summary, keywords, category, sentiment,
         entities, reading_time, word_count, crawl_duration, create_at

3. watch_sources - 数据源表
   字段: id, name, code, source_type, url_template

请只返回一个JSON对象（不要任何其他文字）：
{"action": "query", "sql": "你的SQL语句", "explanation": "你要查询什么"}

注意：
- SQL只支持SELECT语句
- 时间相关查询用 datetime('now', '-24 hours') 格式
- 模糊搜索用 LIKE '%关键词%'
- 默认按collect_at DESC排序
- 最多返回20条"""

        full_content = ""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
            messages = [{"role": "system", "content": system_prompt}]
            history_msgs = ConversationRepository.get_recent_messages(conversation_id, 20)
            for m in history_msgs:
                role = "assistant" if m["role"] == "assistant" else "user"
                messages.append({"role": role, "content": m["content"]})
            messages.append({"role": "user", "content": message})
            stream = client.chat.completions.create(
                model=model["model_name"],
                messages=messages,
                stream=True,
                extra_body={"thinking": {"type": "enabled"}}
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content

            result_text = "🔍 正在分析数据...\n\n"
            self.write("data: " + json.dumps({"type": "chunk", "content": result_text}, ensure_ascii=False) + "\n\n")
            self.flush()
            yield
            query_data = self._execute_ai_query(full_content, model, conversation_id)
            yield from self._stream_query_result(conversation_id, query_data, model)
        except Exception as e:
            ConversationRepository.save_message(conversation_id, "system", str(e)[:200], "error")
            self.write("data: " + json.dumps({"type": "error", "content": str(e)[:200]}, ensure_ascii=False) + "\n\n")
            self.flush()
        finally:
            self.finish()

    def _execute_ai_query(self, full_content, model, conversation_id):
        try:
            content = full_content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```\w*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            m = re.search(r'\{[^{}]*"action"\s*:\s*"query"[^{}]*\}', content, re.DOTALL)
            if m:
                content = m.group(0)
            j = json.loads(content)
            sql = j.get("sql", "")
            explanation = j.get("explanation", "")

            if not sql or not sql.strip().upper().startswith("SELECT"):
                return {"error": "AI生成的SQL无效"}

            with get_connection() as conn:
                try:
                    rows = conn.execute(sql).fetchall()
                    columns = [desc[0] for desc in conn.execute(f"SELECT * FROM ({sql}) LIMIT 0").description] if rows else []
                    data_rows = []
                    for row in rows[:20]:
                        r = {}
                        for i, col in enumerate(columns):
                            val = row[i]
                            if isinstance(val, str) and len(val) > 200:
                                val = val[:200] + "..."
                            r[col] = val
                        data_rows.append(r)
                    return {
                        "sql": sql,
                        "explanation": explanation,
                        "columns": columns,
                        "rows": data_rows,
                        "count": len(data_rows)
                    }
                except Exception as e:
                    ConversationRepository.save_message(conversation_id, "system", f"SQL执行错误: {str(e)}", "error")
                    return {"error": f"SQL执行错误: {str(e)}"}
        except Exception as e:
            return {"error": f"无法解析AI响应: {str(e)}"}

    @tornado.gen.coroutine
    def _stream_query_result(self, conversation_id, query_data, model):
        if "error" in query_data:
            error_content = "查询失败: " + query_data["error"]
            ConversationRepository.save_message(conversation_id, "assistant", error_content, "error")
            self.write("data: " + json.dumps({"type": "error", "content": error_content}, ensure_ascii=False) + "\n\n")
            self.write("data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n")
            self.flush()
            return

        if not query_data.get("rows"):
            msg = "没有查询到匹配的数据。"
            ConversationRepository.save_message(conversation_id, "assistant", msg, "text")
            self.write("data: " + json.dumps({"type": "chunk", "content": msg}, ensure_ascii=False) + "\n\n")
            self.write("data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n")
            self.flush()
            return

        md = f"**{query_data.get('explanation', '查询结果')}** (共 {query_data['count']} 条)\n\n"
        md += "| " + " | ".join(query_data["columns"]) + " |\n"
        md += "| " + " | ".join(["---"] * len(query_data["columns"])) + " |\n"
        for row in query_data["rows"]:
            md += "| " + " | ".join(str(row.get(c, "")) for c in query_data["columns"]) + " |\n"

        extra = {"type": "data_query", "sql": query_data.get("sql"), "columns": query_data["columns"],
                 "rows": query_data["rows"][:20], "count": query_data["count"]}
        ConversationRepository.save_message(conversation_id, "assistant", md, "data_query", extra)

        self.write("data: " + json.dumps({"type": "chunk", "content": md}, ensure_ascii=False) + "\n\n")
        self.flush()
        yield
        self.write("data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n")
        self.flush()

    @tornado.gen.coroutine
    def _handle_employee(self, conversation_id, at_emp, message, model):
        emp = at_emp["emp"]
        emp_msg = at_emp["message"]

        if emp["emp_type"] == "AI":
            try:
                from openai import OpenAI
                client = OpenAI(api_key=emp.get("api_key", model["api_key"]),
                                base_url=emp.get("base_url", model["base_url"]))
                messages = []
                if emp.get("system_prompt"):
                    messages.append({"role": "system", "content": emp["system_prompt"]})
                history_msgs = ConversationRepository.get_recent_messages(conversation_id, 30)
                for m in history_msgs:
                    role = "assistant" if m["role"] == "assistant" else "user"
                    cnt = m["content"]
                    if role == "user" and cnt.startswith(f"@{emp['alias']}"):
                        cnt = cnt[len(emp['alias'])+1:].strip()
                    messages.append({"role": role, "content": cnt})
                messages.append({"role": "user", "content": emp_msg})

                ConversationRepository.save_message(conversation_id, "user", f"@{emp['alias']} {emp_msg}", "at_employee")
                stream = client.chat.completions.create(
                    model=emp.get("model_code_name", model["model_name"]),
                    messages=messages,
                    stream=True,
                    extra_body={"thinking": {"type": "enabled"}}
                )
                full_content = ""
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_content += delta.content
                        data = json.dumps({"type": "chunk", "content": delta.content}, ensure_ascii=False)
                        self.write(f"data: {data}\n\n")
                        self.flush()
                        yield
                ConversationRepository.save_message(conversation_id, "assistant", full_content, "text",
                                                    {"from": emp["alias"]})
                self.write("data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n")
                self.flush()
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "invalid" in err_str.lower():
                    err_str = "API Key 已失效，请前往后台「模型引擎」更新密钥"
                ConversationRepository.save_message(conversation_id, "system", f"@{emp['alias']}: {err_str[:200]}", "error")
                self.write("data: " + json.dumps({"type": "error", "content": err_str[:200]}, ensure_ascii=False) + "\n\n")
                self.flush()
        else:
            import requests as req
            api_url = emp.get("api_url")
            pc = emp.get("params_config")
            alias = emp.get("alias", "")

            param_value = ""
            if isinstance(pc, dict) and pc.get("param_key"):
                param_value = self._extract_param_with_ai(emp_msg, pc, emp, model)

            if isinstance(pc, dict) and pc.get("required") and not param_value:
                hint = pc.get("placeholder", f"请输入{pc.get('param_label', '参数')}")
                self.write("data: " + json.dumps({
                    "type": "chunk",
                    "content": f"📝 **@{alias}**\n\n> {hint}\n\n请提供城市名称后重试，如：`@{alias} 北京`"
                }, ensure_ascii=False) + "\n\n")
                self.flush()
                yield
                self.write("data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n")
                self.flush()
                self.finish()
                return

            if isinstance(pc, dict) and pc.get("param_key"):
                url = f"{api_url}?{pc['param_key']}={req.utils.quote(param_value)}"
            else:
                url = api_url

            ConversationRepository.save_message(conversation_id, "user", f"@{alias} {emp_msg}".strip(), "at_employee")
            try:
                resp = req.get(url, timeout=15, verify=False)
                raw = resp.text
                try:
                    data = resp.json()
                except Exception:
                    data = {"raw_text": raw[:500]}

                result_text = self._format_api_result(data, emp)
                if not result_text or result_text.strip() == "":
                    result_text = json.dumps(data, ensure_ascii=False, indent=2)

                ConversationRepository.save_message(conversation_id, "assistant", result_text, "api_result",
                                                    {"from": alias})
                self.write("data: " + json.dumps({"type": "chunk", "content": result_text}, ensure_ascii=False) + "\n\n")
                self.flush()
                yield
                self.write("data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n")
                self.flush()
            except Exception as e:
                error_msg = f"API调用失败: {str(e)[:150]}"
                ConversationRepository.save_message(conversation_id, "system", error_msg, "error")
                self.write("data: " + json.dumps({"type": "error", "content": error_msg}, ensure_ascii=False) + "\n\n")
                self.flush()
        self.finish()

    def _extract_param_with_ai(self, message, params_config, emp, model):
        param_label = params_config.get("param_label", "参数")
        if not message or not message.strip():
            return ""

        cities = ["北京", "上海", "广州", "深圳", "成都", "杭州", "重庆", "武汉", "西安",
                  "南京", "天津", "苏州", "长沙", "郑州", "东莞", "青岛", "沈阳", "宁波",
                  "昆明", "大连", "厦门", "合肥", "佛山", "福州", "哈尔滨", "济南", "温州",
                  "长春", "石家庄", "常州", "泉州", "南宁", "贵阳", "南昌", "太原", "烟台",
                  "嘉兴", "南通", "金华", "珠海", "惠州", "徐州", "海口", "乌鲁木齐", "兰州"]
        for city in cities:
            if city in message:
                return city

        if any(w in message for w in ["怎么样", "如何", "是什么", "好不好", "行不行", "可以吗", "能"]):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=model["api_key"], base_url=model["base_url"])
                prompt = f"""从以下用户消息中提取{param_label}，只返回提取的值，不要其他文字：
消息: {message}
如果无法提取，返回"无法提取"。"""
                resp = client.chat.completions.create(
                    model=model["model_name"],
                    messages=[{"role": "user", "content": prompt}]
                )
                extracted = resp.choices[0].message.content.strip()
                if extracted and extracted != "无法提取" and len(extracted) < 20:
                    return extracted
            except Exception:
                pass

        return ""

    def _format_api_result(self, data, emp):
        alias = emp.get("alias", "")
        inner = data
        if isinstance(data, dict):
            for k in ("data", "result", "results"):
                if k in data and isinstance(data[k], (dict, list)):
                    inner = data[k]
                    break

        if alias == "音乐":
            if isinstance(inner, dict):
                title = inner.get("name") or inner.get("title") or inner.get("song") or inner.get("songname") or ""
                artist = inner.get("author") or inner.get("artist") or inner.get("singer") or inner.get("ar") or ""
                url = inner.get("url") or inner.get("music_url") or inner.get("mp3") or inner.get("src") or ""
                pic = inner.get("pic") or inner.get("cover") or inner.get("img") or inner.get("album_pic") or ""
                album = inner.get("album") or inner.get("al") or ""
                lines = []
                if title:
                    lines.append(f'<div style="padding:16px;border-radius:16px;background:linear-gradient(135deg,rgba(168,85,247,0.15),rgba(0,212,255,0.08));border:1px solid rgba(168,85,247,0.2);margin:8px 0;">')
                    if pic:
                        lines.append(f'<img src="{pic}" style="width:100%;max-width:240px;border-radius:12px;margin-bottom:12px;box-shadow:0 8px 30px rgba(0,0,0,0.4);" onerror="this.style.display=\'none\'">')
                    lines.append(f'<h3 style="margin:0 0 8px;color:#fff;">🎵 {title}</h3>')
                    if artist:
                        lines.append(f'<p style="margin:4px 0;color:rgba(255,255,255,0.7);">👤 {artist}</p>')
                    if album:
                        lines.append(f'<p style="margin:4px 0;color:rgba(255,255,255,0.5);">💿 {album}</p>')
                    if url:
                        lines.append(f'<p style="margin:12px 0 0;"><a href="{url}" target="_blank" style="color:var(--accent);text-decoration:none;">🔗 试听链接</a></p>')
                    lines.append('</div>')
                    return "".join(lines)
                if not title:
                    return json.dumps(inner, ensure_ascii=False, indent=2)
            if isinstance(inner, list) and inner:
                return self._format_api_result(inner[0], emp)
            return json.dumps(inner, ensure_ascii=False, indent=2)

        if alias == "天气":
            if isinstance(inner, dict):
                lines = []
                city = inner.get("city") or inner.get("cityname") or inner.get("cityName") or ""
                weather_now = inner.get("weather") or inner.get("tianqi") or inner.get("nowText") or ""
                temp_now = inner.get("temperature") or inner.get("wendu") or inner.get("temp") or ""
                hum = inner.get("humidity") or inner.get("shidu") or ""
                wind = inner.get("wind") or inner.get("fengli") or inner.get("windDir") or ""
                aqi = inner.get("aqi") or inner.get("air") or ""

                emoji_map = {"晴": "☀️", "多云": "⛅", "阴": "☁️", "雨": "🌧️", "雪": "❄️", "雾": "🌫️",
                             "风": "💨", "雷": "⛈️", "霾": "😷", "沙": "🏜️"}

                lines.append(f'<div style="padding:16px;border-radius:16px;background:linear-gradient(135deg,rgba(0,180,220,0.12),rgba(34,211,238,0.06));border:1px solid rgba(0,180,220,0.2);margin:8px 0;">')
                if city:
                    lines.append(f'<h3 style="margin:0 0 12px;color:#fff;">📍 {city}</h3>')
                if weather_now or temp_now:
                    lines.append('<div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;">')
                    lines.append(f'<span style="font-size:48px;">{self._weather_emoji(weather_now, emoji_map)}</span>')
                    lines.append('<div>')
                    if weather_now:
                        lines.append(f'<p style="margin:0;font-size:20px;color:#fff;font-weight:600;">{weather_now}</p>')
                    if temp_now:
                        lines.append(f'<p style="margin:4px 0 0;font-size:32px;color:var(--accent);font-weight:700;">{temp_now}°C</p>')
                    lines.append('</div></div>')
                if wind or hum:
                    lines.append('<p style="color:rgba(255,255,255,0.6);font-size:13px;margin:4px 0;">')
                    parts = []
                    if wind: parts.append(f"🌬️ {wind}")
                    if hum: parts.append(f"💧 湿度 {hum}")
                    lines.append(" &nbsp;|&nbsp; ".join(parts))
                    lines.append('</p>')
                if aqi:
                    lines.append(f'<p style="color:rgba(255,255,255,0.6);font-size:13px;margin:4px 0;">🌿 AQI: {aqi}</p>')

                forecast = inner.get("data") or inner.get("forecast") or inner.get("list") or []
                if isinstance(forecast, list) and forecast:
                    lines.append('<div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap;">')
                    for day in forecast[:3]:
                        date = day.get("date") or day.get("day") or day.get("fxDate") or ""
                        w = day.get("weather") or day.get("type") or day.get("textDay") or ""
                        high = day.get("high") or day.get("tempMax") or ""
                        low = day.get("low") or day.get("tempMin") or ""
                        lines.append(f'<div style="flex:1;min-width:90px;padding:10px;border-radius:10px;background:rgba(255,255,255,0.04);text-align:center;">')
                        if date:
                            lines.append(f'<p style="font-size:12px;color:rgba(255,255,255,0.5);margin:0 0 6px;">{date}</p>')
                        lines.append(f'<span style="font-size:22px;">{self._weather_emoji(w, emoji_map)}</span>')
                        if w:
                            lines.append(f'<p style="font-size:12px;color:#fff;margin:4px 0;">{w}</p>')
                        if high and low:
                            lines.append(f'<p style="font-size:11px;color:rgba(255,255,255,0.5);margin:2px 0;">{low} ~ {high}</p>')
                        lines.append('</div>')
                    lines.append('</div>')
                lines.append('</div>')
                return "".join(lines)
            return json.dumps(inner, ensure_ascii=False, indent=2)

        return json.dumps(inner, ensure_ascii=False, indent=2)

    def _weather_emoji(self, text, emoji_map):
        if not text:
            return "🌤️"
        for c, e in emoji_map.items():
            if c in text:
                return e
        return "🌤️"


class UserConversationListHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        if not user:
            return self.write({"success": False, "message": "未登录"})
        conversations = ConversationRepository.get_user_conversations(user["id"], 50)
        self.write({"success": True, "data": conversations})


class UserConversationMessagesHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        conv_id = self.get_argument("id", "")
        if not conv_id or not conv_id.isdigit():
            return self.write({"success": False, "message": "参数错误"})
        conv = ConversationRepository.get_by_id(int(conv_id), user["id"])
        if not conv:
            return self.write({"success": False, "message": "对话不存在"})
        messages = ConversationRepository.get_messages(int(conv_id))
        self.write({"success": True, "data": {"conversation": conv, "messages": messages}})


class UserConversationDeleteHandler(UserBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_info()
        conv_id = self.get_body_argument("id", "")
        if not conv_id or not conv_id.isdigit():
            return self.write({"success": False, "message": "参数错误"})
        ConversationRepository.delete(int(conv_id), user["id"])
        self.write({"success": True, "message": "已删除"})


class UserModelListHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        models = AIModelRepository.get_all(status=1)
        self.write({"success": True, "data": models})


class UserEmployeeListHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        emps = DigitalEmployeeRepository.get_all(status=1)
        result = []
        for e in emps:
            result.append({
                "id": e["id"], "name": e["name"], "alias": e["alias"],
                "emp_type": e["emp_type"], "description": e.get("description", ""),
                "params_config": e.get("params_config")
            })
        self.write({"success": True, "data": result})


class UserHomeHandler(UserBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_info()
        if not user:
            return self.redirect("/user/login")
        self.render("user/home.html", user=user)
