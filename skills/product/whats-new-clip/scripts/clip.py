#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10.1"]
# ///
"""Cut a release's What's New clip from a spec: an opening card, one scene per change, an end card.

    uv run scripts/clip.py <command> --help

Commands:
  init     write a spec skeleton for a version, or start it from the last release's spec
  check    name every problem in a spec before anything is rendered
  render   build the clip: h264 + aac, 30 fps, faststart
  stills   pull review stills: one mid-segment per card and scene, and one every N seconds;
           --safe tints what a feed covers
  peek     stills of a film between two of its seconds, read as render reads it: for `in` and `out`

Needs Python 3.9+, Pillow 10.1+, and ffmpeg and ffprobe on PATH for render, stills, peek and film checks.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFont

FPS = 30
READ_WPS = 3.0       # words a second a viewer reads; a caption must be readable twice in its scene
MIN_SCENE = 1.5      # seconds: shorter and a change is a flash
MIN_CARD = 1.0
MAX_LINES = 2
MIN_CONTRAST = 4.5   # WCAG AA for text
MAX_UPSCALE = 1.25   # past this a screen is blown up past its own pixels and reads as soft
MAX_PEEK = 60        # stills in one peek: more than a person looks at
MIN_FILL = 0.2       # under this share of the frame a screen is too small to read: the wrong shape for the size
DEFAULT_SIZE = (1080, 1920)
DEFAULT_MAX = 30.0
OPEN_SECONDS, END_SECONDS = 2.0, 2.5
MUSIC_LUFS = -20.0
# The share of the frame a feed's own buttons, names and captions cover: top, right, bottom, left.
SAFE_TALL = (0.13, 0.15, 0.22, 0.06)
SAFE_WIDE = (0.06, 0.06, 0.06, 0.06)
THEME = {"background": "#0E1116", "band": "#1A2029", "text": "#F4F6F8", "muted": "#A7B0BB", "accent": "#5CD69B"}
CONTRAST_PAIRS = (("text", "band"), ("text", "background"), ("muted", "background"), ("accent", "background"))

TINT = (255, 59, 48)  # what a feed covers, on review stills
STILL_RE = re.compile(r".+_\d+\.\d\ds\.png")
MARK = "<fill in"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
VERSION_RE = re.compile(r"(?<![\d.])\d+\.\d+\.\d+(?![\d.]*\d)")
CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯豈-﫿]")
KEYS = {
    "spec": {"product", "version", "size", "max_seconds", "safe", "theme", "open", "end", "music", "scenes", "note"},
    "theme": set(THEME) | {"font", "logo"},
    "open": {"line", "seconds"},
    "end": {"lines", "image", "seconds"},
    "music": {"file", "lufs"},
    "scene": {"caption", "source", "in", "out", "seconds", "crop", "words_by", "note"},
}

# Every frame leaves the filter graph as BT.709 and says so. Converting RGB without naming the
# matrix gives BT.601 pixels, and a BT.709 label on those shifts every colour.
TO_YUV = ("scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,"
          "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")
ENCODE = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
          "-r", str(FPS), "-g", str(FPS), "-color_primaries", "bt709", "-color_trc", "bt709",
          "-colorspace", "bt709", "-an"]


# ---------------------------------------------------------------- small parts


def num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def parse_colour(text):
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", str(text))
    if not m:
        raise ValueError(f"{text!r} is not a colour like #0E1116")
    v = m.group(1)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def contrast(a, b) -> float:
    def lum(c):
        def ch(x):
            x /= 255
            return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
        r, g, b_ = (ch(x) for x in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def reading_units(text: str) -> int:
    """Words a reader takes in. A run of CJK characters counts one word per two characters."""
    units = 0
    for token in str(text).split():
        cjk = len(CJK_RE.findall(token))
        rest = CJK_RE.sub("", token)
        units += math.ceil(cjk / 2) + (1 if any(c.isalnum() for c in rest) else 0)
    return units


def reading_seconds(text: str) -> float:
    return 2 * reading_units(text) / READ_WPS


def resolve(base: str, path: str) -> str:
    path = os.path.expanduser(str(path))
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))


def is_still(source) -> bool:
    return isinstance(source, str) and os.path.splitext(source)[1].lower() in IMAGE_EXT


def parse_size(text):
    m = re.fullmatch(r"(\d+)x(\d+)", text or "")
    if not m or int(m.group(1)) % 2 or int(m.group(2)) % 2:
        raise ValueError(f"size {text!r}: write WxH with even numbers, like 1080x1920")
    return int(m.group(1)), int(m.group(2))


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}: not valid JSON ({e})") from None


def normalise(spec: dict, size=None, base: str = ".") -> dict:
    """The spec with every default filled in. Tolerates bad types: problems() reports them."""
    s = copy.deepcopy(spec) if isinstance(spec, dict) else {}
    raw = s.get("size")
    ok = isinstance(raw, list) and len(raw) == 2 and all(isinstance(v, int) and v > 0 for v in raw)
    s["size"] = tuple(size or (raw if ok else DEFAULT_SIZE))
    if not num(s.get("max_seconds")):
        s["max_seconds"] = DEFAULT_MAX
    theme = dict(THEME)
    theme.update(s["theme"] if isinstance(s.get("theme"), dict) else {})
    s["theme"] = theme
    W, H = s["size"]
    safe = s.get("safe")
    ok = isinstance(safe, list) and len(safe) == 4 and all(num(v) for v in safe)
    s["safe"] = tuple(safe) if ok else (SAFE_TALL if H > W else SAFE_WIDE)
    for key, seconds in (("open", OPEN_SECONDS), ("end", END_SECONDS)):
        part = dict(s[key]) if isinstance(s.get(key), dict) else {}
        if not num(part.get("seconds")):
            part["seconds"] = seconds
        s[key] = part
    if isinstance(s.get("music"), dict):
        s["music"] = {"lufs": MUSIC_LUFS, **s["music"]}
    else:
        s["music"] = None
    scenes = s.get("scenes") if isinstance(s.get("scenes"), list) else []
    s["scenes"] = [sc for sc in scenes if isinstance(sc, dict)]
    s["_base"] = base
    return s


# ---------------------------------------------------------------- the timeline


def scene_seconds(scene: dict):
    if "in" in scene or "out" in scene:
        a, b = scene.get("in"), scene.get("out")
        return float(b) - float(a) if num(a) and num(b) else None
    return float(scene["seconds"]) if num(scene.get("seconds")) else None


def timeline(s: dict):
    """The clip's segments in order. Each runs a whole number of frames, so the cuts land where it says."""
    segs, frame = [], 0

    def add(kind, label, seconds, **extra):
        nonlocal frame
        n = max(1, int(seconds * FPS + 0.5))
        segs.append({"kind": kind, "label": label, "start": frame / FPS, "seconds": n / FPS, "frames": n, **extra})
        frame += n

    add("open", "open", s["open"]["seconds"])
    for i, sc in enumerate(s["scenes"], 1):
        add("scene", f"scene-{i:02d}", scene_seconds(sc) or 0.0, index=i, scene=sc)
    add("end", "end", s["end"]["seconds"])
    return segs


