# -*- coding: utf-8 -*-
"""
MCP tools for watchlist (自选股) management.

These tools allow AI clients to list, add, and remove stocks
from the user's watchlist.
"""

from __future__ import annotations

import logging
from typing import List

from src.config import Config
from src.services.system_config_service import SystemConfigService
from src.services.watchlist_service import WatchlistError, WatchlistService

logger = logging.getLogger(__name__)


def _get_watchlist_service() -> WatchlistService:
    """Build a WatchlistService wired to the live SystemConfigService."""
    config = Config.get_instance()
    service = SystemConfigService(config)
    return WatchlistService(service)


def list_watchlist() -> dict:
    """List all stocks currently in the watchlist (自选股).

    Returns the complete list of stock codes the user is tracking.
    """
    wl = _get_watchlist_service()
    codes = wl.get_codes()
    return {
        "stock_codes": codes,
        "count": len(codes),
    }


def add_stock(stock_code: str) -> dict:
    """Add a stock to the watchlist.

    Supports A-share (6-digit like 600519), HK (HK00700 or 00700.HK),
    and US tickers (AAPL, TSLA).

    Args:
        stock_code: The stock code to add. Examples: "600519", "HK00700", "AAPL".
    """
    wl = _get_watchlist_service()
    try:
        codes = wl.add_code(stock_code)
        return {
            "success": True,
            "stock_code": stock_code.strip(),
            "message": f"已加入自选: {stock_code.strip()}",
            "current_count": len(codes),
        }
    except WatchlistError as e:
        return {
            "success": False,
            "stock_code": stock_code.strip(),
            "message": e.message,
            "error": e.error,
        }


def remove_stock(stock_code: str) -> dict:
    """Remove a stock from the watchlist.

    Args:
        stock_code: The stock code to remove. Examples: "600519", "HK00700", "AAPL".
    """
    wl = _get_watchlist_service()
    try:
        codes = wl.remove_code(stock_code)
        return {
            "success": True,
            "stock_code": stock_code.strip(),
            "message": f"已移除自选: {stock_code.strip()}",
            "current_count": len(codes),
        }
    except WatchlistError as e:
        return {
            "success": False,
            "stock_code": stock_code.strip(),
            "message": e.message,
            "error": e.error,
        }
