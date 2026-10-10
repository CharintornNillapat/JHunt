# src/generator/ideation_engine.py
"""
Ideation Engine for Enterprise-Grade Portfolio Project Specifications.
Synthesizes trending Thailand tech stacks with industrial business domains
into rigorous, interview-ready engineering specifications.
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from src.extractor.schemas import ProjectIdeaSpec
from src.extractor.llm_extractor import is_daily_quota_exhausted

logger = logging.getLogger(__name__)

_UNSET = object()
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = "gemini-1.5-flash"
DEFAULT_RATE_LIMIT_DELAY = 4.0
MAX_RETRIES = 4
INITIAL_BACKOFF = 2.0

IDEATION_SYSTEM_INSTRUCTION = """You are a Principal Software Systems Architect and Staff Engineering Hiring Manager in Thailand.
Your mission is to design an enterprise-grade, production-scale portfolio project blueprint specifically tailored for engineering candidates interviewing at leading Thailand tech companies (e.g., Agoda, LINE MAN Wongnai, SCB 10X, Bitkub, True Digital, Central Group).

Core Directives:
1. STRICTLY FORBID TOY APPLICATIONS:
   - Never generate trivial To-Do apps, generic blogs, simple note-takers, or basic unauthenticated CRUD.
   - The project must model a complex commercial vertical with concurrency, failure modes, and consistency requirements.
2. THAILAND INDUSTRY CONTEXT:
   - Ground the project in real Thailand business verticals: FinTech & Digital Payments (PromptPay webhook reconciliation, double-entry ledgers), Food Delivery & Logistics (geospatial driver dispatch, route telemetry), E-commerce (flash sale inventory locking, order state machines), or Digital Healthcare (PDPA compliance, encrypted audit trails).
3. NON-TRIVIAL ENGINEERING CHALLENGES:
   - Focus on senior-level interview talking points: idempotency keys, distributed locking with Redis/Redlock, outbox pattern with Kafka/RabbitMQ, database partitioning and indexing, cache stampede prevention, or graceful degradation.
4. ALIGNED TO PROVIDED TECH STACK:
   - Build directly upon the requested tech stack.
"""


class IdeationEngine:
    """
    Generates structured enterprise portfolio project blueprints matching
    market co-occurrence clusters using Gemini API.
    """

    def __init__(
        self,
        api_key: Any = _UNSET,
        model: Optional[str] = None,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        client: Any = _UNSET,
    ):
        if api_key is _UNSET:
            self.api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        else:
            self.api_key = (api_key or "").strip()

        model_name = (model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)).strip()
        self.model = model_name
        self.rate_limit_delay = rate_limit_delay
        self._last_call_time: float = 0.0

        if client is not _UNSET:
            self.client = client
        elif self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def _throttle(self) -> None:
        """Throttles calls to stay well within free tier quotas."""
        if self._last_call_time > 0:
            elapsed = time.monotonic() - self._last_call_time
            sleep_needed = self.rate_limit_delay - elapsed
            if sleep_needed > 0:
                time.sleep(sleep_needed)

    def generate_project_spec(
        self,
        target_role: str,
        tech_stack: List[str],
        domain_hint: Optional[str] = None,
    ) -> Optional[ProjectIdeaSpec]:
        """
        Generates a comprehensive ProjectIdeaSpec for the given role and stack.
        Returns validated ProjectIdeaSpec on success, or fallback/None on error.
        """
        if not self.client:
            logger.warning("[IdeationEngine] No Gemini API client configured; generating rule-based template spec.")
            return self._build_fallback_spec(target_role, tech_stack, domain_hint)

        stack_str = ", ".join(tech_stack)
        domain_clause = f"Focus on domain: '{domain_hint}'." if domain_hint else "Select an impactful Thailand tech domain."
        user_prompt = f"""Target Role: {target_role}
Market Tech Stack: {stack_str}
{domain_clause}

