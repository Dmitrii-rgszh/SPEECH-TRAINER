from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Optional, Tuple

from .utils import MODELS_DIR, ensure_dir, run_subprocess

_WAV2LIP_MODEL = None
_WAV2LIP_DEVICE = None
_WAV2LIP_RUN_LOCK = threading.Lock()


def _wav2lip_repo() -> Path:
    repo = os.getenv("WAV2LIP_REPO")
    if repo:
        return Path(repo).expanduser().resolve()
    return (MODELS_DIR / "wav2lip").resolve()


def _wav2lip_python() -> str:
    return os.getenv("WAV2LIP_PYTHON", sys.executable)


def _wav2lip_checkpoint(repo_dir: Path) -> Path:
    ckpt = os.getenv("WAV2LIP_CHECKPOINT")
    if ckpt:
        return Path(ckpt).expanduser().resolve()
    checkpoints = repo_dir / "checkpoints"
    for candidate in (
        checkpoints / "Wav2Lip-SD-NOGAN.pt",
        checkpoints / "wav2lip.pth",
        checkpoints / "wav2lip_gan.pth",
        checkpoints / "Wav2Lip-SD-GAN.pt",
    ):
        if candidate.exists():
            return candidate.resolve()
    return (checkpoints / "wav2lip_gan.pth").resolve()


def _parse_pads() -> tuple[int, int, int, int]:
    raw = os.getenv("WAV2LIP_PADS")
    if raw:
        parts = [p.strip() for p in raw.replace(",", " ").split()]
        if len(parts) == 4:
            try:
                return tuple(int(p) for p in parts)  # top, bottom, left, right
            except ValueError:
                pass
    return (0, 10, 0, 0)


def _detect_face_box(video_path: str, repo_dir: Path) -> tuple[int, int, int, int]:
    import sys

    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))

    import cv2  # type: ignore
    import numpy as np  # type: ignore
    import torch  # type: ignore
    import face_detection  # type: ignore

    cap = cv2.VideoCapture(video_path)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("Failed to read first frame for face detection.")

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Wav2Lip device: {device}", flush=True)
    detector = face_detection.FaceAlignment(
        face_detection.LandmarksType._2D,
        flip_input=False,
        device=device,
    )
    rects = detector.get_detections_for_batch(np.array([rgb]))
    rect = rects[0] if rects else None
    del detector
    if rect is None:
        raise RuntimeError("Face not detected on the first frame for Wav2Lip box.")

    x1, y1, x2, y2 = [int(v) for v in rect]
    pad_top, pad_bottom, pad_left, pad_right = _parse_pads()
    # Smaller expansion keeps mouth scale closer to source face.
    extra = int(os.getenv("WAV2LIP_BOX_EXTRA", "0"))

    h, w = frame.shape[:2]
    x1 = max(0, x1 - pad_left - extra)
    x2 = min(w, x2 + pad_right + extra)
    y1 = max(0, y1 - pad_top - extra)
    y2 = min(h, y2 + pad_bottom + extra)

    if x2 <= x1 or y2 <= y1:
        raise RuntimeError("Invalid face box computed for Wav2Lip.")

    return (y1, y2, x1, x2)


def _load_wav2lip_model(ckpt: Path, repo_dir: Path):
    global _WAV2LIP_MODEL, _WAV2LIP_DEVICE
    if _WAV2LIP_MODEL is not None:
        return _WAV2LIP_MODEL, _WAV2LIP_DEVICE

    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))

    import torch  # type: ignore
    from models import Wav2Lip  # type: ignore

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        checkpoint = torch.load(str(ckpt))
    else:
        checkpoint = torch.load(str(ckpt), map_location=lambda storage, loc: storage)

    if not isinstance(checkpoint, dict):
        model = checkpoint.to(device).eval()
    else:
        model = Wav2Lip()
        state_dict = checkpoint["state_dict"]
        new_state = {k.replace("module.", ""): v for k, v in state_dict.items()}
        model.load_state_dict(new_state)
        model = model.to(device).eval()

    _WAV2LIP_MODEL = model
    _WAV2LIP_DEVICE = device
    return model, device


