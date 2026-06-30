# -*- coding: utf-8 -*-
"""
MCP tools for triggering AI-powered stock analysis.

These tools allow AI clients to kick off the analysis pipeline
and check on task status.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from src.config import Config
from src.services.system_config_service import SystemConfigService
from src.services.watchlist_service import WatchlistService
from src.services.analysis_service import AnalysisService
from src.services.task_queue import TaskQueue

logger = logging.getLogger(__name__)


def trigger_analysis(stock_codes: Optional[List[str]] = None) -> dict:
    """Trigger AI-powered analysis for stock(s).

    If no stock_codes are provided, analyzes the entire watchlist.
    Analysis includes technical indicators, AI decision dashboard,
    and battle plan (entry/exit points, stop-loss).

    Args:
        stock_codes: Optional list of stock codes to analyze.
            If empty or not provided, analyzes all stocks in the watchlist.
            Examples: ["600519"], ["600519", "000858", "AAPL"].
    """
    config = Config.get_instance()
    service = SystemConfigService(config)
    wl = WatchlistService(service)

    # Resolve stock list
    if not stock_codes:
        codes = wl.get_codes()
    else:
        codes = []
        for c in stock_codes:
            try:
                validated = WatchlistService.validate_code(c)
                codes.append(validated)
            except Exception as e:
                return {
                    "success": False,
                    "message": f"无效的股票代码 '{c}': {e}",
                }

    if not codes:
        return {
            "success": False,
            "message": "自选股列表为空，请先添加股票或指定 stock_codes 参数",
        }

    # Batch limit
    if len(codes) > 50:
        return {
            "success": False,
            "message": f"单次最多分析 50 只股票，当前 {len(codes)} 只",
        }

    try:
        analysis_service = AnalysisService()

        # Submit each stock as a task
        task_ids = []
        for code in codes:
            try:
                result = analysis_service.analyze_stock(code)
                task_ids.append({
                    "stock_code": code,
                    "query_id": getattr(result, "query_id", None) or getattr(result, "task_id", "unknown"),
                })
            except Exception as e:
                task_ids.append({
                    "stock_code": code,
                    "error": str(e),
                })

        return {
            "success": True,
            "message": f"已提交 {len(codes)} 只股票的分析任务",
            "tasks": task_ids,
        }
    except Exception as e:
        logger.error(f"触发分析失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"触发分析失败: {str(e)}",
        }


def get_analysis_status(query_id: str) -> dict:
    """Check the status of a previously triggered analysis task.

    Args:
        query_id: The task/query ID returned by trigger_analysis.
    """
    if not query_id or not query_id.strip():
        return {"success": False, "message": "query_id 不能为空"}

    try:
        task_queue = TaskQueue()
        task = task_queue.get_task(query_id.strip())

        if task is None:
            return {
                "success": False,
                "query_id": query_id.strip(),
                "message": f"未找到任务 {query_id.strip()}",
            }

        return {
            "success": True,
            "query_id": query_id.strip(),
            "status": getattr(task, "status", "unknown"),
            "progress": getattr(task, "progress", None),
            "result": getattr(task, "result", None),
        }
    except Exception as e:
        logger.error(f"查询分析状态失败 {query_id}: {e}", exc_info=True)
        return {
            "success": False,
            "query_id": query_id.strip(),
            "message": f"查询失败: {str(e)}",
        }
