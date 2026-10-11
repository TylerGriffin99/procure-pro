import uuid

import pytest

from app.exceptions import InternalError, NotFoundError, reloaded, require
from app.models.harness_session import HarnessSession
from app.models.wbs_code import WBSCode
from app.services.harness_service import require_owned
from app.services.project_service import require_in_project

OWNER = uuid.uuid4()
PROJECT = uuid.uuid4()


def test_require_none_raises_not_found_with_uniform_detail():
    with pytest.raises(NotFoundError) as excinfo:
        require(None, "Claim")
    assert excinfo.value.detail == "Claim not found"
    assert excinfo.value.status_code == 404


def test_require_returns_the_value_itself():
    value = object()
    assert require(value, "Thing") is value


def test_require_treats_empty_values_as_present():
    empty: list[int] = []
    assert require(empty, "x") is empty
    assert require(0, "x") == 0


@pytest.mark.parametrize("session", [None, HarnessSession(user_id=uuid.uuid4())])
def test_require_owned_reports_missing_and_foreign_sessions_as_not_found(session):
    with pytest.raises(NotFoundError) as excinfo:
        require_owned(session, OWNER)
    assert excinfo.value.detail == "Session not found"


def test_require_owned_returns_the_owned_session():
    session = HarnessSession(user_id=OWNER)
    assert require_owned(session, OWNER) is session


@pytest.mark.parametrize("wbs", [None, WBSCode(project_id=uuid.uuid4())])
def test_require_in_project_reports_missing_and_foreign_wbs_as_not_found(wbs):
    with pytest.raises(NotFoundError) as excinfo:
        require_in_project(wbs, PROJECT)
    assert excinfo.value.detail == "WBS code not found"


def test_require_in_project_returns_the_project_wbs():
    wbs = WBSCode(project_id=PROJECT)
    assert require_in_project(wbs, PROJECT) is wbs


def test_reloaded_none_is_an_internal_error_not_a_404():
    with pytest.raises(InternalError) as excinfo:
        reloaded(None, "Assessment")
    assert excinfo.value.detail == "Assessment vanished after commit"
    assert excinfo.value.status_code == 500


def test_reloaded_returns_the_value_itself():
    value = object()
    assert reloaded(value, "Thing") is value
