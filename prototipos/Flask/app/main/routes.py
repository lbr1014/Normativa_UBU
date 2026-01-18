from flask import render_template, request
from flask_login import login_required, current_user
from . import main_bp
from ..extensions import db
from ..forms import EditUserForm
from ..usuario import User
from app.consulta import Consulta

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
    q = Consulta.query.order_by(Consulta.created_at.desc())
    if not getattr(current_user, "is_admin", False):
        q = q.filter(Consulta.user_id == int(current_user.id))

    consultas = q.limit(50).all()
    return render_template("pag_principal.html", user=current_user,  consultas=consultas)

@main_bp.route("/edit_user", methods=["GET", "POST"])
@login_required
def edit_user():
    form = EditUserForm(obj=current_user) if request.method == "GET" else EditUserForm()

    
    if form.validate_on_submit():
        
        # === NOMBRE ===
        if form.nombre.data:
            current_user.nombre = form.nombre.data.strip()
            
        # === EMAIL ===
        if form.email.data:
            new_email = form.email.data.strip().lower()
        
            if new_email != current_user.email:
                exists = User.get_by_email(new_email)
                            
                if exists:
                    form.email.errors.append("Ya existe un usuario con ese email.")
                    return render_template("edit_user.html", form=form, user=current_user)

            current_user.email = new_email
        
        # === CONTRASEÑA ===
        if form.new_password.data:
            current_user.set_password(form.new_password.data)

        db.session.commit()
                 
    return render_template("edit_user.html", form=form, user=current_user)

@main_bp.get("/historial")
@login_required
def historial():
    q = Consulta.query.order_by(Consulta.created_at.desc())

    # Si no es admin, filtrar por su user_id
    if not getattr(current_user, "is_admin", False):
        q = q.filter(Consulta.user_id == int(current_user.id))

    consultas = q.limit(200).all()
    return render_template("historial.html", consultas=consultas)

@main_bp.post("/consulta/<int:consulta_id>/delete")
@login_required
def delete_consulta(consulta_id: int):
    consulta = Consulta.query.get_or_404(consulta_id)

    if not current_user.is_admin and consulta.user_id != int(current_user.id):
        return {"ok": False, "error": "No autorizado"}, 403

    db.session.delete(consulta)
    db.session.commit()

    return {"ok": True, "deleted": consulta_id}
