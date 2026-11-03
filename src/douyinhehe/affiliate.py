"""Affiliate analytics using declared/manual metrics, not fabricated platform attribution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metrics:
    views: int
    clicks: int
    orders: int
    commission: float

    def as_dict(self) -> dict:
        if min(self.views, self.clicks, self.orders, self.commission) < 0 or self.orders > self.clicks:
            raise ValueError("Thống kê affiliate không hợp lệ.")
        return {
            "views": self.views,
            "clicks": self.clicks,
            "orders": self.orders,
            "commission": self.commission,
            "ctr_percent": round(100 * self.clicks / self.views, 2) if self.views else 0,
            "conversion_percent": round(100 * self.orders / self.clicks, 2) if self.clicks else 0,
            "revenue_per_1000_views": round(self.commission * 1000 / self.views, 2) if self.views else 0,
        }
