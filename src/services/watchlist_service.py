# -*- coding: utf-8 -*-
"""
===================================
自选股 Watchlist 服务层
===================================

职责：
1. 封装自选股（STOCK_LIST）的读取、添加、删除逻辑
2. 提供股票代码验证和规范化
3. 被 REST API 端点和 MCP 工具共享使用
"""

from __future__ import annotations

import logging
import re
from typing import List

from data_provider.base import normalize_stock_code

logger = logging.getLogger(__name__)

# Stock code validation patterns (aligned with frontend validateStockCode)
_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"                              # A-share 6-digit
    r"|(?:SH|SZ|BJ)\d{6}"                     # exchange-prefixed A-share
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"                # exchange-suffixed A-share
    r"|\d{1,5}\.HK"                           # HK suffix format
    r"|HK\d{1,5}"                             # HK prefix format
    r"|\d{5}"                                 # bare 5-digit HK code
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"         # US ticker
    r")$",
    re.IGNORECASE,
)


class WatchlistError(Exception):
    """Raised when a watchlist operation fails for a known, user-facing reason."""

    def __init__(self, error: str, message: str):
        super().__init__(message)
        self.error = error
        self.message = message


class WatchlistService:
    """Service for managing the stock watchlist (STOCK_LIST).

    Delegates persistence to SystemConfigService.
    """

    def __init__(self, system_config_service):
        """Initialize with a SystemConfigService instance.

        Args:
            system_config_service: An instance of
                ``src.services.system_config_service.SystemConfigService``.
        """
        self._config = system_config_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_codes(self) -> List[str]:
        """Return the current watchlist stock codes as-is (no normalization)."""
        config_data = self._config.get_config(include_schema=False)
        stock_list_str = ""
        for item in config_data.get("items", []):
            if item.get("key") == "STOCK_LIST":
                stock_list_str = str(item.get("value", ""))
                break
        return [c.strip() for c in stock_list_str.split(",") if c.strip()]

    def add_code(self, code: str) -> List[str]:
        """Validate *code* and append it to the watchlist if not already present.

        Returns the updated list of codes.
        """
        validated = self.validate_code(code)
        codes = self.get_codes()
        existing_keys = [self.match_key(c) for c in codes]
        if self.match_key(validated) not in existing_keys:
            codes.append(code.strip())
            self._write_codes(codes)
        return codes

    def remove_code(self, code: str) -> List[str]:
        """Validate *code* and remove it from the watchlist if present.

        Returns the updated list of codes.
        """
        validated = self.validate_code(code)
        codes = self.get_codes()
        existing_keys = [self.match_key(c) for c in codes]
        requested_key = self.match_key(validated)
        if requested_key in existing_keys:
            idx = existing_keys.index(requested_key)
            codes.pop(idx)
            self._write_codes(codes)
        return codes

    @staticmethod
    def validate_code(code: str) -> str:
        """Validate stock code format and return canonical normalized form.

        Raises:
            WatchlistError: If the code is empty or does not match any
                supported format.
        """
        stripped = code.strip()
        if not stripped:
            raise WatchlistError(
                error="invalid_stock_code",
                message="股票代码不能为空",
            )
        if not _STOCK_CODE_RE.match(stripped):
            raise WatchlistError(
                error="invalid_stock_code",
                message=f"'{stripped}' 不是合法的股票代码格式",
            )
        return normalize_stock_code(stripped)

    @staticmethod
    def match_key(code: str) -> str:
        """Return the equivalence key used for watchlist add/remove matching."""
        normalized = normalize_stock_code(code.strip())
        if re.fullmatch(r"\d{5}", normalized):
            return f"HK{normalized}"
        return normalized.upper()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_codes(self, codes: List[str]) -> None:
        """Persist stock codes to STOCK_LIST as-is (no normalization)."""
        config_data = self._config.get_config(include_schema=False)
        config_version = config_data.get("config_version", "")
        self._config.update(
            config_version=config_version,
            items=[{"key": "STOCK_LIST", "value": ",".join(codes)}],
            mask_token="******",
            reload_now=True,
        )
