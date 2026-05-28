# 数据库链接与建表
import os
import sqlite3

# 获得项目根路径的方法
def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

# 获得数据文件的路径
DB_PATH = os.path.join(_project_root(), "database", "app.db")

# 获得数据库连接
def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 初始化数据库表
def init_db():
    with get_connection() as conn:
        # 用户表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role_id INTEGER DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # IM 好友关系表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS im_contacts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                remark TEXT DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, contact_id)
            )
            """
        )

        # IM 好友请求表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS im_friend_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                message TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # IM 群组表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS im_groups(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                avatar TEXT DEFAULT NULL,
                owner_id INTEGER NOT NULL,
                announcement TEXT DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # IM 群成员表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS im_group_members(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                nickname TEXT DEFAULT NULL,
                join_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(group_id, user_id)
            )
            """
        )

        # IM 私聊消息表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS im_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                msg_type TEXT DEFAULT 'text',
                content TEXT DEFAULT NULL,
                file_name TEXT DEFAULT NULL,
                file_size INTEGER DEFAULT 0,
                file_path TEXT DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # IM 群聊消息表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS im_group_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                from_user_id INTEGER NOT NULL,
                msg_type TEXT DEFAULT 'text',
                content TEXT DEFAULT NULL,
                file_name TEXT DEFAULT NULL,
                file_size INTEGER DEFAULT 0,
                file_path TEXT DEFAULT NULL,
                at_employee TEXT DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        
        # 数据库迁移：为消息表添加撤回标记字段
        try:
            conn.execute("ALTER TABLE im_messages ADD COLUMN is_recalled INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE im_group_messages ADD COLUMN is_recalled INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE im_messages ADD COLUMN emp_alias TEXT DEFAULT NULL")
        except Exception:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS im_chat_servers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL DEFAULT 10086,
                is_active INTEGER DEFAULT 0,
                max_connections INTEGER DEFAULT 1000,
                description TEXT DEFAULT NULL,
                status INTEGER DEFAULT 1,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS im_group_announcements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                from_admin TEXT NOT NULL DEFAULT 'system',
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS im_group_bans(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                reason TEXT DEFAULT NULL,
                ban_type TEXT NOT NULL DEFAULT 'mute_all',
                is_active INTEGER DEFAULT 1,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_tools(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                tool_type TEXT NOT NULL DEFAULT 'api',
                description TEXT DEFAULT NULL,
                config TEXT DEFAULT NULL,
                employee_id INTEGER DEFAULT NULL,
                status INTEGER DEFAULT 1,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # 功能模块表（菜单）
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS functions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT NULL,
                url TEXT DEFAULT NULL,
                parent_id INTEGER DEFAULT NULL,
                sort_order INTEGER DEFAULT 0,
                is_menu INTEGER DEFAULT 1,
                status INTEGER DEFAULT 1,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        
        # 角色表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT NULL,
                is_system INTEGER DEFAULT 0,
                status INTEGER DEFAULT 1,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        
        # 权限表（角色与功能的映射）
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                function_id INTEGER NOT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(role_id, function_id)
            )
            """
        )
        
        # 插入默认超级管理员角色
        conn.execute(
            """
            INSERT OR IGNORE INTO roles (id, name, code, description, is_system) 
            VALUES (1, '超级管理员', 'super_admin', '系统超级管理员，拥有所有权限', 1)
            """
        )
        
        # 插入默认功能菜单
        default_functions = [
            (1, '控制台', 'dashboard', 'fas fa-tachometer-alt', '/admin/dashboard', None, 1, 1),
            (2, '用户管理', 'users', 'fas fa-users', '/admin/users', None, 2, 1),
            (3, '功能管理', 'functions', 'fas fa-cogs', '/admin/functions', None, 3, 1),
            (4, '角色管理', 'roles', 'fas fa-user-tag', '/admin/roles', None, 4, 1),
            (5, '权限管理', 'permissions', 'fas fa-key', '/admin/permissions', None, 5, 1),
            (6, '模型引擎', 'models', 'fas fa-brain', '/admin/models', None, 6, 1),
            (7, '瞭望采集', 'watch_collect', 'fas fa-search', '/admin/watch/collect', None, 7, 1),
            (8, '数据仓库', 'watch_data', 'fas fa-database', '/admin/watch/data', None, 8, 1),
            (9, '接口管理', 'api_interfaces', 'fas fa-plug', '/admin/api-interfaces', None, 9, 1),
            (10, '数字员工', 'digital_employees', 'fas fa-robot', '/admin/digital-employees', None, 10, 1),
            (11, '智慧舆情', 'sentiment', 'fas fa-chart-pie', None, None, 11, 1),
            (12, '数智大屏', 'sentiment_dashboard', 'fas fa-globe', '/admin/sentiment/dashboard', 11, 1, 1),
            (13, '智能舆情', 'sentiment_analysis', 'fas fa-brain', '/admin/sentiment/analysis', 11, 2, 1),
            (14, '系统管理', 'system_mgmt', 'fas fa-cog', None, None, 12, 1),
            (15, '数据采集', 'data_collect', 'fas fa-satellite-dish', None, None, 13, 1),
            (16, '智能聊天', 'im_chat', 'fas fa-comments', None, None, 14, 1),
            (17, '群管理', 'im_groups', 'fas fa-users', '/admin/im/groups', 16, 1, 1),
            (18, '文件管理', 'im_files', 'fas fa-folder', '/admin/im/files', 16, 2, 1),
            (19, '服务器管理', 'im_servers', 'fas fa-server', '/admin/im/servers', 16, 3, 1),
            (20, '工具管理', 'im_tools', 'fas fa-tools', '/admin/im/tools', 16, 4, 1),
        ]
        for func in default_functions:
            conn.execute(
                """
                INSERT OR IGNORE INTO functions (id, name, code, icon, url, parent_id, sort_order, is_menu) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                func
            )
        conn.execute("UPDATE functions SET parent_id = 14 WHERE id IN (3, 4, 5)")
        conn.execute("UPDATE functions SET parent_id = 15 WHERE id IN (7, 8)")
        conn.execute("UPDATE functions SET parent_id = 16 WHERE id IN (17, 18, 19, 20)")
        
        # 为超级管理员分配所有权限
        conn.execute(
            """
            INSERT OR IGNORE INTO permissions (role_id, function_id)
            SELECT 1, id FROM functions
            """
        )
        
        # 数据库迁移：为旧版users表添加role_id列
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role_id INTEGER DEFAULT NULL")
        except Exception:
            pass  # 列已存在，忽略

        # 模型引擎表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_models(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model_name TEXT NOT NULL,
                description TEXT DEFAULT NULL,
                is_default INTEGER DEFAULT 0,
                status INTEGER DEFAULT 1,
                total_tokens INTEGER DEFAULT 0,
                total_calls INTEGER DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # token统计日志表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS token_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 插入默认示例模型
        conn.execute(
            """
            INSERT OR IGNORE INTO ai_models (id, name, code, api_key, base_url, model_name, description, is_default)
            VALUES (1, 'DeepSeek V4 Pro', 'deepseek_v4', 'sk-0611a5df2b9449f8bc2eadaa3f9a47a2',
                    'https://api.deepseek.com', 'deepseek-chat', 'DeepSeek 高性能大模型', 1)
            """
        )

        # 瞭望数据源表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_sources(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                source_type TEXT NOT NULL DEFAULT 'web',
                url_template TEXT NOT NULL,
                page_param TEXT DEFAULT NULL,
                headers_json TEXT DEFAULT NULL,
                cookies TEXT DEFAULT NULL,
                status INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 瞭望采集数据表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_data(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                page INTEGER DEFAULT 1,
                title TEXT DEFAULT NULL,
                url TEXT DEFAULT NULL,
                summary TEXT DEFAULT NULL,
                raw_html TEXT DEFAULT NULL,
                source_name TEXT DEFAULT NULL,
                deep_crawl_status INTEGER DEFAULT 0,
                deep_crawl_at TEXT DEFAULT NULL,
                collect_at TEXT NOT NULL DEFAULT (datetime('now')),
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 数据库迁移：为旧版watch_data表添加deep_crawl_status列
        try:
            conn.execute("ALTER TABLE watch_data ADD COLUMN deep_crawl_status INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE watch_data ADD COLUMN deep_crawl_at TEXT DEFAULT NULL")
        except Exception:
            pass

        # AI深度采集详情表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_data_detail(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_id INTEGER NOT NULL,
                full_content TEXT DEFAULT NULL,
                ai_summary TEXT DEFAULT NULL,
                keywords TEXT DEFAULT NULL,
                category TEXT DEFAULT NULL,
                sentiment TEXT DEFAULT NULL,
                entities TEXT DEFAULT NULL,
                reading_time TEXT DEFAULT NULL,
                word_count INTEGER DEFAULT 0,
                crawl_duration REAL DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # AI深度采集日志表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deep_crawl_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_id INTEGER DEFAULT NULL,
                action TEXT NOT NULL,
                message TEXT DEFAULT NULL,
                status TEXT DEFAULT 'info',
                duration REAL DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 插入默认百度新闻采集源
        default_headers = '{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,zh-HK;q=0.7,en-US;q=0.6,en;q=0.5", "Accept-Encoding": "gzip, deflate, br", "Connection": "keep-alive"}'
        conn.execute(
            """
            INSERT OR IGNORE INTO watch_sources (id, name, code, source_type, url_template, page_param, headers_json, cookies, sort_order)
            VALUES (1, '百度新闻', 'baidu_news', 'web',
                    'https://www.baidu.com/s?ie=utf-8&wd={keyword}&pn={pn}&tn=news&rtt=4',
                    'pn', ?, NULL, 1)
            """,
            (default_headers,)
        )

        # 接口管理表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_interfaces(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                method TEXT NOT NULL DEFAULT 'GET',
                resp_format TEXT NOT NULL DEFAULT 'JSON',
                params_desc TEXT DEFAULT NULL,
                example_url TEXT DEFAULT NULL,
                qps_limit TEXT DEFAULT NULL,
                has_token INTEGER DEFAULT 0,
                remark TEXT DEFAULT NULL,
                status INTEGER DEFAULT 1,
                tags TEXT DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 插入默认接口
        conn.execute(
            """
            INSERT OR IGNORE INTO api_interfaces (id, name, code, url, method, resp_format,
                params_desc, example_url, qps_limit, has_token, remark, tags)
            VALUES (1, '随机网易云音乐', 'music_wy_rand', 'https://api.52vmy.cn/api/music/wy/rand',
                'GET', 'JSON', '无需参数', 'https://api.52vmy.cn/api/music/wy/rand',
                '每2秒最多4次 携带Token可无视限制', 1, '随机获取一首网易云音乐歌曲', '娱乐,音乐')
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO api_interfaces (id, name, code, url, method, resp_format,
                params_desc, example_url, qps_limit, has_token, remark, tags)
            VALUES (2, '三日天气查询', 'weather_3day', 'https://api.52vmy.cn/api/query/tian',
                'GET', 'JSON', 'city=城市名称', 'https://api.52vmy.cn/api/query/tian?city=北京市',
                '每2秒最多4次 携带Token可无视限制', 1, '查询城市未来三日天气', '工具,天气')
            """
        )

        # 数字员工表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS digital_employees(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                alias TEXT NOT NULL UNIQUE,
                emp_type TEXT NOT NULL DEFAULT '普通',
                model_id INTEGER DEFAULT NULL,
                api_id INTEGER DEFAULT NULL,
                system_prompt TEXT DEFAULT NULL,
                params_config TEXT DEFAULT NULL,
                description TEXT DEFAULT NULL,
                status INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 插入默认数字员工
        conn.execute(
            """
            INSERT OR IGNORE INTO digital_employees (id, name, alias, emp_type, model_id, api_id,
                system_prompt, params_config, description, sort_order)
            VALUES (1, '川小农', '川小农', 'AI', 1, NULL,
                '姓名：川小农
角色：你是一名专业的文案编写高手(专家级)，你有丰富的与AI、计算机科学与技术、数据库、信息安全、物联网有关领域的专业知识、项目经验和工作经验。同时你也具备较强的技术实践经验能力和技术储备。你需要根据工作步骤按要求完成任务。你需要根据步骤中的提示最终生成详细的文案内容。
工作步骤：
1、用户输入"开始"后，提示用户输入关键字或关键信息或关键词，以用作生成第2步备选文案主题。关键字或关键词形如:四川薪资，人才、就业
2、当用户根据提示输入关键词等信息后，你需要根据要求及需求生成10个备选主题，以markdown格式输出渲染，用户可以根据这10个主题完成第3步中的大纲生成任务，markdown格式输出如下:
```
【川农文案生成助手】-v1.0
### 备选主题列表
---
作者:郭一宁
[1]、xxxxxxxxxx
[2]、yyyyyyyyyy
……
[10]、zzzzzzzzzz
```
3、提示用户输入第2步生成的列表中的主题编号，你需要根据用户输入的编号找到对应的主题信息，再以该主题信息生成三种不同风格的大纲，以供用户选择大纲生成详细内容，大纲风格及格式以markdown格式输出，格式如下:
```
【风格一】专业报告风
需要生成一级+二级章节大纲，体现专业、格式规范、可以用于word风格。
【风格二】小红书种草风
需要生成一级主要小标题，风格参考小红书特点或规则。
【风格三】普通叙述风
只需要生成编写思路。
```
4、提示用户输入【风格一】或【风格二】或【风格三】选择风格，你需要根据选择的风格生成详细内容。内容生成时一个一个章节生成！！！注意：这非常重要！！！。
5、内容生成时一个一个章节生成！！！生成详细内容时，一个章节段落生成后，提示用户确认，如果有修改要求，按新的要求生成后，再继续，如果用户输入"继续"则可以生成下一个章节或段落内容。
限制条件：
--必须按工作步骤执行。
--体现专业性、职业性、规范性。
--其他未靠完善或有缺漏的逻辑由你自行补全。',
                NULL, '川小农文案编写生成助手，按步骤引导创作专业文案', 1)
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO digital_employees (id, name, alias, emp_type, model_id, api_id,
                system_prompt, params_config, description, sort_order)
            VALUES (2, '天气查询', '天气', '普通', NULL, 2,
                NULL,
                '{"param_key":"city","param_label":"城市名称","required":true,"placeholder":"请输入城市名称"}',
                '通过三日天气API查询指定城市的天气信息', 2)
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO digital_employees (id, name, alias, emp_type, model_id, api_id,
                system_prompt, params_config, description, sort_order)
            VALUES (3, '随机音乐', '音乐', '普通', NULL, 1,
                NULL,
                NULL,
                '随机获取一首网易云音乐歌曲，返回歌曲卡片信息', 3)
            """
        )

        # 插入普通用户和会员角色
        conn.execute(
            """
            INSERT OR IGNORE INTO roles (id, name, code, description, is_system)
            VALUES (2, '普通用户', 'user', '前台普通用户，可注册获得', 1)
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO roles (id, name, code, description, is_system)
            VALUES (3, '会员', 'vip', '付费会员，享有更多权限(本期预留)', 1)
            """
        )

        # 对话历史表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT DEFAULT NULL,
                model_id INTEGER DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 对话消息表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                msg_type TEXT DEFAULT 'text',
                extra TEXT DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 智慧舆情分析记录表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sentiment_analysis(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                analysis_type TEXT NOT NULL DEFAULT 'comprehensive',
                data_source TEXT DEFAULT NULL,
                prompt TEXT DEFAULT NULL,
                result TEXT DEFAULT NULL,
                risk_level TEXT DEFAULT 'low',
                risk_score REAL DEFAULT 0,
                keywords TEXT DEFAULT NULL,
                summary TEXT DEFAULT NULL,
                status TEXT DEFAULT 'completed',
                model_used TEXT DEFAULT NULL,
                tokens_used INTEGER DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # 智慧舆情报告表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sentiment_reports(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER,
                report_type TEXT NOT NULL DEFAULT 'daily',
                title TEXT NOT NULL,
                content TEXT DEFAULT NULL,
                chart_data TEXT DEFAULT NULL,
                create_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )