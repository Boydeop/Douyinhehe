"""Local data, licensing gates, niche research, and affiliate tracking."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
from urllib.parse import urlsplit

KEYWORDS = {
    "Nhà bếp": ["厨房好物", "厨房神器", "厨房收纳", "厨房用品"],
    "Gia dụng": ["居家好物", "家居神器", "生活小妙招", "实用好物"],
    "Nhà nhỏ": ["小户型收纳", "空间利用", "折叠家具", "节省空间"],
    "Decor": ["房间装饰", "桌面布置", "家居装饰", "氛围感好物"],
    "Vệ sinh": ["清洁神器", "家务妙招", "清洁好物", "浴室收纳"],
    "Công nghệ": ["智能家居", "创意小物", "数码好物", "桌面好物"],
}


def user_data_dir() -> Path:
    root = os.environ.get("DOUYINHEHE_HOME") or os.environ.get("APPDATA")
    return (Path(root) if root else Path.home() / ".local" / "share") / "Douyinhehe"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class LicenseGrant:
    original_url: str
    creator: str
    evidence: str
    commercial: bool
    derivative: bool
    platforms: str = "facebook,tiktok,youtube,instagram,threads"
    expires_on: str = ""
    evidence_file: str = ""
    evidence_sha256: str = ""

    def validate(self) -> None:
        if not self.original_url.strip() or not self.creator.strip() or not self.evidence.strip():
            raise ValueError("Cần URL gốc, tác giả và bằng chứng cấp phép.")
        if not self.commercial or not self.derivative:
            raise ValueError("Cần quyền khai thác thương mại và quyền chỉnh sửa nội dung.")
        if not any(x.strip() for x in self.platforms.split(",")):
            raise ValueError("Cần xác định nền tảng được phép phân phối.")
        if self.expires_on:
            try:
                expires = date.fromisoformat(self.expires_on)
            except ValueError as exc:
                raise ValueError("Ngày hết hạn giấy phép phải theo YYYY-MM-DD.") from exc
            if expires < datetime.now(timezone.utc).date():
                raise PermissionError("Giấy phép đã hết hạn. Không được tải, render hoặc đăng video.")
        if self.evidence_file:
            path = Path(self.evidence_file)
            if not path.is_file():
                raise FileNotFoundError("Không tìm thấy tệp bằng chứng cấp phép.")
            actual = file_sha256(path)
            if self.evidence_sha256 and self.evidence_sha256.lower() != actual:
                raise PermissionError("Tệp bằng chứng cấp phép đã thay đổi (SHA-256 không khớp).")
        elif self.evidence_sha256:
            raise ValueError("Có SHA-256 bằng chứng nhưng thiếu đường dẫn tệp bằng chứng.")


def opportunity_score(visual: float, engagement: float, product: float, legibility: float, freshness: float) -> float:
    """Weighted human-assessed 0..100 heuristic; not a view/sales prediction."""
    values = (visual, engagement, product, legibility, freshness)
    if any(not 0 <= x <= 100 for x in values):
        raise ValueError("Mỗi tiêu chí phải nằm trong khoảng 0–100.")
    return round(sum(x * w for x, w in zip(values, (.30, .25, .20, .15, .10))), 1)


def verify_affiliate_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Link affiliate phải là HTTPS hợp lệ, không chứa thông tin đăng nhập.")
    return url.strip()


class Store:
    def __init__(self, database: Path | str | None = None):
        self.path = Path(database) if database else user_data_dir() / "douyinhehe.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, creator TEXT NOT NULL,
                evidence TEXT NOT NULL, commercial INTEGER NOT NULL, derivative INTEGER NOT NULL,
                platforms TEXT NOT NULL, niche TEXT NOT NULL DEFAULT '',
                score REAL NOT NULL DEFAULT 0, file_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                expires_on TEXT NOT NULL DEFAULT '', evidence_file TEXT NOT NULL DEFAULT '',
                evidence_sha256 TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, niche TEXT NOT NULL,
                affiliate_url TEXT NOT NULL, campaign TEXT NOT NULL DEFAULT '',
                clicks INTEGER NOT NULL DEFAULT 0, orders INTEGER NOT NULL DEFAULT 0,
                revenue REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY, source_id INTEGER, platform TEXT NOT NULL,
                scheduled_for TEXT NOT NULL, provider_id TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES sources(id)
            );
            CREATE TABLE IF NOT EXISTS render_jobs (
                id INTEGER PRIMARY KEY, job_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed')),
                payload TEXT NOT NULL, result_path TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS translation_cache (
                cache_key TEXT PRIMARY KEY, text TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """)
            existing = {row[1] for row in conn.execute("PRAGMA table_info(sources)")}
            for col in ("expires_on", "evidence_file", "evidence_sha256"):
                if col not in existing:
                    conn.execute(f"ALTER TABLE sources ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def save_source(self, grant: LicenseGrant, niche: str = "", score: float = 0) -> int:
        grant.validate()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO sources(url,creator,evidence,commercial,derivative,platforms,niche,score,created_at,
                                    expires_on,evidence_file,evidence_sha256)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(url) DO UPDATE SET creator=excluded.creator,evidence=excluded.evidence,
                commercial=excluded.commercial,derivative=excluded.derivative,
                platforms=excluded.platforms,niche=excluded.niche,score=excluded.score,
                expires_on=excluded.expires_on,evidence_file=excluded.evidence_file,
                evidence_sha256=excluded.evidence_sha256
            """, (grant.original_url.strip(), grant.creator.strip(), grant.evidence.strip(),
                  int(grant.commercial), int(grant.derivative), grant.platforms,
                  niche, score, now_utc(), grant.expires_on, grant.evidence_file,
                  file_sha256(Path(grant.evidence_file)) if grant.evidence_file else ""))
            row = conn.execute("SELECT id FROM sources WHERE url=?", (grant.original_url.strip(),)).fetchone()
            return int(row[0])

    def sources(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY id DESC")]

    def update_download(self, url: str, filename: Path) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sources SET file_path=? WHERE url=?", (str(filename), url))

    def save_product(self, name: str, niche: str, affiliate_url: str, campaign: str = "") -> int:
        verify_affiliate_url(affiliate_url)
        if not name.strip():
            raise ValueError("Cần tên sản phẩm.")
        with self._connect() as conn:
            return int(conn.execute("""INSERT INTO products(name,niche,affiliate_url,campaign,created_at)
                VALUES(?,?,?,?,?)""", (name.strip(), niche.strip(), affiliate_url.strip(), campaign.strip(), now_utc())).lastrowid)

    def products(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id DESC")]

    def record_results(self, product_id: int, clicks: int, orders: int, revenue: float) -> None:
        if min(clicks, orders, revenue) < 0 or orders > clicks:
            raise ValueError("Thống kê không hợp lệ.")
        with self._connect() as conn:
            cur = conn.execute("UPDATE products SET clicks=?,orders=?,revenue=? WHERE id=?",
                               (clicks, orders, revenue, product_id))
            if cur.rowcount == 0:
                raise ValueError("Không tìm thấy sản phẩm.")

    def cache_get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT text FROM translation_cache WHERE cache_key=?", (key,)).fetchone()
            return row[0] if row else None

    def cache_set(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO translation_cache VALUES(?,?,?)", (key, value, now_utc()))

    def record_publication(self, source_id: int | None, platform: str, schedule: str,
                           provider_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute("""INSERT INTO publications(source_id,platform,scheduled_for,provider_id,status,created_at)
                            VALUES(?,?,?,?,?,?)""", (source_id, platform, schedule, provider_id, status, now_utc()))

    def publications(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM publications ORDER BY id DESC")]

    def enqueue_renders(self, jobs: list[tuple[str, dict]]) -> tuple[int, int]:
        """Deduplicate by immutable manifest contents, not filename alone."""
        import json
        inserted = 0
        with self._connect() as conn:
            for key, payload in jobs:
                cur = conn.execute("""INSERT OR IGNORE INTO render_jobs
                    (job_key,status,payload,created_at,updated_at)
                    VALUES(?,'pending',?,?,?)""",
                    (key, json.dumps(payload, ensure_ascii=False), now_utc(), now_utc()))
                inserted += cur.rowcount
        return inserted, len(jobs) - inserted

    def claim_next_render(self) -> dict | None:
        """Atomic claim for one pending local render, avoiding duplicate workers."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM render_jobs WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
            if row is None:
                return None
            conn.execute("""UPDATE render_jobs SET status='running',
                attempts=attempts+1,updated_at=? WHERE id=?""", (now_utc(), row['id']))
            return dict(row)

    def finish_render(self, job_id: int, path: str, error: str) -> None:
        with self._connect() as conn:
            cur = conn.execute("""UPDATE render_jobs
                SET status=?,result_path=?,error=?,updated_at=?
                WHERE id=? AND status='running'""",
                ("failed" if error else "done", path, error, now_utc(), job_id))
            if cur.rowcount != 1:
                raise RuntimeError("Render job was not running")

    def retry_failed_renders(self) -> int:
        with self._connect() as conn:
            return conn.execute("""UPDATE render_jobs SET status='pending',error='',updated_at=?
                WHERE status='failed'""", (now_utc(),)).rowcount

    def recover_interrupted_renders(self) -> int:
        """Only safe for local renders, never for remote posts (risk of duplicates)."""
        with self._connect() as conn:
            return conn.execute("""UPDATE render_jobs SET status='pending',updated_at=?
                WHERE status='running'""", (now_utc(),)).rowcount

    def render_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            return {r['status']: r['n'] for r in conn.execute(
                "SELECT status,COUNT(*) n FROM render_jobs GROUP BY status")}

    def render_jobs(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM render_jobs ORDER BY id DESC LIMIT ?", (limit,))]
