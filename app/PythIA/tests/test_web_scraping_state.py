from datetime import datetime
from zoneinfo import ZoneInfo

from tests.__init__ import BaseTestCase
from app.extensions import db
from app.web_scraping_state import WebScrapingSate


class WebScrapingStateModelTest(BaseTestCase):
    def test_con_created_at(self):
        job = WebScrapingSate()
        db.session.add(job)
        db.session.commit()

        saved = WebScrapingSate.query.get(job.id)
        self.assertIsNotNone(saved)
        self.assertIsNotNone(saved.created_at)

    def test_sin_created_at(self):
        fijo = datetime(2020, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))

        job = WebScrapingSate(created_at=fijo)
        db.session.add(job)
        db.session.commit()

        saved = WebScrapingSate.query.get(job.id)
        self.assertEqual(saved.created_at.replace(tzinfo=None), fijo.replace(tzinfo=None))

    def test_defaults(self):
        job = WebScrapingSate()
        db.session.add(job)
        db.session.commit()

        saved = WebScrapingSate.query.get(job.id)
        self.assertEqual(saved.status, "queued")
        self.assertEqual(saved.progress, 0)

    def test_campos_obligatorios(self):
        job = WebScrapingSate(
            message=None,
            error=None,
            started_at=None,
            finished_at=None,
        )
        db.session.add(job)
        db.session.commit()

        saved = WebScrapingSate.query.get(job.id)
        self.assertIsNone(saved.message)
        self.assertIsNone(saved.error)
        self.assertIsNone(saved.started_at)
        self.assertIsNone(saved.finished_at)

    def test_update(self):
        job = WebScrapingSate()
        db.session.add(job)
        db.session.commit()

        start = datetime.now(ZoneInfo("Europe/Madrid"))
        finish = datetime.now(ZoneInfo("Europe/Madrid"))

        job.status = "running"
        job.progress = 10
        job.message = "Iniciando scraping…"
        job.started_at = start
        db.session.commit()

        saved = WebScrapingSate.query.get(job.id)
        self.assertEqual(saved.status, "running")
        self.assertEqual(saved.progress, 10)
        self.assertEqual(saved.message, "Iniciando scraping…")
        self.assertIsNotNone(saved.started_at)

        saved.status = "done"
        saved.progress = 100
        saved.message = "Scraping terminado."
        saved.finished_at = finish
        db.session.commit()

        saved2 = WebScrapingSate.query.get(job.id)
        self.assertEqual(saved2.status, "done")
        self.assertEqual(saved2.progress, 100)
        self.assertEqual(saved2.message, "Scraping terminado.")
        self.assertIsNotNone(saved2.finished_at)

    def test_failed(self):
        job = WebScrapingSate(status="failed", progress=0, message="Falló el scraping.", error="boom")
        db.session.add(job)
        db.session.commit()

        saved = WebScrapingSate.query.get(job.id)
        self.assertEqual(saved.status, "failed")
        self.assertEqual(saved.message, "Falló el scraping.")
        self.assertEqual(saved.error, "boom")
