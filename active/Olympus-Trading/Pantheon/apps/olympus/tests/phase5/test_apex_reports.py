"""
Phase 5 - Apex report generation tests.
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.memory.database import Database
from core.memory.repository import Repository
from core.reporting.apex_reports import ApexReportGenerator


def _insert_cycle(db: Database, cycle_time: datetime, top_long: str, top_short: str) -> str:
    cycle_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO ranking_cycles (
            cycle_id, cycle_timestamp, universe_size, scored_count,
            error_count, duration_seconds, top_longs_json, top_shorts_json, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cycle_id,
            cycle_time.isoformat(),
            185,
            181,
            4,
            3.1,
            json.dumps([{"symbol": top_long, "score": 90.0, "rank": 1}]),
            json.dumps([{"symbol": top_short, "score": 10.0, "rank": 1}]),
            cycle_time.isoformat(),
        ),
    )
    db.execute(
        """
        INSERT INTO cycle_rankings (cycle_id, cycle_timestamp, symbol, direction, rank, score)
        VALUES (?, ?, ?, 'long', 1, 90.0)
        """,
        (cycle_id, cycle_time.isoformat(), top_long),
    )
    db.execute(
        """
        INSERT INTO cycle_rankings (cycle_id, cycle_timestamp, symbol, direction, rank, score)
        VALUES (?, ?, ?, 'short', 1, 10.0)
        """,
        (cycle_id, cycle_time.isoformat(), top_short),
    )
    return cycle_id


def _insert_trade(
    db: Database,
    *,
    symbol: str,
    direction: str,
    regime: str,
    cycle_id: str,
    exit_time: datetime,
    realized_pnl: float,
    r_multiple: float,
    rank_at_entry: int,
    score_at_entry: float,
    exit_reason: str = "target",
) -> str:
    trade_id = str(uuid.uuid4())
    entry_time = exit_time - timedelta(minutes=20)
    position_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO trades (
            trade_id, position_id, symbol, direction,
            entry_price, exit_price, stop_price, target_price,
            size, entry_time, exit_time, hold_duration_minutes,
            realized_pnl, r_multiple, exit_reason, status, regime,
            rank_at_entry, score_at_entry, rank_at_exit, score_at_exit,
            entry_cycle_id, exit_cycle_id, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'closed', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            position_id,
            symbol,
            direction,
            100.0,
            101.0,
            99.0,
            104.0,
            10,
            entry_time.isoformat(),
            exit_time.isoformat(),
            20.0,
            realized_pnl,
            r_multiple,
            exit_reason,
            regime,
            rank_at_entry,
            score_at_entry,
            rank_at_entry + 1,
            score_at_entry - 5.0,
            cycle_id,
            None,
            exit_time.isoformat(),
        ),
    )
    db.execute(
        """
        INSERT INTO trade_features (
            trade_id, symbol, roc_5, roc_10, roc_20, acceleration,
            rvol_at_entry, vwap_deviation_at_entry, range_position_at_entry,
            raw_score, score_at_entry, close_at_entry, volume_at_entry,
            vwap_at_entry, atr_at_entry, high_20, low_20, bar_count_used,
            captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            symbol,
            0.5,
            1.0,
            2.0,
            0.2,
            1.5,
            0.01,
            0.75,
            score_at_entry,
            score_at_entry,
            100.0,
            1_000_000.0,
            100.1,
            1.2,
            105.0,
            95.0,
            20,
            entry_time.isoformat(),
        ),
    )
    return trade_id


def _insert_event(db: Database, event_time: datetime, event_type: str, metadata: dict) -> None:
    db.execute(
        """
        INSERT INTO system_events (
            event_time, event_type, symbol, description, metadata_json
        ) VALUES (?, ?, NULL, ?, ?)
        """,
        (
            event_time.isoformat(),
            event_type,
            f"{event_type} event",
            json.dumps(metadata),
        ),
    )


