"""
get_current_time tool: returns the current date/time in the tenant's office
timezone (transfer.timezone, default Asia/Karachi), spoken in Urdu.
"""

from __future__ import annotations

from livekit.agents import RunContext, function_tool

from config.schema import TenantConfig
from tools.platform.escalate import DEFAULT_TZ


def create_time_tool(config: TenantConfig, **kwargs):
    """Factory: creates a get_current_time function_tool."""
    tz_name = (getattr(config.transfer, "timezone", None) or DEFAULT_TZ).strip() or DEFAULT_TZ

    @function_tool(name="get_current_time")
    async def get_current_time(context: RunContext) -> str:
        """موجودہ تاریخ اور وقت بتائیں۔ Get the current date and time."""
        from datetime import datetime

        import pytz

        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)

        weekdays = [
            "پیر",
            "منگل",
            "بدھ",
            "جمعرات",
            "جمعہ",
            "ہفتہ",
            "اتوار",
        ]
        months = [
            "",
            "جنوری",
            "فروری",
            "مارچ",
            "اپریل",
            "مئی",
            "جون",
            "جولائی",
            "اگست",
            "ستمبر",
            "اکتوبر",
            "نومبر",
            "دسمبر",
        ]

        day_name = weekdays[now.weekday()]
        month_name = months[now.month]
        time_str = now.strftime("%H:%M")

        # No fixed city name here -- transfer.timezone is tenant-configurable,
        # so "local time" stays correct regardless of which timezone is set.
        return (
            f"آج {day_name} ہے، {now.day} {month_name} {now.year}۔ "
            f"اس وقت {time_str} بجے ہیں (مقامی وقت)۔"
        )

    return get_current_time
