from __future__ import annotations

from pathlib import Path
import shutil


def ensure_template_copy(src: str | Path, dest: str | Path) -> Path:
    src_path = Path(src)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest_path)
    return dest_path
