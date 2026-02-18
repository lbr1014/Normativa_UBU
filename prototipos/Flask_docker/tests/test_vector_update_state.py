from datetime import datetime
from zoneinfo import ZoneInfo

from tests.__init__ import BaseTestCase
from app.extensions import db
from app.vector_update_state import VectorUpdateState

class VectorUpdateStateModelTest(BaseTestCase):
    def test_con_created_at(self):
        job = VectorUpdateState()
        db.session.add(job)
        db.session.commit()

        saved = VectorUpdateState.query.get(job.id)
        self.assertIsNotNone(saved)
        self.assertIsNotNone(saved.created_at)
        
    def test_sin_created_at(self):
        fijo = datetime(2020, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))

        job = VectorUpdateState(created_at=fijo)
        db.session.add(job)
        db.session.commit()

        saved = VectorUpdateState.query.get(job.id)
        self.assertEqual(saved.created_at.replace(tzinfo=None), fijo.replace(tzinfo=None))

    def test_defaults(self):
        job = VectorUpdateState()
        db.session.add(job)
        db.session.commit()

        saved = VectorUpdateState.query.get(job.id)
        self.assertEqual(saved.status, "queued")
        self.assertEqual(saved.progress, 0)
        
    def test_campos_obligatorios(self):
        job = VectorUpdateState(
            current_doc=None,
            error=None,
            started_at=None,
            finished_at=None,
        )
        db.session.add(job)
        db.session.commit()

        saved = VectorUpdateState.query.get(job.id)
        self.assertIsNone(saved.current_doc)
        self.assertIsNone(saved.error)
        self.assertIsNone(saved.started_at)
        self.assertIsNone(saved.finished_at)

    def test_update(self):
        job = VectorUpdateState()
        db.session.add(job)
        db.session.commit()

        start = datetime.now(ZoneInfo("Europe/Madrid"))
        finish = datetime.now(ZoneInfo("Europe/Madrid"))

        job.status = "running"
        job.progress = 50
        job.current_doc = "pliego1.pdf"
        job.started_at = start
        db.session.commit()

        saved = VectorUpdateState.query.get(job.id)
        self.assertEqual(saved.status, "running")
        self.assertEqual(saved.progress, 50)
        self.assertEqual(saved.current_doc, "pliego1.pdf")
        self.assertIsNotNone(saved.started_at)

        saved.status = "done"
        saved.progress = 100
        saved.finished_at = finish
        db.session.commit()

        saved2 = VectorUpdateState.query.get(job.id)
        self.assertEqual(saved2.status, "done")
        self.assertEqual(saved2.progress, 100)
        self.assertIsNotNone(saved2.finished_at)
