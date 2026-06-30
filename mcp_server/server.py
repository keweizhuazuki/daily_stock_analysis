# -*- coding: utf-8 -*-
"""
===================================
MCP Server — FastMCP instance + tool registration
===================================

Creates a FastMCP server named "dsa-watchlist" and registers all
stock watchlist, data, and analysis tools.

When run as ``python -m mcp_server``, starts with the transport
configured via ``MCP_SERVER_TRANSPORT`` (default: stdio).
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from src.config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("dsa-watchlist")


# ---------------------------------------------------------------------------
# Tool registration — watchlist
# ---------------------------------------------------------------------------

from mcp_server.tools.watchlist import list_watchlist as _list_watchlist
from mcp_server.tools.watchlist import add_stock as _add_stock
from mcp_server.tools.watchlist import remove_stock as _remove_stock

mcp.tool()(_list_watchlist)
mcp.tool()(_add_stock)
mcp.tool()(_remove_stock)


# ---------------------------------------------------------------------------
# Tool registration — stock data
# ---------------------------------------------------------------------------

from mcp_server.tools.stocks import search_stock as _search_stock
from mcp_server.tools.stocks import get_stock_quote as _get_stock_quote
from mcp_server.tools.stocks import get_stock_history as _get_stock_history

mcp.tool()(_search_stock)
mcp.tool()(_get_stock_quote)
mcp.tool()(_get_stock_history)


# ---------------------------------------------------------------------------
# Tool registration — analysis
# ---------------------------------------------------------------------------

from mcp_server.tools.analysis import trigger_analysis as _trigger_analysis
from mcp_server.tools.analysis import get_analysis_status as _get_analysis_status

mcp.tool()(_trigger_analysis)
mcp.tool()(_get_analysis_status)


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

def _ensure_config_loaded() -> None:
    """Make sure the Config singleton and .env are loaded before use."""
    Config.get_instance()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_server() -> FastMCP:
    """Return the configured FastMCP server instance.

    Useful for embedding the MCP server inside another process
    (e.g., FastAPI lifespan).
    """
    _ensure_config_loaded()
    return mcp


def run_server() -> None:
    """Start the MCP server with the configured transport.

    Reads ``MCP_SERVER_TRANSPORT`` from the Config instance.
    Defaults to ``"stdio"`` (for Claude Desktop compatibility).
    """
    _ensure_config_loaded()
    config = Config.get_instance()
    transport = config.mcp_server_transport or "stdio"

    logger.info("Starting MCP server (transport=%s)", transport)

    if transport == "sse":
        mcp.run(
            transport="sse",
            host=config.mcp_server_host or "127.0.0.1",
            port=config.mcp_server_port or 8080,
        )
    else:
        mcp.run(transport="stdio")


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # stderr so stdout stays clean for stdio transport
    )
    run_server()
