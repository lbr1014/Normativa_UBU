from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.datastructures import FileStorage

from tests.support import BaseAppTestCase

from app.documentos import Documento, DocumentosService, infer_document_metadata_from_filename
from app.extensions import db


class DocumentosUnitTest(BaseAppTestCase):
    def _service(self) -> DocumentosService:
        return DocumentosService(
            self._docs_dir,
            index_pliegos_dir=lambda path: {},
            delete_chunks=MagicMock(),
            markdown_dir=self._docs_dir / "markdown",
            markdown_converter=MagicMock(),
        )

    def test_infer_document_metadata_from_filename(self):
        expediente, tipo = infer_document_metadata_from_filename("EXP-123__Pliego_de_clausulas_administrativas_1.pdf")
        self.assertEqual(expediente, "EXP-123")
        self.assertEqual(tipo, "administrativo")

        expediente, tipo = infer_document_metadata_from_filename("EXP-123__Pliego_de_prescripciones_tecnicas_2.pdf")
        self.assertEqual(expediente, "EXP-123")
        self.assertEqual(tipo, "tecnico")

    def test_save_uploads_persists_only_pdf_files(self):
        service = self._service()
        pdf = FileStorage(stream=BytesIO(b"%PDF-1.4 data"), filename="uno.pdf")
        txt = FileStorage(stream=BytesIO(b"hola"), filename="dos.txt")

        service.save_uploads([pdf, txt])

        docs = Documento.query.all()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].nombre, "uno.pdf")
        self.assertTrue((self._docs_dir / "uno.pdf").exists())

    def test_delete_document_removes_record_and_files(self):
        service = self._service()
        doc = self.create_document(nombre="borrar.pdf")
        markdown_path = Path(service.markdown_path_for_filename(doc.nombre))
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text("contenido", encoding="utf-8")
        doc.markdown_path = str(markdown_path)
        doc.markdown_content = "contenido"
        service.delete_chunks = MagicMock()
        self.create_chunk(document=doc)

        service.delete_document(doc.id)

        self.assertIsNone(db.session.get(Documento, doc.id))
        self.assertFalse(Path(doc.path).exists())
        self.assertFalse(markdown_path.exists())
        service.delete_chunks.assert_called_once_with("borrar.pdf")

    @patch("app.main.routes.qdrant_get_payloads", return_value={"legacy-qid": {"metadata": {"filename": "legacy.pdf"}, "content": "texto"}})
    def test_build_meta_by_consulta_uses_fragmentos_and_legacy_qdrant(self, mock_qdrant):
        from app.main.routes import build_meta_by_consulta

        user = self.create_user()
        consulta_saved = self.create_consulta(
            user,
            fragmentos=[{"ranking": 1, "qdrant_point_id": "saved-qid", "metadata": {"filename": "saved.pdf"}, "chunk": "guardado"}],
        )
        consulta_legacy = self.create_consulta(user, pregunta="legacy")
        chunk = self.create_chunk(qdrant_point_id="legacy-qid")
        self.link_consulta_chunk(consulta_legacy, chunk)

        meta = build_meta_by_consulta([consulta_saved, consulta_legacy])

        self.assertEqual(meta[consulta_saved.id]["metadata"]["filename"], "saved.pdf")
        self.assertEqual(meta[consulta_legacy.id]["metadata"]["filename"], "legacy.pdf")
        mock_qdrant.assert_called_once()
