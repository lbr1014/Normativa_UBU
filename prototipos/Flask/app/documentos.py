from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Dict, Optional
from werkzeug.utils import secure_filename
import hashlib

from .extensions  import db

ALLOWED_EXT = {".pdf"}

class Documento(db.Model):
    __tablename__ = "documents"
     
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False,  index=True)
    path = db.Column(db.String(500), unique=True, nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    modified_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    chunks = db.Column(db.Integer, nullable=False,  default=0)
    hash = db.Column(db.String(100),  nullable=False, index=True)
    status = db.Column(db.String(25), nullable=False,default="cargado", index=True)
    error_message = db.Column(db.Text, nullable=True)
    
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    

class DocumentosService:
    def __init__(
        self,
        docs_dir: Path,
        *,
        index_pliegos_dir,              
        delete_chunks,              
        count_chunks,               
        allowed_ext: Optional[set[str]] = None,
    ):
        self.docs_dir = docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        self.index_pliegos_dir = index_pliegos_dir
        self.delete_chunks = delete_chunks
        self.count_chunks = count_chunks
        self.allowed_ext = allowed_ext or ALLOWED_EXT

    def sanitize_filename(self, filename: str) -> str:
        return secure_filename(filename or "")

    def resolve_pdf_path(self, filename: str) -> Path:
        safe = self.sanitize_filename(filename)
        if not safe:
            raise ValueError("Nombre de archivo inválido")
        if Path(safe).suffix.lower() not in self.allowed_ext:
            raise ValueError("Extensión no permitida")
        return self.docs_dir / safe

    def list_documents(self) -> List[Documento]:
        docs: List[Documento] = []
        for p in sorted(self.docs_dir.glob("*.pdf")):
            stat = p.stat()
            name = p.name
            try:
                chunks = int(self.count_chunks(name))
            except Exception:
                chunks = 0

            docs.append(
                Documento(
                    name=name,
                    size_bytes=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    chunks=chunks,
                )
            )

        docs.sort(key=lambda d: d.modified, reverse=True)
        return docs

    def save_uploads(self, files: Iterable) -> List[Documento]:
        """
        Guarda PDFs subidos y devuelve los docs resultantes (para mostrar/flash si quieres).
        """
        saved: List[Documento] = []

        for f in files:
            safe = self.sanitize_filename(getattr(f, "filename", "") or "")
            if not safe:
                continue
            if Path(safe).suffix.lower() not in self.allowed_ext:
                continue

            dest = self.docs_dir / safe
            f.save(dest)

            stat = dest.stat()
            try:
                chunks = int(self.count_chunks(safe))
            except Exception:
                chunks = 0

            saved.append(
                Documento(
                    name=safe,
                    size_bytes=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    chunks=chunks,
                )
            )

        return saved

    def delete_document(self, filename: str) -> str:
        """
        Borra en Qdrant y después en disco (como tu lógica actual).
        Devuelve el nombre seguro borrado.
        """
        pdf_path = self.resolve_pdf_path(filename)
        safe_name = pdf_path.name

        if not pdf_path.exists():
            raise FileNotFoundError("El archivo no existe")

        self.delete_chunks(safe_name)

        pdf_path.unlink()

        return safe_name

    def update_vector_db(self) -> Dict:
        """
        Re-indexa el directorio completo.
        Devuelve summary + chunk_counts como tu endpoint actual.
        """
        summary = self.index_pliegos_dir(self.docs_dir)

        chunk_counts: Dict[str, int] = {}
        for pdf_path in sorted(self.docs_dir.glob("*.pdf")):
            name = pdf_path.name
            try:
                chunk_counts[name] = int(self.count_chunks(name))
            except Exception:
                chunk_counts[name] = 0

        return {"summary": summary, "chunk_counts": chunk_counts}
