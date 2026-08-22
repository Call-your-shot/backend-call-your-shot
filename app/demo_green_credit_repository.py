"""Thread-safe in-memory green-credit adapter for the email-only demo UI.

This adapter deliberately implements the same repository protocol as the
Supabase adapter.  Routes and application services therefore do not need to
know whether a request is using demo identity or production authentication.
The state is process-local and is reset whenever the API process restarts.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .green_credit_repository import GreenCreditRepositoryError

_UTC = timezone.utc
_DEMO_PROPERTY_ID = UUID("11111111-1111-4111-8111-111111111111")

_PROJECT_IDS = {
    "battery": UUID("13131313-1313-4131-8131-131313131313"),
    "housing": UUID("14141414-1414-4141-8141-141414141414"),
    "habitat": UUID("15151515-1515-4151-8151-151515151515"),
}


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(_UTC)


def _microcredits(credits: int) -> int:
    return credits * 1_000_000


def _stable_uuid(kind: str, value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"call-your-shot:{kind}:{value}")


def _project(
    *,
    project_id: UUID,
    slug: str,
    title: str,
    description: str,
    category: str,
    location: str,
    target_credits: int,
    funded_credits: int,
    minimum_credits: int,
    impact_unit: str,
    expected_impact: float,
    verification_method: str,
    sponsor_name: str,
    sponsor_commitment_dollars: int,
) -> dict[str, Any]:
    return {
        "id": project_id,
        "slug": slug,
        "title": title,
        "description": description,
        "category": category,
        "location": location,
        "image_path": None,
        "target_microcredits": _microcredits(target_credits),
        "funded_microcredits": _microcredits(funded_credits),
        "remaining_microcredits": _microcredits(target_credits - funded_credits),
        "minimum_allocation_microcredits": _microcredits(minimum_credits),
        "status": "open",
        "impact_unit": impact_unit,
        "expected_impact": expected_impact,
        "verification_method": verification_method,
        "opens_at": _at("2026-08-15T00:00:00+00:00"),
        "closes_at": _at("2027-08-22T00:00:00+00:00"),
        "metadata": {
            "curated": True,
            "sponsor_name": sponsor_name,
            "sponsor_commitment_dollars": sponsor_commitment_dollars,
            "credits_per_sponsor_dollar": 100,
        },
        "created_at": _at("2026-08-15T00:00:00+00:00"),
    }


def _initial_projects() -> dict[UUID, dict[str, Any]]:
    projects = [
        _project(
            project_id=_PROJECT_IDS["battery"],
            slug="illawarra-community-battery",
            title="Illawarra Community Battery",
            description=(
                "Support shared battery capacity that helps local households "
                "use more renewable electricity after sunset."
            ),
            category="energy_storage",
            location="Illawarra, NSW",
            target_credits=250_000,
            funded_credits=162_450,
            minimum_credits=1,
            impact_unit="kWh of community storage supported",
            expected_impact=500,
            verification_method="Commissioning records and quarterly operator reports",
            sponsor_name="BrightGrid Community Fund",
            sponsor_commitment_dollars=2_500,
        ),
        _project(
            project_id=_PROJECT_IDS["housing"],
            slug="social-housing-solar",
            title="Solar for Social Housing",
            description=(
                "Help install rooftop solar for households facing energy "
                "hardship across regional New South Wales."
            ),
            category="rooftop_solar",
            location="New South Wales",
            target_credits=400_000,
            funded_credits=289_300,
            minimum_credits=1,
            impact_unit="solar capacity installed (kW)",
            expected_impact=25,
            verification_method="Installer certificates and annual generation reports",
            sponsor_name="Green Horizon Foundation",
            sponsor_commitment_dollars=4_000,
        ),
        _project(
            project_id=_PROJECT_IDS["habitat"],
            slug="coastal-habitat-restoration",
            title="Coastal Habitat Restoration",
            description=(
                "Restore native coastal vegetation and improve habitat "
                "resilience along the South Coast."
            ),
            category="habitat_restoration",
            location="South Coast, NSW",
            target_credits=150_000,
            funded_credits=98_250,
            minimum_credits=1,
            impact_unit="square metres restored",
            expected_impact=10_000,
            verification_method="Geotagged planting records and independent completion review",
            sponsor_name="Coast & Country Impact Pool",
            sponsor_commitment_dollars=1_500,
        ),
    ]
    return {row["id"]: row for row in projects}


_ACCOUNT_SEEDS = {
    "sarah.chen@example.com": (2_310, 3_510, 1_200, 5_014, 118, "tenant"),
    "david.marino@example.com": (1_880, 2_580, 700, 8_600, 74, "landlord"),
    "priya.nair@example.com": (2_840, 4_760, 1_920, 6_800, 156, "tenant"),
    # These aliases match the email-only identities used by the backend demo.
    "tenant@example.com": (2_310, 3_510, 1_200, 5_014, 118, "tenant"),
    "landlord@example.com": (1_880, 2_580, 700, 8_600, 74, "landlord"),
}


class DemoGreenCreditStore:
    """Shared process-local state with atomic wallet/project allocation updates."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.reset()

    def reset(self) -> None:
        with self.lock:
            self.projects = _initial_projects()
            self.accounts: dict[str, dict[str, Any]] = {}
            self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
            for email, seed in _ACCOUNT_SEEDS.items():
                self.accounts[email] = self._seed_account(email, *seed)

    @staticmethod
    def _seed_account(
        email: str,
        available: int,
        earned: int,
        allocated: int,
        verified_solar_kwh: int,
        recent_earn: int,
        role: str,
    ) -> dict[str, Any]:
        account_id = _stable_uuid("green-credit-account", email)
        occurred_at = _at("2026-08-21T04:30:00+00:00")
        return {
            "wallet": {
                "account_id": account_id,
                "status": "active",
                "available_microcredits": _microcredits(available),
                "lifetime_earned_microcredits": _microcredits(earned),
                "lifetime_allocated_microcredits": _microcredits(allocated),
                "verified_solar_kwh": float(verified_solar_kwh),
            },
            "ledger": [
                {
                    "id": _stable_uuid("green-credit-ledger", f"{email}:recent-earn"),
                    "entry_type": "earn",
                    "amount_microcredits": _microcredits(recent_earn),
                    "property_id": _DEMO_PROPERTY_ID,
                    "project_id": None,
                    "source_energy_reading_id": _stable_uuid(
                        "energy-reading", f"{email}:2026-08"
                    ),
                    "source_solar_kwh": float(recent_earn),
                    "beneficiary_role": role,
                    "description": "Credits earned from verified solar use",
                    "occurred_at": occurred_at,
                    "created_at": occurred_at,
                }
            ],
            "allocations": [],
        }

    def account(self, email: str) -> dict[str, Any]:
        with self.lock:
            if email not in self.accounts:
                # New email-only demo users can browse immediately and begin
                # with an empty wallet; no fake earned credits are invented.
                self.accounts[email] = self._seed_account(
                    email, 0, 0, 0, 0, 0, "tenant"
                )
                self.accounts[email]["ledger"].clear()
            return self.accounts[email]


