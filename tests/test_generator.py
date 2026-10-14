# tests/test_generator.py
"""
Unit tests for the portfolio ideation engine, markdown rendering,
and file exporting layer.
Verifies prompt synthesis, schema validation, frontmatter generation,
filesystem writing, database registration, and fallback deduplication.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.extractor.schemas import FailureMode, ProjectIdeaSpec
from src.generator.ideation_engine import FALLBACK_TITLES, IdeationEngine
from src.generator.markdown_exporter import MarkdownExporter, _slugify
from src.generator import generate_and_export_role_blueprint
from src.storage.db import DatabaseManager


def make_spec(**overrides) -> ProjectIdeaSpec:
    fields = dict(
        title="Real-Time PromptPay Webhook & Settlement Gateway",
        domain_industry="FinTech & Digital Payments (Thailand)",
        core_problem="Credit each PromptPay payment exactly once despite retried webhooks.",
        target_tech_stack=["Python", "FastAPI", "PostgreSQL", "Docker"],
        system_boundary="One FastAPI service and one PostgreSQL database.",
        walking_skeleton=[
            "POST /webhooks/promptpay stores the event",
            "Idempotent webhook signature verification",
        ],
        contracts="`POST /webhooks/promptpay` returns 200 `{status}`.",
        database_schema="`ledger_entries(event_id UNIQUE, amount_satang)`",
        failure_modes=[FailureMode(failure="Duplicate delivery", recovery="ON CONFLICT DO NOTHING")],
        acceptance_tests=["pytest: 100 duplicate deliveries yield exactly 1 ledger row"],
        out_of_scope=["Refunds"],
        difficulty="Intermediate",
    )
    fields.update(overrides)
    return ProjectIdeaSpec(**fields)


class TestMarkdownExporterAndTemplate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jhunt_gen_test_")
        self.export_dir = Path(self.temp_dir) / "exported_ideas"
        self.db_path = Path(self.temp_dir) / "test_market.db"
        self.db = DatabaseManager(db_path=self.db_path)
        self.exporter = MarkdownExporter(export_dir=self.export_dir, db=self.db)
        self.sample_spec = make_spec()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_slugify_utility(self):
        self.assertEqual(_slugify("Backend Engineer"), "backend-engineer")
        self.assertEqual(_slugify("AI / ML Engineer"), "ai-ml-engineer")
        self.assertEqual(_slugify('Dangerous: / Path *? "Name"'), "dangerous-path-name")

    def test_render_spec_structure(self):
        rendered = self.exporter.render_spec(
            spec=self.sample_spec,
            target_role="Backend Engineer",
            generated_date="2026-10-10",
        )

        # YAML Frontmatter assertions
        self.assertTrue(rendered.startswith("---"))
        self.assertIn('title: "Real-Time PromptPay Webhook & Settlement Gateway"', rendered)
        self.assertIn('role: "Backend Engineer"', rendered)
        self.assertIn('difficulty: "Intermediate"', rendered)
        self.assertIn('domain_industry: "FinTech & Digital Payments (Thailand)"', rendered)
        self.assertIn('provenance: "llm"', rendered)
        self.assertIn('- "FastAPI"', rendered)
        self.assertIn("- portfolio-project", rendered)

        # Markdown body: buildable sections, rendered from the spec only
        self.assertIn("# Real-Time PromptPay Webhook & Settlement Gateway", rendered)
        self.assertIn("> **Provenance:** Gemini 3.8 Flash (LLM)", rendered)

        # Test curated fallback rendering
        fallback_spec = make_spec(title="Idempotent PromptPay Webhook Processor")
        rendered_fallback = self.exporter.render_spec(
            spec=fallback_spec,
            target_role="Backend Engineer",
            generated_date="2026-10-10",
        )
        self.assertIn('provenance: "fallback"', rendered_fallback)
        self.assertIn("> **Provenance:** Curated Archetype (Fallback)", rendered_fallback)
        for heading in (
            "## Core Problem",
            "## System Boundary",
            "## Walking Skeleton",
            "## Contracts",
            "## Data Model",
            "## Failure Modes & Recovery",
            "## Acceptance Tests",
            "## Out of Scope",
        ):
            self.assertIn(heading, rendered)
        self.assertIn("1. POST /webhooks/promptpay stores the event", rendered)
        self.assertIn("- **Duplicate delivery.** ON CONFLICT DO NOTHING", rendered)
        self.assertIn("- [ ] pytest: 100 duplicate deliveries yield exactly 1 ledger row", rendered)
        self.assertNotIn("Complete implementation of", rendered)

    def test_acceptance_tests_and_verification_alias_parity(self):
        spec1 = ProjectIdeaSpec(
            title="Spec 1",
            domain_industry="FinTech",
            core_problem="Problem 1",
            system_boundary="Boundary 1",
            contracts="Contracts 1",
            database_schema="Schema 1",
            acceptance_tests=["pytest: check 1"],
        )
        self.assertEqual(spec1.acceptance_tests, ["pytest: check 1"])
        self.assertEqual(spec1.verification, ["pytest: check 1"])

        spec2 = ProjectIdeaSpec(
            title="Spec 2",
            domain_industry="FinTech",
            core_problem="Problem 2",
            system_boundary="Boundary 2",
            contracts="Contracts 2",
            database_schema="Schema 2",
            verification=["pytest: check 2"],
        )
        self.assertEqual(spec2.acceptance_tests, ["pytest: check 2"])
        self.assertEqual(spec2.verification, ["pytest: check 2"])

        spec1.verification = ["pytest: updated check"]
        self.assertEqual(spec1.acceptance_tests, ["pytest: updated check"])

    def test_frontmatter_survives_quotes_in_llm_output(self):
        rendered = self.exporter.render_spec(
            spec=make_spec(title='Ledger "Exactly-Once": Engine'),
            target_role="Backend Engineer",
            generated_date="2026-10-10",
        )
        self.assertIn('title: "Ledger \\"Exactly-Once\\": Engine"', rendered)

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
        self.assertIn("PromptPay Webhook", exported_path.read_text(encoding="utf-8"))

        # Verify record in SQLite database (same columns as Turso)
        records = self.db.get_generated_projects(limit=10)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], self.sample_spec.title)
        self.assertEqual(records[0]["role"], "Backend Engineer")
        self.assertEqual(records[0]["domain"], self.sample_spec.domain_industry)
        self.assertEqual(records[0]["difficulty"], "Intermediate")
        self.assertEqual(records[0]["provenance"], "llm")
        self.assertIn("## Core Problem", records[0]["spec_markdown"])

        # Verify fallback export records provenance as 'fallback'
        fallback_spec = make_spec(title="Idempotent PromptPay Webhook Processor")
        self.exporter.export(
            spec=fallback_spec,
            target_role="Backend Engineer",
            custom_date="2026-10-10",
        )
        all_records = {r["title"]: r for r in self.db.get_generated_projects(limit=10)}
        self.assertEqual(all_records["Idempotent PromptPay Webhook Processor"]["provenance"], "fallback")

    def test_export_skips_already_saved_spec_when_asked(self):
        first = self.exporter.export(spec=self.sample_spec, target_role="Backend Engineer", skip_if_saved=True)
        second = self.exporter.export(spec=self.sample_spec, target_role="Backend Engineer", skip_if_saved=True)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(self.db.get_generated_projects()), 1)

    def test_export_checks_turso_before_saving_fallback(self):
        turso = MagicMock()
        turso.is_available = True
        turso.has_blueprint.return_value = True
        exporter = MarkdownExporter(export_dir=self.export_dir, db=self.db, turso=turso)

        result = exporter.export(spec=self.sample_spec, target_role="Backend Engineer", skip_if_saved=True)

        self.assertIsNone(result)
        turso.sync_blueprint.assert_not_called()

    def test_render_spec_strips_double_periods_in_failure_modes(self):
        spec = make_spec(
            failure_modes=[
                FailureMode(
                    failure="The provider delivers the same event twice.",
                    recovery="Return 200 duplicate.",
                ),
                FailureMode(
                    failure="Database connection timed out",
                    recovery="Retry with exponential backoff.",
                ),
            ]
        )
        rendered = self.exporter.render_spec(
            spec=spec,
            target_role="Backend Engineer",
            generated_date="2026-10-10",
        )
        self.assertIn("- **The provider delivers the same event twice.** Return 200 duplicate.", rendered)
        self.assertNotIn("twice..**", rendered)
        self.assertIn("- **Database connection timed out.** Retry with exponential backoff.", rendered)

    def test_render_spec_deduplicates_step_prefixes_in_walking_skeleton(self):
        spec = make_spec(
            walking_skeleton=[
                "Step 1: POST /webhooks/promptpay stores raw event",
                "2. Verify HMAC signature before database touch",
                "3. Step 3: Write ledger entry in same transaction",
                "Deploy thin slice locally",
            ]
        )
        rendered = self.exporter.render_spec(
            spec=spec,
            target_role="Backend Engineer",
            generated_date="2026-10-10",
        )
        self.assertIn("1. POST /webhooks/promptpay stores raw event", rendered)
        self.assertNotIn("1. Step 1:", rendered)
        self.assertIn("2. Verify HMAC signature before database touch", rendered)
        self.assertNotIn("2. 2.", rendered)
        self.assertIn("3. Write ledger entry in same transaction", rendered)
        self.assertNotIn("3. Step 3:", rendered)
        self.assertIn("4. Deploy thin slice locally", rendered)


class TestIdeationEngine(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.engine = IdeationEngine(
            api_key="mock-api-key",
            model="gemini-3.8-flash",
            rate_limit_delay=0.0,
            client=self.mock_client,
        )

    def test_generate_project_spec_success_parsed(self):
        expected_spec = make_spec(
            title="Flash-Sale Inventory Reservation Engine",
            target_tech_stack=["Go", "Redis", "PostgreSQL"],
        )
        mock_resp = MagicMock()
        mock_resp.parsed = expected_spec
        self.mock_client.models.generate_content.return_value = mock_resp

        result = self.engine.generate_project_spec(
            target_role="Backend Engineer",
            tech_stack=["Go", "PostgreSQL", "Redis"],
        )
        self.assertEqual(result.title, "Flash-Sale Inventory Reservation Engine")
        self.assertFalse(IdeationEngine.is_fallback(result))

    def test_model_chosen_stack_is_not_re_merged_with_market_stack(self):
        mock_resp = MagicMock()
        mock_resp.parsed = make_spec(target_tech_stack=["Go", "PostgreSQL"])
        self.mock_client.models.generate_content.return_value = mock_resp

        result = self.engine.generate_project_spec(
            target_role="Backend Engineer",
            tech_stack=["Go", "PostgreSQL", "Kafka", "Kubernetes", "Redis"],
        )
        self.assertEqual(result.target_tech_stack, ["Go", "PostgreSQL"])

    def test_generate_project_spec_success_json_text(self):
        mock_resp = MagicMock()
        mock_resp.parsed = None
        mock_resp.text = make_spec(title="Telemetry Ingestion with Dead Letters").model_dump_json()
        self.mock_client.models.generate_content.return_value = mock_resp

        result = self.engine.generate_project_spec(
            target_role="Data Engineer / Data Analyst",
            tech_stack=["Python", "PostgreSQL"],
        )
        self.assertEqual(result.title, "Telemetry Ingestion with Dead Letters")
        self.assertEqual(result.failure_modes[0].failure, "Duplicate delivery")

    def test_generate_project_spec_retry_on_transient_error(self):
        mock_resp = MagicMock()
        mock_resp.parsed = make_spec(title="ID Document OCR Queue")
        self.mock_client.models.generate_content.side_effect = [
            Exception("429 RESOURCE_EXHAUSTED"),
            mock_resp,
        ]

        with patch("time.sleep"):
            result = self.engine.generate_project_spec(
                target_role="AI / ML Engineer",
                tech_stack=["Python", "PyTorch", "FastAPI"],
            )

        self.assertEqual(result.title, "ID Document OCR Queue")
        self.assertEqual(self.mock_client.models.generate_content.call_count, 2)

    def test_daily_quota_returns_fallback_without_retry(self):
        self.mock_client.models.generate_content.side_effect = Exception(
            "429 Quota exceeded for quota metric 'GenerateRequestsPerDayPerProjectPerModel'"
        )

        result = self.engine.generate_project_spec(target_role="Backend Engineer", tech_stack=["Python"])

        self.assertTrue(IdeationEngine.is_fallback(result))
        self.assertEqual(self.mock_client.models.generate_content.call_count, 1)

    def test_fallback_spec_generation(self):
        # Offline engine with no client
        offline_engine = IdeationEngine(client=None)

        spec_backend = offline_engine.generate_project_spec(
            target_role="Backend Engineer",
            tech_stack=["Python", "FastAPI", "PostgreSQL"],
        )
        self.assertIn("PromptPay", spec_backend.title)
        self.assertTrue(IdeationEngine.is_fallback(spec_backend))

        spec_data = offline_engine.generate_project_spec(
            target_role="Data Engineer / Data Analyst",
            tech_stack=["Python", "Spark", "Airflow"],
        )
        self.assertIn("Telemetry", spec_data.title)

    def test_fallback_specs_are_scoped_and_claim_no_metrics(self):
        offline_engine = IdeationEngine(client=None)
        banned = re.compile(r"\bp\d{2}\b|\d+\s*ms\b|/sec\b|\bFPS\b|cardholder|CVV", re.IGNORECASE)

        for role in ("Backend Engineer", "Data Engineer / Data Analyst", "Frontend Engineer"):
            spec = offline_engine.generate_project_spec(target_role=role, tech_stack=[])
            text = spec.model_dump_json()
            self.assertIsNone(banned.search(text), f"{role}: {banned.search(text)}")
            self.assertTrue(spec.walking_skeleton and spec.failure_modes and spec.verification)
            self.assertIn(spec.title, FALLBACK_TITLES)

    def test_ideation_system_instruction_contains_architecture_guardrails(self):
        from src.generator.ideation_engine import IDEATION_SYSTEM_INSTRUCTION
        # Webhook status codes: 5xx / 409, never 422
        self.assertIn("422", IDEATION_SYSTEM_INSTRUCTION)
        self.assertTrue(
            "5xx" in IDEATION_SYSTEM_INSTRUCTION or "503" in IDEATION_SYSTEM_INSTRUCTION
        )
        self.assertIn("409", IDEATION_SYSTEM_INSTRUCTION)
        # Autonomous / independent transactions for status updates
        self.assertTrue(
            "autonomous" in IDEATION_SYSTEM_INSTRUCTION.lower()
            or "independent transaction" in IDEATION_SYSTEM_INSTRUCTION.lower()
        )
        # Concurrency & invariants: asyncio.gather, forbid pytest-xdist
        self.assertIn("asyncio.gather", IDEATION_SYSTEM_INSTRUCTION)
        self.assertIn("pytest-xdist", IDEATION_SYSTEM_INSTRUCTION)
        self.assertTrue(
            "interleaving" in IDEATION_SYSTEM_INSTRUCTION.lower()
        )
        # Tech stack versions
        self.assertTrue(
            "version" in IDEATION_SYSTEM_INSTRUCTION.lower()
        )

    def test_generate_project_spec_strips_stack_versions(self):
        mock_spec = make_spec(
            target_tech_stack=["Python 3.12", "PostgreSQL 16", "FastAPI v0.110.0", "Docker"]
        )
        mock_resp = MagicMock()
        mock_resp.parsed = mock_spec
        self.mock_client.models.generate_content.return_value = mock_resp

        result = self.engine.generate_project_spec(
            target_role="Backend Engineer",
            tech_stack=["Python", "FastAPI", "PostgreSQL"],
        )
        self.assertEqual(
            result.target_tech_stack,
            ["Python", "PostgreSQL", "FastAPI", "Docker"]
        )


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