def _wav2lip_inprocess(
    repo_dir: Path,
    ckpt: Path,
    video_path: str,
    audio_path: str,
    out_video_path: str,
    box: Optional[Tuple[int, int, int, int]],
) -> None:
    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))

    import cv2  # type: ignore
    import numpy as np  # type: ignore
    import torch  # type: ignore
    import audio as wav2lip_audio  # type: ignore

    model, device = _load_wav2lip_model(ckpt, repo_dir)

    video_stream = cv2.VideoCapture(video_path)
    fps = float(os.getenv("WAV2LIP_FPS", "25"))
    if video_stream.isOpened():
        fps = video_stream.get(cv2.CAP_PROP_FPS) or fps

    frames = []
    while True:
        ok, frame = video_stream.read()
        if not ok:
            break
        frames.append(frame)
    video_stream.release()
    if not frames:
        raise RuntimeError("No frames read from base video for Wav2Lip.")

    tmp_wav = Path(out_video_path).with_suffix(".tmp.wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        str(tmp_wav),
    ]
    run_subprocess(cmd, timeout_s=30)

    wav = wav2lip_audio.load_wav(str(tmp_wav), 16000)
    mel = wav2lip_audio.melspectrogram(wav)
    if np.isnan(mel.reshape(-1)).sum() > 0:
        raise RuntimeError("Mel contains NaN values for Wav2Lip.")

    mel_step_size = 16
    mel_chunks = []
    mel_idx_multiplier = 80.0 / fps
    i = 0
    while True:
        start_idx = int(i * mel_idx_multiplier)
        if start_idx + mel_step_size > len(mel[0]):
            mel_chunks.append(mel[:, len(mel[0]) - mel_step_size :])
            break
        mel_chunks.append(mel[:, start_idx : start_idx + mel_step_size])
        i += 1

    full_frames = frames[: len(mel_chunks)]

    if box is None:
        raise RuntimeError("Wav2Lip box is required for fast in-process mode.")

    y1, y2, x1, x2 = box
    frame_h, frame_w = full_frames[0].shape[:2]
    y1 = max(0, min(y1, frame_h - 1))
    y2 = max(1, min(y2, frame_h))
    x1 = max(0, min(x1, frame_w - 1))
    x2 = max(1, min(x2, frame_w))

    out_avi = Path(out_video_path).with_suffix(".avi")
    out = cv2.VideoWriter(
        str(out_avi),
        cv2.VideoWriter_fourcc(*"DIVX"),
        fps,
        (frame_w, frame_h),
    )

    batch_size = int(os.getenv("WAV2LIP_BATCH_SIZE", "16"))
    batch_size = max(1, batch_size)
    img_size = 96
    use_fp16 = (
        device == "cuda"
        and os.getenv("WAV2LIP_FP16", "1").lower() in {"1", "true", "yes"}
    )

    if device == "cuda":
        torch.backends.cudnn.benchmark = True

    for start in range(0, len(mel_chunks), batch_size):
        end = min(start + batch_size, len(mel_chunks))
        curr = end - start

        frames_batch = []
        img_batch_list = []
        mel_batch_list = []

        for i in range(start, end):
            idx = i % len(full_frames)
            frame_to_save = full_frames[idx].copy()
            face = frame_to_save[y1:y2, x1:x2]
            face = cv2.resize(face, (img_size, img_size))

            frames_batch.append(frame_to_save)
            img_batch_list.append(face)
            mel_batch_list.append(mel_chunks[i])

        img_batch = np.asarray(img_batch_list)
        mel_batch = np.asarray(mel_batch_list)

        img_masked = img_batch.copy()
        img_masked[:, img_size // 2 :] = 0
        img_batch = np.concatenate((img_masked, img_batch), axis=3) / 255.0
        mel_batch = np.reshape(mel_batch, [curr, mel_batch.shape[1], mel_batch.shape[2], 1])

        img_batch = torch.FloatTensor(np.transpose(img_batch, (0, 3, 1, 2))).to(device)
        mel_batch = torch.FloatTensor(np.transpose(mel_batch, (0, 3, 1, 2))).to(device)

        with torch.no_grad():
            if use_fp16:
                with torch.cuda.amp.autocast():
                    pred = model(mel_batch, img_batch)
            else:
                pred = model(mel_batch, img_batch)

        pred = pred.detach().cpu().numpy().transpose(0, 2, 3, 1) * 255.0
        for b in range(curr):
            p = cv2.resize(pred[b].astype(np.uint8), (x2 - x1, y2 - y1))
            frame_to_save = frames_batch[b]
            frame_to_save[y1:y2, x1:x2] = p
            out.write(frame_to_save)

    out.release()

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-i",
        str(out_avi),
        "-strict",
        "-2",
        "-q:v",
        "1",
        str(out_video_path),
    ]
    run_subprocess(ffmpeg_cmd, timeout_s=60)
    try:
        tmp_wav.unlink(missing_ok=True)
        out_avi.unlink(missing_ok=True)
    except Exception:
        pass


