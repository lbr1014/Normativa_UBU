from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, user_id: str, nombre: str, email: str, password_hash: str):
        self.id = user_id                 
        self.nombre = nombre
        self.email = email
        self.password_hash = password_hash

    @classmethod
    def create(cls, user_id: str, nombre: str, email: str, password_plain: str):
        return cls(
            user_id=user_id,
            nombre=nombre,
            email=email,
            password_hash=generate_password_hash(password_plain)
        )

    def check_password(self, password_plain: str) -> bool:
        return check_password_hash(self.password_hash, password_plain)
