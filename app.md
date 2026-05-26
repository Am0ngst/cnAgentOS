根目录
    app.md
    app.py
    text.py

    app
        __init__.py

        controllers
            auth.py
            base.py
            home.py
            __init__.py

        models
            db.py
            user.py
            __init__.py

            __pycache__
                db.cpython-311.pyc
                text.cpython-311.pyc
                user.cpython-311.pyc
                __init__.cpython-311.pyc

        static (view中的静态资源)
            css (样式)
                base.css (基础通用样式)

            js (js脚本)
                base.js (基础通用脚本)

        templates (view-视图)
            base.html (基础模板)
            index.html (后台首页模板)
            login.html (登录页模板)
            register.html (注册页模板)

        __pycache__
            __init__.cpython-311.pyc

    database (sqlite数据库目录，用于存放sqlite文件和sql脚本文件)
        app.db (当前自动生成的sqlite数据库，通过init_db()方法运行时检查创建)

    venv (python3.11下创建venv空间，语法:python -m venv venv，注意：项目依赖需要在此空间下安装)