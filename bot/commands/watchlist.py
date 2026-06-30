# -*- coding: utf-8 -*-
"""
===================================
自选股管理命令
===================================

通过机器人对话管理自选股，支持添加、删除、查看自选股列表。
用法：
    /wl                    — 查看自选股列表
    /wl add <代码>          — 添加股票到自选
    /wl remove <代码>       — 从自选删除股票
    /wl help               — 显示帮助
"""

from typing import List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse
from src.config import Config
from src.services.system_config_service import SystemConfigService
from src.services.watchlist_service import WatchlistError, WatchlistService


class WatchlistCommand(BotCommand):
    """机器人自选股管理命令"""

    @property
    def name(self) -> str:
        return "watchlist"

    @property
    def aliases(self) -> List[str]:
        return ["wl", "自选", "addstock", "removestock", "watchlist"]

    @property
    def description(self) -> str:
        return "管理自选股列表 — 添加/删除/查看自选股"

    @property
    def usage(self) -> str:
        return "/wl [add <代码> | remove <代码>]"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """执行自选股管理命令"""
        wl = self._get_watchlist_service()

        if not args or (len(args) == 1 and args[0] in ("list", "列表", "查看")):
            return self._handle_list(wl)

        action = args[0].lower()
        if action in ("add", "添加", "加入", "增加", "+"):
            return self._handle_add(wl, args[1:])
        elif action in ("remove", "rm", "del", "delete", "删除", "移除", "去掉", "-"):
            return self._handle_remove(wl, args[1:])
        elif action in ("help", "帮助", "?", "h"):
            return self._handle_help()
        else:
            # Treat bare stock code as "add"
            return self._handle_add(wl, args)

    # ------------------------------------------------------------------
    # Sub-command handlers
    # ------------------------------------------------------------------

    def _handle_list(self, wl: WatchlistService) -> BotResponse:
        codes = wl.get_codes()
        if not codes:
            return BotResponse.text_response("📋 自选股列表为空。使用 `/wl add <代码>` 添加股票。")
        lines = ["📋 **自选股列表**", ""]
        for i, code in enumerate(codes, 1):
            lines.append(f"{i}. `{code}`")
        lines.append("")
        lines.append(f"共 {len(codes)} 只股票")
        return BotResponse.markdown_response("\n".join(lines))

    def _handle_add(self, wl: WatchlistService, args: List[str]) -> BotResponse:
        if not args:
            return BotResponse.text_response("⚠️ 请提供股票代码。用法: `/wl add <代码>`")

        code = args[0].strip()
        try:
            codes = wl.add_code(code)
            return BotResponse.markdown_response(
                f"✅ `{code}` 已加入自选股\n\n当前自选共 **{len(codes)}** 只股票"
            )
        except WatchlistError as e:
            return BotResponse.text_response(f"❌ {e.message}")

    def _handle_remove(self, wl: WatchlistService, args: List[str]) -> BotResponse:
        if not args:
            return BotResponse.text_response("⚠️ 请提供股票代码。用法: `/wl remove <代码>`")

        code = args[0].strip()
        try:
            codes = wl.remove_code(code)
            return BotResponse.markdown_response(
                f"✅ `{code}` 已从自选股移除\n\n当前自选共 **{len(codes)}** 只股票"
            )
        except WatchlistError as e:
            return BotResponse.text_response(f"❌ {e.message}")

    def _handle_help(self) -> BotResponse:
        lines = [
            "📋 **自选股管理 — 使用帮助**",
            "",
            "• `/wl` — 查看自选股列表",
            "• `/wl add <代码>` — 添加股票到自选",
            "  - A股: `/wl add 600519` (贵州茅台)",
            "  - 港股: `/wl add HK00700` (腾讯)",
            "  - 美股: `/wl add AAPL` (苹果)",
            "• `/wl remove <代码>` — 从自选删除股票",
            "• `/wl help` — 显示此帮助",
            "",
            "💡 也可以直接输入 `/addstock <代码>` 快速添加",
            "💡 或 `/removestock <代码>` 快速删除",
        ]
        return BotResponse.markdown_response("\n".join(lines))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_watchlist_service() -> WatchlistService:
        config = Config.get_instance()
        service = SystemConfigService(config)
        return WatchlistService(service)
