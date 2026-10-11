import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.constants.enums import AssessmentStatus, FlagSeverity, FlagType
from app.schemas.claim import ClaimResponse
from app.schemas.claim_flag import ClaimParseFlagResponse


def fake_flag(**overrides) -> SimpleNamespace:
    fields = {
        "id": uuid.uuid4(),
        "flag_type": "over_claim",
        "severity": "warning",
        "line_item_ref": "1.1",
        "description": "over",
        "expected_value": Decimal("1.00"),
        "actual_value": Decimal("2.00"),
        "resolved": False,
        "resolved_by": None,
        "resolved_at": None,
        "created_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    return SimpleNamespace(**(fields | overrides))


def fake_claim() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        claim_number=1,
        period_from=None,
        period_to=None,
        payment_due=None,
        claim_received=None,
        provisional_payment_schedule_due=None,
        payment_schedule_due=None,
        parsed_at=None,
        line_items=[],
        original_contract_total=None,
        variations_total=None,
        revised_contract_total=None,
        retention_amount=None,
        claimed_amount=None,
    )


def test_flag_response_types_flag_type_and_severity_by_enum():
    dto = ClaimParseFlagResponse.model_validate(fake_flag(), from_attributes=True)
    assert dto.flag_type is FlagType.over_claim
    assert dto.severity is FlagSeverity.warning
    wire = dto.model_dump(mode="json")
    assert (wire["flag_type"], wire["severity"]) == ("over_claim", "warning")


@pytest.mark.parametrize("field", ["flag_type", "severity"])
def test_flag_response_rejects_values_outside_the_enum(field):
    with pytest.raises(ValidationError, match=field):
        ClaimParseFlagResponse.model_validate(fake_flag(**{field: "bogus"}), from_attributes=True)


def test_claim_response_assessment_status_is_an_enum_with_the_same_wire_value():
    dto = ClaimResponse.from_claim(fake_claim(), assessment_status=AssessmentStatus.finalised)
    assert dto.assessment_status is AssessmentStatus.finalised
    assert dto.model_dump(mode="json")["assessment_status"] == "finalised"
    assert ClaimResponse.from_claim(fake_claim()).assessment_status is None
