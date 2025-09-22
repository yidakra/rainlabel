#!/usr/bin/env python3
import os
import sys
import subprocess
import glob
import random
from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = PROJECT_ROOT / "videos"
FULL_DIR = VIDEOS_DIR / "full"

# 60-second demo clip length (seconds)
CLIP_SECONDS = 60
CLIPS_PER_VIDEO = 5

YOUTUBE_URLS: List[str] = [
    "https://www.youtube.com/watch?v=f4ANM4paUJo&t=1754s",
    "https://www.youtube.com/live/jplmUJNfzJA",
    "https://www.youtube.com/live/smuWgA3q7aU",
    "https://www.youtube.com/watch?v=-HGTzeYXaVE",

]


def ensure_tools_available() -> None:
    """Verify yt-dlp and ffmpeg are installed and on PATH."""
    missing: List[str] = []
    for tool in ("yt-dlp", "ffmpeg", "ffprobe"):
        if not shutil_which(tool):
            missing.append(tool)
    if missing:
        msg = (
            "Missing required tools: " + ", ".join(missing) +
            "\nInstall on macOS via Homebrew:\n  brew install yt-dlp ffmpeg\n"
        )
        print(msg, file=sys.stderr)
        sys.exit(1)


def shutil_which(cmd: str) -> Optional[str]:
    from shutil import which
    return which(cmd)


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, text=True)


def download_video(url: str) -> Path:
    """Download a YouTube video to videos/full using yt-dlp with the video id as filename.
    Returns the absolute path to the downloaded file.
    """
    FULL_DIR.mkdir(parents=True, exist_ok=True)
    # Use id as basename; yt-dlp decides extension
    out_tpl = str(FULL_DIR / "%(id)s.%(ext)s")
    # If already downloaded (any extension), skip
    vid_id = extract_video_id(url)
    existing = find_existing_download(vid_id)
    if existing:
        print(f"[download] Skipping, already present: {existing}")
        return existing

    print(f"[download] {url}")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-o",
        out_tpl,
        url,
    ]
    res = run(cmd)
    # yt-dlp prints the final path; re-glob by id
    existing = find_existing_download(vid_id)
    if not existing:
        print(res.stdout)
        raise RuntimeError("Download appeared to succeed but file was not found.")
    return existing


def extract_video_id(url: str) -> str:
    # Relies on yt-dlp to normalize; for naming/globbing we only need a stable token.
    # Use simple heuristics:
    if "watch?v=" in url:
        return url.split("watch?v=")[-1].split("&")[0]
    if "/live/" in url:
        return url.rstrip("/").split("/live/")[-1].split("?")[0]
    # Fallback: sanitize whole URL
    return "urlhash_" + str(abs(hash(url)))


def find_existing_download(video_id: str) -> Optional[Path]:
    for path in glob.glob(str(FULL_DIR / f"{video_id}.*")):
        return Path(path)
    return None


def ffprobe_duration_seconds(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    res = run(cmd)
    try:
        return float(res.stdout.strip())
    except ValueError as ex:
        raise RuntimeError(f"Failed to parse duration from ffprobe output: {res.stdout}") from ex


def pick_spread_starts(duration_s: float, clip_len: int, num: int) -> List[int]:
    """Pick `num` random start times, roughly spread across the video, ensuring each fits `clip_len`."""
    max_start = max(0.0, duration_s - clip_len)
    if max_start <= 0:
        return [0] * num
    segment = max_start / num
    starts: List[int] = []
    for i in range(num):
        seg_start = i * segment
        seg_end = min(max_start, (i + 1) * segment)
        if seg_end <= seg_start:
            choice = int(seg_start)
        else:
            choice = int(random.uniform(seg_start, seg_end))
        starts.append(choice)
    return starts


def make_clip(input_path: Path, start_s: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        print(f"[clip] Skipping existing: {out_path.name}")
        return
    print(f"[clip] {input_path.name} -> {out_path.name} (start={start_s}s, len={CLIP_SECONDS}s)")
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_s),
        "-t",
        str(CLIP_SECONDS),
        "-i",
        str(input_path),
        # Normalize timestamps so clips start at t=0
        "-reset_timestamps",
        "1",
        "-avoid_negative_ts",
        "make_zero",
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(out_path),
    ]
    run(cmd)


def main() -> None:
    ensure_tools_available()
    VIDEOS_DIR.mkdir(exist_ok=True)
    FULL_DIR.mkdir(parents=True, exist_ok=True)

    for url in YOUTUBE_URLS:
        try:
            full_path = download_video(url)
        except subprocess.CalledProcessError as e:
            print(f"[error] yt-dlp failed for {url}:\n{e.stdout}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"[error] {url}: {e}", file=sys.stderr)
            continue

        try:
            duration = ffprobe_duration_seconds(full_path)
        except subprocess.CalledProcessError as e:
            print(f"[error] ffprobe failed for {full_path.name}:\n{e.stdout}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"[error] failed to get duration for {full_path.name}: {e}", file=sys.stderr)
            continue

        vid_id = full_path.stem
        starts = pick_spread_starts(duration, CLIP_SECONDS, CLIPS_PER_VIDEO)
        for idx, start in enumerate(starts, start=1):
            clip_name = f"{vid_id}_clip{idx:02d}.mp4"
            clip_path = VIDEOS_DIR / clip_name
            try:
                make_clip(full_path, start, clip_path)
            except subprocess.CalledProcessError as e:
                print(f"[error] ffmpeg failed for {clip_name}:\n{e.stdout}", file=sys.stderr)
            except Exception as e:
                print(f"[error] failed creating {clip_name}: {e}", file=sys.stderr)

        # Auto-run analyzer on generated clips (opt-in via env)
        if os.environ.get("RUN_ANALYZER") == "1":
            try:
                analyze = PROJECT_ROOT / "scripts" / "analyze_video.py"
                if analyze.exists():
                    print("\n[analyze] Running analyzer on created clips...")
                    run([sys.executable, str(analyze)])
            except KeyboardInterrupt:
                print("\n[analyze] Canceled by user (Ctrl-C)")
                return
            except subprocess.CalledProcessError as e:
                print(f"[warn] analyzer run failed:\n{e.stdout}", file=sys.stderr)
        else:
            print("\n[analyze] Skipping auto-run (set RUN_ANALYZER=1 to enable).")

    print("\nAll done. Your demo clips are in:")
    print(f"  {VIDEOS_DIR}")
    print("Run the analyzer to create sidecar JSONs when ready:")
    print(f"  python {PROJECT_ROOT / 'scripts' / 'analyze_video.py'}")
    print("Or re-run this script with auto-analyze enabled:")
    print("  RUN_ANALYZER=1 python scripts/prepare_demo_clips.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user (Ctrl-C)")
        sys.exit(130)


