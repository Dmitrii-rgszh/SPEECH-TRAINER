# LIPSYNC (MuseTalk + SadTalker + CodeFormer/GFPGAN)

This service generates a lip‑synced video from the configured avatar image and an audio WAV.

## Folder layout (weights in CLEAN_AVATARS)

```
CLEAN_AVATARS/
  PIPELINE/
    MuseTalk/
    SadTalker/
    CodeFormer/
    GFPGAN/
  RESULTS/
```

## Clone repos

```
git clone https://github.com/TMElyralab/MuseTalk CLEAN_AVATARS/PIPELINE/MuseTalk
git clone https://github.com/OpenTalker/SadTalker CLEAN_AVATARS/PIPELINE/SadTalker
git clone https://github.com/sczhou/CodeFormer CLEAN_AVATARS/PIPELINE/CodeFormer
git clone https://github.com/TencentARC/GFPGAN CLEAN_AVATARS/PIPELINE/GFPGAN
```

## Weights (store under CLEAN_AVATARS)

- MuseTalk: download weights to `CLEAN_AVATARS/PIPELINE/MuseTalk/models` as described in the MuseTalk README.
- SadTalker: download checkpoints to `CLEAN_AVATARS/PIPELINE/SadTalker/checkpoints` and GFPGAN weights to `CLEAN_AVATARS/PIPELINE/SadTalker/gfpgan/weights`.
- CodeFormer: download weights to `CLEAN_AVATARS/PIPELINE/CodeFormer/weights`.

## Notes

- Install FFmpeg and set `lip_sync.ffmpeg_path` in config.json if it is not on PATH.
- The LIPSYNC service runs GPU by default (CUDA required).
