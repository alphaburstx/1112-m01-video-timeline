#!/usr/bin/env python3
"""Deterministic fixture generation only; no timeline planner or renderer."""
import argparse
import array
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

RATE = 48000
SPECS = [
    dict(name="a_vfr_late.mov", size=[192,108], frames=72, fps=24,
         video_start="2", audio_start="11/5", audio_end="5", sar="1/1",
         color=[150,20,30], tone=330, pulses=["2/5","19/20","7/4","49/20"],
         vfr=True, description="VFR, nonzero video origin, audio 200ms late"),
    dict(name="b_portrait_early.mov", size=[72,144], frames=75, fps=25,
         video_start="5/4", audio_start="1", audio_end="17/4", sar="1/1",
         color=[20,145,35], tone=550, pulses=["3/20","3/5","7/5","12/5","27/10"],
         vfr=False, description="portrait, audio 250ms before video"),
    dict(name="c_silent.mov", size=[128,128], frames=48, fps=24,
         video_start="0", audio_start=None, audio_end=None, sar="1/1",
         color=[20,35,150], tone=None, pulses=[], vfr=False,
         description="square, no audio stream"),
    dict(name="d_sar.mov", size=[96,128], frames=72, fps=24,
         video_start="3/2", audio_start="3/2", audio_end="9/2", sar="2/1",
         color=[150,135,20], tone=770, pulses=["1/2","8/5","5/2"],
         vfr=False, description="non-square pixels, display aspect 3:2"),
]

def frac(value):
    return Fraction(value)

def pts(spec, i):
    if spec["vfr"]:
        return Fraction(i//3,8) + [Fraction(0),Fraction(1,20),Fraction(1,12)][i%3]
    return Fraction(i,spec["fps"])

def frame(spec, index):
    w,h=spec["size"]
    color=bytes(c+(index%4)*15 for c in spec["color"])
    data=bytearray(color*(w*h))
    # Binary frame index and source identity remain visible in the top/bottom bands.
    for y in range(4, min(14,h)):
        for x in range(4,w-4):
            bit=(index//(1<<min(6,(x-4)*7//(w-8))))%2
            p=(y*w+x)*3
            data[p:p+3]=bytes([235,235,235] if bit else [12,12,12])
    for y in range(h-10,h-4):
        for x in range(4,min(w-4,4+int(pts(spec,index)*24))):
            p=(y*w+x)*3
            data[p:p+3]=b"\xe0\xe0\xe0"
    return data

def audio(spec, filename):
    start=frac(spec["audio_start"])
    end=frac(spec["audio_end"])
    origin=frac(spec["video_start"])
    count=int((end-start)*RATE)
    centers=[float(frac(p)) for p in spec["pulses"]]
    buf=array.array("h")
    for n in range(count):
        t=float(start-origin)+n/RATE
        v=.06*math.sin(2*math.pi*spec["tone"]*t)
        for center in centers:
            # 12ms triangular burst; the 1kHz pulse is distinguishable from the pilot.
            env=max(0.0,1.0-abs(t-center)/.006)
            v += .65*env*math.sin(2*math.pi*1000*(t-center))
        buf.append(round(max(-1,min(1,v))*32767))
    if sys.byteorder!="little":
        buf.byteswap()
    with wave.open(str(filename),"wb") as dst:
        dst.setparams((1,2,RATE,0,"NONE","not compressed"))
        dst.writeframes(buf.tobytes())

def call(cmd):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError("Command failed: "+repr(cmd)+"\n"+p.stderr.decode(errors="replace"))
    return p.stdout

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,default=Path("media"))
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    records=[]
    for spec in SPECS:
        with tempfile.TemporaryDirectory(prefix="m01-fixture-") as temp:
            tmp=Path(temp)
            raw=tmp/"frames.rgb"
            with raw.open("wb") as stream:
                for i in range(spec["frames"]):
                    stream.write(frame(spec,i))
            w,h=spec["size"]
            cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-f","rawvideo",
                 "-pixel_format","rgb24","-video_size",f"{w}x{h}","-framerate",str(spec["fps"]),"-i",str(raw)]
            if spec["audio_start"] is not None:
                audio(spec,tmp/"tone.wav")
                cmd += ["-i",str(tmp/"tone.wav")]
            if spec["vfr"]:
                # Integer ticks at 120kHz; cycle 50ms, 33 1/3ms, 41 2/3ms.
                expr="floor(N/3)*15000+if(eq(mod(N,3),0),0,if(eq(mod(N,3),1),6000,10000))"
            else:
                expr=f"N*{120000//spec['fps']}"
            vstart=int(frac(spec["video_start"])*120000)
            vf=f"settb=1/120000,setpts='{expr}+{vstart}',setsar={spec['sar']}"
            cmd += ["-map","0:v:0","-vf",vf,"-c:v","libx264","-preset","medium",
                    "-crf","10","-pix_fmt","yuv420p","-bf","2","-g","24",
                    "-fps_mode","passthrough","-enc_time_base:v","1:120000",
                    "-video_track_timescale","120000"]
            if spec["audio_start"] is not None:
                offset=int(frac(spec["audio_start"])*RATE)
                cmd += ["-map","1:a:0","-af",f"asetpts=PTS+{offset}","-c:a","pcm_s16le"]
            cmd += ["-copyts","-avoid_negative_ts","disabled","-map_metadata","-1",
                    "-fflags","+bitexact","-flags:v","+bitexact",str(args.output/spec["name"])]
            call(cmd)
        target=args.output/spec["name"]
        probe=json.loads(call(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(target)]))
        records.append(dict(spec,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size,probe=probe))
        print(spec["name"],records[-1]["sha256"])
    rotated=args.output/"e_rotated.mov"
    call(["ffmpeg","-hide_banner","-loglevel","error","-y","-display_rotation:v:0","90","-i",str(args.output/"b_portrait_early.mov"),
          "-map","0","-c","copy","-copyts","-avoid_negative_ts","disabled",
          "-map_metadata","-1",str(rotated)])
    rotated_probe=json.loads(call(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(rotated)]))
    records.append(dict(SPECS[1],name="e_rotated.mov",rotation=90,description="portrait coded pixels with 90-degree display rotation",
                        sha256=hashlib.sha256(rotated.read_bytes()).hexdigest(),bytes=rotated.stat().st_size,probe=rotated_probe))
    print(rotated.name,records[-1]["sha256"])
    manifest=dict(version=1,seed=20261112,ffmpeg=call(["ffmpeg","-version"]).decode().splitlines()[0],
                  total_video_seconds="14",fixtures=records)
    (args.output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__":
    main()
