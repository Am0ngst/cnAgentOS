# 程序的主入口
# 承担服务器容器+程序作用
# 服务器容器:提供http容器服务，程序放置于该容器中运行
# 程序:本体-智能瞭望与智能问数系统B/s架构

import os
import tornado.ioloop
import tornado.web

# from app.controllers.base import BaseHandler
# 引入auth - controller层
from app.controllers.auth import LoginHandler, LogoutHandler
from app.controllers.home import IndexHandler
# 引入admin - 后台管理控制器
from app.controllers.admin import (
    AdminLoginHandler, AdminLogoutHandler, AdminIndexHandler, DashboardHandler,
    UserManageHandler, UserCreateHandler, UserUpdateHandler,
    UserDeleteHandler, UserBatchDeleteHandler, UserCountHandler, UserRolesHandler
)
# 引入RBAC控制器
from app.controllers.rbac import (
    FunctionManageHandler, FunctionCreateHandler, FunctionUpdateHandler,
    FunctionDeleteHandler, FunctionTreeHandler, FunctionParentsHandler,
    RoleManageHandler, RoleCreateHandler, RoleUpdateHandler,
    RoleDeleteHandler, RoleListHandler,
    PermissionManageHandler, PermissionGrantHandler, PermissionGetHandler,
    MenuHandler
)
from app.controllers.model_engine import (
    ModelEngineHandler, ModelCreateHandler, ModelUpdateHandler,
    ModelDeleteHandler, ModelSetDefaultHandler,
    ModelTokenStatsHandler, ModelChatHandler, ModelChatSSEHandler
)
from app.controllers.watch_engine import (
    WatchCollectHandler, WatchSourceManageHandler, WatchExecuteHandler,
    WatchDataHandler, WatchDataDeleteHandler, WatchDataBatchDeleteHandler
)
from app.controllers.api_interface_mgr import (
    ApiInterfaceHandler, ApiInterfaceCreateHandler,
    ApiInterfaceUpdateHandler, ApiInterfaceDeleteHandler
)
from app.controllers.digital_employee_mgr import (
    DigitalEmployeeHandler, DigitalEmployeeCreateHandler,
    DigitalEmployeeUpdateHandler, DigitalEmployeeDeleteHandler,
    DigitalEmployeeDispatchHandler, DigitalEmployeeChatSSEHandler,
    DigitalChatPageHandler
)
from app.controllers.deep_crawl import (
    DeepCrawlSingleHandler, DeepCrawlBatchHandler,
    DeepCrawlStatsHandler, DeepCrawlDetailHandler
)
from app.controllers.user_chat import (
    UserLoginHandler, UserRegisterHandler, UserLogoutHandler,
    UserChatHandler, UserChatSSEHandler,
    UserConversationListHandler, UserConversationMessagesHandler,
    UserConversationDeleteHandler,
    UserModelListHandler, UserEmployeeListHandler
)
#引入db - model层
from app.models.db import init_db

# class HealthHandler(tornado.web.RequestHandler):
#     def get(self):
#     self.write({"status":"ok"})

# class LoginHandler(tornado.web.RequestHandler):
#     defget(self):
#         self.write(f"""<h3>模拟登录验证测试BaesHandler</h3>

#         <form method="post">
            
#         <button type="submit">登录admin</button>
#         {self.xsrf_form_html()}
#         </form>
#         """)
#     def post(self):
#         next_url = self.get_argument("next","/private")
#         self.set_secure_cookie("username","admin")
#         # 写完安全的cookie以后，跳转到目标地址
#         self.redirect(next_url)

# class PrivateHandler(BaseHandler):
#     @tornado.web.authenticated
#     def get(self):
#         self.write(self.current_user)