def total_seconds(segs) -> float:
    return sum(seg["frames"] for seg in segs) / FPS


def still_times(segs, duration: float, every=None):
    """(label, second) pairs: the middle of each segment, then one every `every` seconds."""
    times = [(seg["label"], round(seg["start"] + seg["seconds"] / 2, 3)) for seg in segs]
    if every is not None:
        if every <= 0:
            raise ValueError("--every must be more than 0")
        i = 0
        while i * every < duration - 1e-9:
            times.append(("every", round(i * every, 3)))
            i += 1
    return [(label, t) for label, t in times if 0 <= t < duration]


# ---------------------------------------------------------------- layout and drawing


@lru_cache(maxsize=None)
def font(px, path=None):
    px = max(8, int(round(px)))
    if path:
        return ImageFont.truetype(path, px)
    f = ImageFont.load_default(size=px)
    if not isinstance(f, ImageFont.FreeTypeFont):
        raise RuntimeError("this Pillow has no FreeType; install Pillow 10.1+ from PyPI (uv run brings it)")
    return f


def line_h(f) -> int:
    ascent, descent = f.getmetrics()
    return ascent + descent


def sizes(size):
    u = min(size)
    return {"caption": 0.058 * u, "open": 0.085 * u, "version": 0.036 * u, "end": 0.075 * u,
            "end_small": 0.042 * u, "logo": 0.16 * u, "image": 0.11 * max(size)}


def font_path(s):
    path = s["theme"].get("font")
    if not isinstance(path, str) or MARK in path:
        return None
    path = resolve(s["_base"], path)
    return path if os.path.isfile(path) else None


def wrap(text: str, f, max_w: float):
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}" if cur else word
            if cur and f.getlength(trial) > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    return lines


def layout(size, safe, line_h):
    """Where things go: the caption band at the top of the safe zone, the screen's box under it."""
    W, H = size
    u = min(W, H)
    top, right, bottom, left = safe
    m, pad, bar = round(0.04 * u), round(0.03 * u), max(2, round(0.008 * u))
    band_y = math.ceil(top * H)
    band_h = MAX_LINES * line_h + 2 * pad
    bar_x = math.ceil(left * W)
    text_x = bar_x + bar + pad
    box_y = band_y + band_h + m
    side = math.ceil(max(left, right) * W)
    return {
        "band": (0, band_y, W, band_h),
        "bar": (bar_x, band_y + pad, bar, band_h - 2 * pad),
        "text": (text_x, band_y + pad, math.floor(W - right * W) - text_x),
        "box": (m, box_y, W - 2 * m, H - m - box_y),
        "card": (side, W - 2 * side, (top * H + H - bottom * H) / 2),
    }


def layout_for(s, size=None):
    size = tuple(size or s["size"])
    return layout(size, s["safe"], line_h(font(sizes(size)["caption"], font_path(s))))


