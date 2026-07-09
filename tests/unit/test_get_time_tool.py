"""Tests for get_current_time tool output."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from config.schema import TenantConfig
from tools.platform.get_time import create_time_tool


@pytest.mark.asyncio
async def test_get_current_time_returns_urdu_date_and_day():
    config = TenantConfig.model_validate({"tenant": {"id": "t1", "slug": "test", "name": "Test"}})
    tool = create_time_tool(config)
    fn = getattr(tool, "fnc", None) or getattr(tool, "_fnc", None) or tool

    mock_now = MagicMock()
    mock_now.weekday.return_value = 4  # جمعہ
    mock_now.month = 4
    mock_now.day = 17
    mock_now.year = 2026
    mock_now.strftime.return_value = "21:45"
    mock_tz = MagicMock()

    with patch("pytz.timezone", return_value=mock_tz), patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        result = await fn(MagicMock())

    assert result == "آج جمعہ ہے، 17 اپریل 2026۔ اس وقت 21:45 بجے ہیں (مقامی وقت)۔"
