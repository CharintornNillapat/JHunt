# tests/test_generator.py
"""
Unit tests for the portfolio ideation engine, Jinja2 markdown templating,
and file exporting layer.
Verifies prompt synthesis, schema validation, frontmatter generation,
filesystem writing, and database registration.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.extractor.schemas import ProjectIdeaSpec
from src.generator.ideation_engine import IdeationEngine
from src.generator.markdown_exporter import MarkdownExporter, _slugify
from src.generator import generate_and_export_role_blueprint
from src.storage.db import DatabaseManager


class TestMarkdownExporterAndTemplate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jhunt_gen_test_")
        self.export_dir = Path(self.temp_dir) / "exported_ideas"
        self.db_path = Path(self.temp_dir) / "test_market.db"
        self.db = DatabaseManager(db_path=self.db_path)
        self.exporter = MarkdownExporter(export_dir=self.export_dir, db=self.db)

        self.sample_spec = ProjectIdeaSpec(
            title="Real-Time PromptPay Webhook & Settlement Gateway",
            domain_industry="FinTech & Digital Payments (Thailand)",
            target_tech_stack=["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
            architecture_overview="Microservice architecture processing inbound banking webhooks with idempotency keys.",
            core_features=[
                "Idempotent webhook signature verification",
                "Double-entry ledger reconciliation worker",
            ],
            database_schema="PostgreSQL `ledger` table with ACID constraints and unique idempotency keys.",
            engineering_challenges=[
                "Preventing double-spend under concurrent duplicate webhooks",
                "Sub-50ms acknowledgement latency",
            ],
            difficulty="Advanced",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_slugify_utility(self):
        self.assertEqual(_slugify("Backend Engineer"), "backend-engineer")
        self.assertEqual(_slugify("AI / ML Engineer"), "ai-ml-engineer")
        self.assertEqual(_slugify('Dangerous: / Path *? "Name"'), "dangerous-path-name")

    def test_render_spec_jinja2_structure(self):
        rendered = self.exporter.render_spec(
            spec=self.sample_spec,
            target_role="Backend Engineer",
            generated_date="2026-10-10",
        )

        # YAML Frontmatter assertions
        self.assertTrue(rendered.startswith("---"))
        self.assertIn('title: "Real-Time PromptPay Webhook & Settlement Gateway"', rendered)
        self.assertIn('role: "Backend Engineer"', rendered)
        self.assertIn('difficulty: "Advanced"', rendered)
        self.assertIn('domain_industry: "FinTech & Digital Payments (Thailand)"', rendered)
        self.assertIn('- "FastAPI"', rendered)
        self.assertIn("- portfolio-project", rendered)

        # Markdown Body assertions
        self.assertIn("# Real-Time PromptPay Webhook & Settlement Gateway", rendered)
        self.assertIn("## 1. Executive Summary & Business Context", rendered)
        self.assertIn("## 2. System Architecture & Data Flow", rendered)
        self.assertIn("## 3. Core Feature Requirements", rendered)
        self.assertIn("## 4. Database Schema Proposal & Storage Design", rendered)
        self.assertIn("## 5. Key Engineering Challenges (Portfolio Highlights)", rendered)
        self.assertIn("## 6. Recommended Portfolio Deliverables", rendered)
        self.assertIn("Idempotent webhook signature verification", rendered)

    def test_export_writes_file_and_records_in_db(self):
        exported_path = self.exporter.export(
            spec=self.sample_spec,
            target_role="Backend Engineer",
            custom_date="2026-10-10",
        )

        # Verify file on disk
        self.assertTrue(exported_path.exists())
        self.assertTrue(exported_path.is_file())
        self.assertIn("2026-10-10_backend-engineer_real-time-promptpay", exported_path.name)

        with open(exported_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("PromptPay Webhook", content)

        # Verify record in SQLite database
        records = self.db.get_generated_projects(limit=10)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], self.sample_spec.title)
        self.assertEqual(records[0]["role"], "Backend Engineer")
        self.assertEqual(records[0]["file_path"], str(exported_path))


class TestIdeationEngine(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.engine = IdeationEngine(
            api_key="mock-api-key",
            model="gemini-2.0-flash",
            rate_limit_delay=0.0,
            client=self.mock_client,
        )

    def test_generate_project_spec_success_parsed(self):
        expected_spec = ProjectIdeaSpec(
            title="Distributed Flash-Sale Inventory Locking Engine",
            domain_industry="E-Commerce (Thailand)",
            target_tech_stack=["Go", "Redis", "PostgreSQL", "Docker"],
            architecture_overview="High-concurrency ticket locking engine.",
            core_features=["Atomic inventory deduction"],
            database_schema="PostgreSQL tickets table",
            engineering_challenges=["Cache stampede prevention"],
            difficulty="Advanced",
        )

        mock_resp = MagicMock()
        mock_resp.parsed = expected_spec
        self.mock_client.models.generate_content.return_value = mock_resp

        result = self.engine.generate_project_spec(
            target_role="Backend Engineer",
            tech_stack=["Go", "PostgreSQL", "Redis"],
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Distributed Flash-Sale Inventory Locking Engine")
        self.assertIn("Go", result.target_tech_stack)

    def test_generate_project_spec_success_json_text(self):
        json_spec = """{
            "title": "Real-Time Telemetry Ingestion Pipeline",
            "domain_industry": "Logistics & Fleet Telemetry",
            "target_tech_stack": ["Python", "Apache Spark", "Airflow", "Kafka"],
            "architecture_overview": "Streaming fleet ingestion engine",
            "core_features": ["Sub-second courier tracking"],
            "database_schema": "GeoJSON coordinate storage",
            "engineering_challenges": ["Out-of-order packet reconciliation"],
            "difficulty": "Advanced"
        }"""
        mock_resp = MagicMock()
        mock_resp.parsed = None
        mock_resp.text = json_spec
        self.mock_client.models.generate_content.return_value = mock_resp

        result = self.engine.generate_project_spec(
            target_role="Data Engineer / Data Analyst",
            tech_stack=["Python", "Spark", "Airflow"],
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Real-Time Telemetry Ingestion Pipeline")
        self.assertEqual(result.difficulty, "Advanced")

    def test_generate_project_spec_retry_on_transient_error(self):
        expected_spec = ProjectIdeaSpec(
            title="Real-time OCR & ID Document Verification API",
            domain_industry="Digital Banking / e-KYC",
            target_tech_stack=["Python", "PyTorch", "FastAPI", "Docker"],
            architecture_overview="Asynchronous OCR engine.",
            core_features=["National ID extraction"],
            database_schema="Encrypted audit records",
            engineering_challenges=["GPU batch inference latency"],
            difficulty="Advanced",
        )
        mock_resp = MagicMock()
        mock_resp.parsed = expected_spec

        self.mock_client.models.generate_content.side_effect = [
            Exception("429 RESOURCE_EXHAUSTED"),
            mock_resp,
        ]

        with patch("time.sleep"):
            result = self.engine.generate_project_spec(
                target_role="AI / ML Engineer",
                tech_stack=["Python", "PyTorch", "FastAPI"],
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Real-time OCR & ID Document Verification API")
        self.assertEqual(self.mock_client.models.generate_content.call_count, 2)

    def test_fallback_spec_generation(self):
        # Offline engine with no client
        offline_engine = IdeationEngine(client=None)

        spec_backend = offline_engine.generate_project_spec(
            target_role="Backend Engineer",
            tech_stack=["Python", "FastAPI", "PostgreSQL"],
        )
        self.assertIsNotNone(spec_backend)
        self.assertIn("PromptPay", spec_backend.title)

        spec_data = offline_engine.generate_project_spec(
            target_role="Data Engineer / Data Analyst",
            tech_stack=["Python", "Spark", "Airflow"],
        )
        self.assertIsNotNone(spec_data)
        self.assertIn("Telemetry", spec_data.title)


class TestGeneratorOrchestrator(unittest.TestCase):
    def test_generate_and_export_role_blueprint(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_orch_test_")
        try:
            export_dir = Path(temp_dir) / "ideas"
            db_path = Path(temp_dir) / "market.db"
            db = DatabaseManager(db_path=db_path)
            exporter = MarkdownExporter(export_dir=export_dir, db=db)
            engine = IdeationEngine(client=None)  # Use fallback spec

            file_path = generate_and_export_role_blueprint(
                target_role="Backend Engineer",
                tech_stack=["Python", "FastAPI", "PostgreSQL", "Redis"],
                engine=engine,
                exporter=exporter,
            )

            self.assertIsNotNone(file_path)
            self.assertTrue(file_path.exists())
            self.assertIn("backend-engineer", file_path.name)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
