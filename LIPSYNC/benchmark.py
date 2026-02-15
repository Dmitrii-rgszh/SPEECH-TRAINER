"""
Benchmark script for LIPSYNC optimization.
Measures generation time before/after optimization.
"""

import subprocess
import time
import sys
from pathlib import Path

# Config
LIPSYNC_URL = "http://127.0.0.1:7002"
TEST_AUDIO = Path("E:/musetalk_tmp/test_audio3.wav")
OUTPUT_DIR = Path("E:/musetalk_tmp/benchmark")
NUM_RUNS = 3


def ensure_test_audio():
    """Create test audio if not exists."""
    if TEST_AUDIO.exists():
        return
    
    print("Creating test audio...")
    # Use TTS to generate test audio
    import requests
    resp = requests.post(
        "http://127.0.0.1:7001/speak",
        json={"text": "Привет, как дела? Это тестовое сообщение для бенчмарка."},
        timeout=30
    )
    if resp.ok:
        TEST_AUDIO.parent.mkdir(parents=True, exist_ok=True)
        TEST_AUDIO.write_bytes(resp.content)
        print(f"Created: {TEST_AUDIO}")
    else:
        raise RuntimeError("Failed to create test audio")


def benchmark_single(run_id: int) -> dict:
    """Run single benchmark."""
    import requests
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"run_{run_id}.mp4"
    
    start = time.time()
    
    with open(TEST_AUDIO, "rb") as f:
        files = {"audio": ("test.wav", f, "audio/wav")}
        resp = requests.post(f"{LIPSYNC_URL}/generate", files=files, timeout=300)
    
    elapsed = time.time() - start
    
    if resp.ok:
        output_path.write_bytes(resp.content)
        size_kb = len(resp.content) / 1024
        return {
            "run": run_id,
            "time_sec": round(elapsed, 2),
            "size_kb": round(size_kb, 1),
            "status": "ok",
        }
    else:
        return {
            "run": run_id,
            "time_sec": round(elapsed, 2),
            "status": "error",
            "error": resp.text[:200],
        }


def run_benchmark():
    """Run full benchmark."""
    import requests
    
    print("=" * 60)
    print("LIPSYNC Optimization Benchmark")
    print("=" * 60)
    
    # Check server
    try:
        health = requests.get(f"{LIPSYNC_URL}/health", timeout=5).json()
        print(f"\nServer: {health.get('pipeline', 'unknown')}")
        print(f"Resolution: {health.get('resolution', 'N/A')}")
        print(f"FP16: {health.get('fp16', 'N/A')}")
        print(f"Expression scale: {health.get('expression_scale', 'N/A')}")
    except Exception as e:
        print(f"Error: Cannot connect to LIPSYNC server: {e}")
        return
    
    # Ensure test audio
    ensure_test_audio()
    
    # Force precompute first
    print("\n[1/2] Running precompute...")
    try:
        precompute_start = time.time()
        resp = requests.post(f"{LIPSYNC_URL}/precompute", timeout=120)
        precompute_time = time.time() - precompute_start
        if resp.ok:
            print(f"  Precompute: {precompute_time:.2f}s")
        else:
            print(f"  Precompute failed: {resp.text[:100]}")
    except Exception as e:
        print(f"  Precompute error: {e}")
    
    # Run benchmarks
    print(f"\n[2/2] Running {NUM_RUNS} generation tests...")
    results = []
    
    for i in range(NUM_RUNS):
        print(f"\n  Run {i+1}/{NUM_RUNS}...", end=" ", flush=True)
        result = benchmark_single(i + 1)
        results.append(result)
        
        if result["status"] == "ok":
            print(f"{result['time_sec']}s ({result['size_kb']} KB)")
        else:
            print(f"ERROR: {result.get('error', 'unknown')[:50]}")
    
    # Summary
    successful = [r for r in results if r["status"] == "ok"]
    if successful:
        times = [r["time_sec"] for r in successful]
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"  Successful runs: {len(successful)}/{NUM_RUNS}")
        print(f"  Average time: {avg_time:.2f}s")
        print(f"  Min time: {min_time:.2f}s")
        print(f"  Max time: {max_time:.2f}s")
        
        # Compare with baseline (20 sec assumed)
        baseline = 20.0
        speedup = baseline / avg_time
        print(f"\n  Baseline (old): ~{baseline}s")
        print(f"  Speedup: {speedup:.1f}×")
        
        if speedup >= 1.5:
            print(f"\n  ✅ Target achieved (≥1.5× speedup)")
        else:
            print(f"\n  ⚠️ Target not achieved (need ≥1.5× speedup)")
    else:
        print("\nAll runs failed!")


if __name__ == "__main__":
    run_benchmark()
