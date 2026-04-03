from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import re
from typing import Iterable, Optional
import unicodedata
from zoneinfo import ZoneInfo

from werkzeug.utils import secure_filename

from .chunk import Chunk
from .consultaChunk import ConsultaChunk
from .embedding import Embedding
from .extensions import db

ALLOWED_EXT = {".pdf"}
MADRID_TZ = ZoneInfo("Europe/Madrid")


class JobCancelledError(RuntimeError):
    pass


class Documento(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False, index=True)
    path = db.Column(db.String(500), unique=True, nullable=False)
    markdown_path = db.Column(db.String(500), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    modified_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    markdown_updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    chunks = db.Column(db.Integer, nullable=False, default=0)
    hash = db.Column(db.String(100), nullable=False, index=True)
    markdown_source_hash = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(25), nullable=False, default="cargado", index=True)
    markdown_content = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    numero_expediente = db.Column(db.String(255), nullable=True, index=True)
    tipo_documento = db.Column(db.String(30), nullable=True, index=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.modified_at:
            self.modified_at = datetime.now(MADRID_TZ)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return normalized.lower().strip()


def infer_document_metadata_from_filename(filename: str) -> tuple[str | None, str | None]:
    stem = Path(filename or "").stem
    if "__" not in stem:
        return None, None

    expediente_part, doc_part = stem.split("__", 1)
    expediente = expediente_part.strip() or None

    match = re.match(r"(?P<doc>.+?)_(?P<index>\d+)$", doc_part.strip())
    raw_doc_name = match.group("doc").strip() if match else doc_part.strip()

    normalized_doc_name = _normalize_text(raw_doc_name).replace("_", " ")
    if "clausulas administrativas" in normalized_doc_name or "administrativ" in normalized_doc_name:
        return expediente, "administrativo"
    if "prescripciones tecnicas" in normalized_doc_name or "tecnic" in normalized_doc_name:
        return expediente, "tecnico"

    return expediente, None


class DocumentosService:
    def __init__(
        self,
        docs_dir: Path,
        index_pliegos_dir,
        delete_chunks,
        markdown_dir: Path | None = None,
        markdown_converter=None,
    ):
        self.docs_dir = docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir = markdown_dir or (self.docs_dir / "markdown")
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        self.index_pliegos_dir = index_pliegos_dir
        self.delete_chunks = delete_chunks
        self.markdown_converter = markdown_converter

    def filename(self, filename: str) -> str:
        return secure_filename(filename or "")

    def resolve_pdf_path(self, filename: str) -> Path:
        safe = self.filename(filename)
        if not safe:
            raise ValueError("Nombre de archivo invalido")
        if Path(safe).suffix.lower() not in ALLOWED_EXT:
            raise ValueError("Extension no permitida")
        return self.docs_dir / safe

    def list_documents_paginated(self, page: int, per_page: int):
        return Documento.query.order_by(Documento.modified_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False,
        )

    def markdown_path_for_filename(self, filename: str) -> Path:
        safe = self.filename(filename)
        if not safe:
            raise ValueError("Nombre de archivo invalido")
        return self.markdown_dir / f"{Path(safe).stem}.md"

    def markdown_path_for_doc(self, doc: Documento) -> Path:
        if doc.markdown_path:
            return Path(doc.markdown_path)
        return self.markdown_path_for_filename(doc.nombre)

    def has_markdown(self, doc: Documento) -> bool:
        if doc.markdown_content:
            return True
        if not doc.markdown_path or not doc.markdown_source_hash:
            return False
        md_path = Path(doc.markdown_path)
        return md_path.exists() and doc.markdown_source_hash == doc.hash

    def clear_markdown_metadata(self, doc: Documento) -> None:
        doc.markdown_path = None
        doc.markdown_source_hash = None
        doc.markdown_updated_at = None

    def sync_markdown_metadata_from_disk(self, doc: Documento) -> None:
        md_path = self.markdown_path_for_filename(doc.nombre)
        if not md_path.exists():
            self.clear_markdown_metadata(doc)
            return

        doc.markdown_path = str(md_path)
        doc.markdown_source_hash = doc.hash
        doc.markdown_updated_at = datetime.fromtimestamp(md_path.stat().st_mtime, MADRID_TZ)

    def get_markdown_status_map(self, docs: Iterable[Documento]) -> dict[int, bool]:
        return {doc.id: self.has_markdown(doc) for doc in docs}

    def count_pending_markdown(self, docs: Iterable[Documento] | None = None) -> int:
        if docs is None:
            docs = Documento.query.all()
        return sum(1 for doc in docs if not self.has_markdown(doc))

    def save_uploads(self, files: Iterable) -> None:
        for f in files:
            if not f or not f.filename:
                continue

            nombre = self.filename(f.filename)
            if not nombre.lower().endswith(".pdf"):
                continue

            dest = self.docs_dir / nombre
            f.save(dest)
            self._upsert_from_path(dest, status="cargado")

        db.session.commit()

    def sync_from_folder(self) -> None:
        for p in sorted(self.docs_dir.glob("*.pdf")):
            self._upsert_from_path(p, status=None)
        db.session.commit()
        self.purge_missing_files()

    def purge_missing_files(self) -> int:
        deleted = 0
        for doc in Documento.query.all():
            if Path(doc.path).exists():
                continue

            self.delete_markdown_file(doc)
            try:
                self.delete_chunks(doc.nombre)
            except Exception:
                pass
            self.delete_document_relations(doc)
            db.session.delete(doc)
            deleted += 1

        if deleted:
            db.session.commit()
        return deleted

    def _upsert_from_path(self, p: Path, status: Optional[str]) -> None:
        stat = p.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, MADRID_TZ)
        rel_path = str(p)
        file_hash = sha256_file(p)
        numero_expediente, tipo_documento = infer_document_metadata_from_filename(p.name)

        doc = Documento.query.filter_by(path=rel_path).first()
        if not doc:
            existing_markdown = self._read_markdown_if_exists_by_filename(p.name)
            doc = Documento(
                nombre=p.name,
                path=rel_path,
                markdown_path=None,
                size_bytes=stat.st_size,
                modified_at=mtime,
                markdown_updated_at=None,
                chunks=0,
                hash=file_hash,
                markdown_source_hash=None,
                markdown_content=existing_markdown,
                status=self._status_for_existing_markdown(status or "cargado", existing_markdown),
                error_message=None,
                numero_expediente=numero_expediente,
                tipo_documento=tipo_documento,
            )
            db.session.add(doc)
            self.sync_markdown_metadata_from_disk(doc)
            return

        previous_hash = doc.hash
        hash_changed = previous_hash != file_hash

        doc.nombre = p.name
        doc.size_bytes = stat.st_size
        doc.modified_at = mtime
        doc.hash = file_hash
        doc.numero_expediente = numero_expediente
        doc.tipo_documento = tipo_documento

        if hash_changed:
            doc.markdown_content = None
            self.delete_markdown_file(doc)
        elif not doc.markdown_content:
            doc.markdown_content = self._read_markdown_if_exists(doc)

        if previous_hash != file_hash:
            self.delete_markdown_file(doc)
        elif not self.has_markdown(doc):
            self.sync_markdown_metadata_from_disk(doc)

        if status is not None:
            doc.status = self._status_for_existing_markdown(status, doc.markdown_content)
            doc.error_message = None
        elif doc.markdown_content and doc.status != "indexado":
            doc.status = "con markdown"

    def delete_document(self, doc_id: int) -> None:
        doc = Documento.query.get(doc_id)
        if not doc:
            return

        try:
            self.delete_chunks(doc.nombre)
        except Exception:
            pass

        self.delete_document_relations(doc)

        try:
            pdf_path = Path(doc.path)
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception:
            pass

        self.delete_markdown_file(doc)
        db.session.delete(doc)
        db.session.commit()

    def delete_markdown_file(self, doc: Documento) -> None:
        try:
            candidate_paths: list[Path] = []
            if doc.markdown_path:
                candidate_paths.append(Path(doc.markdown_path))
            if doc.nombre:
                candidate_paths.append(self.markdown_path_for_filename(doc.nombre))

            for md_path in candidate_paths:
                if md_path.exists():
                    md_path.unlink()
        except Exception:
            pass

        doc.markdown_content = None
        self.clear_markdown_metadata(doc)

    def _read_markdown_if_exists_by_filename(self, filename: str) -> str | None:
        md_path = self.markdown_path_for_filename(filename)
        if not md_path.exists():
            return None
        return md_path.read_text(encoding="utf-8")

    def _read_markdown_if_exists(self, doc: Documento) -> str | None:
        return self._read_markdown_if_exists_by_filename(doc.nombre)

    def _status_for_existing_markdown(self, base_status: str, markdown_content: str | None) -> str:
        if markdown_content and base_status != "indexado":
            return "con markdown"
        return base_status

    def persist_markdown_for_document(self, doc: Documento) -> bool:
        markdown_content = self._read_markdown_if_exists(doc)
        if markdown_content is None:
            return False

        doc.markdown_content = markdown_content
        if doc.status != "indexado":
            doc.status = "con markdown"
        doc.error_message = None
        return True

    def delete_document_relations(self, doc: Documento) -> None:
        chunk_ids_subq = db.session.query(Chunk.id).filter(Chunk.document_id == doc.id).subquery()

        ConsultaChunk.query.filter(
            ConsultaChunk.chunk_id.in_(chunk_ids_subq)
        ).delete(synchronize_session=False)
        db.session.commit()

        Embedding.query.filter(
            Embedding.chunk_id.in_(chunk_ids_subq)
        ).delete(synchronize_session=False)
        db.session.commit()

        Chunk.query.filter(Chunk.document_id == doc.id).delete(synchronize_session=False)
        db.session.commit()

    def convert_document_to_markdown(self, doc: Documento, on_page_start=None) -> bool:
        if doc.markdown_content:
            if doc.status != "indexado":
                doc.status = "con markdown"
            doc.error_message = None
            db.session.commit()
            return False

        if self.has_markdown(doc):
            if self.persist_markdown_for_document(doc):
                db.session.commit()
            return False

        if self.markdown_converter is None:
            raise RuntimeError("No hay conversor de Markdown configurado.")

        pdf_path = Path(doc.path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no existe en contenedor: {pdf_path}")

        md_path = self.markdown_converter(pdf_path, self.markdown_dir, on_page_start=on_page_start)
        doc.markdown_path = str(md_path)
        doc.markdown_source_hash = doc.hash
        doc.markdown_updated_at = datetime.now(MADRID_TZ)

        if not self.persist_markdown_for_document(doc):
            raise RuntimeError(f"No se pudo guardar el Markdown generado para {doc.nombre}.")

        db.session.commit()
        return True

    def convert_pending_to_markdown(
        self,
        on_progress=None,
        on_current_doc=None,
        should_cancel=None,
        on_page_start=None,
    ) -> dict[str, int]:
        converted = 0
        failed = 0
        skipped = 0

        docs = Documento.query.order_by(Documento.modified_at.desc()).all()
        pending_docs = []
        changed_existing = False

        for doc in docs:
            if doc.markdown_content:
                if doc.status not in {"indexado", "con markdown"}:
                    doc.status = "con markdown"
                    doc.error_message = None
                    changed_existing = True
                skipped += 1
                continue

            if self.has_markdown(doc):
                if self.persist_markdown_for_document(doc):
                    changed_existing = True
                skipped += 1
                continue

            pending_docs.append(doc)

        if changed_existing:
            db.session.commit()

        total = len(pending_docs)
        if on_progress:
            on_progress(0, total)

        for i, doc in enumerate(pending_docs, start=1):
            if should_cancel and should_cancel():
                raise JobCancelledError("Conversión a Markdown cancelada por el usuario.")

            if on_current_doc:
                on_current_doc(doc.nombre)

            page_callback = None
            if on_page_start is not None:
                def page_callback(page: int, total_pages: int, doc_index=i, total_docs=total):
                    on_page_start(doc_index, total_docs, page, total_pages)

            try:
                if self.convert_document_to_markdown(doc, on_page_start=page_callback):
                    converted += 1
                else:
                    skipped += 1
            except JobCancelledError:
                raise
            except Exception:
                db.session.rollback()
                failed += 1

            if on_progress:
                on_progress(i, total)

        return {
            "converted": converted,
            "failed": failed,
            "skipped": skipped,
            "total": total,
        }

    def update_vector_db(self, on_progress=None, on_current_doc=None, should_cancel=None) -> dict[str, int]:
        from .rag.PrototipoRAG import index_pdf

        self.purge_missing_files()
        docs = Documento.query.filter(Documento.status.in_(["cargado", "con markdown", "fallido"])).all()

        total = len(docs)
        indexed = 0
        failed = 0
        if on_progress:
            on_progress(0, total)

        for i, doc in enumerate(docs, start=1):
            if should_cancel and should_cancel():
                raise JobCancelledError("Actualización cancelada por el usuario.")
            if on_current_doc:
                on_current_doc(doc.nombre)

            try:
                doc.status = "procesado"
                doc.error_message = None
                db.session.commit()

                pdf_path = Path(doc.path)
                if not pdf_path.exists():
                    raise FileNotFoundError(f"PDF no existe en contenedor: {pdf_path}")

                try:
                    self.delete_chunks(doc.nombre)
                except Exception:
                    pass

                chunk_ids_subq = db.session.query(Chunk.id).filter(Chunk.document_id == doc.id).subquery()

                ConsultaChunk.query.filter(
                    ConsultaChunk.chunk_id.in_(chunk_ids_subq)
                ).delete(synchronize_session=False)
                db.session.commit()

                Embedding.query.filter(
                    Embedding.chunk_id.in_(chunk_ids_subq)
                ).delete(synchronize_session=False)
                db.session.commit()

                Chunk.query.filter(Chunk.document_id == doc.id).delete(synchronize_session=False)
                db.session.commit()

                vector_docs = index_pdf(
                    pdf_path,
                    document_id=doc.id,
                    numero_expediente=doc.numero_expediente,
                    tipo_documento=doc.tipo_documento,
                )
                if not vector_docs:
                    raise RuntimeError("index_pdf devolvió 0 chunks (PDF sin texto o ruta inválida)")

                update_sql(doc, vector_docs)
                db.session.commit()

                doc.chunks = len(vector_docs)
                doc.status = "indexado"
                db.session.commit()
                indexed += 1
                if on_progress:
                    on_progress(i, total)

            except Exception as ex:
                db.session.rollback()
                doc.status = "fallido"
                doc.error_message = str(ex)
                db.session.commit()
                failed += 1

        return {"total": total, "indexed": indexed, "failed": failed}


def update_sql(doc, vector_docs) -> None:
    from .chunk import Chunk
    from .embedding import Embedding
    from .extensions import db
    from .rag.PrototipoRAG import embedding_model

    for vd in vector_docs:
        qid = str(vd.id)
        meta = vd.metadata or {}
        seg = int(meta.get("segment_index", -1))
        sha = (meta.get("sha256") or meta.get("doc_sha256") or "").strip()
        numero_expediente = meta.get("numero_expediente")
        tipo_documento = meta.get("tipo_documento")

        if seg < 0 or not sha:
            continue

        c = Chunk.query.filter_by(document_id=doc.id, doc_sha256=sha, segment_index=seg).first()
        if c is None:
            c = Chunk(
                document_id=doc.id,
                qdrant_point_id=qid,
                segment_index=seg,
                doc_sha256=sha,
                n_chars=len(vd.content or ""),
                n_tokens=None,
                numero_expediente=numero_expediente,
                tipo_documento=tipo_documento,
            )
            db.session.add(c)
            db.session.flush()
        else:
            c.qdrant_point_id = qid
            c.n_chars = len(vd.content or "")
            c.numero_expediente = numero_expediente
            c.tipo_documento = tipo_documento

        exists = Embedding.query.filter_by(chunk_id=c.id, model_id=embedding_model.model_id).first()
        if not exists:
            e = Embedding(
                chunk_id=c.id,
                model_id=embedding_model.model_id,
                embedding_size=embedding_model.embedding_size,
                distance="cosine",
            )
            db.session.add(e)
