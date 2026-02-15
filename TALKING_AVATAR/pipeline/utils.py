from __future__ import annotations

import os
import secrets
import subprocess
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "outputs"
MODELS_DIR = BASE_DIR / "models"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ffmpeg_path() -> str:
    return os.getenv("FFMPEG_PATH", "ffmpeg")


def ffprobe_path() -> str:
    return os.getenv("FFPROBE_PATH", "ffprobe")


def run_subprocess(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    timeout_s: Optional[int] = None,
) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=False,
    )
    if proc.returncode != 0:
        tail = (proc.stdout or "")[-4000:]
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{tail}")
    return proc.stdout or ""


def audio_duration_sec(audio_path: Path) -> float:
    cmd = [
        ffprobe_path(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    output = run_subprocess(cmd, timeout_s=10)
    try:
        return max(0.0, float(output.strip()))
    except ValueError:
        raise RuntimeError(f"Failed to parse audio duration: {output!r}")


def timestamp_id(prefix: str = "job") -> str:
    ms = int((time.time() % 1) * 1000)
    nonce = secrets.token_hex(2)
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{ms:03d}_{nonce}"
