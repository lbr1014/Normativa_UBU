from tests.base import BaseTestCase
from app.usuario import User

class AdminTest(BaseTestCase):

    def test_admin_necesita_admin(self):
        self.crear_usuario(email="user@example.com", password="contraseña", is_admin=False)

        self.login("user@example.com", follow_redirects=True)

        r = self.client.get("/admin/users", follow_redirects=False)

        self.assertIn(r.status_code, (302, 303, 403))

    def test_admin_pag_correcta_para_admin(self):
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)

        self.login("admin@example.com", follow_redirects=True)

        r = self.client.get("/admin/users")
        self.assertEqual(r.status_code, 200)

    def test_admin_cambia_tipo_usuario(self):
        # Admin logueado
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        # Usuario normal a modificar
        u = self.crear_usuario(email="user1@example.com", password="contraseña", is_admin=False)
        self.assertFalse(u.is_admin)

        # Cambiar el usuario normal a admin
        r = self.client.post(f"/admin/users/{u.id}", follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("/admin/users", r.headers.get("Location", ""))

        # Recargar de BD y comprobar que ahora sea admin
        u_db = User.get_by_id(u.id)
        self.assertIsNotNone(u_db)
        self.assertTrue(u_db.is_admin)

        # Volver a cambiar para que deje de ser admin
        r2 = self.client.post(f"/admin/users/{u.id}", follow_redirects=False)
        self.assertIn(r2.status_code, (302, 303))

        u_db2 = User.get_by_id(u.id)
        self.assertIsNotNone(u_db2)
        self.assertFalse(u_db2.is_admin)

    def test_admin_borra_usuario(self):
        # Admin logueado
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        # Usuario a borrar
        u = self.crear_usuario(email="user2@example.com", password="contraseña", is_admin=False)
        self.assertIsNotNone(User.get_by_id(u.id))

        # Borrar
        r = self.client.post(f"/admin/users/{u.id}/delete", follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("/admin/users", r.headers.get("Location", ""))

        # Ya no existe
        self.assertIsNone(User.get_by_id(u.id))

    def test_admin_no_puede_cambiarse_a_si_mismo(self):
        admin = self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        r = self.client.post(f"/admin/users/{admin.id}", follow_redirects=False)
        self.assertEqual(r.status_code, 400)

        # Sigue siendo admin
        admin_db = User.get_by_id(admin.id)
        self.assertTrue(admin_db.is_admin)

    def test_admin_no_puede_borrarse_a_si_mismo(self):
        admin = self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        r = self.client.post(f"/admin/users/{admin.id}/delete", follow_redirects=False)
        self.assertEqual(r.status_code, 400)

        # Sigue existiendo
        self.assertIsNotNone(User.get_by_id(admin.id))