_STORE = DemoGreenCreditStore()


def reset_demo_green_credit_state() -> None:
    """Restore deterministic demo state (used by tests and local demos)."""
    _STORE.reset()


class DemoGreenCreditRepository:
    """Email-scoped implementation of the green-credit repository contract."""

    def __init__(self, email: str, store: DemoGreenCreditStore = _STORE) -> None:
        self.email = email.strip().lower()
        self.store = store

    def get_wallet(self) -> dict[str, Any] | None:
        with self.store.lock:
            return deepcopy(self.store.account(self.email)["wallet"])

    def list_ledger(
        self, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]:
        with self.store.lock:
            rows = self.store.account(self.email)["ledger"]
            filtered = [
                row for row in rows if cursor is None or row["created_at"] < cursor
            ]
            sorted_rows = sorted(
                filtered, key=lambda row: row["created_at"], reverse=True
            )
            return deepcopy(sorted_rows[:limit])

    def list_allocations(
        self, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]:
        with self.store.lock:
            rows = self.store.account(self.email)["allocations"]
            filtered = [
                row
                for row in rows
                if cursor is None or row["allocated_at"] < cursor
            ]
            sorted_rows = sorted(
                filtered, key=lambda row: row["allocated_at"], reverse=True
            )
            return deepcopy(sorted_rows[:limit])

    def list_projects(
        self, status: str | None, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]:
        with self.store.lock:
            rows = [
                row
                for row in self.store.projects.values()
                if row["status"] != "draft"
                and (status is None or row["status"] == status)
                and (cursor is None or row["created_at"] < cursor)
            ]
            rows.sort(
                key=lambda row: (row["created_at"], str(row["id"])), reverse=True
            )
            return deepcopy(rows[:limit])

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            try:
                row = self.store.projects.get(UUID(project_id))
            except ValueError:
                row = None
            return deepcopy(row) if row and row["status"] != "draft" else None

    def allocate(
        self, project_id: str, requested_microcredits: int, idempotency_key: str
    ) -> dict[str, Any]:
        with self.store.lock:
            account = self.store.account(self.email)
            wallet = account["wallet"]
            replay_key = (self.email, idempotency_key)
            existing = self.store.idempotency.get(replay_key)
            if existing is not None:
                if (
                    existing["project_id"] != project_id
                    or existing["requested_microcredits"] != requested_microcredits
                ):
                    raise GreenCreditRepositoryError(
                        "Idempotency key was already used for a different request",
                        409,
                        "IDEMPOTENCY_CONFLICT",
                    )
                result = deepcopy(existing["response"])
                result["available_balance_microcredits"] = wallet[
                    "available_microcredits"
                ]
                result["idempotent_replay"] = True
                return result

            try:
                project_uuid = UUID(project_id)
            except ValueError as exc:
                raise GreenCreditRepositoryError(
                    "Green project not found", 404, "NOT_FOUND"
                ) from exc
            project = self.store.projects.get(project_uuid)
            if project is None:
                raise GreenCreditRepositoryError(
                    "Green project not found", 404, "NOT_FOUND"
                )
            if project["status"] != "open":
                raise GreenCreditRepositoryError(
                    "Green project is not open for allocations",
                    409,
                    "PROJECT_NOT_OPEN",
                )

            remaining = project["remaining_microcredits"]
            if remaining <= 0:
                raise GreenCreditRepositoryError(
                    "Green project is fully funded", 409, "PROJECT_NOT_OPEN"
                )
            allocated = min(requested_microcredits, remaining)
            if (
                allocated < project["minimum_allocation_microcredits"]
                and allocated != remaining
            ):
                raise GreenCreditRepositoryError(
                    "Allocation is below the project minimum", 422, "VALIDATION_ERROR"
                )
            if wallet["available_microcredits"] < allocated:
                raise GreenCreditRepositoryError(
                    "Insufficient green-credit balance",
                    409,
                    "INSUFFICIENT_BALANCE",
                )

            now = datetime.now(_UTC)
            allocation_id = uuid4()
            project["funded_microcredits"] += allocated
            project["remaining_microcredits"] -= allocated
            if project["remaining_microcredits"] == 0:
                project["status"] = "funded"
            wallet["available_microcredits"] -= allocated
            wallet["lifetime_allocated_microcredits"] += allocated

            allocation = {
                "id": allocation_id,
                "project_id": project_uuid,
                "requested_microcredits": requested_microcredits,
                "allocated_microcredits": allocated,
                "status": "confirmed",
                "idempotency_key": idempotency_key,
                "allocated_at": now,
            }
            account["allocations"].append(allocation)
            account["ledger"].append(
                {
                    "id": uuid4(),
                    "entry_type": "allocate",
                    "amount_microcredits": -allocated,
                    "property_id": None,
                    "project_id": project_uuid,
                    "source_energy_reading_id": None,
                    "source_solar_kwh": None,
                    "beneficiary_role": None,
                    "description": f"Green credits allocated to {project['title']}",
                    "occurred_at": now,
                    "created_at": now,
                }
            )
            response = {
                "allocation_id": allocation_id,
                "requested_microcredits": requested_microcredits,
                "allocated_microcredits": allocated,
                "partial": allocated < requested_microcredits,
                "available_balance_microcredits": wallet["available_microcredits"],
                "project_remaining_microcredits": project["remaining_microcredits"],
                "project_status": project["status"],
                "idempotent_replay": False,
            }
            self.store.idempotency[replay_key] = {
                "project_id": project_id,
                "requested_microcredits": requested_microcredits,
                "response": deepcopy(response),
            }
            return deepcopy(response)

    def accrue(
        self, property_id: str, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        raise GreenCreditRepositoryError(
            "Demo email identity cannot call the internal accrual endpoint",
            403,
            "INTERNAL_AUTHORIZATION_ERROR",
        )


def create_demo_repository(email: str) -> DemoGreenCreditRepository:
    return DemoGreenCreditRepository(email)
