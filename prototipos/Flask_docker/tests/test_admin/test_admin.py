import io
from tests.__init__ import BaseTestCase
from app.usuario import User
from app.extensions import db
import tempfile
from contextlib import nullcontext
from pathlib import Path
from app.admin import routes as admin_routes
from unittest.mock import patch, MagicMock

from app.vector_update_state import VectorUpdateState
from app.web_scraping_state import WebScrapingSate
from app.admin.routes import documentos_async

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
        
        # Si el usuario no existe
        r = self.client.post("/admin/users/999999", follow_redirects=False)
        self.assertEqual(r.status_code, 404)

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
        
        # Si el usuario no existe
        r = self.client.post("/admin/users/999999/delete", follow_redirects=False)
        self.assertEqual(r.status_code, 404)

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
        
    def test_admin_crear_usuario_get(self):
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        r = self.client.get("/admin/users/add")
        self.assertEqual(r.status_code, 200)
        
        self.assertIn(b"name=\"nombre\"", r.data)
        self.assertIn(b"name=\"email\"", r.data)
        
    def test_admin_crear_usuario_correcto(self):
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        r = self.client.post(
            "/admin/users/add",
            data={
                "nombre": "Nuevo",
                "email": "nuevo@example.com",
                "password": "123456",
                "is_admin": "y",
            },
            follow_redirects=False
        )
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("/admin/users", r.headers.get("Location", ""))

        # Comprobar que el usuario se creó correctamente
        u = User.get_by_email("nuevo@example.com")
        self.assertIsNotNone(u)
        self.assertEqual(u.nombre, "Nuevo")
        self.assertTrue(u.is_admin)
        self.assertTrue(u.check_password("123456"))
        
        # Borrar usuario
        user_id = u.id
        db.session.delete(u)
        db.session.commit()

        self.assertIsNone(User.get_by_id(user_id))
        
    def test_admin_crear_usuario_email_duplicado(self):
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        # ya existe
        self.crear_usuario(email="dup@example.com", password="contraseña", is_admin=False)

        r = self.client.post(
            "/admin/users/add",
            data={
                "nombre": "Dup",
                "email": "dup@example.com",
                "password": "123456",
            },
            follow_redirects=True
        )
        self.assertEqual(r.status_code, 200)

        # Debe mostrarse el error del form
        self.assertIn(b"Ya existe un usuario con ese email.", r.data)

        # Y NO debe crearse un segundo usuario con ese email
        users_dup = User.query.filter_by(email="dup@example.com").all()
        self.assertEqual(len(users_dup), 1)
    
    def test_admin_pliegos_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pliegos_test"
            self.app.config["DOCS_DIR"] = str(p)

            with self.app.app_context():
                out = admin_routes.pliegos_dir()
                self.assertEqual(out, p.resolve())
                self.assertTrue(out.exists())
                self.assertTrue(out.is_dir())
                
    def test_admin_documents_vacio(self):
        # Admin logueado
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)
        
        r = self.client.post("/admin/documents/upload", data={}, follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))

    def test_admin_actualizar_documentos(self):
        # Admin logueado
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)
        
        fake_svc = MagicMock()
        with patch("app.admin.routes.documentos_service", return_value=fake_svc):
            data = {
                "files": (io.BytesIO(b"%PDF-1.4 test"), "test.pdf"),
            }
            r = self.client.post(
                "/admin/documents/upload",
                data=data,
                content_type="multipart/form-data",
                follow_redirects=False,
            )
            self.assertIn(r.status_code, (302, 303))
            self.assertTrue(fake_svc.save_uploads.called)
    
    @patch("app.admin.routes.executor.submit")
    def test_admin_actualizar_vector(self, mock_submit):
        # Admin logueado
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)
        
        r = self.client.post("/admin/vector-db/update")
        self.assertEqual(r.status_code, 202)

        job_id = r.get_json()["job_id"]
        job = VectorUpdateState.query.get(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "queued")

        mock_submit.assert_called_once()
        
    def test_admin_vector_estado(self):
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        job = VectorUpdateState(status="queued", progress=0, current_doc=None, error=None)
        db.session.add(job)
        db.session.commit()

        r = self.client.get(f"/admin/vector-db/status/{job.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "queued")

        r2 = self.client.get("/admin/vector-db/status/999999")
        self.assertEqual(r2.status_code, 404)
        
    def test_admin_documentos_service(self):
        with self.app.app_context():
            with patch("app.admin.routes.DocumentosService") as MockSvc:
                admin_routes.documentos_service()
                MockSvc.assert_called_once()
                
    def test_admin_documento_async_inexistente(self):
        documentos_async(self.app, 999999)
    
    def test_admin_documento_async_correcto(self):
        job = VectorUpdateState(status="queued", progress=0, current_doc=None, error=None)
        db.session.add(job)
        db.session.commit()

        fake_svc = MagicMock()
        def fake_update_vector_db(*, on_progress, on_current_doc):
            on_current_doc("doc1.pdf")
            on_progress(1, 2)
            on_progress(2, 2)

        fake_svc.update_vector_db.side_effect = fake_update_vector_db

        ctx = self.app.app_context()
        ctx.push()
        try:
            with patch.object(self.app, "app_context", return_value=nullcontext()):
                with patch("app.admin.routes.documentos_service", return_value=fake_svc):
                    documentos_async(self.app, job.id)
        finally:
            ctx.pop()

        db.session.expire_all()
        job2 = VectorUpdateState.query.get(job.id)
        self.assertEqual(job2.current_doc, "doc1.pdf")
        self.assertEqual(job2.status, "done")
        self.assertEqual(job2.progress, 100)
        self.assertIsNone(job2.error)
        self.assertIsNotNone(job2.finished_at)
        
    def test_admin_documento_async_error(self):
        job = VectorUpdateState(status="queued", progress=0, current_doc=None, error=None)
        db.session.add(job)
        db.session.commit()

        fake_svc = MagicMock()
        fake_svc.update_vector_db.side_effect = RuntimeError("fallo para los test")

        ctx = self.app.app_context()
        ctx.push()
        try:
            with patch.object(self.app, "app_context", return_value=nullcontext()):
                with patch("app.admin.routes.documentos_service", return_value=fake_svc):
                    documentos_async(self.app, job.id)
        finally:
            ctx.pop()
            
        db.session.expire_all()
        job2 = VectorUpdateState.query.get(job.id)
        self.assertEqual(job2.status, "failed")
        self.assertIn("fallo para los test", job2.error)
        self.assertIsNotNone(job2.finished_at)
        
    @patch("app.admin.routes.executor.submit")
    def test_admin_web_scraping_crea_job(self, mock_submit):
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        r = self.client.post("/admin/documents/web_scraping")
        self.assertEqual(r.status_code, 202)

        job_id = r.get_json()["job_id"]
        job = WebScrapingSate.query.get(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "queued")

        mock_submit.assert_called_once()

    def test_admin_web_scraping_estado(self):
        self.crear_usuario(email="admin@example.com", password="contraseña", is_admin=True)
        self.login("admin@example.com", follow_redirects=True)

        job = WebScrapingSate(status="queued", progress=0, message="En cola", error=None)
        db.session.add(job); db.session.commit()

        r = self.client.get(f"/admin/documents/web_scraping/status/{job.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "queued")

        r2 = self.client.get("/admin/documents/web_scraping/status/999999")
        self.assertEqual(r2.status_code, 404)
