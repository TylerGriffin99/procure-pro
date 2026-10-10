#!/usr/bin/env python3
"""
Seed a sample project — Gilmours Central Seismic Strengthening — with its full
WBS breakdown and retention tiers, so the workspace opens with a project
already loaded instead of an empty dashboard.

Run after seed_user.py (the project is attached to the demo user):

    python scripts/seed_project.py

The script is idempotent — running it again will not create a duplicate.
"""

import asyncio
import os
import sys
import uuid
from decimal import Decimal

# Make the backend package importable regardless of where this is run from.
BACKEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"
)
sys.path.insert(0, BACKEND_DIR)

from app.database import async_session  # noqa: E402
from app.repos import user_repo, project_repo  # noqa: E402
from app.services import project_service  # noqa: E402
from app.schemas.project import (  # noqa: E402
    ProjectCreate,
    WBSCodeCreate,
    RetentionTierCreate,
)

DEMO_EMAIL = "user@test.com"
PROJECT_NAME = "Gilmours Central Seismic Strengthening"
# Deterministic id so the project URL (/projects/<id>) is stable across reseeds.
PROJECT_ID = uuid.UUID("da7c194d-0b70-485d-a9ae-43ccbaddb234")

# (code, description, level, parent_code, sort_order, contract_sum)
# Mirrors the GILMOURS_WBS template in frontend/src/pages/CreateProject.tsx.
WBS: list[tuple[str, str, str, str | None, int, str | None]] = [
    ("DM", "Demolition", "category", None, 0, None),
    ("DM-01", "Demolition existing structure", "subcategory", "DM", 1, "120480.00"),
    ("DM-02", "Removal and reinstatement of PIR", "subcategory", "DM", 2, "27944.00"),
    (
        "DM-03",
        "Removal and reinstatement of chiller units",
        "subcategory",
        "DM",
        3,
        "6490.25",
    ),
    ("DM-04", "Temp lighting to birdcage - setup", "subcategory", "DM", 4, "14297.75"),
    ("DM-05", "Bulk Excavation", "subcategory", "DM", 5, "64504.78"),
    ("DR", "Drainage", "category", None, 10, None),
    (
        "DR-01",
        "Relocation of stormwater, sewer and water",
        "subcategory",
        "DR",
        11,
        "156773.92",
    ),
    ("CP", "Car Park & Yard", "category", None, 20, None),
    ("CP-01", "Concrete driveway", "subcategory", "CP", 21, "30800.00"),
    ("CP-02", "Asphalt prep and hotmix", "subcategory", "CP", 22, "24860.00"),
    ("SS", "Substructure", "category", None, 30, None),
    ("SS-01", "General substructure works", "subcategory", "SS", 31, "256840.78"),
    ("SS-02", "Pile drilling", "subcategory", "SS", 32, "62257.00"),
    ("SS-03", "Reinforcing steel", "subcategory", "SS", 33, "104865.35"),
    ("FR", "Frame", "category", None, 40, None),
    ("FR-01", "Steel", "subcategory", "FR", 41, "1184000.00"),
    ("EW", "External Walls and Exterior Finishes", "category", None, 50, None),
    ("EW-01", "Works to external walls", "subcategory", "EW", 51, "47537.47"),
    ("IP", "Internal Partitions & Doors", "category", None, 60, None),
    ("IP-01", "Redecoration", "subcategory", "IP", 61, "18344.00"),
    ("CF", "Ceiling Finishes", "category", None, 70, None),
    ("CF-01", "Suspended ceilings", "subcategory", "CF", 71, "68026.70"),
    ("HV", "HVAC", "category", None, 80, None),
    (
        "HV-01",
        "Removal and reinstatement of aircon units",
        "subcategory",
        "HV",
        81,
        "14298.00",
    ),
    ("FP", "Fire Protection", "category", None, 90, None),
    ("FP-01", "Fire Sprinkler Alteration", "subcategory", "FP", 91, "200000.00"),
    ("PL", "Preliminaries", "category", None, 100, None),
    ("PL-01", "General", "subcategory", "PL", 101, "250000.00"),
    ("PL-02", "Temp fencing and hoarding", "subcategory", "PL", 102, "40160.00"),
    ("PL-03", "Scaffolding and Encapsulation", "subcategory", "PL", 103, "893343.50"),
    ("PL-04", "Ply barriers to birdcage", "subcategory", "PL", 104, "22500.00"),
    ("PL-05", "Temp ablution blocks", "subcategory", "PL", 105, "54865.97"),
    ("PL-06", "Temp office", "subcategory", "PL", 106, "37607.20"),
    ("PL-07", "Temp driveway", "subcategory", "PL", 107, "50565.00"),
    (
        "PL-08",
        "Temp lighting to birdcage - setup",
        "subcategory",
        "PL",
        108,
        "21131.25",
    ),
    ("MG", "Margin", "category", None, 110, None),
    ("MG-01", "General Margin", "subcategory", "MG", 111, "250000.00"),
    ("PS", "Provisional Sums", "category", None, 120, None),
    ("PS-01", "Provisional Sums", "subcategory", "PS", 121, "150000.00"),
    ("VR", "Variations", "category", None, 130, None),
    ("VR-01", "Variations", "subcategory", "VR", 131, "0"),
]

# (tier_order, percentage, up_to_amount)
RETENTION: list[tuple[int, str, str | None]] = [
    (1, "0.10", "200000"),
    (2, "0.05", "800000"),
    (3, "0.0175", None),
]


async def seed() -> None:
    async with async_session() as db:
        user = await user_repo.get_by_email(db, DEMO_EMAIL)
        if user is None:
            print(
                f"Demo user '{DEMO_EMAIL}' not found — run scripts/seed_user.py first."
            )
            sys.exit(1)

        if await project_repo.get_by_id(db, PROJECT_ID) is not None:
            print(
                f"Project '{PROJECT_NAME}' ({PROJECT_ID}) already exists; nothing to do."
            )
            return

        wbs_codes = [
            WBSCodeCreate(
                code=code,
                description=description,
                level=level,
                parent_code=parent_code,
                sort_order=sort_order,
                contract_sum=(
                    Decimal(contract_sum) if contract_sum is not None else None
                ),
            )
            for (code, description, level, parent_code, sort_order, contract_sum) in WBS
        ]
        contract_sum = sum(
            (w.contract_sum or Decimal(0) for w in wbs_codes), Decimal(0)
        )

        retention_tiers = [
            RetentionTierCreate(
                tier_order=tier_order,
                percentage=Decimal(percentage),
                up_to_amount=(Decimal(up_to) if up_to is not None else None),
            )
            for (tier_order, percentage, up_to) in RETENTION
        ]

        data = ProjectCreate(
            name=PROJECT_NAME,
            project_number="GIL-001",
            client_name="Foodstuffs North Island",
            contractor_name="Kynoch Construction Ltd",
            contract_sum=contract_sum,
            gst_rate=Decimal("0.15"),
            provisional_sum_total=Decimal("150000"),
            retention_tiers=retention_tiers,
            wbs_codes=wbs_codes,
        )
        project = await project_service.create_project(
            db, data, user, project_id=PROJECT_ID
        )
        print(
            f"Created project '{project.name}' (id={project.id}) "
            f"with {len(wbs_codes)} WBS codes and contract sum {contract_sum}."
        )


if __name__ == "__main__":
    asyncio.run(seed())
