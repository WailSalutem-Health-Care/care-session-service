import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from app.care_sessions.repository import CareSessionRepository


class DummyResult:
    def __init__(self, val=None, vals=None):
        self._val = val
        self._vals = vals or []

    def scalar_one_or_none(self):
        return self._val

    def scalar(self):
        return self._val

    def scalars(self):
        class S:
            def __init__(self, vals):
                self._vals = vals

            def all(self):
                return self._vals

        return S(self._vals)


@pytest.mark.asyncio
async def test_get_by_id_calls_db_execute(fake_db):
    expected = SimpleNamespace(id="1")

    async def exec_fn(stmt):
        return DummyResult(val=expected)

    fake_db.execute.side_effect = exec_fn

    repo = CareSessionRepository(fake_db, "test_schema")
    res = await repo.get_by_id("1")

    assert res is expected


@pytest.mark.asyncio
async def test_list_sessions_returns_list_and_total(fake_db):

    # The repository sets the search_path first (one execute), then runs a count query, then the select.
    # Provide three results in the same order: search_path (empty), count, rows
    results = [DummyResult(), DummyResult(val=2), DummyResult(vals=[SimpleNamespace(id=1), SimpleNamespace(id=2)])]

    async def exec_fn(stmt):
        return results.pop(0)

    fake_db.execute.side_effect = exec_fn

    repo = CareSessionRepository(fake_db, "test_schema")
    sessions, total = await repo.list_sessions()

    assert total == 2
    assert isinstance(sessions, list)


@pytest.mark.asyncio
async def test_get_active_by_patient_calls_db(fake_db):
    # simulate search_path then select returning a session
    results = [DummyResult(), DummyResult(val=SimpleNamespace(id=1))]

    async def exec_fn(stmt):
        return results.pop(0)

    fake_db.execute.side_effect = exec_fn
    repo = CareSessionRepository(fake_db, "test_schema")
    res = await repo.get_active_by_patient("patient-1")
    assert res is not None


@pytest.mark.asyncio
async def test_delete_returns_true_when_found(fake_db):
    # get_by_id returns a session, then commit is expected
    async def exec_fn(stmt):
        return DummyResult()

    fake_db.execute.side_effect = exec_fn
    fake_db.commit = AsyncMock()

    repo = CareSessionRepository(fake_db, "test_schema")

    # stub get_by_id to return a simple object with deleted_at attr
    repo.get_by_id = AsyncMock(return_value=SimpleNamespace(deleted_at=None))
    res = await repo.delete("1")
    assert res is True
