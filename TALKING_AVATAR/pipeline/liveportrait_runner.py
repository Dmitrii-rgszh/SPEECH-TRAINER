from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from PIL import Image

from .utils import MODELS_DIR, TEMP_DIR, ensure_dir, ffmpeg_path, run_subprocess


def _liveportrait_repo() -> Path:
    repo = os.getenv("LIVEPORTRAIT_REPO")
    if repo:
        return Path(repo).expanduser().resolve()
    return (MODELS_DIR / "liveportrait").resolve()


def _liveportrait_python() -> str:
    return os.getenv("LIVEPORTRAIT_PYTHON", sys.executable)


def _default_driving_video(repo_dir: Path) -> Path:
    return repo_dir / "assets" / "examples" / "driving" / "d0.mp4"


def _build_driving_video(template_path: Path, duration_sec: float, out_path: Path) -> None:
    cmd = [
        ffmpeg_path(),
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(template_path),
        "-t",
        str(duration_sec),
        "-r",
        "25",
        "-an",
        str(out_path),
    ]
    run_subprocess(cmd, timeout_s=120)


def _cache_dir() -> Path:
    return Path(
        os.getenv("LIVEPORTRAIT_CACHE_DIR", str(TEMP_DIR / "liveportrait_cache"))
    ).resolve()


