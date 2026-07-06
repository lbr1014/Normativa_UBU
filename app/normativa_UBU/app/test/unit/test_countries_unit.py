"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias para app.main.code.countries, encargado de gestionar información relacionada con países, códigos ISO 
y localización de nombres de países en distintos idiomas. Las pruebas verifican el funcionamiento normal del módulo cuando dispone de las 
librerías externas (pycountry y babel) y también los mecanismos de respaldo implementados cuando dichas dependencias no están disponibles. 
Además, comprueban la normalización de códigos e idiomas, la obtención de nombres localizados y la conversión entre distintos formatos de identificación de países.
"""

import builtins
import sys
import types
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


def _load_countries_module(*, extra_modules: dict[str, types.ModuleType] | None = None, block_imports: set[str] | None = None):
    """
    Carga el módulo countries para pruebas, permitiendo bloquear ciertas importaciones o inyectar módulos falsos para simular distintos 
    escenarios de disponibilidad de dependencias.
    """
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "app" / "main" / "code" / "countries.py"
    module_name = f"countries_test_{uuid4().hex}"

    old_modules: dict[str, object] = {}
    if extra_modules:
        for k, m in extra_modules.items():
            old_modules[k] = sys.modules.get(k)
            sys.modules[k] = m

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        """
        Permite bloquear ciertas importaciones para simular la ausencia de dependencias.
        """
        if block_imports and name in block_imports:
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    loader = SourceFileLoader(module_name, str(module_path))
    spec = spec_from_loader(loader.name, loader)
    module = module_from_spec(spec)
    sys.modules[loader.name] = module
    try:
        from unittest import mock

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            loader.exec_module(module)
        return module
    finally:
        if extra_modules:
            for k, old in old_modules.items():
                if old is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = old


class CountriesUnitTest(unittest.TestCase):
    def test_import_fallbacks_without_pycountry_and_babel(self):
        """
        Verifica que el módulo continúa funcionando correctamente cuando las librerías pycountry y babel no están instaladas, utilizando 
        los mecanismos de respaldo definidos internamente.
        """
        m = _load_countries_module(block_imports={"pycountry", "babel"})
        self.assertIsNone(m.pycountry)
        self.assertIsNone(m.Locale)

        choices = m.country_choices("en")
        self.assertTrue(any(code == "ES" for code, _name in choices))

        self.assertEqual(m.normalize_country_code("xx"), "ES")
        self.assertEqual(m.country_name_for_code("US", "en"), "United States")
        self.assertEqual(m.country_numeric_for_code("US"), "840")
        self.assertIn("ES", m.COUNTRY_BY_CODE)

    def test_babel_locale_parse_error_falls_back_to_es(self):
        """
        Comprueba que, cuando se produce un error al interpretar una configuración regional mediante Babel, el sistema utiliza correctamente 
        el idioma español como alternativa.
        """
        fake_babel = types.ModuleType("babel")
        fake_core = types.ModuleType("babel.core")

        class UnknownLocaleError(Exception):
            pass

        fake_core.UnknownLocaleError = UnknownLocaleError

        class Locale:
            @staticmethod
            def parse(lang, sep="-"):
                if lang == "xx":
                    raise UnknownLocaleError("bad")
                return types.SimpleNamespace(territories={"es": "España", 1: "ignored"})

        fake_babel.Locale = Locale
        m = _load_countries_module(extra_modules={"babel": fake_babel, "babel.core": fake_core}, block_imports={"pycountry"})
        names = m._territory_names_for_lang("xx")
        self.assertEqual(names.get("ES"), "España")

    def test_with_pycountry_uses_localized_territories_and_numeric_zfill(self):
        """
        Verifica el uso de datos proporcionados por pycountry y babel, incluyendo la obtención de nombres localizados de países y la normalización de códigos numéricos ISO.
        """
        fake_pycountry = types.ModuleType("pycountry")

        class _Countries:
            def __iter__(self):
                """
                Simula un iterable de países con atributos similares a los de pycountry.
                """
                return iter(
                    [
                        types.SimpleNamespace(alpha_2="ES", name="Spain", numeric="724"),
                        types.SimpleNamespace(alpha_2="US", name="United States", numeric="7"),
                        types.SimpleNamespace(alpha_2=None, name="bad"),
                    ]
                )

            def get(self, alpha_2=None):
                """
                Simula la función get de pycountry para obtener información de países por código alpha-2.
                """
                if alpha_2 == "US":
                    return types.SimpleNamespace(alpha_2="US", name="United States", numeric="7")
                return None

        fake_pycountry.countries = _Countries()

        fake_babel = types.ModuleType("babel")
        fake_core = types.ModuleType("babel.core")

        class UnknownLocaleError(Exception):
            """Simula la excepción lanzada por Babel cuando no se puede interpretar una configuración regional."""
            

        fake_core.UnknownLocaleError = UnknownLocaleError

        class Locale:
            @staticmethod
            def parse(_lang, sep="-"):
                """
                Simula la función de análisis de Babel para obtener nombres localizados de territorios.
                """
                return types.SimpleNamespace(territories={"US": "Estados Unidos"})

        fake_babel.Locale = Locale

        m = _load_countries_module(extra_modules={"pycountry": fake_pycountry, "babel": fake_babel, "babel.core": fake_core})

        self.assertIn(("US", "Estados Unidos"), m.country_choices("es"))
        self.assertEqual(m.country_name_for_code("US", "es"), "Estados Unidos")
        self.assertEqual(m.country_numeric_for_code("US"), "007")

        with patch.object(m, "_territory_names_for_lang", return_value={}):
            self.assertEqual(m.country_name_for_code("US", "es"), "United States")

    def test_normalize_lang_empty_and_underscore(self):
        """
        Comprueba la normalización de identificadores de idioma, gestionando correctamente valores vacíos y formatos alternativos que utilizan guiones bajos.
        """
        m = _load_countries_module(block_imports={"pycountry", "babel"})
        self.assertEqual(m._normalize_lang(""), "es")
        self.assertEqual(m._normalize_lang("   "), "es")
        self.assertEqual(m._normalize_lang("es_ES"), "es-es")
