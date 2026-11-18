"""Encode actual browser captures of the live Power BI report into a silent MP4."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

parser = argparse.ArgumentParser()
parser.add_argument("frames", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
frames = json.loads(args.frames.read_text())
assert frames
args.output.parent.mkdir(parents=True, exist_ok=True)
concat = args.frames.parent / "capture.ffconcat"
chapters = args.frames.parent / "chapters.ffmeta"
lines = ["ffconcat version 1.0"]
chapter_lines = [";FFMETADATA1", "title=Germany Power & Renewables - Power BI walkthrough",
                 "comment=Actual sampled browser captures; silent; command idle gaps compressed"]
timeline = []
elapsed = 0.0
for index, frame in enumerate(frames):
    duration = min(max((frames[index + 1]["at"] - frame["at"]) / 1000, 0.1), 0.65) if index + 1 < len(frames) else 2.5
    lines.extend([f"file '{frame['path']}'", f"duration {duration:.4f}"])
    if not timeline or timeline[-1]["scene"] != frame["scene"]:
        timeline.append({"scene": frame["scene"], "start_seconds": round(elapsed, 3)})
    elapsed += duration
lines.append(f"file '{frames[-1]['path']}'")
concat.write_text("\n".join(lines) + "\n")
for index, scene in enumerate(timeline):
    end = timeline[index + 1]["start_seconds"] if index + 1 < len(timeline) else elapsed
    chapter_lines.extend(["[CHAPTER]", "TIMEBASE=1/1000", f"START={round(scene['start_seconds'] * 1000)}",
                          f"END={round(end * 1000)}", f"title={scene['scene']}"])
chapters.write_text("\n".join(chapter_lines) + "\n")
command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-y", "-safe", "0", "-i", str(concat),
           "-i", str(chapters), "-map_metadata", "1", "-map_chapters", "1", "-vf",
           "crop=1238:700:0:64,format=yuv420p", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
           "-r", "25", "-an", "-movflags", "+faststart", str(args.output)]
subprocess.run(command, check=True)
metadata = {
    "report_url": "https://app.fabric.microsoft.com/groups/af058716-784e-466d-b01b-06f7413c9fdb/reports/5b92ecf0-ba8f-4e3e-8fdd-26476b3747fc",
    "captured_on": "2026-11-18", "source": "Actual live Power BI report, captured through the browser",
    "capture_method": "Sampled browser screenshots; not a continuous high-frame-rate desktop recording",
    "editing": "Idle gaps between commands compressed; report canvas cropped; no chart reconstruction or simulated values",
    "audio": "None", "captured_frames": len(frames), "encoded_fps": 25,
    "width": 1238, "height": 700, "duration_seconds_approx": round(elapsed, 3), "chapters": timeline,
    "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    "captured_frame_hashes": [hashlib.sha256(Path(f["path"]).read_bytes()).hexdigest() for f in frames],
}
args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(json.dumps({"output": str(args.output), "seconds": elapsed, "frames": len(frames)}, indent=2))
