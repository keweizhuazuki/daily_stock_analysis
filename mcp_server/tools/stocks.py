# -*- coding: utf-8 -*-
"""
MCP tools for stock data queries.

These tools allow AI clients to search for stocks, get real-time quotes,
and retrieve historical K-line data.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.stock_service import StockService

logger = logging.getLogger(__name__)

# Path to the stock autocomplete index
_STOCKS_INDEX_PATH = Path(os.environ.get("STOCKS_INDEX_PATH", "data/stocks.index.json"))


def _load_stock_index() -> List[Dict[str, Any]]:
    """Load the stock autocomplete index from disk."""
    index_path = _STOCKS_INDEX_PATH
    if not index_path.exists():
        logger.warning(f"Stock index not found at {index_path}")
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "stocks" in data:
            return data["stocks"]
        return []
    except Exception:
        logger.warning(f"Failed to load stock index from {index_path}", exc_info=True)
        return []


def search_stock(query: str, include_quote: bool = False) -> dict:
    """Search for a stock by code or name fragment.

    Searches the stock autocomplete index for matching stocks.
    Supports Chinese name keywords (e.g., "茅台"), partial codes
    (e.g., "600"), and US tickers (e.g., "TSLA").

    Args:
        query: Stock code fragment or name keyword to search for.
        include_quote: Whether to include live price data (slower).
            Default: false.
    """
    if not query or not query.strip():
        return {"matches": [], "total_count": 0, "message": "查询关键词不能为空"}

    q = query.strip().lower()
    index = _load_stock_index()
    matches: List[dict] = []

    for entry in index:
        code = str(entry.get("code", "")).lower()
        name = str(entry.get("name", "")).lower()
        pinyin = str(entry.get("pinyin", "")).lower()
        if q in code or q in name or q in pinyin:
            matches.append({
                "code": entry.get("code", ""),
                "name": entry.get("name", ""),
                "market": entry.get("market", ""),
                "pinyin": entry.get("pinyin", ""),
            })

    # Limit to 20 results
    matches = matches[:20]

    # Optionally enrich with live quotes
    if include_quote and matches:
        stock_service = StockService()
        for m in matches:
            try:
                quote = stock_service.get_realtime_quote(m["code"])
                if quote:
                    m["quote"] = {
                        "price": getattr(quote, "price", None) or quote.get("price"),
                        "change_pct": getattr(quote, "change_pct", None) or quote.get("change_pct"),
                        "volume": getattr(quote, "volume", None) or quote.get("volume"),
                    }
            except Exception:
                pass

    return {
        "matches": matches,
        "total_count": len(matches),
    }


def get_stock_quote(stock_code: str) -> dict:
    """Get real-time quote for a specific stock.

    Returns current price, change percentage, volume, and other
    real-time market data.

    Args:
        stock_code: The stock code. Examples: "600519", "HK00700", "AAPL".
    """
    if not stock_code or not stock_code.strip():
        return {"success": False, "message": "股票代码不能为空"}

    stock_service = StockService()
    try:
        quote = stock_service.get_realtime_quote(stock_code.strip())
        if quote is None:
            return {
                "success": False,
                "stock_code": stock_code.strip(),
                "message": f"无法获取 {stock_code.strip()} 的实时行情",
            }

        # Handle both dataclass and dict return types
        if hasattr(quote, "__dataclass_fields__"):
            result = {
                "success": True,
                "stock_code": getattr(quote, "code", stock_code.strip()),
                "stock_name": getattr(quote, "name", ""),
                "price": getattr(quote, "price", None),
                "change": getattr(quote, "change_amount", None),
                "change_percent": getattr(quote, "change_pct", None),
                "open": getattr(quote, "open_price", None),
                "high": getattr(quote, "high_price", None),
                "low": getattr(quote, "low_price", None),
                "volume": getattr(quote, "volume", None),
                "prev_close": getattr(quote, "prev_close", None),
            }
        else:
            result = {
                "success": True,
                "stock_code": stock_code.strip(),
                "quote": quote,
            }
        return result
    except Exception as e:
        logger.error(f"获取行情失败 {stock_code}: {e}", exc_info=True)
        return {
            "success": False,
            "stock_code": stock_code.strip(),
            "message": f"获取行情失败: {str(e)}",
        }


def get_stock_history(
    stock_code: str,
    period: str = "daily",
    days: int = 30,
) -> dict:
    """Get historical K-line (candlestick) data for a stock.

    Args:
        stock_code: The stock code. Examples: "600519", "HK00700", "AAPL".
        period: Data period — "daily", "weekly", or "monthly". Default: "daily".
        days: Number of trading days to return (max 365). Default: 30.
    """
    if not stock_code or not stock_code.strip():
        return {"success": False, "message": "股票代码不能为空"}

    if period not in ("daily", "weekly", "monthly"):
        return {"success": False, "message": f"不支持的周期: {period}，支持: daily, weekly, monthly"}

    days = max(1, min(days, 365))

    stock_service = StockService()
    try:
        history = stock_service.get_history_data(
            stock_code.strip(),
            period=period,
            days=days,
        )
        if history is None:
            return {
                "success": False,
                "stock_code": stock_code.strip(),
                "message": f"无法获取 {stock_code.strip()} 的历史数据",
            }

        # Normalize response
        if hasattr(history, "data"):
            klines = history.data
        elif isinstance(history, dict):
            klines = history.get("data", history.get("klines", []))
        else:
            klines = list(history) if history else []

        return {
            "success": True,
            "stock_code": stock_code.strip(),
            "period": period,
            "data_points": len(klines) if klines else 0,
            "klines": klines[:days],
        }
    except Exception as e:
        logger.error(f"获取历史数据失败 {stock_code}: {e}", exc_info=True)
        return {
            "success": False,
            "stock_code": stock_code.strip(),
            "message": f"获取历史数据失败: {str(e)}",
        }
