import tornado.web

from app.controllers.base import BaseHandler

class IndexHandler(BaseHandler):
    def get(self):
        self.render("login.html")
