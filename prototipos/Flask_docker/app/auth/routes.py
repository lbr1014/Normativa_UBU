from flask import render_template, redirect, url_for
from flask_login import login_user, logout_user, login_required
from . import auth_bp
from ..forms import LoginForm, SignupForm
from ..usuario import User
from ..extensions import db

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        password = form.password.data

        user = User.get_by_email(email)

        if user and user.check_password(password):
            user.update_last_login()
            db.session.commit()
            login_user(user)
            return redirect(url_for("main.pag_principal"))

        form.password.errors.append("Email o contraseña incorrectos.")

    return render_template("login.html", form=form)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.inicio"))

@auth_bp.route("/singup", methods=["GET", "POST"])
def singup():
    form = SignupForm()

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        email = form.email.data.lower().strip()
        password = form.password.data

        if User.get_by_email(email):
            form.email.errors.append("Ya existe un usuario con ese email.")
            return render_template("singup.html", form=form)

        user = User(nombre=nombre, email=email)
        user.set_password(password)
        user.update_last_login()

        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("main.pag_principal"))

    return render_template("singup.html", form=form)
