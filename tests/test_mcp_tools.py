# -*- coding: utf-8 -*-
"""Unit tests for MCP server tool functions."""

import pytest

from src.services.watchlist_service import WatchlistError, WatchlistService


# ---------------------------------------------------------------------------
# Fake / mock helpers
# ---------------------------------------------------------------------------

class FakeSystemConfigService:
    """In-memory SystemConfigService stand-in for testing WatchlistService."""

    def __init__(self, stock_list: str = "") -> None:
        self.stock_list = stock_list
        self.config_version = "cfg-test-v1"
        self.update_calls: list[str] = []

    def get_config(self, include_schema: bool = False) -> dict:
        return {
            "config_version": self.config_version,
            "items": [{"key": "STOCK_LIST", "value": self.stock_list}],
        }

    def update(self, **kwargs) -> None:
        items = kwargs.get("items", [])
        for item in items:
            if item.get("key") == "STOCK_LIST":
                self.stock_list = item.get("value", "")
        self.update_calls.append(self.stock_list)


def _make_wl(codes: str = "") -> WatchlistService:
    return WatchlistService(FakeSystemConfigService(codes))


# ---------------------------------------------------------------------------
# WatchlistService tests
# ---------------------------------------------------------------------------

class TestWatchlistService:
    """Tests for the core WatchlistService (shared by REST + MCP)."""

    def test_get_codes_empty(self):
        wl = _make_wl("")
        assert wl.get_codes() == []

    def test_get_codes_has_entries(self):
        wl = _make_wl("600519,000858")
        assert wl.get_codes() == ["600519", "000858"]

    def test_get_codes_trims_whitespace(self):
        wl = _make_wl(" 600519 , 000858 ")
        assert wl.get_codes() == ["600519", "000858"]

    def test_add_code_new(self):
        wl = _make_wl("600519")
        codes = wl.add_code("000858")
        assert "000858" in codes
        assert "600519" in codes
        assert len(codes) == 2

    def test_add_code_duplicate_does_not_double_count(self):
        wl = _make_wl("600519")
        codes = wl.add_code("600519")
        assert codes == ["600519"]

    def test_add_code_hk_variant_detected_as_duplicate(self):
        """HK00700 and 00700 should be treated as the same stock."""
        wl = _make_wl("00700")
        codes = wl.add_code("HK00700")
        assert len(codes) == 1

    def test_remove_code_existing(self):
        wl = _make_wl("600519,000858")
        codes = wl.remove_code("000858")
        assert codes == ["600519"]

    def test_remove_code_missing_is_noop(self):
        wl = _make_wl("600519")
        codes = wl.remove_code("000001")
        assert codes == ["600519"]

    def test_remove_code_hk_variant(self):
        wl = _make_wl("00700")
        codes = wl.remove_code("HK00700")
        assert codes == []

    def test_remove_code_case_insensitive_us(self):
        wl = _make_wl("aapl")
        codes = wl.remove_code("AAPL")
        assert codes == []

    # -- validation --------------------------------------------------------

    def test_validate_code_empty_raises(self):
        with pytest.raises(WatchlistError) as exc:
            WatchlistService.validate_code("")
        assert exc.value.error == "invalid_stock_code"

    def test_validate_code_invalid_format_raises(self):
        with pytest.raises(WatchlistError) as exc:
            WatchlistService.validate_code("garbage!!!")
        assert exc.value.error == "invalid_stock_code"

    def test_validate_code_valid_ashare(self):
        result = WatchlistService.validate_code("600519")
        assert result == "600519"

    def test_validate_code_valid_hk_prefixed(self):
        result = WatchlistService.validate_code("HK00700")
        assert "00700" in result

    def test_validate_code_valid_us_ticker(self):
        result = WatchlistService.validate_code("AAPL")
        assert result.upper() == "AAPL"

    # -- match_key ---------------------------------------------------------

    def test_match_key_hk_bare_5digit(self):
        assert WatchlistService.match_key("00700") == "HK00700"

    def test_match_key_ashare_uppercase(self):
        key = WatchlistService.match_key("600519")
        assert key == "600519"


# ---------------------------------------------------------------------------
# MCP tool function tests (import via mcp_server.tools)
# ---------------------------------------------------------------------------

class TestMcpWatchlistTools:
    """Test MCP tool functions in isolation using a monkeypatched service."""

    def test_list_watchlist_empty(self, monkeypatch):
        from mcp_server.tools.watchlist import list_watchlist

        def _fake_get_wl():
            return _make_wl("")

        monkeypatch.setattr(
            "mcp_server.tools.watchlist._get_watchlist_service", _fake_get_wl
        )
        result = list_watchlist()
        assert result["count"] == 0
        assert result["stock_codes"] == []

    def test_list_watchlist_with_entries(self, monkeypatch):
        from mcp_server.tools.watchlist import list_watchlist

        def _fake_get_wl():
            return _make_wl("600519,000858")

        monkeypatch.setattr(
            "mcp_server.tools.watchlist._get_watchlist_service", _fake_get_wl
        )
        result = list_watchlist()
        assert result["count"] == 2
        assert "600519" in result["stock_codes"]

    def test_add_stock_success(self, monkeypatch):
        from mcp_server.tools.watchlist import add_stock

        def _fake_get_wl():
            return _make_wl("")

        monkeypatch.setattr(
            "mcp_server.tools.watchlist._get_watchlist_service", _fake_get_wl
        )
        result = add_stock("600519")
        assert result["success"] is True
        assert result["current_count"] == 1

    def test_add_stock_invalid_code(self, monkeypatch):
        from mcp_server.tools.watchlist import add_stock

        def _fake_get_wl():
            return _make_wl("")

        monkeypatch.setattr(
            "mcp_server.tools.watchlist._get_watchlist_service", _fake_get_wl
        )
        result = add_stock("!!!bad!!!")
        assert result["success"] is False

    def test_remove_stock_success(self, monkeypatch):
        from mcp_server.tools.watchlist import remove_stock

        def _fake_get_wl():
            return _make_wl("600519")

        monkeypatch.setattr(
            "mcp_server.tools.watchlist._get_watchlist_service", _fake_get_wl
        )
        result = remove_stock("600519")
        assert result["success"] is True
        assert result["current_count"] == 0
