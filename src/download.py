"""Stream-download the lightweight PatentsView bulk files.

Only downloads files that are not already on disk. Uses a streaming
request with a progress bar so a big file never loads into memory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests
from tqdm import tqdm

from src.config import FILES, RAW_DIR


def download_one(url: str, dest: Path, chunk: int = 1 << 15) -> Path:
    """Stream `url` to `dest` with a progress bar. Skips if already present."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.name} already present ({dest.stat().st_size/1e6:.1f} MB)")
        return dest

    print(f"  [get ] {url}")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, unit_divisor=1024,
            desc=dest.name, leave=True,
        ) as bar:
            for block in r.iter_content(chunk_size=chunk):
                if not block:
                    continue
                f.write(block)
                bar.update(len(block))
        tmp.replace(dest)
    return dest


def main() -> None:
    print(f"Downloading {len(FILES)} file(s) to {RAW_DIR}")
    for name, url in FILES.items():
        dest = RAW_DIR / f"{name}.tsv.zip"
        try:
            download_one(url, dest)
        except requests.HTTPError as e:
            print(f"  [fail] {name}: {e}", file=sys.stderr)
            raise
    print("Download complete.")


if __name__ == "__main__":
    main()
