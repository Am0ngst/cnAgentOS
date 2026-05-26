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
        ]
        for func in default_functions:
            conn.execute(
                """
                INSERT OR IGNORE INTO functions (id, name, code, icon, url, parent_id, sort_order, is_menu) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                func
            )
        
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
            VALUES (1, 'DeepSeek V4 Pro', 'deepseek_v4', 'sk-8249d07d3adf4e5ca54b1d4f0c16a30d',
                    'https://api.deepseek.com', 'deepseek-v4-pro', 'DeepSeek 高性能大模型', 1)
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
                '你是一个智能助手名叫川小农，你热情、专业、乐于助人。请用中文回复用户的问题，回答简洁清晰。',
                NULL, '基于默认AI模型的智能对话助手，支持SSE流式响应', 1)
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