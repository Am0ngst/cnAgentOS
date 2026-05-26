import tornado.web
from app.controllers.admin import AdminBaseHandler
from app.models.api_interface import ApiInterfaceRepository


class ApiInterfaceHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        keyword = self.get_argument("keyword", "").strip()
        tags = self.get_argument("tags", "").strip()
        per_page = 12

        data_list, total = ApiInterfaceRepository.get_page(
            page, per_page,
            keyword=keyword or None,
            tags=tags or None
        )
        total_pages = (total + per_page - 1) // per_page

        self.render("admin/api_interfaces.html",
                    title="接口管理",
                    username=self.current_user.decode('utf-8'),
                    active_menu="api_interfaces",
                    data_list=data_list,
                    page=page,
                    total_pages=total_pages,
                    total=total,
                    keyword=keyword,
                    tags=tags)


class ApiInterfaceCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = self.get_body_argument("name", "").strip()
        code = self.get_body_argument("code", "").strip()
        url = self.get_body_argument("url", "").strip()
        method = self.get_body_argument("method", "GET").strip()
        resp_format = self.get_body_argument("resp_format", "JSON").strip()
        params_desc = self.get_body_argument("params_desc", "").strip() or None
        example_url = self.get_body_argument("example_url", "").strip() or None
        qps_limit = self.get_body_argument("qps_limit", "").strip() or None
        has_token = int(self.get_body_argument("has_token", "0"))
        remark = self.get_body_argument("remark", "").strip() or None
        tags = self.get_body_argument("tags", "").strip() or None

        if not name or not code or not url:
            return self.write({"success": False, "message": "名称/编码/接口地址不能为空"})

        aid = ApiInterfaceRepository.create(
            name, code, url, method, resp_format,
            params_desc, example_url, qps_limit, has_token, remark, tags
        )
        if aid:
            self.write({"success": True, "message": "创建成功", "id": aid})
        else:
            self.write({"success": False, "message": "编码已存在或创建失败"})


class ApiInterfaceUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        aid = self.get_body_argument("id", "")
        if not aid:
            return self.write({"success": False, "message": "参数错误"})

        kwargs = {}
        for f in ["name", "code", "url", "method", "resp_format",
                  "params_desc", "example_url", "qps_limit", "remark", "tags"]:
            v = self.get_body_argument(f, "").strip()
            if v:
                kwargs[f] = v
        ht = self.get_body_argument("has_token", "")
        st = self.get_body_argument("status", "")
        if ht:
            kwargs["has_token"] = int(ht)
        if st:
            kwargs["status"] = int(st)

        ApiInterfaceRepository.update(int(aid), **kwargs)
        self.write({"success": True, "message": "更新成功"})


class ApiInterfaceDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        aid = self.get_body_argument("id", "")
        if aid:
            ApiInterfaceRepository.delete(int(aid))
            self.write({"success": True, "message": "删除成功"})
        else:
            self.write({"success": False, "message": "参数错误"})