def _build_fixture_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "apex_reports.db"
    db = Database(db_path)
    db.initialize()

    cycle_time = datetime(2026, 4, 23, 15, 0, tzinfo=timezone.utc)
    cycle_id = _insert_cycle(db, cycle_time, "AAPL", "TSLA")

    _insert_trade(
        db,
        symbol="AAPL",
        direction="long",
        regime="trend_up",
        cycle_id=cycle_id,
        exit_time=datetime(2026, 4, 23, 16, 0, tzinfo=timezone.utc),
        realized_pnl=120.0,
        r_multiple=1.8,
        rank_at_entry=2,
        score_at_entry=88.0,
    )
    _insert_trade(
        db,
        symbol="TSLA",
        direction="short",
        regime="mixed",
        cycle_id=cycle_id,
        exit_time=datetime(2026, 4, 23, 17, 0, tzinfo=timezone.utc),
        realized_pnl=-45.0,
        r_multiple=-0.7,
        rank_at_entry=6,
        score_at_entry=22.0,
        exit_reason="stop",
    )
    _insert_trade(
        db,
        symbol="TSLA",
        direction="short",
        regime="mixed",
        cycle_id=cycle_id,
        exit_time=datetime(2026, 4, 23, 18, 0, tzinfo=timezone.utc),
        realized_pnl=-30.0,
        r_multiple=-0.4,
        rank_at_entry=7,
        score_at_entry=24.0,
        exit_reason="rotation",
    )

    _insert_event(
        db,
        datetime(2026, 4, 23, 15, 5, tzinfo=timezone.utc),
        "cycle_diagnostics",
        {"regime": {"name": "mixed"}},
    )
    _insert_event(
        db,
        datetime(2026, 4, 23, 18, 5, tzinfo=timezone.utc),
        "broker_mismatch",
        {"mismatch": True},
    )
    db.close()
    return db_path


def test_generate_daily_report_persists_structured_payload(tmp_path):
    db_path = _build_fixture_db(tmp_path)
    generator = ApexReportGenerator(db_path=db_path)

    result = generator.generate("daily_performance", report_date=date(2026, 4, 23))

    assert result is not None
    db = Database(db_path)
    row = db.query_one("SELECT * FROM apex_reports WHERE report_type = 'daily_performance'")
    assert row is not None
    payload = json.loads(row["content_json"])
    assert payload["meta"]["schema_version"] == 1
    assert payload["performance"]["trade_count"] == 3
    assert "risk" in payload
    assert "ranking" in payload
    assert "recommendations" in payload
    db.close()


def test_generate_is_idempotent_for_same_window(tmp_path):
    db_path = _build_fixture_db(tmp_path)
    generator = ApexReportGenerator(db_path=db_path)

    first = generator.generate("risk_watch", report_date=date(2026, 4, 23))
    second = generator.generate("risk_watch", report_date=date(2026, 4, 23))

    assert first is not None
    assert second is not None
    db = Database(db_path)
    row = db.query_one("SELECT COUNT(*) AS n FROM apex_reports WHERE report_type = 'risk_watch'")
    assert row["n"] == 1
    db.close()


def test_repository_exposes_apex_report_queries(tmp_path):
    db_path = _build_fixture_db(tmp_path)
    generator = ApexReportGenerator(db_path=db_path)
    generator.generate("daily_performance", report_date=date(2026, 4, 23))
    generator.generate("weekly_performance", report_date=date(2026, 4, 23))
    generator.generate("ranking_behavior", report_date=date(2026, 4, 23))

    db = Database(db_path)
    repo = Repository(db)
    latest = repo.get_latest_apex_report("daily_performance")
    bundle = repo.get_latest_apex_summary_bundle()
    unconsumed = repo.get_unconsumed_apex_reports(limit=10)

    assert latest is not None
    assert latest["content"]["meta"]["report_type"] == "daily_performance"
    assert bundle["weekly_performance"] is not None
    assert len(unconsumed) == 3
    db.close()


def test_generate_empty_window_is_valid(tmp_path):
    db_path = _build_fixture_db(tmp_path)
    generator = ApexReportGenerator(db_path=db_path)

    result = generator.generate("daily_performance", report_date=date(2026, 4, 29))

    assert result is not None
    db = Database(db_path)
    row = db.query_one(
        "SELECT content_json FROM apex_reports WHERE report_type = 'daily_performance' ORDER BY generated_at DESC LIMIT 1"
    )
    payload = json.loads(row["content_json"])
    assert payload["performance"]["trade_count"] == 0
    db.close()