Design an enterprise-grade portfolio project spec that demonstrates deep technical competence with this stack.
Return structured JSON matching the ProjectIdeaSpec schema."""

        config = types.GenerateContentConfig(
            system_instruction=IDEATION_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ProjectIdeaSpec,
            temperature=0.2,
        )

        backoff = INITIAL_BACKOFF
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                self._last_call_time = time.monotonic()
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config,
                )

                spec: Optional[ProjectIdeaSpec] = None
                if hasattr(response, "parsed") and isinstance(response.parsed, ProjectIdeaSpec):
                    spec = response.parsed
                elif hasattr(response, "text") and response.text:
                    spec = ProjectIdeaSpec.model_validate_json(response.text)

                if spec is not None:
                    # Ensure tech stack includes requested stack elements
                    merged_stack = sorted(set(spec.target_tech_stack + tech_stack))
                    spec.target_tech_stack = merged_stack
                    return spec

                logger.warning(f"[IdeationEngine] Attempt {attempt}: Received empty spec response.")

            except Exception as e:
                err_str = str(e)
                if is_daily_quota_exhausted(err_str):
                    logger.warning(
                        f"[IdeationEngine] Gemini daily quota exhausted ({err_str[:120]}). "
                        "Immediately falling back to curated archetype spec without retrying."
                    )
                    return self._build_fallback_spec(target_role, tech_stack, domain_hint)

                is_rate_limit = (
                    "429" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "rate limit" in err_str.lower()
                    or "quota" in err_str.lower()
                )
                is_transient = is_rate_limit or "503" in err_str or "timeout" in err_str.lower()

                if is_transient and attempt < MAX_RETRIES:
                    jitter = random.uniform(0.2, 1.0)
                    sleep_time = backoff + jitter
                    logger.warning(
                        f"[IdeationEngine] Transient error ({err_str[:120]}). Retrying in {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time)
                    backoff *= 2.0
                    continue

                logger.error(f"[IdeationEngine] Generation error (attempt {attempt}): {e}")
                if not is_transient:
                    break

        logger.warning("[IdeationEngine] API calls failed; falling back to curated archetype spec.")
        return self._build_fallback_spec(target_role, tech_stack, domain_hint)

    def _build_fallback_spec(
        self,
        target_role: str,
        tech_stack: List[str],
        domain_hint: Optional[str] = None,
    ) -> ProjectIdeaSpec:
        """
        Deterministic, production-grade fallback spec for offline usage or API outages.
        """
        role_lower = target_role.lower()

        if "data" in role_lower:
            return ProjectIdeaSpec(
                title="Real-Time E-Commerce Clickstream & Delivery Telemetry Pipeline",
                domain_industry=domain_hint or "E-Commerce Logistics & Analytics (Thailand)",
                target_tech_stack=tech_stack or ["Python", "Apache Spark", "Airflow", "PostgreSQL", "Kafka"],
                architecture_overview="End-to-end event streaming architecture with dual ingestion paths: sub-second stream processing for real-time driver ETA estimation and hourly micro-batch aggregation for warehouse reporting.",
                core_features=[
                    "High-throughput GPS telemetry ingestion (10k events/sec) with Schema Registry validation",
                    "Sessionization and real-time customer intent scoring using sliding time windows",
                    "Automated daily partition backfilling and deduplication with idempotent dbt transformations",
                    "Data quality assertions and alerting using Great Expectations",
                ],
                database_schema="Star schema on PostgreSQL/BigQuery: FactDeliveryEvents (driver_id, order_id, geo_point, event_timestamp), DimMerchant, DimRoute with BRIN indexing on temporal columns.",
                engineering_challenges=[
                    "Out-of-order event handling with watermarking and dead-letter queues",
                    "Idempotent sink writes preventing duplicate merchant billings on network retries",
                    "Backpressure regulation during 11.11 shopping festival volume spikes",
                ],
                difficulty="Advanced",
            )
        elif "frontend" in role_lower:
            return ProjectIdeaSpec(
                title="High-Performance Real-Time Fleet Dispatch Dashboard",
                domain_industry=domain_hint or "On-Demand Delivery & Logistics Operations",
                target_tech_stack=tech_stack or ["TypeScript", "React", "Next.js", "Tailwind CSS"],
                architecture_overview="Mission-control web interface rendering live vehicle telemetry and order status over WebSockets with virtualized map canvases and optimistic UI updates.",
                core_features=[
                    "Real-time geospatial fleet rendering supporting 2,000+ active courier nodes at 60 FPS",
                    "Optimistic order dispatch action queue with automatic rollback on network failure",
                    "Role-based operational views with keyboard-first dispatcher shortcuts",
                    "Offline-first sync engine caching incident reports in IndexedDB",
                ],
                database_schema="Client-side normalized state store with optimistic staging cache synced against REST/WebSocket endpoints.",
                engineering_challenges=[
                    "Canvas vs DOM rendering trade-offs under high-frequency coordinates updates",
                    "WebSocket reconnection backoff and state reconciliation without UI freeze",
                    "Minimizing bundle size and optimizing Core Web Vitals on mobile field devices",
                ],
                difficulty="Intermediate",
            )
        else:
            return ProjectIdeaSpec(
                title="Idempotent Payment Orchestrator & PromptPay Webhook Engine",
                domain_industry=domain_hint or "FinTech & Digital Payment Gateway (Thailand)",
                target_tech_stack=tech_stack or ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
                architecture_overview="Distributed transaction engine handling payment callbacks, PromptPay QR verification, and double-entry ledger reconciliation with strict zero-loss guarantees.",
                core_features=[
                    "Idempotent webhook ingestion verifying digital signatures and payload digests",
                    "Distributed locking mechanism preventing double-spend and concurrent charge race conditions",
                    "Automated settlement reconciliation matching bank settlement files against internal ledger",
                    "Token bucket rate-limiting and circuit breaker pattern on upstream bank integrations",
                ],
                database_schema="PostgreSQL Relational Schema: `payments` (id, order_id, amount_cents, currency, status, idempotency_key UNIQUE), `ledger_entries` (entry_id, account_id, debit, credit, balance_after) with composite index on (merchant_id, created_at).",
                engineering_challenges=[
                    "Zero double-spend enforcement across distributed replicas via atomic Redis locks and DB row-level locking",
                    "Sub-50ms p99 response times on webhook acknowledgments while offloading settlement to async workers",
                    "Compliance with Thailand PDPA data residency and encryption of cardholder credentials",
                ],
                difficulty="Advanced",
            )
