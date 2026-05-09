from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.models import Direction
from core.trading.reconciliation import (
    BrokerReconciler,
    broker_position_map,
    detect_position_mismatch,
    local_position_map,
)


def _settings(paper=True, auto=False, block=True):
    return SimpleNamespace(
        ALPACA_PAPER=paper,
        OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS=auto,
        OLYMPUS_BLOCK_ENTRIES_ON_BROKER_MISMATCH=block,
    )


def _position(symbol="AAPL", direction=Direction.LONG, size=10):
    return SimpleNamespace(symbol=symbol, direction=direction, size=size)


def test_detect_position_mismatch_exact_match_is_clean():
    local = {"AAPL": {"side": "long", "qty": 10}}
    broker = {"AAPL": {"side": "long", "qty": 10}}

    result = detect_position_mismatch(local, broker)

    assert result.mismatch is False
    assert result.reason == "clean"


def test_detect_position_mismatch_broker_only_position():
    result = detect_position_mismatch({}, {"AAPL": {"side": "long", "qty": 10}})

    assert result.mismatch is True
    assert result.reason == "broker_only_position"
    assert result.entries_blocked is True


def test_detect_position_mismatch_local_only_position():
    result = detect_position_mismatch({"AAPL": {"side": "long", "qty": 10}}, {})

    assert result.mismatch is True
    assert result.reason == "local_only_position"


def test_detect_position_mismatch_quantity_mismatch():
    local = {"AAPL": {"side": "long", "qty": 10}}
    broker = {"AAPL": {"side": "long", "qty": 11}}

    result = detect_position_mismatch(local, broker)

    assert result.mismatch is True
    assert result.reason == "quantity_or_side_mismatch"


def test_position_maps_normalize_side_and_quantity():
    assert local_position_map([_position("aapl", Direction.SHORT, 5)]) == {
        "AAPL": {"side": "short", "qty": 5}
    }
    assert broker_position_map([{"symbol": "aapl", "side": "buy", "qty": "-5"}]) == {
        "AAPL": {"side": "long", "qty": 5}
    }


def test_auto_repair_runs_only_when_paper_and_enabled():
    alpaca = MagicMock()
    alpaca.get_positions.return_value = [{"symbol": "AAPL", "side": "long", "qty": 10}]
    alpaca.get_open_orders.return_value = [{"symbol": "AAPL", "side": "buy"}]
    alpaca.cancel_all_orders.return_value = True
    alpaca.close_all_positions.return_value = True

    reconciler = BrokerReconciler(alpaca, _settings(paper=True, auto=True))
    result = reconciler.check_and_repair([])

    assert result.repair_attempted is True
    assert result.repair_succeeded is True
    alpaca.cancel_all_orders.assert_called_once()
    alpaca.close_all_positions.assert_called_once_with(cancel_orders=True)


def test_auto_repair_forbidden_when_not_paper():
    alpaca = MagicMock()
    alpaca.get_positions.return_value = [{"symbol": "AAPL", "side": "long", "qty": 10}]
    alpaca.get_open_orders.return_value = []

    reconciler = BrokerReconciler(alpaca, _settings(paper=False, auto=True))

    with pytest.raises(RuntimeError):
        reconciler.check_and_repair([])
