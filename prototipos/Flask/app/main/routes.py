from flask import render_template
from flask_login import login_required, current_user
from . import main_bp

@main_bp.route("/")
def inicio():
    return render_template(
        "index.html",
        titulo="Implementación de un RAG sobre las licitaciones del estado",
        autor="Autora: Lydia Blanco Ruiz"
    )

@main_bp.route("/pagina_principal")
@login_required
def pag_principal():
    return render_template("pag_principal.html", user=current_user)
