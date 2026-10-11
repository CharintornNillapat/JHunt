# src/generator/ideation_engine.py
"""
Ideation Engine for portfolio project specifications.
Turns a role's dominant market stack into one tightly scoped, locally verifiable
project spec: one core problem, one service, one datastore.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from google.genai import types

from src.extractor.gemini_client import BaseGeminiService, DailyQuotaExhaustedError
from src.extractor.schemas import FailureMode, ProjectIdeaSpec

logger = logging.getLogger(__name__)

IDEATION_SYSTEM_INSTRUCTION = """You design portfolio projects for software engineers applying to companies in Thailand.
Each project must be buildable and verifiable by one developer on a laptop in two to four weeks.

Depth over breadth:
- Choose ONE core engineering problem and solve it thoroughly. Good examples: crediting a merchant ledger exactly once when PromptPay payment webhooks are retried concurrently; ingesting out-of-order delivery telemetry with a dead-letter table for malformed messages. Every section of the spec must serve that one problem.
- System boundary: exactly one service and one primary datastore, plus at most one cache or queue, and only when the core problem cannot be solved without it. No microservices, no second database, no service mesh, no multi-region setup.
- Ground the problem in a real Thailand business context without widening the scope.
- Use the provided market stack where it fits the core problem. Leave out anything the problem does not need.

Every section must be concrete enough to build from:
- walking_skeleton: ordered steps. Step 1 is a thin end-to-end slice that runs locally (request in, row stored, result readable). Each later step adds one capability.
- contracts: typed request, response and event models (Pydantic or OpenAPI) with status codes.
- database_schema: tables, keys and the constraints that enforce the core invariant.
- failure_modes: concrete failures (duplicate delivery, crash between two writes, dependency down, malformed input) and how the system detects and recovers from each.
- verification: falsifiable checks runnable locally with pytest, Locust or Playwright, stated as counts or invariants (for example "100 duplicate deliveries produce exactly 1 ledger row").
- out_of_scope: the tempting additions you deliberately excluded.

