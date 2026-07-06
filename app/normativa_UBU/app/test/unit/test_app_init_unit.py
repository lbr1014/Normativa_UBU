"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias de la factoria de aplicacion n (create_app) y de las funciones auxiliares de inicialización de la aplicación Flask. 
Su objetivo es verificar la correcta construcción de la configuración a partir de variables de entorno, la inicialización de directorios y servicios, 
la gestión de errores durante el arranque y el funcionamiento de los componentes de autenticación. 
Las pruebas cubren distintos escenarios de despliegue, incluyendo entornos de desarrollo, pruebas y producción.
"""

import os
import secrets
from unittest.mock import patch

import app.main.code as app_factory
from app.main.code.extensions import login_manager
from app.main.code.model.user import User
from app.test.support import BaseAppTestCase


class AppInitHelpersUnitTest(BaseAppTestCase):
    def test_get_required_env_raises_when_value_is_missing(self):
        """
        Verifica que se lanza una excepción cuando una variable de entorno obligatoria no está definida.
        """
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError) as raised:
            app_factory._get_required_env("FLASK_SESSION_SIGNER")

        self.assertIn("FLASK_SESSION_SIGNER", str(raised.exception))

    def test_get_required_env_returns_test_secret_in_test_env(self):
        """
        Comprueba que se utiliza un valor secreto de pruebas cuando la aplicación se ejecuta en entorno de testing.
        """
        with patch.dict(os.environ, {"PYTHIA_TESTING": "1"}, clear=True):
            self.assertEqual(app_factory._get_required_env("MISSING"), "test-secret")

    def test_build_database_url_returns_none_when_postgres_parts_are_missing(self):
        """
        Verifica que no se genera una URL de conexión a base de datos cuando faltan parámetros esenciales de configuración.
        """
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(app_factory._build_database_url_from_env())

        with patch.dict(
            os.environ,
            {"POSTGRES_USER": "user", "POSTGRES_PASSWORD": secrets.token_urlsafe(16)},
            clear=True,
        ):
            self.assertIsNone(app_factory._build_database_url_from_env())

    def test_build_database_url_prefers_database_url(self):
        """
        Comprueba que se prioriza el uso de la variable DATABASE_URL cuando está disponible.
        """
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///direct.sqlite"}, clear=True):
            self.assertEqual(app_factory._build_database_url_from_env(), "sqlite:///direct.sqlite")

    def test_build_database_url_builds_postgres_url_with_defaults(self):
        """
        Verifica la construcción correcta de la URL de conexión PostgreSQL utilizando los parámetros predeterminados.
        """
        password = secrets.token_urlsafe(16)
        env = {"POSTGRES_USER": "pythia", "POSTGRES_PASSWORD": password, "POSTGRES_DB": "rag"}

        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                app_factory._build_database_url_from_env(),
                f"postgresql+psycopg2://pythia:{password}@db:5432/rag",
            )

    def test_build_database_url_builds_postgres_url_with_custom_host_and_port(self):
        """
        Comprueba la generación de URLs PostgreSQL utilizando host y puerto personalizados.
        """
        password = secrets.token_urlsafe(16)
        env = {
            "POSTGRES_USER": "pythia",
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": "rag",
            "POSTGRES_HOST": "postgres.local",
            "POSTGRES_PORT": "6543",
        }

        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                app_factory._build_database_url_from_env(),
                f"postgresql+psycopg2://pythia:{password}@postgres.local:6543/rag",
            )


class CreateAppUnitTest(BaseAppTestCase):
    def test_create_app_raises_when_database_url_cannot_be_built(self):
        """
        Verifica que la creación de la aplicación falla cuando no es posible obtener una configuración válida para la base de datos.
        """
        with patch("app.main.code.load_dotenv"), patch.dict(
            os.environ,
            {"FLASK_SESSION_SIGNER": "test-secret"},
            clear=True,
        ), self.assertRaises(RuntimeError) as raised:
            app_factory.create_app()

        self.assertIn("DATABASE_URL", str(raised.exception))

    def test_create_app_normalizes_legacy_postgres_url(self):
        """
        Comprueba la normalización de URL PostgreSQL heredadas al formato soportado por SQLAlchemy.
        """
        with patch("app.main.code.load_dotenv"), patch.object(app_factory.db, "init_app"), patch.object(
            app_factory.migrate, "init_app"
        ), patch.object(app_factory.mail, "init_app"), patch.object(app_factory.csrf, "init_app"), patch.dict(
            os.environ,
            {
                "FLASK_SESSION_SIGNER": "test-secret",
                "DATABASE_URL": "postgres://user:pass@db:5432/rag",
            },
            clear=True,
        ):
            created_app = app_factory.create_app()

        self.assertEqual(
            created_app.config["SQLALCHEMY_DATABASE_URI"],
            "postgresql://user:pass@db:5432/rag",
        )

    def test_create_app_uses_sqlite_memory_when_testing_and_no_database_url(self):
        """
        Verifica que se utiliza una base de datos SQLite en memoria cuando la aplicación se ejecuta en modo de pruebas.
        """
        with patch("app.main.code.load_dotenv"), patch.object(app_factory.db, "init_app"), patch.object(
            app_factory.migrate, "init_app"
        ), patch.object(app_factory.mail, "init_app"), patch.object(app_factory.csrf, "init_app"), patch.dict(
            os.environ,
            {"FLASK_SESSION_SIGNER": "test-secret", "PYTHIA_TESTING": "1"},
            clear=True,
        ):
            created_app = app_factory.create_app()

        self.assertEqual(created_app.config["SQLALCHEMY_DATABASE_URI"], "sqlite:///:memory:")

    def test_create_app_configures_data_dir_from_project_root_when_no_env_and_not_docker(self):
        """
        Comprueba que el directorio de datos se configura correctamente utilizando la estructura del proyecto cuando no existe una configuración específica.
        """
        with patch("app.main.code.load_dotenv"), patch.object(app_factory.db, "init_app"), patch.object(
            app_factory.migrate, "init_app"
        ), patch.object(app_factory.mail, "init_app"), patch.object(app_factory.csrf, "init_app"), patch.dict(
            os.environ,
            {"FLASK_SESSION_SIGNER": "test-secret", "PYTHIA_TESTING": "1"},
            clear=True,
        ), patch("app.main.code.Path.is_dir", return_value=False), patch(
            "pathlib.Path.mkdir", return_value=None
        ), patch("pathlib.Path.write_text", return_value=None), patch("pathlib.Path.unlink", return_value=None):
            created_app = app_factory.create_app()

        self.assertTrue(str(created_app.config["DATA_DIR"]).endswith("data"))

    def test_create_app_max_content_length_invalid_env_uses_default(self):
        """
        Verifica que se emplea el tamaño máximo de subida por defecto cuando la configuración proporcionada es inválida.
        """
        with patch("app.main.code.load_dotenv"), patch.object(app_factory.db, "init_app"), patch.object(
            app_factory.migrate, "init_app"
        ), patch.object(app_factory.mail, "init_app"), patch.object(app_factory.csrf, "init_app"), patch.dict(
            os.environ,
            {
                "FLASK_SESSION_SIGNER": "test-secret",
                "PYTHIA_TESTING": "1",
                "MAX_CONTENT_LENGTH": "not-an-int",
            },
            clear=True,
        ):
            created_app = app_factory.create_app()

        self.assertEqual(created_app.config["MAX_CONTENT_LENGTH"], 250 * 1024 * 1024)

    def test_create_app_data_dir_falls_back_to_project_data_when_not_docker(self):
        """
        Comprueba la correcta configuración del directorio de datos a partir de variables de entorno personalizadas.
        """
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp(prefix="pythia-appinit-"))
        with patch("app.main.code.load_dotenv"), patch.object(app_factory.db, "init_app"), patch.object(
            app_factory.migrate, "init_app"
        ), patch.object(app_factory.mail, "init_app"), patch.object(app_factory.csrf, "init_app"), patch.dict(
            os.environ,
            {"FLASK_SESSION_SIGNER": "test-secret", "PYTHIA_TESTING": "1", "DATA_DIR": str(tmp)},
            clear=True,
        ), patch("app.main.code.Path.is_dir", return_value=False):
            created_app = app_factory.create_app()

        self.assertEqual(Path(created_app.config["DATA_DIR"]).resolve(), tmp.resolve())

    def test_create_app_profile_dir_chmod_and_cleanup_errors_are_ignored(self):
        """
        Verifica que los errores producidos durante la asignación de permisos o la limpieza de archivos temporales no impiden la creación de la aplicación.
        """
        import sys
        from types import ModuleType

        fake_os = ModuleType("os")
        fake_os.name = "posix"
        fake_os.environ = os.environ
        fake_os.path = os.path
        fake_os.mkdir = os.mkdir

        prev_os = sys.modules.get("os")
        sys.modules["os"] = fake_os
        try:
            import importlib

            mod = importlib.reload(app_factory)
            with patch("app.main.code.load_dotenv"), patch.object(mod.db, "init_app"), patch.object(
                mod.migrate, "init_app"
            ), patch.object(mod.mail, "init_app"), patch.object(mod.csrf, "init_app"), patch.dict(
                os.environ,
                {"FLASK_SESSION_SIGNER": "test-secret", "PYTHIA_TESTING": "1", "DATA_DIR": str(self._tmpdir)},
                clear=True,
            ), patch("pathlib.Path.chmod", side_effect=OSError), patch("pathlib.Path.unlink", side_effect=OSError):
                created_app = mod.create_app()
        finally:
            if prev_os is None:
                del sys.modules["os"]
            else:
                sys.modules["os"] = prev_os
            import importlib

            importlib.reload(app_factory)

        self.assertIn("PROFILE_UPLOAD_FOLDER", created_app.config)

    def test_create_app_raises_runtime_error_when_profile_dir_is_not_writable(self):
        """
        Verifica que la creación de la aplicación lanza un error en tiempo de ejecución cuando el directorio de perfiles no es escribible.
        """
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp(prefix="pythia-appinit-unwritable-"))
        with patch("app.main.code.load_dotenv"), patch.object(app_factory.db, "init_app"), patch.object(
            app_factory.migrate, "init_app"
        ), patch.object(app_factory.mail, "init_app"), patch.object(app_factory.csrf, "init_app"), patch.dict(
            os.environ,
            {"FLASK_SESSION_SIGNER": "test-secret", "PYTHIA_TESTING": "1", "DATA_DIR": str(tmp)},
            clear=True,
        ):
            # Fuerza el fallo justo al crear PROFILE_UPLOAD_FOLDER (data_dir/profiles)
            def mkdir_side_effect(self, *args, **kwargs):
                if str(self).endswith("profiles"):
                    raise OSError("nope")
                

            with patch("pathlib.Path.mkdir", new=mkdir_side_effect), self.assertRaises(RuntimeError) as raised:
                app_factory.create_app()

        self.assertIn("No hay permisos de escritura", str(raised.exception))

    def test_login_manager_user_loader_loads_user_by_integer_id(self):
        """
        Verifica que el gestor de autenticación carga correctamente un usuario a partir de su identificador almacenado en sesión.
        """
        with patch.object(User, "get_by_id", return_value="loaded-user") as mock_get_by_id:
            self.assertEqual(login_manager._user_callback("12"), "loaded-user")

        mock_get_by_id.assert_called_once_with(12)
