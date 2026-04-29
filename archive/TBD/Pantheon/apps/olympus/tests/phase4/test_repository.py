"""
Phase 4 — Repository tests.
Verifies the read layer returns correct, filtered results.
"""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.memory.database import Database
from core.memory.repository import Repository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mem_db():
    db = Database(Path(":memory:"))
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def repo(mem_db):
    return Repository(mem_db)


def _insert_trade(db, symbol="AAPL", direction="long", exit_reason="target",
                  realized_pnl=50.0, r_multiple=2.5,
                  entry_time=None, exit_time=None):
    now = datetime.now(timezone.utc)
    entry = (entry_time or now).isoformat()
    exit_ = (exit_time or now).isoformat()
    trade_id = str(uuid.uuid4())
    position_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO trades (
            trade_id, position_id, symbol, direction,
            entry_price, exit_price, stop_price, target_price,
            size, entry_time, exit_time, hold_duration_minutes,
            realized_pnl, r_multiple, exit_reason, status,
            ingested_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            trade_id, position_id, symbol, direction,
            150.0, 155.0, 148.0, 156.0,
            10, entry, exit_,
            90.0, realized_pnl, r_multiple, exit_reason, "closed",
            now.isoformat(),
        ),
    )
    return trade_id


def _insert_cycle(db, universe_size=185):
    cycle_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """
        INSERT INTO ranking_cycles (
            cycle_id, cycle_timestamp, universe_size, scored_count,
            error_count, duration_seconds, ingested_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (cycle_id, now, universe_size, 180, 5, 11.0, now),
    )
    return cycle_id


# ---------------------------------------------------------------------------
# get_trade_count
# ---------------------------------------------------------------------------


def test_get_trade_count_empty(repo):
    assert repo.get_trade_count() == 0


def test_get_trade_count_all(repo, mem_db):
    _insert_trade(mem_db, symbol="AAPL")
    _insert_trade(mem_db, symbol="MSFT")
    assert repo.get_trade_count() == 2


def test_get_trade_count_filtered_by_symbol(repo, mem_db):
    _insert_trade(mem_db, symbol="AAPL")
    _insert_trade(mem_db, symbol="MSFT")
    assert repo.get_trade_count(symbol="AAPL") == 1


# ---------------------------------------------------------------------------
# get_performance_summary
# ---------------------------------------------------------------------------


def test_performance_summary_empty(repo):
    summary = repo.get_performance_summary()
    assert summary.get("total_trades") == 0 or summary == {}


def test_performance_summary_counts(repo, mem_db):
    _insert_trade(mem_db, realized_pnl=50.0)
    _insert_trade(mem_db, realized_pnl=-20.0)
    summary = repo.get_performance_summary()
    assert summary["total_trades"] == 2
    assert summary["winners"] == 1
    assert summary["losers"] == 1


def test_performance_summary_since_filter(repo, mem_db):
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    new_time = datetime.now(timezone.utc)
    _insert_trade(mem_db, realized_pnl=30.0, entry_time=old_time, exit_time=old_time)
    _insert_trade(mem_db, realized_pnl=40.0, entry_time=new_time, exit_time=new_time)

    since = datetime.now(timezone.utc) - timedelta(days=1)
    summary = repo.get_performance_summary(since=since)
    assert summary["total_trades"] == 1
    assert summary["total_pnl"] == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# get_symbol_performance
# ---------------------------------------------------------------------------


def test_get_symbol_performance(repo, mem_db):
    _insert_trade(mem_db, symbol="AAPL", direction="long", realized_pnl=50.0)
    _insert_trade(mem_db, symbol="AAPL", direction="long", realized_pnl=30.0)
    rows = repo.get_symbol_performance()
    aapl = next((r for r in rows if r["symbol"] == "AAPL"), None)
    assert aapl is not None
    assert aapl["total_trades"] == 2
    assert aapl["win_rate_pct"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# get_symbol_rank_history
# ---------------------------------------------------------------------------


def test_get_symbol_rank_history(repo, mem_db):
    cycle_id = _insert_cycle(mem_db)
    now = datetime.now(timezone.utc).isoformat()
    mem_db.execute(
        """
        INSERT INTO cycle_rankings (cycle_id, cycle_timestamp, symbol, direction, rank, score)
        VALUES (?, ?, 'AAPL', 'long', 1, 82.5)
        """,
        (cycle_id, now),
    )
    rows = repo.get_symbol_rank_history("AAPL", "long")
    assert len(rows) == 1
    assert rows[0]["rank"] == 1
    assert rows[0]["score"] == pytest.approx(82.5)


# ---------------------------------------------------------------------------
# get_trades_for_apex
# ---------------------------------------------------------------------------


def test_get_trades_for_apex_returns_joined_rows(repo, mem_db):
    trade_id = _insert_trade(mem_db, symbol="AAPL")
    rows = repo.get_trades_for_apex(limit=10)
    assert any(r["trade_id"] == trade_id for r in rows)


# ---------------------------------------------------------------------------
# get_loss_streaks
# ---------------------------------------------------------------------------


def test_get_loss_streaks(repo, mem_db):
    base = datetime.now(timezone.utc)
    for i in range(3):
        _insert_trade(
            mem_db,
            realized_pnl=-10.0,
            exit_time=base + timedelta(hours=i),
        )
    streaks = repo.get_loss_streaks(min_streak=3)
    assert len(streaks) >= 1
    assert streaks[0]["streak_length"] >= 3


def test_get_loss_streaks_filters_short_streaks(repo, mem_db):
    """A streak of 2 losses should not appear when min_streak=3."""
    base = datetime.now(timezone.utc)
    _insert_trade(mem_db, realized_pnl=-10.0, exit_time=base)
    _insert_trade(mem_db, realized_pnl=-10.0, exit_time=base + timedelta(hours=1))
    streaks = repo.get_loss_streaks(min_streak=3)
    assert len(streaks) == 0


# ---------------------------------------------------------------------------
# get_cycle_count
# ---------------------------------------------------------------------------


def test_get_cycle_count(repo, mem_db):
    assert repo.get_cycle_count() == 0
    _insert_cycle(mem_db)
    assert repo.get_cycle_count() == 1
    _insert_cycle(mem_db)
    assert repo.get_cycle_count() == 2
