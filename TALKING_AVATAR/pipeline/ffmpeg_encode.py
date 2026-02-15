from __future__ import annotations

from pathlib import Path

from .utils import ffmpeg_path, run_subprocess


def encode(input_path: str, output_path: str) -> None:
    in_path = Path(input_path)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_path(),
        "-y",
        "-i",
        str(in_path),
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.2",
        "-crf",
        "18",
        "-r",
        "25",
        str(out_path),
    ]
    run_subprocess(cmd, timeout_s=120)
