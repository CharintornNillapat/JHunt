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

from src.extractor.gemini_client import (
    BaseGeminiService,
    DailyQuotaExhaustedError,
    is_daily_quota_exhausted,
    is_transient_error,
    calculate_backoff_sleep,
    FALLBACK_MODEL,
    MAX_RETRIES,
    INITIAL_BACKOFF,
)
from src.extractor.schemas import ProjectIdeaSpec

logger = logging.getLogger(__name__)

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


class IdeationEngine(BaseGeminiService):
    """
    Generates structured enterprise portfolio project blueprints matching
    market co-occurrence clusters using Gemini API.
    """


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

        try:
            spec = self._generate(user_prompt, config, ProjectIdeaSpec)
        except DailyQuotaExhaustedError:
            spec = None
        if spec is None:
            logger.warning("[IdeationEngine] Gemini unavailable; using curated archetype spec.")
            return self._build_fallback_spec(target_role, tech_stack, domain_hint)
        spec.target_tech_stack = sorted(set(spec.target_tech_stack + tech_stack))
        return spec

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