def fit(w, h, box_w, box_h):
    scale = min(box_w / w, box_h / h)
    return max(2, int(w * scale) // 2 * 2), max(2, int(h * scale) // 2 * 2)


def screen_rect(lay, src_w, src_h):
    """The screen scaled into the box: centred across, at the box's top so it sits under its caption."""
    bx, by, bw, bh = lay["box"]
    w, h = fit(src_w, src_h, bw, bh)
    return bx + (bw - w) // 2, by, w, h


def colour(s, key):
    return parse_colour(s["theme"][key])


def bold(f):
    return max(1, round(f.size / 48))


def draw_centred(d, lines, f, centre_x, y, fill, stroke=0):
    for line in lines:
        d.text((centre_x - f.getlength(line) / 2, y), line, font=f, fill=fill, stroke_width=stroke, stroke_fill=fill)
        y += line_h(f)
    return y


def picture(path, max_w, max_h):
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def card(s, size, blocks):
    """A card: blocks (a picture, or (lines, font, colour, stroke)) stacked and centred in the safe zone."""
    W, H = size
    img = Image.new("RGB", size, colour(s, "background"))
    d = ImageDraw.Draw(img)
    _, _, centre_y = layout_for(s, size)["card"]
    gap = round(0.03 * min(size))
    heights = [b.height if isinstance(b, Image.Image) else len(b[0]) * line_h(b[1]) for b in blocks]
    y = round(centre_y - (sum(heights) + gap * (len(blocks) - 1)) / 2)
    for block, h in zip(blocks, heights):
        if isinstance(block, Image.Image):
            img.paste(block, ((W - block.width) // 2, y), block)
        else:
            lines, f, fill, stroke = block
            draw_centred(d, lines, f, W / 2, y, fill, stroke)
        y += h + gap
    return img


def logo_block(s, size):
    path = s["theme"].get("logo")
    if not isinstance(path, str) or MARK in path:
        return []
    px = round(sizes(size)["logo"])
    return [picture(resolve(s["_base"], path), px * 3, px)]


def render_open(s, size):
    z, fp = sizes(size), font_path(s)
    _, width, _ = layout_for(s, size)["card"]
    tf, vf = font(z["open"], fp), font(z["version"], fp)
    version = " ".join(str(s.get("version", "")))  # tracked figures
    return card(s, size, logo_block(s, size) + [
        (wrap(s["open"]["line"], tf, width), tf, colour(s, "text"), bold(tf)),
        ([version], vf, colour(s, "accent"), bold(vf)),
    ])


def render_end(s, size):
    z, fp = sizes(size), font_path(s)
    _, width, _ = layout_for(s, size)["card"]
    lines = s["end"].get("lines") or []
    big, small = font(z["end"], fp), font(z["end_small"], fp)
    blocks = logo_block(s, size)
    if lines:
        blocks.append((wrap(lines[0], big, width), big, colour(s, "text"), bold(big)))
    for line in lines[1:]:
        blocks.append((wrap(line, small, width), small, colour(s, "muted"), 0))
    image = s["end"].get("image")
    if isinstance(image, str) and MARK not in image:
        blocks.append(picture(resolve(s["_base"], image), width, round(z["image"])))
    return card(s, size, blocks)


def render_foreground(s, size, caption, rect):
    """Everything over the screen: the background with a rounded hole where the screen shows, and the band."""
    W, H = size
    u = min(W, H)
    lay = layout_for(s, size)
    fg = Image.new("RGBA", size, colour(s, "background") + (255,))
    x, y, w, h = rect
    r, k = round(0.025 * (w + h)), 3
    hole = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(hole).rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=r * k, fill=255)
    alpha = Image.new("L", size, 255)
    alpha.paste(ImageChops.invert(hole.resize((w, h), Image.LANCZOS)), (x, y))
    fg.putalpha(alpha)
    d = ImageDraw.Draw(fg)
    o = max(2, round(0.003 * u))
    d.rounded_rectangle([x - o, y - o, x + w - 1 + o, y + h - 1 + o], radius=r + o, outline=colour(s, "band"), width=o)
    bx, by, bw, bh = lay["band"]
    d.rectangle([bx, by, bx + bw - 1, by + bh - 1], fill=colour(s, "band"))
    ax, ay, aw, ah = lay["bar"]
    d.rectangle([ax, ay, ax + aw - 1, ay + ah - 1], fill=colour(s, "accent"))
    f = font(sizes(size)["caption"], font_path(s))
    tx, _, tw = lay["text"]
    lines = wrap(caption, f, tw)
    ty = by + (bh - len(lines) * line_h(f)) // 2
    for line in lines:
        d.text((tx, ty), line, font=f, fill=colour(s, "text"), stroke_width=bold(f), stroke_fill=colour(s, "text"))
        ty += line_h(f)
    return fg


# ---------------------------------------------------------------- ffmpeg


def need_tools():
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        raise RuntimeError(f"{' and '.join(missing)} must be on PATH for this command")


def run_ffmpeg(args):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y", *args],
                          capture_output=True, text=True)
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
    v = next((st for st in data.get("streams", []) if st.get("codec_type") == "video"), None)
    if v is None:
        raise RuntimeError(f"{path} has no video stream")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for side in v.get("side_data_list") or []:
        if "rotation" in side:
            rot = int(float(side["rotation"]))
    if abs(rot) % 180 == 90:
        w, h = h, w
    duration = float((data.get("format") or {}).get("duration") or v.get("duration") or 0)
    return {"width": w, "height": h, "duration": duration}


def source_size(path):
    if is_still(path):
        with Image.open(path) as img:
            return img.size
    info = probe(path)
    return info["width"], info["height"]


def loop(path):
    return ["-loop", "1", "-framerate", str(FPS), "-i", path]


def encode_card(png, frames, out):
    run_ffmpeg([*loop(png), "-vf", TO_YUV, "-frames:v", str(frames), *ENCODE, out])


# A screen recording has frames only where the picture changed, so a seek in one lands on the
# next change, not on what was on screen. Every read of a film therefore runs it through fps
# first, which holds each frame until the next, and counts from there. start_time=0 counts from
# the film's own start, where its picture starts after its sound.

STEADY = f"fps={FPS}:start_time=0"


def frames_at(video, times, paths):
    """Write the picture on screen at each of `times` (seconds) to the path beside it in `paths`.

    A time falls on the nearest of the film's 30 frames a second, as `trim` rounds it.
    """
    wanted = [max(0, math.floor(t * FPS + 0.5)) for t in times]
    numbers = sorted(set(wanted))
    with tempfile.TemporaryDirectory() as td:
        got = {}
        for i in range(0, len(numbers), 100):
            part = numbers[i:i + 100]
            pick = "+".join(f"eq(n,{n})" for n in part)
            # tpad holds the last picture, so a time after the film's last change still has a frame.
            vf = (f"{STEADY},tpad=stop_mode=clone:stop_duration={part[-1] / FPS + 1:.3f},"
                  f"select='{pick}',setpts=N/({FPS}*TB)")
            run_ffmpeg(["-i", video, "-vf", vf, "-frames:v", str(len(part)),
                        os.path.join(td, f"{i:05d}_%05d.png")])
            for k, n in enumerate(part, start=1):
                got[n] = os.path.join(td, f"{i:05d}_{k:05d}.png")
        for n, path in zip(wanted, paths):
            if not os.path.exists(got[n]):
                raise RuntimeError(f"ffmpeg wrote no frame for {n / FPS:.2f} s of {video}")
            shutil.copyfile(got[n], path)


def encode_scene(bg, fg, src, seg, rect, out):
    sc, (x, y, w, h) = seg["scene"], rect
    if is_still(src):
        src_in, chain = loop(src), ""
    else:
        src_in = ["-i", src]
        chain = f"{STEADY},trim=start={float(sc['in']):.3f}:end={float(sc['out']):.3f},setpts=PTS-STARTPTS,"
    if sc.get("crop"):
        sw, sh = source_size(src)
        cx, cy, cw, ch = sc["crop"]
        chain += f"crop={round(cw * sw)}:{round(ch * sh)}:{round(cx * sw)}:{round(cy * sh)},"
    chain += f"scale={w}:{h}:flags=lanczos,setsar=1"
    graph = (f"[1:v]{chain}[s];[0:v][s]overlay={x}:{y}:eof_action=repeat:format=rgb[t];"
             f"[t][2:v]overlay=0:0:format=rgb,{TO_YUV}[v]")
    run_ffmpeg([*loop(bg), *src_in, *loop(fg), "-filter_complex", graph, "-map", "[v]",
                "-frames:v", str(seg["frames"]), *ENCODE, out])


# ---------------------------------------------------------------- check


def strings(obj, where):
    if isinstance(obj, str):
        yield where, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings(v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strings(v, f"{where}[{i}]")


def problems(spec, path, media=None, words_only=False, size=None):
    """Every problem in a spec, each as one line. words_only skips the films and other files."""
    if not isinstance(spec, dict):
        return ["spec: the top level must be an object"]
    base = os.path.dirname(os.path.abspath(path))
    media = media or base
    bad = []
    s = normalise(spec, size, base)
    W, H = s["size"]

    def keys(obj, kind, where):
        if isinstance(obj, dict):
            bad.extend(f"{where}: no key {k}" for k in sorted(set(obj) - KEYS[kind]))
        elif obj is not None:
            bad.append(f"{where}: must be an object")

    keys(spec, "spec", "spec")
    for part in ("theme", "open", "end", "music"):
        keys(spec.get(part), part, part)

    texts = [(w, t) for k, v in spec.items() if k != "scenes" for w, t in strings(v, k)]
    for i, sc in enumerate(spec.get("scenes") or [], 1):
        texts += list(strings(sc, f"scene-{i:02d}"))
    for where, text in texts:
        if MARK in text and not (words_only and where.endswith((".source", ".file", ".logo", ".image", ".font"))):
            bad.append(f"{where}: still a {MARK} ...> mark; write it (or drop the key, where it is optional)")

    version = spec.get("version")
    if not isinstance(version, str) or not version.strip():
        bad.append("spec: no version")
    else:
        name = os.path.basename(path)
        if name != f"{version}.json":
            bad.append(f"version {version}: the file is {name}; name it {version}.json, "
                       "so a copy of the last release's spec cannot keep its version")
        for where, text in texts:
            bad += [f"{where}: says {v}, but the version is {version}"
                    for v in VERSION_RE.findall(text) if v != version]

    raw = spec.get("size")
    if raw is not None and not (isinstance(raw, list) and len(raw) == 2
                                and all(isinstance(v, int) and v >= 64 and v % 2 == 0 for v in raw)):
        bad.append("size: [width, height] in pixels, both even")
    if "max_seconds" in spec and not (num(spec["max_seconds"]) and spec["max_seconds"] > 0):
        bad.append("max_seconds: the longest the clip may run, in seconds")
    if "safe" in spec and not (isinstance(spec["safe"], list) and len(spec["safe"]) == 4
                               and all(num(v) and 0 <= v < 0.45 for v in spec["safe"])):
        bad.append("safe: [top, right, bottom, left], each a share of the frame from 0 to 0.45")

    good = {}
    for key in THEME:
        try:
            good[key] = parse_colour(s["theme"][key])
        except ValueError as e:
            bad.append(f"theme.{key}: {e}")
    for a, b in CONTRAST_PAIRS:
        if a in good and b in good and contrast(good[a], good[b]) < MIN_CONTRAST:
            bad.append(f"theme: {a} on {b} has contrast {contrast(good[a], good[b]):.1f}:1; "
                       f"text needs {MIN_CONTRAST}:1 or more")

    def need_file(where, value, root):
        if words_only or not isinstance(value, str) or MARK in value:
            return None
        full = resolve(root, value)
        if not os.path.isfile(full):
            bad.append(f"{where}: no file {full}")
            return None
        return full

    paths = [("theme.font", s["theme"].get("font"), "the spec's folder"),
             ("theme.logo", s["theme"].get("logo"), "the spec's folder"),
             ("end.image", s["end"].get("image"), "the spec's folder"),
             ("music.file", (s["music"] or {}).get("file"), "--media")]
    paths += [(f"scene-{i:02d}", sc.get("source"), "--media")
              for i, sc in enumerate(spec.get("scenes") or [], 1) if isinstance(sc, dict)]
    for where, value, root in paths:
        if isinstance(value, str) and MARK not in value and (os.path.isabs(value) or value.startswith("~")):
            bad.append(f"{where}: {value} holds on one machine only; write the path relative to {root}")

    font_file = need_file("theme.font", s["theme"].get("font"), base)
    if font_file:
        try:
            ImageFont.truetype(font_file, 20)
        except OSError:
            bad.append(f"theme.font: {font_file} is not a font Pillow can read")
    need_file("theme.logo", s["theme"].get("logo"), base)
    need_file("end.image", s["end"].get("image"), base)
    if s["music"] is not None:
        need_file("music.file", s["music"].get("file"), media)
        if not num(s["music"]["lufs"]) or not -40 <= s["music"]["lufs"] <= -10:
            bad.append("music.lufs: a loudness from -40 to -10")

    z, fp = sizes((W, H)), font_path(s)
    lay = layout_for(s)
    _, card_w, _ = lay["card"]
    for part in ("open", "end"):
        if s[part]["seconds"] < MIN_CARD:
            bad.append(f"{part}.seconds: {MIN_CARD} or more, so the card can be read")
    line = s["open"].get("line")
    if not isinstance(line, str) or not line.strip():
        bad.append("open.line: the fixed opening line, the same every release")
    elif MARK not in line and len(wrap(line, font(z["open"], fp), card_w)) > 3:
        bad.append("open.line: runs past three lines on the card; shorten it")
    lines = s["end"].get("lines")
    if not isinstance(lines, list) or not lines or not all(isinstance(x, str) and x.strip() for x in lines):
        bad.append("end.lines: the product's name, then where to get it")
    else:
        for i, text in enumerate(lines):
            f = font(z["end"] if i == 0 else z["end_small"], fp)
            if MARK not in text and len(wrap(text, f, card_w)) > 2:
                bad.append(f"end.lines[{i}]: runs past two lines on the card; shorten it")

    scenes = spec.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        bad.append("scenes: none; a clip shows at least one change")
        scenes = []
    cap_font = font(z["caption"], fp)
    _, _, text_w = lay["text"]
    for i, sc in enumerate(scenes, 1):
        label = f"scene-{i:02d}"
        if not isinstance(sc, dict):
            bad.append(f"{label}: must be an object")
            continue
        keys(sc, "scene", label)
        caption = sc.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            bad.append(f"{label}: no caption")
            caption = ""
        elif MARK in caption:
            caption = ""  # reported above; its length means nothing yet
        film = "in" in sc or "out" in sc
        if film:
            a, b = sc.get("in"), sc.get("out")
            if not (num(a) and num(b) and 0 <= a < b):
                bad.append(f"{label}: a film needs in and out, seconds into the film, in before out")
            if "seconds" in sc:
                bad.append(f"{label}: a film takes in and out, not seconds")
        elif "seconds" not in sc:
            bad.append(f"{label}: needs seconds (a still) or in and out (a film)")
        elif not num(sc["seconds"]) or sc["seconds"] <= 0:
            bad.append(f"{label}: seconds is how long the still shows")
        source = sc.get("source")
        if not words_only and isinstance(source, str) and MARK not in source:
            if film and is_still(source):
                bad.append(f"{label}: {source} is a still; give it seconds, not in and out")
            if not film and not is_still(source):
                bad.append(f"{label}: {source} is a film; give it in and out, not seconds")
        have = scene_seconds(sc)
        if have is not None and have < MIN_SCENE:
            bad.append(f"{label}: {have:.1f} s is too short to see; a scene runs {MIN_SCENE} s or more")
        if caption and have is not None and reading_seconds(caption) > have + 1e-9:
            bad.append(f"{label}: caption needs {reading_seconds(caption):.1f} s to be read twice and the scene "
                       f"has {have:.1f} s; shorten the words or lengthen the scene")
        if caption:
            wrapped = wrap(caption, cap_font, text_w)
            if len(wrapped) > MAX_LINES:
                bad.append(f"{label}: caption runs to {len(wrapped)} lines at this size; two at most, so shorten it")
            elif any(cap_font.getlength(x) > text_w for x in wrapped):
                bad.append(f"{label}: a word in the caption is wider than the band; shorten it")
        crop = sc.get("crop")
        if crop is not None and not (isinstance(crop, list) and len(crop) == 4 and all(num(v) for v in crop)
                                     and crop[0] >= 0 and crop[1] >= 0 and crop[2] > 0 and crop[3] > 0
                                     and crop[0] + crop[2] <= 1 and crop[1] + crop[3] <= 1):
            bad.append(f"{label}: crop is [x, y, w, h], shares of the film's frame, with x + w and y + h at most 1")
            crop = None
        if words_only:
            continue
        if not isinstance(source, str) or not source.strip():
            bad.append(f"{label}: no source")
        full = need_file(label, source, media)
        pixels = None
        if full and not is_still(full):
            try:
                info = probe(full)
            except RuntimeError as e:
                bad.append(f"{label}: {e}")
            else:
                pixels = info["width"], info["height"]
                if film and num(sc.get("out")) and sc["out"] > info["duration"] + 0.05:
                    bad.append(f"{label}: out {sc['out']} is past the end of {source} ({info['duration']:.2f} s)")
        elif full:
            try:
                with Image.open(full) as img:
                    pixels = img.size
            except OSError:
                bad.append(f"{label}: {source} is not an image Pillow can read")
        if pixels:
            pw, ph = pixels
            if crop:
                pw, ph = max(2, round(crop[2] * pw)), max(2, round(crop[3] * ph))
            _, _, w, h = screen_rect(lay, pw, ph)
            shown, fill = w / pw, w * h / (W * H)
            if shown > MAX_UPSCALE:
                bad.append(f"{label}: shown at {shown:.1f}x its own pixels, so it looks soft; "
                           "crop less, or capture at a higher resolution")
            elif fill < MIN_FILL:
                bad.append(f"{label}: the screen fills {100 * fill:.0f}% of a {W}x{H} frame, too small to read; "
                           "crop to the change, or leave this size out")

    total = total_seconds(timeline(s))
    if total > s["max_seconds"] + 1e-9:
        bad.append(f"the clip runs {total:.1f} s with its cards and the most is {s['max_seconds']:.1f} s: "
                   "drop a scene or shorten one")
    return bad


# ---------------------------------------------------------------- commands


def skeleton_scene(i):
    return {
        "caption": f"{MARK}: change {i}, in the approver's words>",
        "words_by": f"{MARK}: who gave these words>",
        "source": f"{MARK}: the film of change {i}, relative to --media>",
        "in": 0.0,
        "out": 4.0,
    }


def cmd_init(a) -> int:
    if a.scenes < 1:
        raise ValueError("--scenes must be 1 or more")
    path = os.path.join(a.out, f"{a.version}.json")
    if os.path.exists(path):
        raise ValueError(f"{path} exists; edit it, or remove it first")
    scenes = [skeleton_scene(i) for i in range(1, a.scenes + 1)]
    if a.from_spec:
        last = load(a.from_spec)
        spec = {}
        for key, value in last.items():
            if key == "version":
                spec[key] = a.version
            elif key not in ("scenes", "note"):
                spec[key] = value
        spec.setdefault("version", a.version)
        spec["scenes"] = scenes
    else:
        name = a.product or f"{MARK}: the product's name>"
        spec = {
            "product": name,
            "version": a.version,
            "size": list(DEFAULT_SIZE),
            "max_seconds": DEFAULT_MAX,
            "theme": dict(THEME),
            "open": {"line": f"What's new in {a.product}?" if a.product else f"{MARK}: the fixed opening line>",
                     "seconds": OPEN_SECONDS},
            "end": {"lines": [name, f"{MARK}: where to get it>"], "seconds": END_SECONDS},
            "scenes": scenes,
        }
    os.makedirs(a.out, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {path}. Fill every {MARK} ...> mark, then: clip.py check {path} --words")
    return 0


def cmd_check(a) -> int:
    spec = load(a.spec)
    size = parse_size(a.size) if a.size else None
    found = problems(spec, a.spec, a.media, words_only=a.words, size=size)
    for line in found:
        print(line)
    if found:
        print(f"check: {len(found)} problem(s)")
        return 1
    s = normalise(spec, size, os.path.dirname(os.path.abspath(a.spec)))
    W, H = s["size"]
    note = " (words only: films and files not checked)" if a.words else ""
    print(f"check: ok, {len(s['scenes'])} scene(s), {total_seconds(timeline(s)):.1f} s at {W}x{H}{note}")
    return 0


def cmd_render(a) -> int:
    spec = load(a.spec)
    size = parse_size(a.size) if a.size else None
    base = os.path.dirname(os.path.abspath(a.spec))
    media = a.media or base
    found = problems(spec, a.spec, media, size=size)
    if found:
        for line in found:
            print(line)
        print(f"render: {len(found)} problem(s); run check, fix them, then render")
        return 1
    need_tools()
    s = normalise(spec, size, base)
    size = s["size"]
    segs = timeline(s)
    total = total_seconds(segs)
    lay = layout_for(s)
    with tempfile.TemporaryDirectory() as td:
        bg = os.path.join(td, "bg.png")
        Image.new("RGB", size, colour(s, "background")).save(bg)
        parts = []
        for n, seg in enumerate(segs):
            out = os.path.join(td, f"seg{n:03d}.mp4")
            if seg["kind"] == "scene":
                src = resolve(media, seg["scene"]["source"])
                sw, sh = source_size(src)
                crop = seg["scene"].get("crop")
                if crop:
                    sw, sh = max(2, round(crop[2] * sw)), max(2, round(crop[3] * sh))
                rect = screen_rect(lay, sw, sh)
                fg = os.path.join(td, f"fg{n:03d}.png")
                render_foreground(s, size, seg["scene"]["caption"], rect).save(fg)
                encode_scene(bg, fg, src, seg, rect, out)
            else:
                png = os.path.join(td, f"{seg['kind']}.png")
                (render_open if seg["kind"] == "open" else render_end)(s, size).save(png)
                encode_card(png, seg["frames"], out)
            parts.append(out)
        listing = os.path.join(td, "list.txt")
        with open(listing, "w", encoding="utf-8") as f:
            f.writelines("file '{}'\n".format(p.replace("'", "'\\''")) for p in parts)
        args = ["-f", "concat", "-safe", "0", "-i", listing]
        if s["music"]:
            fade = min(1.5, s["end"]["seconds"])
            args += ["-stream_loop", "-1", "-i", resolve(media, s["music"]["file"])]
            audio = (f"[1:a]aresample=48000,loudnorm=I={s['music']['lufs']}:TP=-2:LRA=11,aresample=48000,"
                     f"aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=duration={total:.3f},"
                     f"afade=t=in:d=0.5,afade=t=out:st={max(0.0, total - fade):.3f}:d={fade:.3f}[a]")
        else:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            audio = f"[1:a]atrim=duration={total:.3f}[a]"
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        run_ffmpeg(args + ["-filter_complex", audio, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
                           "-movflags", "+faststart", a.out])
    music = "a music bed under it" if s["music"] else "a silent sound track"
    print(f"Wrote {a.out}: {total:.1f} s, {size[0]}x{size[1]}, {FPS} fps, h264 + aac, {music}.")
    for seg in segs:
        words = seg["scene"]["caption"].replace("\n", " ") if seg["kind"] == "scene" else ""
        print(f"  {seg['start']:5.1f} s  {seg['label']:<9} {words}".rstrip())
    print(f"Next: clip.py stills {a.out} --spec {a.spec} --every 1 --safe --out <a fresh folder>, "
          "and look at every one.")
    return 0


def render_sheet(items, out, tile_h=480):
    """Stills side by side, each labelled with its segment and second."""
    tiles = []
    for path, text in items:
        img = Image.open(path).convert("RGB")
        tiles.append((img.resize((max(1, round(img.width * tile_h / img.height)), tile_h), Image.LANCZOS), text))
    cols = min(len(tiles), 6)
    rows = math.ceil(len(tiles) / cols)
    tw = max(t.width for t, _ in tiles)
    gap, label = round(tile_h * 0.04), round(tile_h * 0.09)
    sheet = Image.new("RGB", (gap + cols * (tw + gap), gap + rows * (tile_h + label + gap)), (17, 20, 24))
    d = ImageDraw.Draw(sheet)
    f = font(label * 0.55)
    for n, (tile, text) in enumerate(tiles):
        x = gap + (n % cols) * (tw + gap) + (tw - tile.width) // 2
        y = gap + (n // cols) * (tile_h + label + gap)
        sheet.paste(tile, (x, y))
        d.text((x, y + tile_h + label * 0.2), text, font=f, fill=(190, 197, 206))
    if out.lower().endswith((".jpg", ".jpeg")):
        sheet.save(out, quality=85, optimize=True)
    else:
        sheet.save(out, optimize=True)


def tint_unsafe(path, safe):
    """Tint the edges of a still that a feed covers with its own buttons, names and captions."""
    img = Image.open(path).convert("RGBA")
    W, H = img.size
    top, right, bottom, left = safe
    veil = Image.new("RGBA", img.size, TINT + (90,))
    inside = [round(left * W), round(top * H), round(W - right * W) - 1, round(H - bottom * H) - 1]
    ImageDraw.Draw(veil).rectangle(inside, fill=(0, 0, 0, 0), outline=TINT + (255,),
                                   width=max(2, round(0.004 * min(W, H))))
    Image.alpha_composite(img, veil).convert("RGB").save(path)


def fresh_folder(out):
    if os.path.isdir(out) and any(STILL_RE.fullmatch(n) for n in os.listdir(out)):
        raise ValueError(f"{out} holds stills from an earlier run; use a fresh folder for each run")


def cmd_stills(a) -> int:
    if not a.spec and a.every is None:
        raise ValueError("give --spec (a still mid-segment) or --every N, or both")
    fresh_folder(a.out)
    info = probe(a.video)
    duration = info["duration"]
    base = os.path.dirname(os.path.abspath(a.spec)) if a.spec else "."
    s = normalise(load(a.spec) if a.spec else {}, (info["width"], info["height"]), base)
    segs = []
    if a.spec:
        segs = timeline(s)
        if abs(total_seconds(segs) - duration) > 0.2:
            print(f"note: the spec runs {total_seconds(segs):.1f} s and the video {duration:.1f} s; "
                  "render again if the spec changed")
    times = still_times(segs, duration, a.every)
    os.makedirs(a.out, exist_ok=True)
    times = sorted(times, key=lambda x: (x[1], x[0]))
    paths = [os.path.join(a.out, f"{label}_{t:06.2f}s.png") for label, t in times]
    frames_at(a.video, [t for _, t in times], paths)
    items = []
    for (label, t), path in zip(times, paths):
        if a.safe:
            tint_unsafe(path, s["safe"])
        items.append((path, f"{label}  {t:.1f} s"))
        print(path)
    if a.sheet and items:
        render_sheet(items, a.sheet)
        print(a.sheet)
    print(f"Wrote {len(items)} still(s). Look at every one before a person sees the clip.")
    return 0


def peek_times(start: float, end: float, every: float, duration: float):
    """The seconds of a film to look at: from `start` to `end`, one every `every`, inside the film."""
    if every <= 0:
        raise ValueError("--every must be more than 0")
    if start < 0 or end < start:
        raise ValueError("--to must not be before --from, and neither before 0")
    if start >= duration:
        raise ValueError(f"--from {start:g} is past the film, which is {duration:.2f} s long")
    times, i = [], 0
    while start + i * every <= min(end, duration - 1e-6) + 1e-9:
        t = round(start + i * every, 2)        # a still's name holds two decimals, under a frame apart
        if t not in times[-1:]:
            times.append(t)
        i += 1
    if len(times) > MAX_PEEK:
        raise ValueError(f"that is {len(times)} stills, and {MAX_PEEK} is the most for one look: "
                         "bring --from and --to closer, or raise --every")
    return times


def cmd_peek(a) -> int:
    fresh_folder(a.out)
    duration = probe(a.film)["duration"]
    times = peek_times(a.from_, a.to, a.every, duration)
    if a.to >= duration:
        print(f"note: the film is {duration:.2f} s long, so the stills stop there")
    os.makedirs(a.out, exist_ok=True)
    paths = [os.path.join(a.out, f"peek_{t:06.2f}s.png") for t in times]
    frames_at(a.film, times, paths)
    for path in paths:
        print(path)
    if a.sheet:
        render_sheet([(path, f"{t:.2f} s") for path, t in zip(paths, times)], a.sheet)
        print(a.sheet)
    print(f"Wrote {len(paths)} still(s) of {os.path.basename(a.film)}, each what render shows at that second "
          "of the film. Set `in` and `out` from these.")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="clip.py", description="Cut a release's What's New clip from a spec.")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="write a spec skeleton for a version")
    i.add_argument("version", help="the release's version; the spec is written as <version>.json")
    i.add_argument("--out", required=True, help="the folder the spec goes in")
    start = i.add_mutually_exclusive_group()
    start.add_argument("--from", dest="from_spec", help="the last release's spec: keep its look, cards and music")
    start.add_argument("--product", help="the product's name, for a first spec")
    i.add_argument("--scenes", type=int, default=3, help="how many scene skeletons (default 3)")

    c = sub.add_parser("check", help="name every problem in a spec")
    c.add_argument("spec")
    c.add_argument("--media", help="the folder scene sources and music are relative to (default: the spec's)")
    c.add_argument("--words", action="store_true", help="check only the words and lengths, before filming")
    c.add_argument("--size", help="check at another size, WxH")

    r = sub.add_parser("render", help="build the clip")
    r.add_argument("spec")
    r.add_argument("--out", required=True, help="the .mp4 to write")
    r.add_argument("--media", help="the folder scene sources and music are relative to (default: the spec's)")
    r.add_argument("--size", help="render at another size, WxH, such as 1920x1080")

    s = sub.add_parser("stills", help="pull review stills from a rendered clip")
    s.add_argument("video")
    s.add_argument("--out", required=True, help="a fresh folder for the stills")
    s.add_argument("--spec", help="the clip's spec: one still in the middle of each card and scene")
    s.add_argument("--every", type=float, help="also one still every N seconds")
    s.add_argument("--safe", action="store_true",
                   help="tint the edges a feed covers with its own buttons and captions (the spec's safe zone)")
    s.add_argument("--sheet", help="also lay every still out in one image (.png or .jpg)")

    k = sub.add_parser("peek", help="stills of a film between two of its seconds, read as render reads it")
    k.add_argument("film")
    k.add_argument("--from", dest="from_", type=float, required=True, help="the film's second to start at")
    k.add_argument("--to", type=float, required=True, help="the film's second to stop at")
    k.add_argument("--every", type=float, default=0.5, help="one still every N seconds (default 0.5)")
    k.add_argument("--out", required=True, help="a fresh folder for the stills")
    k.add_argument("--sheet", help="also lay every still out in one image (.png or .jpg)")
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return {"init": cmd_init, "check": cmd_check, "render": cmd_render, "stills": cmd_stills,
                "peek": cmd_peek}[a.cmd](a)
    except (ValueError, RuntimeError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