Forbidden:
- Latency percentiles, throughput figures, user counts or uptime numbers as targets or facts.
- Storing or processing card numbers, CVVs or bank credentials. Use tokenized references or PromptPay transaction ids.
- Lists of patterns or tools the core problem does not need.
- Toy CRUD apps (to-do lists, blogs, note takers).
"""

_BACKEND_FALLBACK = ProjectIdeaSpec(
    title="Idempotent PromptPay Webhook Processor",
    domain_industry="FinTech / PromptPay payments (Thailand)",
    core_problem=(
        "A payment provider retries PromptPay confirmation webhooks, sometimes concurrently. "
        "Each confirmed payment must credit the merchant ledger exactly once."
    ),
    target_tech_stack=["Python", "FastAPI", "PostgreSQL", "Docker"],
    system_boundary=(
        "One FastAPI service and one PostgreSQL database. In scope: webhook intake, signature check, "
        "idempotent ledger write, merchant balance read. Out of scope: QR generation, refunds, settlement files, any UI."
    ),
    walking_skeleton=[
        "POST /webhooks/promptpay stores the raw event; GET /merchants/{id}/balance reads it back; runs with docker compose up",
        "Verify the HMAC signature and reject unsigned or tampered payloads before touching the database",
        "Write the ledger entry in the same transaction as the event row, with a UNIQUE constraint on event_id",
        "Make concurrent duplicate deliveries of one event produce a single ledger entry",
        "Add a startup sweep that re-processes stored events whose ledger write never happened",
    ],
    contracts=(
        "Pydantic `PromptPayWebhook(event_id: str, transaction_ref: str, amount_satang: int, merchant_id: str, paid_at: datetime)`. "
        "`POST /webhooks/promptpay` returns 200 `{status: 'accepted' | 'duplicate'}`, 401 on a bad signature, 422 on a schema error, "
        "503 when the database is unavailable. `GET /merchants/{merchant_id}/balance` returns `{merchant_id, balance_satang}`."
    ),
    database_schema=(
        "`webhook_events(event_id TEXT PRIMARY KEY, payload JSONB, received_at, processed_at NULL)`; "
        "`ledger_entries(id BIGSERIAL, event_id TEXT UNIQUE REFERENCES webhook_events, merchant_id TEXT, "
        "amount_satang BIGINT CHECK (amount_satang > 0), created_at)`. Balance is SUM(amount_satang) per merchant."
    ),
    failure_modes=[
        FailureMode(
            failure="The provider delivers the same event twice, possibly at the same moment",
            recovery="INSERT ... ON CONFLICT (event_id) DO NOTHING inside one transaction; the loser returns 'duplicate' and writes nothing",
        ),
        FailureMode(
            failure="The service crashes after storing the event but before writing the ledger entry",
            recovery="The event keeps processed_at NULL; the startup sweep re-processes it and the unique event_id makes the retry safe",
        ),
        FailureMode(
            failure="PostgreSQL is unavailable",
            recovery="Return 503 so the provider retries later; never acknowledge an event that was not persisted",
        ),
        FailureMode(
            failure="A tampered or replayed payload",
            recovery="Reject on HMAC mismatch or a timestamp outside the allowed window, before any database write",
        ),
    ],
    verification=[
        "pytest: posting the same event 100 times yields exactly 1 ledger row",
        "pytest: 20 concurrent requests for one event_id (asyncio.gather against a test Postgres) yield exactly 1 ledger row",
        "pytest: killing the process between the event insert and the ledger write, then restarting, yields exactly 1 ledger row",
        "pytest: a payload with a wrong signature returns 401 and leaves both tables unchanged",
        "Locust: a mixed run of unique and duplicate events ends with ledger row count equal to the number of unique events",
    ],
    out_of_scope=[
        "Card payments or storing any card or bank credentials",
        "Refunds and chargebacks",
        "Settlement file reconciliation",
        "Multi-service deployment",
    ],
    difficulty="Intermediate",
)

_DATA_FALLBACK = ProjectIdeaSpec(
    title="Delivery Telemetry Ingestion with a Dead-Letter Table",
    domain_industry="Food delivery logistics (Thailand)",
    core_problem=(
        "Rider GPS pings arrive in batches, out of order, sometimes duplicated and sometimes malformed. "
        "Every valid ping must be stored exactly once without one bad ping rejecting its whole batch."
    ),
    target_tech_stack=["Python", "FastAPI", "PostgreSQL", "Docker"],
    system_boundary=(
        "One FastAPI ingestion service and one PostgreSQL database; the dead-letter queue is a table, not a broker. "
        "Out of scope: live maps, Kafka, Spark, ETA prediction."
    ),
    walking_skeleton=[
        "POST /pings stores a batch; GET /trips/{trip_id}/track returns the stored points; runs with docker compose up",
        "Validate each ping individually; valid ones go to pings, invalid ones go to dead_letters with a reason",
        "Deduplicate device retries with a primary key on (device_id, seq)",
        "Return tracks ordered by recorded_at rather than arrival order",
        "Add POST /dead-letters/replay to re-run stored failures after a parser fix",
    ],
    contracts=(
        "Pydantic `Ping(device_id: str, trip_id: str, seq: int, lat: float (-90..90), lon: float (-180..180), recorded_at: datetime)`. "
        "`POST /pings` takes a JSON array and returns 200 `{accepted: int, duplicates: int, dead_lettered: int}`, 503 when the database is down. "
        "`GET /trips/{trip_id}/track` returns points ordered by recorded_at. `POST /dead-letters/replay` returns `{replayed: int, still_failing: int}`."
    ),
    database_schema=(
        "`pings(device_id TEXT, seq INT, trip_id TEXT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, recorded_at TIMESTAMPTZ, "
        "received_at TIMESTAMPTZ, PRIMARY KEY (device_id, seq))` with an index on (trip_id, recorded_at); "
        "`dead_letters(id BIGSERIAL, raw JSONB, reason TEXT, received_at, replayed_at NULL)`."
    ),
    failure_modes=[
        FailureMode(
            failure="One malformed ping inside a valid batch",
            recovery="Validate per item; the bad ping goes to dead_letters with its error and the rest of the batch is stored",
        ),
        FailureMode(
            failure="A device resends a batch after a timeout",
            recovery="ON CONFLICT (device_id, seq) DO NOTHING; the response counts duplicates instead of failing",
        ),
        FailureMode(
            failure="The database fails halfway through a batch",
            recovery="The batch is one transaction, so it rolls back fully; the client gets 503 and the retry is deduplicated",
        ),
        FailureMode(
            failure="Pings arrive out of order",
            recovery="Order by recorded_at at read time; never infer order from arrival",
        ),
    ],
    verification=[
        "pytest: a batch of 50 pings with 1 malformed stores 49 rows and 1 dead letter",
        "pytest: sending the same batch twice leaves 49 rows",
        "pytest: a shuffled batch returns a track sorted by recorded_at",
        "pytest: replay after fixing the parser moves the dead letter into pings and sets replayed_at",
        "Locust: after a mixed run, the pings row count equals the number of unique valid pings sent",
    ],
    out_of_scope=["Live map UI", "Kafka or any external broker", "ETA prediction", "Multi-region storage"],
    difficulty="Intermediate",
)

_FRONTEND_FALLBACK = ProjectIdeaSpec(
    title="Offline-Tolerant Delivery Dispatch Board",
    domain_industry="On-demand delivery operations (Thailand)",
    core_problem=(
        "Dispatchers assign riders to orders while their connection drops in and out. "
        "Each assignment must apply exactly once, and conflicting assignments must surface instead of silently overwriting."
    ),
    target_tech_stack=["TypeScript", "React", "Next.js", "PostgreSQL"],
    system_boundary=(
        "One Next.js app (UI plus route handlers) and one PostgreSQL database. "
        "Out of scope: maps, real GPS, payments, external auth providers."
    ),
    walking_skeleton=[
        "List orders and riders from PostgreSQL and assign a rider through POST /api/actions",
        "Give every action a client-generated UUID and record applied ids in applied_actions",
        "Queue actions in an IndexedDB outbox while offline and flush them in order when back online",
        "Reject assignments made against a stale order version and show the server state",
    ],
    contracts=(
        "TypeScript `AssignAction { actionId: string; orderId: string; riderId: string; baseVersion: number }`. "
        "`POST /api/actions` returns 200 `{status: 'applied' | 'duplicate' | 'conflict', order}`. "
        "`GET /api/orders?sinceVersion=n` returns orders changed after version n."
    ),
    database_schema=(
        "`orders(id TEXT PRIMARY KEY, status TEXT, rider_id TEXT NULL, version INT NOT NULL)`; "
        "`applied_actions(action_id UUID PRIMARY KEY, order_id TEXT, applied_at TIMESTAMPTZ)`. "
        "An update applies only WHERE version = baseVersion."
    ),
    failure_modes=[
        FailureMode(
            failure="The network drops after the server applied an action but before the client saw the response",
            recovery="The client retries with the same actionId; applied_actions turns the retry into 'duplicate'",
        ),
        FailureMode(
            failure="Two dispatchers assign the same order",
            recovery="The version check lets one apply; the other gets 'conflict' and the UI shows the current assignment",
        ),
        FailureMode(
            failure="The tab closes with actions still queued",
            recovery="The IndexedDB outbox persists and is flushed on the next load",
        ),
    ],
    verification=[
        "Playwright: assign while offline, go online, and exactly 1 applied_actions row exists",
        "Vitest: sending the same action twice returns 'applied' then 'duplicate'",
        "Playwright: two contexts assigning one order produce 1 'applied' and 1 'conflict'",
        "Playwright: reloading with queued actions flushes them and the outbox ends empty",
    ],
    out_of_scope=["Maps and live GPS", "Payments", "Push notifications", "Native mobile app"],
    difficulty="Intermediate",
)

FALLBACK_TITLES = frozenset(
    spec.title for spec in (_BACKEND_FALLBACK, _DATA_FALLBACK, _FRONTEND_FALLBACK)
)


class IdeationEngine(BaseGeminiService):
    """Generates one scoped ProjectIdeaSpec per role from its dominant market stack."""

    @staticmethod
    def is_fallback(spec: ProjectIdeaSpec) -> bool:
        """True when the spec is a curated offline archetype rather than a model-generated one."""
        return spec.title in FALLBACK_TITLES

    def generate_project_spec(
        self,
        target_role: str,
        tech_stack: List[str],
        domain_hint: Optional[str] = None,
    ) -> ProjectIdeaSpec:
        """
        Returns a model-generated spec, or a curated archetype when Gemini is
        unconfigured or unavailable (check with `is_fallback`).
        """
        if not self.client:
            logger.warning("[IdeationEngine] No Gemini API client configured; using curated archetype spec.")
            return self._build_fallback_spec(target_role, tech_stack, domain_hint)

        domain_clause = f"Business domain: {domain_hint}." if domain_hint else "Pick a Thailand business domain where the problem genuinely occurs."
        user_prompt = (
            f"Target role: {target_role}\n"
            f"Most requested stack in current Thailand job postings for this role: {', '.join(tech_stack)}\n"
            f"{domain_clause}\n\n"
            "Design one portfolio project spec following the rules."
        )

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
        return spec

    def _build_fallback_spec(
        self,
        target_role: str,
        tech_stack: List[str],
        domain_hint: Optional[str] = None,
    ) -> ProjectIdeaSpec:
        """Curated archetype for offline use or API outages, picked by role."""
        role_lower = target_role.lower()
        if "data" in role_lower:
            base = _DATA_FALLBACK
        elif "frontend" in role_lower:
            base = _FRONTEND_FALLBACK
        else:
            base = _BACKEND_FALLBACK
        if domain_hint:
            return base.model_copy(update={"domain_industry": domain_hint})
        return base.model_copy(deep=True)
