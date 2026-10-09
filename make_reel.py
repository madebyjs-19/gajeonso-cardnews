# 사용: python3.13 make_reel.py out/YYYYMMDD [1,2,3,5]
# 카드 JPG 중 하이라이트 장면을 이어 붙여 1080x1920 릴스(mp4, 약 12초)를 만든다. 결과: <dir>/reel.mp4
import sys, subprocess, os
d = sys.argv[1]
pick = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "1,2,3,5").split(",")]
HOLD, FADE = 3.0, 0.5
inputs, filt = [], []
for n, i in enumerate(pick):
    inputs += ["-loop", "1", "-t", str(HOLD + FADE), "-i", os.path.join(d, f"card{i}.jpg")]
    filt.append(f"[{n}:v]scale=1080:1350,pad=1080:1920:0:285:color=0x1A2A4A,setsar=1,fps=30,format=yuv420p[v{n}]")
prev, off = "v0", 0.0
for n in range(1, len(pick)):
    off += HOLD
    filt.append(f"[{prev}][v{n}]xfade=transition=fade:duration={FADE}:offset={off}[x{n}]")
    prev = f"x{n}"
total = HOLD * len(pick) + FADE
out = os.path.join(d, "reel.mp4")
cmd = ["ffmpeg", "-y", *inputs, "-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo",
       "-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-map", f"{len(pick)}:a",
       "-t", str(total), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-shortest",
       "-movflags", "+faststart", out]
subprocess.run(cmd, check=True, capture_output=True)
print(out, f"{total:.1f}s")