def run_wav2lip(video_path: str, audio_path: str, out_video_path: str) -> None:
    """
    Run Wav2Lip to sync mouth region by audio.
    Expects official Wav2Lip repo under models/wav2lip with inference.py.
    """
    wait_s = float(os.getenv("WAV2LIP_LOCK_TIMEOUT_SEC", "15"))
    lock_acquired = _WAV2LIP_RUN_LOCK.acquire(timeout=max(0.0, wait_s))
    if not lock_acquired:
        raise RuntimeError(
            f"Wav2Lip is busy (queue timeout after {wait_s:.1f}s). Try again."
        )
    try:
        repo_dir = _wav2lip_repo()
        ensure_dir(Path(out_video_path).parent)

        inference_py = repo_dir / "inference.py"
        if not inference_py.exists():
            raise FileNotFoundError(
                "Wav2Lip inference.py not found. Set WAV2LIP_REPO."
            )

        ckpt_env = os.getenv("WAV2LIP_CHECKPOINT")
        ckpt = _wav2lip_checkpoint(repo_dir)
        if not ckpt.exists():
            raise FileNotFoundError(
                f"Wav2Lip checkpoint not found at {ckpt}. Set WAV2LIP_CHECKPOINT."
            )

        use_box = os.getenv("WAV2LIP_USE_BOX", "1").lower() in {"1", "true", "yes"}
        box = None
        if use_box:
            box = _detect_face_box(video_path, repo_dir)

        inprocess = os.getenv("WAV2LIP_INPROCESS", "1").lower() in {"1", "true", "yes"}
        print(
            f"Wav2Lip config: ckpt_env={ckpt_env!r}, ckpt={ckpt.name}, use_box={use_box}, inprocess={inprocess}",
            flush=True,
        )
        if inprocess:
            _wav2lip_inprocess(repo_dir, ckpt, video_path, audio_path, out_video_path, box)
            return

        cmd = [
            _wav2lip_python(),
            str(inference_py),
            "--checkpoint_path",
            str(ckpt),
            "--face",
            str(video_path),
            "--audio",
            str(audio_path),
            "--outfile",
            str(out_video_path),
            "--fps",
            os.getenv("WAV2LIP_FPS", "25"),
            "--face_det_batch_size",
            "1",
            "--wav2lip_batch_size",
            os.getenv("WAV2LIP_BATCH_SIZE", "16"),
            "--resize_factor",
            "1",
        ]

        if box is not None:
            y1, y2, x1, x2 = box
            cmd.extend(["--box", str(y1), str(y2), str(x1), str(x2)])

        extra_args = os.getenv("WAV2LIP_ARGS")
        if extra_args:
            cmd.extend(extra_args.split())

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        output = run_subprocess(cmd, cwd=repo_dir, env=env, timeout_s=600)
        if os.getenv("WAV2LIP_LOG", "0").lower() in {"1", "true", "yes"}:
            tail = (output or "")[-4000:]
            print(tail, flush=True)
    finally:
        _WAV2LIP_RUN_LOCK.release()
