from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import backend.database as database_module
from backend.services.learning_turn_lease import LearningTurnLease


def prepare_database(monkeypatch, tmp_path):
    path = tmp_path / "turn-lease.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        path,
    )
    monkeypatch.setattr(
        database_module,
        "DATA_DIR",
        tmp_path,
    )

    database_module.init_database()


def test_same_area_allows_only_one_active_turn(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    assert LearningTurnLease.acquire(
        "ads",
        "owner-1",
    ) is True

    assert LearningTurnLease.acquire(
        "ads",
        "owner-2",
    ) is False


def test_different_areas_can_process_concurrently(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    assert LearningTurnLease.acquire(
        "ads",
        "ads-owner",
    ) is True

    assert LearningTurnLease.acquire(
        "it",
        "it-owner",
    ) is True


def test_same_owner_token_cannot_claim_two_areas(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    assert LearningTurnLease.acquire(
        "ads",
        "same-turn-id",
    ) is True

    assert LearningTurnLease.acquire(
        "it",
        "same-turn-id",
    ) is False


def test_only_owner_can_release_lease(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    LearningTurnLease.acquire(
        "ads",
        "owner-1",
    )

    assert LearningTurnLease.release(
        "ads",
        "owner-2",
    ) is False

    assert LearningTurnLease.get("ads") is not None

    assert LearningTurnLease.release(
        "ads",
        "owner-1",
    ) is True

    assert LearningTurnLease.get("ads") is None


def test_expired_lease_can_be_reclaimed(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    now = datetime(
        2026,
        9,
        4,
        12,
        0,
        tzinfo=timezone.utc,
    )

    assert LearningTurnLease.acquire(
        "ads",
        "expired-owner",
        now=now,
        lease_seconds=10,
    ) is True

    assert LearningTurnLease.acquire(
        "ads",
        "new-owner",
        now=now + timedelta(seconds=11),
    ) is True

    lease = LearningTurnLease.get("ads")

    assert lease["owner_token"] == "new-owner"


def test_concurrent_claims_allow_exactly_one_owner(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    barrier = Barrier(2)

    def acquire(owner):
        barrier.wait()
        return LearningTurnLease.acquire(
            "ads",
            owner,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                acquire,
                ("owner-1", "owner-2"),
            )
        )

    assert sorted(results) == [False, True]
