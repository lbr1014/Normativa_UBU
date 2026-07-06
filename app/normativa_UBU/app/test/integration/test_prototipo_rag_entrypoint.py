"""
Autora: Lydia Blanco Ruiz
Prueba de integración del bloque principal (if __name__ == "__main__":) de PrototipoRAG. Su objetivo es verificar que el punto
de entrada del motor RAG puede ejecutarse correctamente en modo de pruebas utilizando el archivo real del sistema, 
evitando las sustituciones realizadas por el entorno de testing. 
La prueba valida la correcta inicialización y ejecución del flujo principal del módulo cuando se lanza como script independiente.
"""

import os
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class PrototipoRAGMainGuardIntegrationTest(unittest.TestCase):
    def test_main_guard_executes_cli_main_in_testing_mode(self):
        """
        Verifica que la ejecución del bloque principal de PrototipoRAG.py se realiza correctamente en modo de pruebas, 
        utilizando el archivo real del módulo y evitando las implementaciones simuladas instaladas por el entorno de testing.
        """
        module_key = "app.main.code.services.rag.PrototipoRAG"
        old = sys.modules.pop(module_key, None)
        try:
            script = Path("app/main/code/services/rag/PrototipoRAG.py").resolve()
            with patch.dict(os.environ, {"PYTHIA_TESTING": "1"}, clear=False):
                runpy.run_path(str(script), run_name="__main__")
        finally:
            if old is not None:
                sys.modules[module_key] = old
