"""
Phase 1 tests — Alpaca broker connection.
Run with: pytest tests/phase1/test_alpaca.py -v
Integration tests require valid Alpaca paper credentials in .env.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ---------------------------------------------------------------------------
# Unit tests (no network — mock the Alpaca SDK)
# ---------------------------------------------------------------------------

class TestAlpacaClientUnit:

    def test_live_trading_guard_raises(self):
        """AlpacaClient must refuse to instantiate when ALPACA_PAPER=False."""
        from core.broker.alpaca import LiveTradingGuardError

        mock_settings = MagicMock()
        mock_settings.ALPACA_PAPER = False

        with patch("core.broker.alpaca.settings", mock_settings):
            from core.broker.alpaca import AlpacaClient
            with pytest.raises(LiveTradingGuardError):
                AlpacaClient()

    def test_ping_returns_true_on_success(self):
        mock_settings = MagicMock()
        mock_settings.ALPACA_PAPER = True
        mock_settings.ALPACA_API_KEY = "fake-key"
        mock_settings.ALPACA_SECRET_KEY = "fake-secret"

        mock_clock = MagicMock()
        mock_client = MagicMock()
        mock_client.get_clock.return_value = mock_clock

        with patch("core.broker.alpaca.settings", mock_settings), \
             patch("core.broker.alpaca.TradingClient", return_value=mock_client):
            from importlib import reload
            import core.broker.alpaca as alpaca_module
            reload(alpaca_module)
            client = alpaca_module.AlpacaClient()
            ok, latency = client.ping()
            assert ok is True
            assert latency >= 0

    def test_ping_returns_false_on_exception(self):
        mock_settings = MagicMock()
        mock_settings.ALPACA_PAPER = True
        mock_settings.ALPACA_API_KEY = "fake-key"
        mock_settings.ALPACA_SECRET_KEY = "fake-secret"

        mock_client = MagicMock()
        mock_client.get_clock.side_effect = ConnectionError("timeout")

        # Reload must happen BEFORE the patch context so the re-import inside
        # reload() doesn't overwrite the patched TradingClient reference.
        from importlib import reload
        import core.broker.alpaca as alpaca_module
        reload(alpaca_module)

        with patch("core.broker.alpaca.settings", mock_settings), \
             patch("core.broker.alpaca.TradingClient", return_value=mock_client):
            client = alpaca_module.AlpacaClient()
            ok, latency = client.ping()
            assert ok is False
            assert latency == -1.0

    def test_is_market_open_returns_bool(self):
        mock_settings = MagicMock()
        mock_settings.ALPACA_PAPER = True
        mock_settings.ALPACA_API_KEY = "fake-key"
        mock_settings.ALPACA_SECRET_KEY = "fake-secret"

        mock_clock = MagicMock()
        mock_clock.is_open = True
        mock_client = MagicMock()
        mock_client.get_clock.return_value = mock_clock

        # Reload must happen BEFORE the patch context so the re-import inside
        # reload() doesn't overwrite the patched TradingClient reference.
        from importlib import reload
        import core.broker.alpaca as alpaca_module
        reload(alpaca_module)

        with patch("core.broker.alpaca.settings", mock_settings), \
             patch("core.broker.alpaca.TradingClient", return_value=mock_client):
            client = alpaca_module.AlpacaClient()
            result = client.is_market_open()
            assert result is True


# ---------------------------------------------------------------------------
# Integration tests (require valid credentials in .env)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAlpacaClientIntegration:
    """Requires valid Alpaca paper credentials. Skip with: pytest -m 'not integration'"""

    @pytest.fixture(scope="class")
    def client(self):
        from core.broker.alpaca import AlpacaClient
        return AlpacaClient()

    def test_ping_succeeds(self, client):
        ok, latency = client.ping()
        assert ok is True
        assert latency > 0

    def test_get_account_returns_expected_keys(self, client):
        account = client.get_account()
        for key in ["equity", "buying_power", "status", "currency"]:
            assert key in account

    def test_account_equity_is_positive(self, client):
        account = client.get_account()
        assert account["equity"] > 0

    def test_get_clock_returns_expected_keys(self, client):
        clock = client.get_clock()
        for key in ["timestamp", "is_open", "next_open", "next_close"]:
            assert key in clock

    def test_is_market_open_returns_bool(self, client):
        result = client.is_market_open()
        assert isinstance(result, bool)
