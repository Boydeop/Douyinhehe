"""Isolated F2 adapter. Bundled as a separate executable to avoid dependency conflicts.

F2 only receives explicitly supplied public Douyin URLs. No credentials are passed
on the command line. Never treat a successful import as verified website access.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit



def validate_source_url(url: str, mode: str) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port or
            host not in {"douyin.com", "www.douyin.com", "v.douyin.com", "v.iesdouyin.com"}):
        raise ValueError("Chỉ hỗ trợ URL Douyin HTTPS hoặc link chia sẻ chính thức")
    if mode == "post" and not parsed.path.startswith("/user/"):
        raise ValueError("Chế độ post yêu cầu URL hồ sơ Douyin")

def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Douyinhehe channel downloader")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--mode", choices=("one", "post"), default="post")
    parser.add_argument("--url")
    parser.add_argument("--path")
    parser.add_argument("--max-counts", type=int, default=50)
    args = parser.parse_args()
    import f2

    if args.doctor:
        # Confirm the actual Douyin command is bundled, not only f2.__init__.
        from f2.cli.cli_commands import main as _cli
        from f2.apps.douyin import cli as _douyin_cli
        if not hasattr(_cli, "main") or not hasattr(_douyin_cli, "douyin"):
            raise RuntimeError("Thiếu lệnh Douyin trong bản đóng gói F2.")
        print("F2/Douyin command ready:", getattr(f2, "__version__", "unknown"))
        return 0

    if not args.url or not args.path or not 0 <= args.max_counts <= 5000:
        parser.error("Cần URL, thư mục và số lượng video từ 0 đến 5000")
    try:
        validate_source_url(args.url, args.mode)
    except ValueError as exc:
        parser.error(str(exc))

    folder = Path(args.path).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    from f2.cli.cli_commands import main as f2_cli
    cli_args = ["dy", "--mode", args.mode, "--url", args.url, "--path", str(folder)]
    if args.mode == "post" and args.max_counts:
        cli_args.extend(["--max-counts", str(args.max_counts)])
    f2_cli.main(args=cli_args, standalone_mode=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
