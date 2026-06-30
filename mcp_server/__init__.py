# -*- coding: utf-8 -*-
"""
===================================
MCP Server - DSA Watchlist & Stock Tools
===================================

Exposes stock watchlist management, stock data query, and analysis
triggering as MCP tools so AI clients (Claude Desktop, Claude Code,
Cursor, etc.) can interact with the Daily Stock Analysis system.

Usage (stdio - Claude Desktop compatible)::

    python -m mcp_server

Usage (SSE - for remote / co-hosted deployments)::

    MCP_SERVER_TRANSPORT=sse python -m mcp_server
"""

from mcp_server.server import create_server, run_server

__all__ = ["create_server", "run_server"]
