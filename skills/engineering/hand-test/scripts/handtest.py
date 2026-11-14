#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10.1"]
# ///
"""Make a hand test's evidence: one video and one board, BEFORE beside AFTER.

    uv run scripts/handtest.py <command> --help

Commands: init, pair, board, stills, find-change, check, archive, verdict, report.
Needs Python 3.9+, Pillow 10.1+, and ffmpeg and ffprobe on PATH for the video commands.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFont

FPS = 30
BG = (17, 20, 24)
HEADER = (6, 8, 10)
TEXT = (242, 244, 247)
MUTED = (160, 168, 178)
RED = (200, 45, 45)
GREEN = (28, 140, 68)
YELLOW = (242, 201, 76)

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_EXT = {".md", ".json", ".txt", ".html"}
OS_LITTER = {".DS_Store", "Thumbs.db", "desktop.ini"}
SUBFOLDERS = {"previous", "extra"}
STATUSES = ("pending", "ok", "not-ok")

MARK = "<fill in"
MARK_TOGETHER = "<fill in: m:ss the pair starts>"
MARK_CHANGE = "<fill in: m:ss the change shows>"

ID_RE = r"[A-Za-z0-9][A-Za-z0-9.-]*"
TOPIC_RE = r"[a-z0-9]+(?:-[a-z0-9]+)*"
FOLDER_RE = re.compile(rf"^({ID_RE})_({TOPIC_RE})_HANDTEST$")

ABS_PATH_RES = [
    re.compile(r"(?<![\w.:/])/(?:Users|home|private|tmp|var|Volumes|mnt|media|root|opt|srv)(?:/|\b)"),
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),
    re.compile(r"(?<![\w])~[\\/]"),
    re.compile(r"\$HOME\b|%USERPROFILE%|%HOMEPATH%|file://"),
]


# ---------------------------------------------------------------- names


def _check_name(id_: str, topic: str) -> None:
    if not re.fullmatch(ID_RE, id_ or ""):
        raise ValueError(f"id {id_!r}: use letters, digits, dots and hyphens, no underscore (like 142 or PR-142)")
    if not re.fullmatch(TOPIC_RE, topic or ""):
        raise ValueError(f"topic {topic!r}: use lower-case kebab-case, like sync-switch")


def folder_name(id_: str, topic: str) -> str:
    _check_name(id_, topic)
    return f"{id_}_{topic}_HANDTEST"


def video_name(id_: str, topic: str) -> str:
    _check_name(id_, topic)
    return f"{id_}_{topic}.mp4"


def board_name(id_: str, topic: str) -> str:
    _check_name(id_, topic)
    return f"{id_}_{topic}_BEFORE_AFTER.png"


def parse_folder_name(name: str):
    m = FOLDER_RE.match(name)
    return (m.group(1), m.group(2)) if m else None


def mmss(seconds: float) -> str:
    s = int(max(0.0, seconds))
    return f"{s // 60}:{s % 60:02d}"


def _short(sha):
    return sha[:8] if sha and re.fullmatch(r"[0-9a-fA-F]{9,40}", sha) else sha


# ---------------------------------------------------------------- pair maths


def choose_layout(w: int, h: int, layout: str = "auto") -> str:
    if layout in ("side", "stacked"):
        return layout
    if layout != "auto":
        raise ValueError(f"layout {layout!r}: use auto, side or stacked")
    return "stacked" if w > h else "side"


def sync_offsets(sync_before: float, sync_after: float, lead=None):
    """Where to start each recording so both reach their moment on the same output frame.

    Returns (start_before, start_after, lead_used): lead_used seconds play before the moment.
    """
    if sync_before < 0 or sync_after < 0:
        raise ValueError("a sync moment is seconds into its recording, so 0 or more")
    used = min(sync_before, sync_after)
    if lead is not None:
        used = min(used, max(0.0, lead))
    return sync_before - used, sync_after - used, used


def pair_duration(rest_before: float, rest_after: float, lead: float, tail=None) -> float:
    longest = max(rest_before, rest_after)
    return longest if tail is None else min(longest, lead + tail)


def _even(x) -> int:
    return max(2, int(round(x)) // 2 * 2)


def fit(w: int, h: int, box_w: int, box_h: int):
    scale = min(box_w / w, box_h / h)
    return _even(w * scale), _even(h * scale)


BADGE = (240, 56)


def pair_layout(layout: str, before_size, after_size) -> dict:
    """Rectangles (x, y, w, h) on the video's canvas for each part of the pair."""
    badge_w, badge_h = BADGE
    gap = 14
    rects = {}

    def place(key, size, vx, y0):
        vw, vh = size
        vx = _even(vx)
        vy = _even(y0 + badge_h + gap)
        rects[key] = (vx, vy, vw, vh)
        rects["badge_" + key] = (vx + vw // 2 - badge_w // 2, int(y0), badge_w, badge_h)

    if layout == "side":
        W, H, header_h, caption_h, gutter = 1920, 1080, 120, 110, 40
        top, bottom = header_h + 20, H - caption_h - 10
        slot_w = (W - 3 * gutter) // 2
        slot_h = bottom - top - badge_h - gap
        vb, va = fit(*before_size, slot_w, slot_h), fit(*after_size, slot_w, slot_h)
        y0 = top + (bottom - top - (badge_h + gap + max(vb[1], va[1]))) // 2
        # The two sides sit close to the middle so the eye can jump between them.
        mid = 120
        place("before", vb, max(gutter, W / 2 - mid / 2 - vb[0]), y0)
        place("after", va, min(W - gutter - va[0], W / 2 + mid / 2), y0)
    elif layout == "stacked":
        W, H, header_h, caption_h, gutter = 1080, 1920, 170, 150, 30
        top, bottom = header_h + 10, H - caption_h - 10
        part_h = (bottom - top) // 2
        slot_w = W - 2 * gutter
        slot_h = part_h - badge_h - gap - 20
        for i, (key, size) in enumerate((("before", before_size), ("after", after_size))):
            v = fit(*size, slot_w, slot_h)
            y0 = top + i * part_h + (part_h - (badge_h + gap + v[1])) // 2
            place(key, v, gutter + (slot_w - v[0]) / 2, y0)
    else:
        raise ValueError(f"layout {layout!r}: use side or stacked")
    rects.update(canvas=(W, H), header=(0, 0, W, header_h), caption=(0, H - caption_h, W, caption_h))
    return rects


def board_layout(before_size, after_size, header_h: int, badge_size, margin: int) -> dict:
    """The board keeps both pictures at full size: BEFORE left, AFTER right, badges above."""
    (wb, hb), (wa, ha), (bw, bh), m = before_size, after_size, badge_size, margin
    W = 3 * m + wb + wa
    y_badge = header_h + m
    y_img = y_badge + bh + m // 2
    H = y_img + max(hb, ha) + m
    rects = {"canvas": (W, H), "before": (m, y_img, wb, hb), "after": (2 * m + wb, y_img, wa, ha)}
    for key in ("before", "after"):
        x, _, w, _ = rects[key]
        bx = min(max(0, x + w // 2 - bw // 2), W - bw)
        rects["badge_" + key] = (bx, y_badge, bw, bh)
    return rects


# ---------------------------------------------------------------- drawing


@lru_cache(maxsize=None)
def font(px):
    f = ImageFont.load_default(size=max(8, int(round(px))))
    if not isinstance(f, ImageFont.FreeTypeFont):
        raise RuntimeError("this Pillow has no FreeType; install Pillow 10.1+ from PyPI (uv run brings it)")
    return f


def lh(f) -> int:
    ascent, descent = f.getmetrics()
    return ascent + descent


def wrap(text: str, fnt, max_w: float):
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split():
            while fnt.getlength(word) > max_w and len(word) > 1:
                cut = len(word) - 1
                while cut > 1 and fnt.getlength(word[:cut]) > max_w:
                    cut -= 1
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(word[:cut])
                word = word[cut:]
            trial = f"{cur} {word}" if cur else word
            if fnt.getlength(trial) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def fit_lines(text: str, max_w: float, px: float, max_lines: int, min_px: float, what: str):
    while True:
        f = font(px)
        lines = wrap(text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines
        if px <= min_px:
            raise ValueError(f"the {what} is too long for its place ({max_lines} line(s)): shorten {text[:50]!r}")
        px = max(min_px, px * 0.9)


def _bold(px):
    return int(px // 40)


def draw_badge(d, rect, text, colour, px):
    x, y, w, h = rect
    d.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=max(2, h // 5), fill=colour)
    d.text((x + w / 2, y + h / 2), text, font=font(px), fill=TEXT, anchor="mm",
           stroke_width=max(1, round(px / 32)), stroke_fill=TEXT)


def draw_lines(d, x, y, lines, f, fill, centre_w=None, bold=False):
    for line in lines:
        lx = x + (centre_w - f.getlength(line)) / 2 if centre_w else x
        d.text((lx, y), line, font=f, fill=fill, stroke_width=_bold(f.size) if bold else 0, stroke_fill=fill)
        y += lh(f)
    return y


def render_intro(size, title: str, lines, sub: str = ""):
    """The intro card: a title, then labelled lines (WHAT CHANGES, HOW TO WATCH), a small line at the foot."""
    W, H = size
    u = min(W, H) / 1080
    pad = round(90 * u)
    max_w = W - 2 * pad
    sf = font(26 * u)
    avail = H - 2 * pad - ((lh(sf) + round(20 * u)) if sub else 0)
    k = 1.0
    while k >= 0.55:
        tf, lf, bf = font(66 * k * u), font(30 * k * u), font(40 * k * u)
        tl = wrap(title, tf, max_w)
        blocks = [(label, wrap(text, bf, max_w)) for label, text in lines]
        need = len(tl) * lh(tf) + round(50 * k * u)
        for label, bl in blocks:
            need += (lh(lf) + round(10 * k * u) if label else 0) + len(bl) * lh(bf) + round(40 * k * u)
        if need <= avail:
            break
        k *= 0.9
    else:
        raise ValueError("the intro is too long for its card: keep WHAT CHANGES and HOW TO WATCH to a few lines each")
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    y = pad + (avail - need) // 2
    y = draw_lines(d, pad, y, tl, tf, TEXT, bold=True) + round(50 * k * u)
    for label, bl in blocks:
        if label:
            y = draw_lines(d, pad, y, [label.upper()], lf, YELLOW, bold=True) + round(10 * k * u)
        y = draw_lines(d, pad, y, bl, bf, TEXT) + round(40 * k * u)
    if sub:
        draw_lines(d, pad, H - pad - lh(sf), wrap(sub, sf, max_w)[:1], sf, MUTED)
    return img


def render_background(lay: dict, title: str, sub: str, caption: str):
    """Everything in the pair that stands still: header, badges, caption, black boxes for the videos."""
    W, H = lay["canvas"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _, _, _, hh = lay["header"]
    d.rectangle([0, 0, W - 1, hh - 1], fill=HEADER)
    stacked = H > W
    tf, tl = fit_lines(title, W - 80, 46, 2 if stacked else 1, 28, "title")
    sf = font(28)
    sl = wrap(sub, sf, W - 80)[:1] if sub else []
    block = len(tl) * lh(tf) + (8 + lh(sf) if sl else 0)
    y = (hh - block) // 2
    y = draw_lines(d, 0, y, tl, tf, TEXT, centre_w=W, bold=True)
    if sl:
        draw_lines(d, 0, y + 8, sl, sf, MUTED, centre_w=W)
    for key, colour, label in (("before", RED, "BEFORE"), ("after", GREEN, "AFTER")):
        x, y0, w, h = lay[key]
        d.rectangle([x, y0, x + w - 1, y0 + h - 1], fill=(0, 0, 0))
        draw_badge(d, lay["badge_" + key], label, colour, 32)
    if caption:
        cx, cy, cw, ch = lay["caption"]
        cf, cl = fit_lines(caption, W - 80, 36, 2, 24, "caption")
        draw_lines(d, 0, cy + (ch - len(cl) * lh(cf)) // 2, cl, cf, TEXT, centre_w=W)
    return img


def render_board(before, after, title: str, caption: str = ""):
    s = max(0.35, max(before.width, after.width) / 1080)
    m = round(48 * s)
    W = 3 * m + before.width + after.width
    tf, tl = fit_lines(title, W - 2 * m, 60 * s, 2, 30 * s, "title")
    cf, cl = fit_lines(caption, W - 2 * m, 38 * s, 3, 24 * s, "caption") if caption else (None, [])
    header_h = m + len(tl) * lh(tf) + (round(16 * s) + len(cl) * lh(cf) if cl else 0) + m
    badge = (round(300 * s), round(84 * s))
    lay = board_layout(before.size, after.size, header_h, badge, m)
    img = Image.new("RGB", lay["canvas"], BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, lay["canvas"][0] - 1, header_h - 1], fill=HEADER)
    y = draw_lines(d, m, m, tl, tf, TEXT, bold=True)
    if cl:
        draw_lines(d, m, y + round(16 * s), cl, cf, MUTED)
    for key, pic, colour, label in (("before", before, RED, "BEFORE"), ("after", after, GREEN, "AFTER")):
        x, y0, _, _ = lay[key]
        img.paste(pic, (x, y0))
        draw_badge(d, lay["badge_" + key], label, colour, 48 * s)
    return img


# ---------------------------------------------------------------- ffmpeg


def need_tools():
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        raise RuntimeError(f"{' and '.join(missing)} must be on PATH for this command")


def run_ffmpeg(args):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *args], capture_output=True, text=True)
    if proc.returncode:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg failed:\n{tail}")


def probe(path: str) -> dict:
    need_tools()
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                          capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"ffprobe could not read {path}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None:
        raise RuntimeError(f"{path} has no video stream")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if "rotate" in (v.get("tags") or {}):
        rot = int(v["tags"]["rotate"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    duration = float((data.get("format") or {}).get("duration") or v.get("duration") or 0)
    return {"width": w, "height": h, "duration": duration, "fps": fps,
            "has_audio": a is not None, "channels": int(a.get("channels", 0)) if a else 0}


def default_how(layout: str, sound: bool) -> str:
    where = ("Top, red: BEFORE, the old version. Bottom, green: AFTER, the new version."
             if layout == "stacked" else
             "Left, red: BEFORE, the old version. Right, green: AFTER, the new version.")
    text = f"{where} Both play at the same time, lined up on the moment that matters."
    if sound:
        text += " Use headphones: BEFORE plays in the left ear, AFTER in the right."
    return text


def cmd_pair(a) -> int:
    pb, pa = probe(a.before), probe(a.after)
    for flag, t, info, side in (("--sync-before", a.sync_before, pb, "BEFORE"), ("--sync-after", a.sync_after, pa, "AFTER")):
        if t > info["duration"]:
            raise ValueError(f"{flag} {t} is past the end of {side} ({info['duration']:.2f} s)")
    layout = choose_layout(pb["width"], pb["height"], a.layout)
    if a.layout == "auto" and choose_layout(pa["width"], pa["height"]) != layout:
        print(f"note: BEFORE and AFTER have different shapes; laid out {layout} from BEFORE's shape")
    start_b, start_a, lead = sync_offsets(a.sync_before, a.sync_after, a.lead)
    dur = pair_duration(pb["duration"] - start_b, pa["duration"] - start_a, lead, a.tail)
    lay = pair_layout(layout, (pb["width"], pb["height"]), (pa["width"], pa["height"]))
    W, H = lay["canvas"]
    sound = pb["has_audio"] or pa["has_audio"]
    intro_s = a.intro_seconds
    intro = render_intro((W, H), a.title, [("WHAT CHANGES", a.what), ("HOW TO WATCH", a.how or default_how(layout, sound))],
                         a.sub or "")
    bg = render_background(lay, a.title, a.sub or "", a.caption or "")
    (bx, by, bw, bh), (ax, ay, aw, ah) = lay["before"], lay["after"]
    with tempfile.TemporaryDirectory() as td:
        intro_png, bg_png = os.path.join(td, "intro.png"), os.path.join(td, "bg.png")
        intro.save(intro_png)
        bg.save(bg_png)
        args = ["-loop", "1", "-framerate", str(FPS), "-t", f"{intro_s:.3f}", "-i", intro_png,
                "-loop", "1", "-framerate", str(FPS), "-i", bg_png,
                "-ss", f"{start_b:.3f}", "-i", a.before,
                "-ss", f"{start_a:.3f}", "-i", a.after]
        fc = [
            f"[0:v]scale={W}:{H},format=yuv420p,setsar=1[iv]",
            f"[2:v]fps={FPS},scale={bw}:{bh},setsar=1[bv]",
            f"[3:v]fps={FPS},scale={aw}:{ah},setsar=1[av]",
            "[1:v]format=yuv420p[bg]",
            # eof_action=repeat holds the shorter side's last frame until the pair ends.
            f"[bg][bv]overlay={bx}:{by}:eof_action=repeat[t1]",
            f"[t1][av]overlay={ax}:{ay}:eof_action=repeat,trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
            "format=yuv420p,setsar=1[pv]",
        ]
        if sound:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            silent = None
            if not (pb["has_audio"] and pa["has_audio"]):
                args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"]
                silent = 5

            def side_audio(index, has, label):
                src = f"[{index}:a]" if has else f"[{silent}:a]"
                return (f"{src}aformat=sample_rates=48000:channel_layouts=mono,apad,"
                        f"atrim=duration={dur:.3f},asetpts=PTS-STARTPTS[{label}]")
            fc += [
                side_audio(2, pb["has_audio"], "ba"),
                side_audio(3, pa["has_audio"], "aa"),
                "[ba][aa]join=inputs=2:channel_layout=stereo:map=0.0-FL|1.0-FR[pa]",
                f"[4:a]atrim=duration={intro_s:.3f},aformat=sample_rates=48000:channel_layouts=stereo[ia]",
                "[iv][ia][pv][pa]concat=n=2:v=1:a=1[v][a]",
            ]
            maps = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
        else:
            fc.append("[iv][pv]concat=n=2:v=1:a=0[v]")
            maps = ["-map", "[v]"]
        run_ffmpeg(args + ["-filter_complex", ";".join(fc), *maps, "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-t", f"{intro_s + dur:.3f}",
                           "-movflags", "+faststart", a.out])
    change_at = intro_s + lead
    print(f"Wrote {a.out}: {mmss(intro_s + dur)} long, {W}x{H}, {layout}, {'with' if sound else 'no'} sound.")
    print(f"BEFORE and AFTER play together from {mmss(intro_s)}; the moment is at {mmss(change_at)} ({change_at:.2f} s).")
    folder = os.path.dirname(os.path.abspath(a.out))
    if os.path.exists(os.path.join(folder, "handtest.json")):
        fill_times(folder, intro_s, change_at, sound)
        print("Filled the video times in README.md and PACKAGE.md.")
    return 0


# ---------------------------------------------------------------- stills and find-change


def still_times(duration: float, at=None, every=None, start: float = 0.0, end=None):
    if at:
        times = sorted(float(t) for t in at)
    elif every:
        if every <= 0:
            raise ValueError("--every must be more than 0")
        stop = duration if end is None else min(end, duration)
        times, i = [], 0
        while start + i * every <= stop + 1e-9:
            times.append(round(start + i * every, 3))
            i += 1
    else:
        raise ValueError("give --at or --every")
    return [t for t in times if 0 <= t < duration]


def still_name(t: float) -> str:
    return f"still_{t:07.2f}s.png"


def cmd_stills(a) -> int:
    info = probe(a.video)
    times = still_times(info["duration"], a.at, a.every, a.start, a.end)
    if not times:
        raise ValueError(f"no time falls inside the video ({info['duration']:.2f} s)")
    os.makedirs(a.out, exist_ok=True)
    for t in times:
        path = os.path.join(a.out, still_name(t))
        run_ffmpeg(["-ss", f"{t:.3f}", "-i", a.video, "-frames:v", "1", path])
        print(path)
    print(f"Wrote {len(times)} still(s). Look at every one before a person sees the video.")
    return 0


def frame_diffs(video: str, t_from: float, t_to: float, crop=None, width: int = 360, level: int = 10):
    """Percent of the picture that changed between consecutive frames; diffs[i] is frame i+1 against frame i.

    A pixel counts as changed when its grey level moves by more than `level`, so a small switch
    flipping still shows while encoder noise does not.
    """
    info = probe(video)
    w, h = info["width"], info["height"]
    vf = []
    if crop:
        cw, ch, cx, cy = (int(v) for v in crop.split(":"))
        vf.append(f"crop={cw}:{ch}:{cx}:{cy}")
        w, h = cw, ch
    width = min(width, _even(w))
    sh = _even(width * h / w)
    vf += [f"fps={FPS}", f"scale={width}:{sh}", "format=gray"]
    proc = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t_from:.3f}", "-t", f"{t_to - t_from:.3f}", "-i", video,
                           "-vf", ",".join(vf), "-f", "rawvideo", "-"], capture_output=True)
    if proc.returncode:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode(errors='replace')[-500:]}")
    n = width * sh
    raw = proc.stdout
    lut = [0] * (level + 1) + [255] * (255 - level)
    diffs, prev = [], None
    for i in range(0, len(raw) - n + 1, n):
        img = Image.frombytes("L", (width, sh), raw[i:i + n])
        if prev is not None:
            changed = ImageChops.difference(img, prev).point(lut).histogram()[255]
            diffs.append(100.0 * changed / n)
        prev = img
    return diffs


def rank_changes(diffs, t0: float, fps: float, top: int):
    pairs = [(t0 + (i + 1) / fps, d) for i, d in enumerate(diffs)]
    return sorted(pairs, key=lambda p: -p[1])[:top]


def first_move(diffs, t0: float, fps: float, frac: float = 0.1, floor: float = 0.005):
    if not diffs or max(diffs) < floor:
        return None
    limit = max(diffs) * frac
    return next(t0 + (i + 1) / fps for i, d in enumerate(diffs) if d >= limit)


def cmd_find_change(a) -> int:
    if a.to <= a.from_:
        raise ValueError("--to must be after --from")
    diffs = frame_diffs(a.video, a.from_, a.to, a.crop, level=a.level)
    start = first_move(diffs, a.from_, FPS)
    if start is None:
        print(f"No change in the picture between {a.from_:.2f} s and {a.to:.2f} s. Check the window and the times.")
        return 1
    print(f"Biggest picture changes between {a.from_:.2f} s and {a.to:.2f} s, at {FPS} fps (time of the first frame that shows it):")
    for t, d in rank_changes(diffs, a.from_, FPS, a.top):
        print(f"  {t:.3f} s   {d:.2f}% of the picture changed")
    print(f"It starts to move at {start:.3f} s (the first frame over a tenth of the biggest change).")
    print("Use the moment the picture shows as --sync-before or --sync-after, not a step's logged time.")
    return 0


# ---------------------------------------------------------------- the evidence folder


def find_marks(text: str):
    return [i for i, line in enumerate(text.splitlines(), 1) if MARK in line]


def find_abs_paths(text: str):
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for rx in ABS_PATH_RES:
            hits += [(i, m.group(0)) for m in rx.finditer(line)]
    return hits


def check_folder(path: str):
    """Every reason the folder is not ready for a person. An empty list means ready."""
    if not os.path.isdir(path):
        return [f"{path}: not a folder"]
    problems = []
    name = os.path.basename(os.path.normpath(path))
    parsed = parse_folder_name(name)
    if not parsed:
        problems.append(f"folder name {name!r} is off the pattern <id>_<topic>_HANDTEST (topic in kebab-case)")
    entries = sorted(e for e in os.listdir(path) if e not in OS_LITTER and not e.startswith("."))
    files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
    dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
    expected = {"README.md", "PACKAGE.md", "handtest.json"}
    if parsed:
        expected |= {video_name(*parsed), board_name(*parsed)}
    problems += [f"missing {req}" for req in sorted(expected) if req not in files]
    videos = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXT]
    images = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXT]
    if len(videos) > 1:
        problems.append(f"more than one video at the top level ({', '.join(videos)}): keep one; "
                        "a redo moves the old take to previous/ (handtest.py archive)")
    if len(images) > 1:
        problems.append(f"more than one board at the top level ({', '.join(images)}): stills and raw pictures go in extra/")
    for f in files:
        if f not in expected:
            problems.append(f"name off the pattern at the top level: {f} (only the video, the board, README.md, "
                            "PACKAGE.md and handtest.json; move the rest to extra/ or previous/)")
    for d in dirs:
        if d not in SUBFOLDERS:
            problems.append(f"unexpected folder {d}/: only previous/ and extra/ sit beside the evidence")
    for f in files:
        if os.path.splitext(f)[1].lower() not in TEXT_EXT:
            continue
        with open(os.path.join(path, f), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        marks = find_marks(text)
        if marks:
            problems.append(f"{f}: {len(marks)} <fill in> mark(s) left, on line(s) {', '.join(map(str, marks))}")
        problems += [f"{f}: line {n}: absolute path or home directory {hit!r}; name only a relative path"
                     for n, hit in find_abs_paths(text)]
    if "handtest.json" in files:
        try:
            with open(os.path.join(path, "handtest.json"), encoding="utf-8") as fh:
                data = json.load(fh)
        except ValueError as e:
            problems.append(f"handtest.json is not valid JSON: {e}")
        else:
            if data.get("status") not in STATUSES:
                problems.append(f"handtest.json: status {data.get('status')!r} is not one of {', '.join(STATUSES)}")
            if parsed and (data.get("id"), data.get("topic")) != parsed:
                problems.append(f"handtest.json: id and topic {data.get('id')!r}, {data.get('topic')!r} "
                                f"do not match the folder name {name!r}")
    return problems


def _load(folder):
    with open(os.path.join(folder, "handtest.json"), encoding="utf-8") as f:
        return json.load(f)


def _save(folder, data):
    with open(os.path.join(folder, "handtest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _inside_git(path):
    if not shutil.which("git"):
        return None
    probe_dir = os.path.abspath(path)
    while not os.path.isdir(probe_dir):
        probe_dir = os.path.dirname(probe_dir)
    proc = subprocess.run(["git", "-C", probe_dir, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


README_TEMPLATE = """# {id}: {title}

**In one sentence:** <fill in: what a person saw before and sees now, with the numbers>

## The change

| | BEFORE | AFTER |
|---|---|---|
| <fill in: what is compared> | <fill in: the old, with a number where there is one> | <fill in: the new> |

## In the video

- `{video}`: the intro card, then BEFORE (red) and AFTER (green) together from {together}.
- The change shows at {change}: <fill in: what happens there, in plain words>.
- `{board}`: <fill in: the moment the board shows>.

## Look for

- See: <fill in: what to look at, or "nothing">
- Hear: <fill in: what to listen for, or "nothing">
- Feel: <fill in: timing or response to notice, or "nothing">

## Measured

<fill in: the numbers from this recording and how they were taken; say "no difference on this device" where that is the truth>

## Notes

<fill in: anything switched on or adjusted for the recording, anything odd, or "none">

## How it was recorded

- Device: <fill in: device or browser, OS, language, screen size>
- BEFORE: base `{base}`, <fill in: built from the base commit, or the change switched off at run time>
- AFTER: head `{head}`
- Input: <fill in: the driver, and how it found each element>
- Format: one video at 30 fps ({sound}) and one board.
- Made: {date}

## Your verdict

- OK: {ok}
- Not OK: {not_ok}
"""

PACKAGE_TEMPLATE = """## Hand test: {title}

- **What changes:** <fill in: before and after in one line, with the numbers>
- **Start:** <fill in: the build or branch, the state or test data, the place to start>
- **Steps:**
  1. <fill in: the first step a person takes>
- **Look for (see, hear, feel):** <fill in: what to notice>
- **Evidence:** `{rel}/`: the video (together from {together}; the change shows at {change}) and the board.
- **OK:** {ok}
- **Not OK:** {not_ok}
"""


def cmd_init(a) -> int:
    root = a.out or os.environ.get("HANDTEST_ROOT")
    if not root:
        raise ValueError("give --out, or set HANDTEST_ROOT to this machine's evidence folder")
    name = folder_name(a.id, a.topic)
    top = None if a.allow_in_repo else _inside_git(root)
    if top:
        print(f"handtest: {root} is inside a git work tree ({top}). Evidence lives outside the repository; "
              "pass --allow-in-repo only if this repository is the evidence store.", file=sys.stderr)
        return 2
    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)
    rel = None
    env_root = os.environ.get("HANDTEST_ROOT")
    if env_root:
        r = os.path.relpath(folder, env_root)
        if not r.startswith(".."):
            rel = r.replace(os.sep, "/")
    if rel is None:
        # Without the evidence root to measure from, the folder it sits in is the group.
        rel = f"{os.path.basename(os.path.abspath(root))}/{name}"
        print(f"note: HANDTEST_ROOT is unset or not a parent of this folder; PACKAGE.md names it {rel}/")
    fields = dict(id=a.id, title=a.title, video=video_name(a.id, a.topic), board=board_name(a.id, a.topic),
                  together=MARK_TOGETHER, change=MARK_CHANGE, rel=rel, sound=SOUND_SPLIT,
                  base=_short(a.base) or "<fill in: base commit>", head=_short(a.head) or "<fill in: head commit>",
                  date=a.date or dt.date.today().isoformat(),
                  ok=a.ok or "<fill in: what OK does in this project>",
                  not_ok=a.not_ok or "<fill in: what Not OK does; usually a comment, the same branch, the evidence made again>")
    data = {"id": a.id, "topic": a.topic, "title": a.title, "base": a.base, "head": a.head,
            "created": fields["date"], "status": "pending", "verdicts": [], "previous": []}
    made, kept = [], []
    for fname, content in (("README.md", README_TEMPLATE.format(**fields)),
                           ("PACKAGE.md", PACKAGE_TEMPLATE.format(**fields)),
                           ("handtest.json", json.dumps(data, indent=2) + "\n")):
        path = os.path.join(folder, fname)
        if os.path.exists(path):
            kept.append(fname)
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        made.append(fname)
    print(f"Evidence folder: {folder}")
    if made:
        print(f"Wrote {', '.join(made)}. Every <fill in: ...> mark is a word you must write.")
    if kept:
        print(f"Kept what was there: {', '.join(kept)}.")
    return 0


SOUND_SPLIT = "BEFORE's sound on the left, AFTER's on the right"


def fill_times(folder: str, together_from: float, change_at: float, sound: bool = True) -> None:
    for fname in ("README.md", "PACKAGE.md"):
        path = os.path.join(folder, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace(MARK_TOGETHER, mmss(together_from)).replace(MARK_CHANGE, mmss(change_at))
        # A redo keeps PACKAGE.md, so times filled by an earlier take are written again.
        text = re.sub(r"(together from )\d+:\d\d", lambda m: m.group(1) + mmss(together_from), text)
        text = re.sub(r"([Tt]he change shows at )\d+:\d\d", lambda m: m.group(1) + mmss(change_at), text)
        text = re.sub(r"(- Format: one video at 30 fps )\([^)]*\)",
                      lambda m: m.group(1) + f"({SOUND_SPLIT if sound else 'no sound'})", text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    data = _load(folder)
    data["video"] = {"together_from": round(together_from, 3), "change_at": round(change_at, 3)}
    _save(folder, data)


def cmd_archive(a) -> int:
    folder = a.folder
    parsed = parse_folder_name(os.path.basename(os.path.normpath(folder)))
    if not parsed:
        raise ValueError(f"{folder} is not an evidence folder (<id>_<topic>_HANDTEST)")
    names = [n for n in (video_name(*parsed), board_name(*parsed), "README.md") if os.path.exists(os.path.join(folder, n))]
    if not names:
        raise ValueError("nothing to archive: no video, board or README.md at the top level")
    stamp = a.stamp or time.strftime("%Y%m%d-%H%M%S", time.localtime(
        max(os.path.getmtime(os.path.join(folder, n)) for n in names)))
    prev = os.path.join(folder, "previous")
    moves = [(n, f"{stamp}_{n}") for n in names]
    clash = [t for _, t in moves if os.path.exists(os.path.join(prev, t))]
    if clash:
        raise FileExistsError(f"previous/{clash[0]} is already there; pass another --stamp")
    os.makedirs(prev, exist_ok=True)
    for src, dst in moves:
        shutil.move(os.path.join(folder, src), os.path.join(prev, dst))
    if os.path.exists(os.path.join(folder, "handtest.json")):
        data = _load(folder)
        data["status"] = "pending"
        data.setdefault("previous", []).append({"stamp": stamp, "files": [d for _, d in moves]})
        data.pop("video", None)
        _save(folder, data)
    print(f"Moved {', '.join(names)} to previous/ as {stamp}_*. Record again, then run init to write a fresh README.md.")
    return 0


def cmd_verdict(a) -> int:
    if a.not_ok and not a.note:
        raise ValueError("a Not OK needs --note: what the person saw that was wrong")
    if a.ok:
        # An OK is only worth recording for evidence a person could judge.
        problems = check_folder(a.folder)
        if problems:
            for p in problems:
                print(f"- {p}", file=sys.stderr)
            print(f"{len(problems)} problem(s): an OK needs a folder that passes check.", file=sys.stderr)
            return 1
    data = _load(a.folder)
    entry = {"verdict": "ok" if a.ok else "not-ok", "by": a.by,
             "at": a.at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if a.note:
        entry["note"] = a.note
    data.setdefault("verdicts", []).append(entry)
    data["status"] = entry["verdict"]
    _save(a.folder, data)
    print(f"Recorded {entry['verdict']} by {a.by} at {entry['at']}.")
    return 0


def _natural(s):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]


def _one_sentence(folder):
    path = os.path.join(folder, "README.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        m = re.search(r"\*\*In one sentence:\*\*\s*(.+)", f.read())
    sentence = m.group(1).strip() if m else ""
    return "" if MARK in sentence else sentence


def _board_data_uri(path, max_w=1600):
    with Image.open(path) as img:
        img = img.convert("RGB")
        if img.width > max_w:
            img = img.resize((max_w, round(img.height * max_w / img.width)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


ORDER = {"pending": 0, "not-ok": 1, "ok": 2}
LABEL = {"pending": "pending", "not-ok": "Not OK", "ok": "OK"}

PAGE_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#14171a;--muted:#5b6570;--line:#dde1e6;
--pending:#9a6b00;--ok:#1c7c44;--bad:#b42d2d}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--card:#1a1e23;--text:#eef0f3;--muted:#9aa3ad;
--line:#2a3038;--pending:#e0b04a;--ok:#4cc27a;--bad:#ee6b6b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{margin:0 0 4px;font-size:28px}
.sum{color:var(--muted);margin:0 0 24px}.card{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:16px;margin:0 0 20px}.card h2{margin:0 0 6px;font-size:20px}
.meta{color:var(--muted);font-size:14px;margin:0 0 10px}.st{font-weight:700}
.st.pending{color:var(--pending)}.st.ok{color:var(--ok)}.st.not-ok{color:var(--bad)}
img,video{display:block;max-width:100%;height:auto;border-radius:6px;margin:10px 0}
a{color:inherit}.prob{color:var(--bad);font-size:14px}
"""


def build_report(root: str, title=None):
    items = []
    for d in sorted(os.listdir(root)):
        parsed = parse_folder_name(d)
        path = os.path.join(root, d)
        if not parsed or not os.path.isdir(path):
            continue
        try:
            data = _load(path)
        except (OSError, ValueError):
            data = {}
        items.append({"dir": d, "id": parsed[0], "topic": parsed[1], "path": path,
                      "title": data.get("title") or parsed[1], "status": data.get("status", "unknown"),
                      "last": (data.get("verdicts") or [None])[-1], "sentence": _one_sentence(path),
                      "video": f"{d}/{video_name(*parsed)}", "board": f"{d}/{board_name(*parsed)}",
                      "problems": check_folder(path)})
    items.sort(key=lambda it: (ORDER.get(it["status"], 1), _natural(it["id"])))
    count = {s: sum(it["status"] == s for it in items) for s in STATUSES}
    other = len(items) - sum(count.values())
    summary = (f"{len(items)} hand test(s): {count['pending']} pending, {count['not-ok']} not OK, {count['ok']} OK"
               + (f", {other} without a status" if other else "") + ".")
    heading = title or "Hand tests"

    def verdict_text(it):
        last = it["last"]
        text = LABEL.get(it["status"], it["status"])
        if last and it["status"] != "pending":
            text += f" ({last.get('by', '?')}, {last.get('at', '?')[:10]})"
            if last.get("note"):
                text += f": {last['note']}"
        return text

    def cell(s):
        return str(s).replace("|", "\\|").replace("<", "&lt;").replace("\n", " ")

    md = [f"# {heading}", "", summary, "", "| Hand test | Verdict | Evidence | Check |", "|---|---|---|---|"]
    for it in items:
        what = f"**{cell(it['id'])}** {cell(it['title'])}" + (f"<br>{cell(it['sentence'])}" if it["sentence"] else "")
        check = "ready" if not it["problems"] else f"{len(it['problems'])} problem(s)"
        links = " · ".join(f"[{kind}]({it[kind]})" if os.path.exists(os.path.join(root, it[kind])) else f"no {kind} yet"
                           for kind in ("video", "board"))
        md.append(f"| {what} | {cell(verdict_text(it))} | {links} | {check} |")
    md_text = "\n".join(md) + "\n"

    e = html.escape
    cards = []
    for it in items:
        board_path = os.path.join(root, it["board"])
        pic = (f'<img alt="BEFORE and AFTER board" src="{_board_data_uri(board_path)}">'
               if os.path.exists(board_path) else "<p class=meta>No board yet.</p>")
        probs = "".join(f"<li>{e(p)}</li>" for p in it["problems"])
        cards.append(
            f'<section class=card id="{e(it["dir"])}"><h2>{e(it["id"])}: {e(it["title"])}</h2>'
            f'<p class=meta><span class="st {e(it["status"])}">{e(verdict_text(it))}</span> · {e(it["dir"])}</p>'
            + (f"<p>{e(it['sentence'])}</p>" if it["sentence"] else "")
            + pic
            + (f'<video controls preload="none" src="{e(it["video"])}"></video>'
               f'<p><a href="{e(it["video"])}">Open the video</a></p>'
               if os.path.exists(os.path.join(root, it["video"])) else "<p class=meta>No video yet.</p>")
            + (f'<details class=prob><summary>{len(it["problems"])} problem(s) before a person sees it</summary>'
               f"<ul>{probs}</ul></details>" if probs else "")
            + "</section>")
    page = (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f'<meta name=viewport content="width=device-width,initial-scale=1"><title>{e(heading)}</title>'
            f"<style>{PAGE_CSS}</style></head><body><main><h1>{e(heading)}</h1><p class=sum>{e(summary)}</p>"
            + "".join(cards) + "</main></body></html>\n")
    md_path, html_path = os.path.join(root, "REPORT.md"), os.path.join(root, "index.html")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)
    return md_path, html_path, summary


def cmd_report(a) -> int:
    md_path, html_path, summary = build_report(a.folder, a.title)
    print(summary)
    print(f"Wrote {md_path} and {html_path}.")
    return 0


def cmd_board(a) -> int:
    with Image.open(a.before) as b, Image.open(a.after) as af:
        img = render_board(b.convert("RGB"), af.convert("RGB"), a.title, a.caption or "")
    img.save(a.out, optimize=True)
    print(f"Wrote {a.out} ({img.width}x{img.height}).")
    return 0


def cmd_check(a) -> int:
    problems = check_folder(a.folder)
    if problems:
        for p in problems:
            print(f"- {p}", file=sys.stderr)
        print(f"{len(problems)} problem(s): fix them before a person sees this.", file=sys.stderr)
        return 1
    print(f"{a.folder}: ready for a person.")
    return 0


# ---------------------------------------------------------------- command line


def build_parser():
    p = argparse.ArgumentParser(prog="handtest.py", description="Make a hand test's evidence: BEFORE beside AFTER.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="make <out>/<id>_<topic>_HANDTEST/ with README, PACKAGE and handtest.json")
    s.add_argument("--out", help="the evidence root or group folder (default: $HANDTEST_ROOT)")
    s.add_argument("--id", required=True, help="the PR, issue or change id, like 142")
    s.add_argument("--topic", required=True, help="kebab-case, like sync-switch")
    s.add_argument("--title", required=True, help="what changes, in plain words")
    s.add_argument("--base", help="the commit BEFORE comes from")
    s.add_argument("--head", help="the commit AFTER comes from")
    s.add_argument("--date", help="YYYY-MM-DD (default: today)")
    s.add_argument("--ok", help="what OK does in this project")
    s.add_argument("--not-ok", dest="not_ok", help="what Not OK does in this project")
    s.add_argument("--allow-in-repo", action="store_true", help="allow an evidence folder inside a git work tree")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("pair", help="the video: intro card, then BEFORE and AFTER together, lined up on the moment")
    s.add_argument("--before", required=True)
    s.add_argument("--after", required=True)
    s.add_argument("--sync-before", type=float, required=True, help="seconds into BEFORE where the moment shows")
    s.add_argument("--sync-after", type=float, required=True, help="seconds into AFTER where the moment shows")
    s.add_argument("--title", required=True)
    s.add_argument("--what", required=True, help="WHAT CHANGES: before and after in plain words, with numbers")
    s.add_argument("--how", help="HOW TO WATCH (default: which side is which, and the sound)")
    s.add_argument("--caption", help="the line under the pair: what to look at")
    s.add_argument("--sub", help="a small line under the title, like the commits and the device")
    s.add_argument("--lead", type=float, default=3.0, help="seconds shown before the moment (default 3)")
    s.add_argument("--tail", type=float, help="seconds shown after the moment (default: until the longer side ends)")
    s.add_argument("--intro-seconds", type=float, default=7.0, help="the intro card's time on screen (default 7)")
    s.add_argument("--layout", choices=("auto", "side", "stacked"), default="auto",
                   help="auto: side by side for portrait, stacked for landscape")
    s.add_argument("--out", required=True, help="<id>_<topic>.mp4, in the evidence folder")
    s.set_defaults(func=cmd_pair)

    s = sub.add_parser("board", help="the board: BEFORE left, AFTER right, at full resolution")
    s.add_argument("--before", required=True)
    s.add_argument("--after", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--caption", help="what to look at")
    s.add_argument("--out", required=True, help="<id>_<topic>_BEFORE_AFTER.png")
    s.set_defaults(func=cmd_board)

    s = sub.add_parser("stills", help="stills for the reviewer pass")
    s.add_argument("video")
    s.add_argument("--out", required=True, help="a scratch folder, not the evidence folder's top level")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--at", type=float, nargs="+", help="seconds")
    g.add_argument("--every", type=float, help="one still every N seconds")
    s.add_argument("--start", type=float, default=0.0, help="with --every: the first still's time (default 0)")
    s.add_argument("--end", type=float, help="with --every: stop here (default: the video's end)")
    s.set_defaults(func=cmd_stills)

    s = sub.add_parser("find-change", help="where a recording's picture changes most between two times")
    s.add_argument("video")
    s.add_argument("--from", dest="from_", type=float, required=True, help="seconds: where to start looking")
    s.add_argument("--to", type=float, required=True, help="seconds: where to stop looking")
    s.add_argument("--top", type=int, default=5, help="how many of the biggest changes to list (default 5)")
    s.add_argument("--crop", help="W:H:X:Y in the recording's pixels, to leave out a clock or status bar")
    s.add_argument("--level", type=int, default=10, help="grey levels a pixel must move to count as changed (default 10)")
    s.set_defaults(func=cmd_find_change)

    s = sub.add_parser("check", help="refuse a folder that is not ready for a person, naming every problem")
    s.add_argument("folder")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("archive", help="the redo: move the video, board and README into previous/")
    s.add_argument("folder")
    s.add_argument("--stamp", help="the prefix (default: the newest file's mtime, YYYYMMDD-HHMMSS)")
    s.set_defaults(func=cmd_archive)

    s = sub.add_parser("verdict", help="record a person's OK or Not OK in handtest.json")
    s.add_argument("folder")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--ok", action="store_true")
    g.add_argument("--not-ok", dest="not_ok", action="store_true")
    s.add_argument("--by", required=True, help="who gave it")
    s.add_argument("--note", help="what they said; needed for a Not OK")
    s.add_argument("--at", help="when, ISO 8601 (default: now, UTC)")
    s.set_defaults(func=cmd_verdict)

    s = sub.add_parser("report", help="REPORT.md and index.html for a folder of hand tests, pending first")
    s.add_argument("folder")
    s.add_argument("--title", help="like Release 1.4")
    s.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError, OSError) as e:
        print(f"handtest: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
