from flask import Flask
from pathlib import Path
import os
from dotenv import load_dotenv

from .extensions import db, login_manager, migrate
from .usuario import User
from .consulta import Consulta
from .documentos import Documento, DocumentosService
from .auth import auth_bp
from .vector_update_state import VectorUpdateState
from .web_scraping_state import WebScrapingSate

def create_app():
    load_dotenv("secret.env")
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )

    SECRET_KEY  = os.environ.get("SECRET_KEY")
    if not SECRET_KEY :
        raise RuntimeError("SECRET_KEY no está definida. Revisa tu .env o variables de entorno.")
    app.config["SECRET_KEY"] = SECRET_KEY 
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL no está definida (Postgres requerido).")

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["DOCS_DIR"] = os.environ.get("DOCS_DIR", "pliegos")

    # init extensions
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Debes iniciar sesión para acceder a esta página."

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.get_by_id(int(user_id))   
    
    # register blueprints
    from .main.routes import main_bp
    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    from .rag.routes import rag_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(rag_bp)

    return app