def _image_hash(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")
    hasher = hashlib.sha1()
    hasher.update(str(image.size).encode("utf-8"))
    hasher.update(image.tobytes())
    return hasher.hexdigest()[:16]


def _cache_variant_hash(repo_dir: Path) -> str:
    """
    Cache variant should change when motion-related options change.
    Otherwise we may reuse an old video with unwanted eye movement.
    """
    driving_template = Path(
        os.getenv("LIVEPORTRAIT_DRIVING", str(_default_driving_video(repo_dir)))
    ).resolve()
    animation_region = os.getenv("LIVEPORTRAIT_ANIMATION_REGION", "lip").strip()
    extra_args = os.getenv("LIVEPORTRAIT_ARGS", "").strip()
    fps = os.getenv("LIVEPORTRAIT_FPS", "25").strip()
    payload = "|".join(
        [
            "v2",  # bump when cache semantics change
            f"driving={driving_template}",
            f"animation_region={animation_region}",
            f"fps={fps}",
            f"extra={extra_args}",
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def _loop_video(src: Path, duration_sec: float, out_path: Path) -> None:
    cmd = [
        ffmpeg_path(),
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(src),
        "-t",
        str(duration_sec),
        "-r",
        "25",
        "-an",
        str(out_path),
    ]
    run_subprocess(cmd, timeout_s=120)


def _blink_interval_sec() -> float:
    raw = os.getenv("LIVEPORTRAIT_BLINK_INTERVAL_SEC", "0").strip()
    try:
        value = float(raw)
    except ValueError:
        return 0.0
    return value if value > 0 else 0.0


def _blink_first_offset_sec() -> float:
    raw = os.getenv("LIVEPORTRAIT_BLINK_FIRST_OFFSET_SEC", "1.0").strip()
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return value if value >= 0 else 0.0


def _blink_duration_sec() -> float:
    raw = os.getenv("LIVEPORTRAIT_BLINK_DURATION_SEC", "0.22").strip()
    try:
        value = float(raw)
    except ValueError:
        return 0.22
    return max(0.12, value)


def _blink_strength_at_offset(dt_sec: float, duration_sec: float) -> float:
    # More natural blink: quick close, tiny hold, slower reopen.
    if duration_sec <= 0:
        return 0.0
    half = duration_sec / 2.0
    if abs(dt_sec) > half:
        return 0.0

    p = (dt_sec + half) / duration_sec  # 0..1
    close_end = 0.34
    hold_end = 0.46

    if p < close_end:
        # Fast close-in.
        t = p / close_end
        return min(1.0, t * t)
    if p < hold_end:
        # Short hold at closed eye.
        return 1.0

    # Slower open-out.
    t = (p - hold_end) / max(1e-6, 1.0 - hold_end)
    v = 1.0 - t
    return max(0.0, v * v * v)


def _detect_face_box(frame):
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    h, w = frame.shape[:2]

    try:
        import torch  # type: ignore
        import face_detection  # type: ignore

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        detector = face_detection.FaceAlignment(
            face_detection.LandmarksType._2D,
            flip_input=False,
            device=device,
        )
        rects = detector.get_detections_for_batch(np.array([rgb]))
        rect = rects[0] if rects else None
        del detector
        if rect is not None:
            x1, y1, x2, y2 = [int(v) for v in rect]
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(x1 + 1, min(x2, w))
            y2 = max(y1 + 1, min(y2, h))
            return x1, y1, x2, y2
    except Exception:
        pass

    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        if len(faces) > 0:
            x, y, fw, fh = max(faces, key=lambda b: b[2] * b[3])
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(w, x + fw)
            y2 = min(h, y + fh)
            if x2 > x1 and y2 > y1:
                return x1, y1, x2, y2
    except Exception:
        pass

    return None


def _blend_eye_blink(frame, eye_box, strength: float) -> None:
    import cv2  # type: ignore

    if strength <= 0:
        return

    x1, y1, x2, y2 = eye_box
    if x2 <= x1 or y2 <= y1:
        return

    roi = frame[y1:y2, x1:x2]
    h, w = roi.shape[:2]
    if h < 4 or w < 4:
        return

    # Keep closure strong but avoid harsh "snap" look.
    target_h = max(1, int(round(h * (1.0 - 0.90 * strength))))
    compressed = cv2.resize(roi, (w, target_h), interpolation=cv2.INTER_CUBIC)
    restored = cv2.resize(compressed, (w, h), interpolation=cv2.INTER_LINEAR)

    alpha = min(0.92, 1.15 * strength)
    mixed = cv2.addWeighted(roi, 1.0 - alpha, restored, alpha, 0)
    frame[y1:y2, x1:x2] = mixed


def _apply_periodic_blinks(video_path: Path, interval_sec: float) -> None:
    import cv2  # type: ignore

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()

    if not frames:
        return

    frame_count = len(frames)
    duration = frame_count / max(fps, 1e-6)
    first_offset = _blink_first_offset_sec()
    if first_offset > duration:
        return
    centers_sec = []
    if interval_sec <= 0:
        centers_sec.append(first_offset)
    else:
        t = first_offset
        while t <= duration:
            centers_sec.append(t)
            t += interval_sec
    blink_count = len(centers_sec)
    if blink_count <= 0:
        return

    face_box = _detect_face_box(frames[0])
    if face_box is None:
        print("Blink schedule skipped: face box not found.", flush=True)
        return

    fx1, fy1, fx2, fy2 = face_box
    fw = fx2 - fx1
    fh = fy2 - fy1

    left_eye = (
        int(fx1 + 0.16 * fw),
        int(fy1 + 0.20 * fh),
        int(fx1 + 0.43 * fw),
        int(fy1 + 0.44 * fh),
    )
    right_eye = (
        int(fx1 + 0.57 * fw),
        int(fy1 + 0.20 * fh),
        int(fx1 + 0.84 * fw),
        int(fy1 + 0.44 * fh),
    )

    blink_dur = _blink_duration_sec()
    centers = [
        min(frame_count - 1, int(round(t_sec * fps)))
        for t_sec in centers_sec
    ]

    for i, frame in enumerate(frames):
        strength = 0.0
        for center in centers:
            dt = (i - center) / max(fps, 1e-6)
            s = _blink_strength_at_offset(dt, blink_dur)
            if s > strength:
                strength = s
        if strength <= 0:
            continue
        _blend_eye_blink(frame, left_eye, strength)
        _blend_eye_blink(frame, right_eye, strength)

    tmp_path = video_path.with_name(video_path.stem + ".blink.tmp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    h, w = frames[0].shape[:2]
    out = cv2.VideoWriter(str(tmp_path), fourcc, fps, (w, h))
    for frame in frames:
        out.write(frame)
    out.release()

    if tmp_path.exists() and tmp_path.stat().st_size > 0:
        tmp_path.replace(video_path)
        print(
            f"Blink schedule applied: first={first_offset:.2f}s, interval={interval_sec:.2f}s, duration={blink_dur:.2f}s, count={blink_count}",
            flush=True,
        )


def _render_liveportrait(image_path: str, duration_sec: float, out_video_path: str) -> None:
    """
    Run LivePortrait to generate base talking avatar video (idle + head motion + blink).

    By default expects official LivePortrait repo under models/liveportrait with inference.py.
    You can override command by setting LIVEPORTRAIT_CMD with placeholders:
    {image} {duration} {output} {fps}
    """
    repo_dir = _liveportrait_repo()
    ensure_dir(Path(out_video_path).parent)

    fps = os.getenv("LIVEPORTRAIT_FPS", "25")

    inference_py = repo_dir / "inference.py"
    if not inference_py.exists():
        raise FileNotFoundError(
            "LivePortrait inference.py not found. "
            "Set LIVEPORTRAIT_REPO or LIVEPORTRAIT_CMD."
        )

    driving_template = Path(
        os.getenv("LIVEPORTRAIT_DRIVING", str(_default_driving_video(repo_dir)))
    )
    if not driving_template.exists():
        raise FileNotFoundError(
            f"Driving template not found: {driving_template}. "
            "Set LIVEPORTRAIT_DRIVING."
        )

    out_path = Path(out_video_path)
    work_dir = out_path.parent
    ensure_dir(work_dir)
    driving_video = work_dir / "driving_loop.mp4"
    _build_driving_video(driving_template, duration_sec, driving_video)

    output_dir = work_dir / "liveportrait_out"
    ensure_dir(output_dir)

    cmd = [
        _liveportrait_python(),
        str(inference_py),
        "-s",
        str(image_path),
        "-d",
        str(driving_video),
        "-o",
        str(output_dir),
        "--flag_use_half_precision",
    ]

    # Keep eyes stable by default; avoid horizontal eye wandering from driving template.
    animation_region = os.getenv("LIVEPORTRAIT_ANIMATION_REGION", "lip").strip()
    if animation_region:
        cmd.extend(["--animation_region", animation_region])

    extra_args = os.getenv("LIVEPORTRAIT_ARGS")
    if extra_args:
        cmd.extend(extra_args.split())

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("RICH_DISABLE", "1")
    run_subprocess(cmd, cwd=repo_dir, env=env, timeout_s=600)

    result_name = f"{Path(image_path).stem}--{driving_video.stem}.mp4"
    result_path = output_dir / result_name
    if not result_path.exists():
        raise FileNotFoundError(f"LivePortrait output not found: {result_path}")
    result_path.replace(out_path)


def run_liveportrait(image_path: str, duration_sec: float, out_video_path: str) -> None:
    cache_enabled = os.getenv("LIVEPORTRAIT_CACHE", "1").lower() in {"1", "true", "yes"}
    if not cache_enabled:
        _render_liveportrait(image_path, duration_sec, out_video_path)
        interval = _blink_interval_sec()
        try:
            _apply_periodic_blinks(Path(out_video_path), interval)
        except Exception as exc:
            print(f"Blink schedule failed, continuing without it: {exc}", flush=True)
        return

    cache_seconds = float(os.getenv("LIVEPORTRAIT_CACHE_SECONDS", "12"))
    cache_dir = _cache_dir()
    ensure_dir(cache_dir)

    key = _image_hash(image_path)
    variant = _cache_variant_hash(_liveportrait_repo())
    cache_video = cache_dir / f"{key}_{variant}_{int(cache_seconds * 10)}.mp4"

    if not cache_video.exists():
        render_duration = max(duration_sec, cache_seconds)
        _render_liveportrait(image_path, render_duration, str(cache_video))

    _loop_video(cache_video, duration_sec, Path(out_video_path))
    interval = _blink_interval_sec()
    try:
        _apply_periodic_blinks(Path(out_video_path), interval)
    except Exception as exc:
        print(f"Blink schedule failed, continuing without it: {exc}", flush=True)