def make_app():
    base_url = os.path.dirname(os.path.abspath(__file__))
    settings = dict(
        # 预留view 层的内容配置
        template_path=os.path.join(base_url, "app", "templates"),
        static_path=os.path.join(base_url, "app", "static"),
        cookie_secret="demo-cookie-secret-change-me",
        login_url="/auth/login",
        xsrf_cookies=True,
        debug=True,
        autoreload=True
    )
    return tornado.web.Application([
        (r"/", IndexHandler),
        (r"/auth/login", LoginHandler),
        (r"/auth/logout", LogoutHandler),
        # 后台管理路由
        (r"/admin/login", AdminLoginHandler),
        (r"/admin/logout", AdminLogoutHandler),
        (r"/admin/?", AdminIndexHandler),
        (r"/admin/dashboard", DashboardHandler),
        (r"/admin/users", UserManageHandler),
        (r"/admin/users/create", UserCreateHandler),
        (r"/admin/users/update", UserUpdateHandler),
        (r"/admin/users/delete", UserDeleteHandler),
        (r"/admin/users/batch_delete", UserBatchDeleteHandler),
        (r"/admin/api/users/count", UserCountHandler),
        (r"/admin/api/users/roles", UserRolesHandler),
        # 功能管理路由
        (r"/admin/functions", FunctionManageHandler),
        (r"/admin/functions/create", FunctionCreateHandler),
        (r"/admin/functions/update", FunctionUpdateHandler),
        (r"/admin/functions/delete", FunctionDeleteHandler),
        (r"/admin/api/functions/tree", FunctionTreeHandler),
        (r"/admin/api/functions/parents", FunctionParentsHandler),
        # 角色管理路由
        (r"/admin/roles", RoleManageHandler),
        (r"/admin/roles/create", RoleCreateHandler),
        (r"/admin/roles/update", RoleUpdateHandler),
        (r"/admin/roles/delete", RoleDeleteHandler),
        (r"/admin/api/roles/list", RoleListHandler),
        # 权限管理路由
        (r"/admin/permissions", PermissionManageHandler),
        (r"/admin/permissions/grant", PermissionGrantHandler),
        (r"/admin/api/permissions/get", PermissionGetHandler),
        (r"/admin/api/menu", MenuHandler),
        # 模型引擎路由
        (r"/admin/models", ModelEngineHandler),
        (r"/admin/models/create", ModelCreateHandler),
        (r"/admin/models/update", ModelUpdateHandler),
        (r"/admin/models/delete", ModelDeleteHandler),
        (r"/admin/models/set_default", ModelSetDefaultHandler),
        (r"/admin/models/token_stats", ModelTokenStatsHandler),
        (r"/admin/models/chat", ModelChatHandler),
        (r"/admin/models/chat_sse", ModelChatSSEHandler),
        # 瞭望管理路由
        (r"/admin/watch/collect", WatchCollectHandler),
        (r"/admin/watch/sources", WatchSourceManageHandler),
        (r"/admin/watch/execute", WatchExecuteHandler),
        (r"/admin/watch/data", WatchDataHandler),
        (r"/admin/watch/data/delete", WatchDataDeleteHandler),
        (r"/admin/watch/data/batch_delete", WatchDataBatchDeleteHandler),
        # 接口管理路由
        (r"/admin/api-interfaces", ApiInterfaceHandler),
        (r"/admin/api-interfaces/create", ApiInterfaceCreateHandler),
        (r"/admin/api-interfaces/update", ApiInterfaceUpdateHandler),
        (r"/admin/api-interfaces/delete", ApiInterfaceDeleteHandler),
        # 数字员工路由
        (r"/admin/digital-employees", DigitalEmployeeHandler),
        (r"/admin/digital-employees/create", DigitalEmployeeCreateHandler),
        (r"/admin/digital-employees/update", DigitalEmployeeUpdateHandler),
        (r"/admin/digital-employees/delete", DigitalEmployeeDeleteHandler),
        (r"/admin/digital-chat", DigitalChatPageHandler),
        (r"/admin/digital-chat/send", DigitalEmployeeDispatchHandler),
        (r"/admin/digital-chat/sse", DigitalEmployeeChatSSEHandler),
        # AI深度采集路由
        (r"/admin/watch/deep-crawl/single", DeepCrawlSingleHandler),
        (r"/admin/watch/deep-crawl/batch", DeepCrawlBatchHandler),
        (r"/admin/watch/deep-crawl/stats", DeepCrawlStatsHandler),
        (r"/admin/watch/deep-crawl/detail", DeepCrawlDetailHandler),
        # 用户侧路由
        (r"/user/login", UserLoginHandler),
        (r"/user/register", UserRegisterHandler),
        (r"/user/logout", UserLogoutHandler),
        (r"/user/chat", UserChatHandler),
        (r"/user/chat/sse", UserChatSSEHandler),
        (r"/user/api/conversations", UserConversationListHandler),
        (r"/user/api/messages", UserConversationMessagesHandler),
        (r"/user/api/conversations/delete", UserConversationDeleteHandler),
        (r"/user/api/models", UserModelListHandler),
        (r"/user/api/employees", UserEmployeeListHandler),
    ],
    **settings
    )

if __name__ == "__main__":
    # 启动服务之前检查并初始化服务器表
    init_db()
    app = make_app()
    app.listen(10086, address='0.0.0.0')

    print("====== Server 启动成功 ======== 端口:10086 ======", flush=True)
    tornado.ioloop.IOLoop.current().start()
