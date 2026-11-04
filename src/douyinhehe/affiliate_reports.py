"""CSV affiliate reports linked by campaign ID (no fabricated attribution)."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CampaignResult:
    campaign: str
    video_id: str
    platform: str
    views: int
    clicks: int
    orders: int
    commission: float

    def stats(self) -> dict:
        return {"campaign": self.campaign, "video_id": self.video_id, "platform": self.platform,
                "views": self.views, "clicks": self.clicks, "orders": self.orders,
                "commission": round(self.commission, 2),
                "cvr_percent": round(self.orders / self.clicks * 100, 2) if self.clicks else 0,
                "rpm_commission": round(self.commission / self.views * 1000, 2) if self.views else 0}


def import_report(path: Path, *, limit: int = 100_000) -> list[dict]:
    file = Path(path)
    if not file.is_file() or file.suffix.lower() != ".csv" or file.stat().st_size > 10_000_000:
        raise ValueError("Chọn CSV báo cáo hợp lệ, tối đa 10 MB.")
    names = {"campaign", "video_id", "platform", "views", "clicks", "orders", "commission"}
    aggregated: dict[tuple[str, str, str], CampaignResult] = {}
    with file.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not names.issubset(reader.fieldnames):
            raise ValueError("CSV thiếu một trong các cột: " + ", ".join(sorted(names)))
        for i, record in enumerate(reader, 1):
            if i > limit:
                raise ValueError("CSV có quá nhiều dòng.")
            try:
                c, v, p = (record[k].strip() for k in ("campaign", "video_id", "platform"))
                if not c or not v or not p:
                    raise ValueError("thiếu mã chiến dịch, video hoặc nền tảng")
                views, clicks, orders = (int(record[k]) for k in ("views", "clicks", "orders"))
                commission = float(record["commission"])
                if min(views, clicks, orders, commission) < 0 or orders > clicks:
                    raise ValueError("giá trị âm hoặc số đơn vượt số click")
                key = (c, v, p)
                old = aggregated.get(key)
                if old:
                    views += old.views
                    clicks += old.clicks
                    orders += old.orders
                    commission += old.commission
                aggregated[key] = CampaignResult(c, v, p, views, clicks, orders, commission)
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"Dòng {i} không hợp lệ: {exc}") from exc
    return [item.stats() for item in sorted(aggregated.values(), key=lambda x: -x.commission)]
