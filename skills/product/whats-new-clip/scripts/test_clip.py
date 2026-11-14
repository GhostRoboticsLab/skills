"""Tests for clip.py.

Run from the repository root:
    uv run --with 'pillow>=10.1' python3 -m unittest discover -s skills/product/whats-new-clip/scripts -v

The pure parts need only Pillow. The render, stills and film checks make tiny
clips with ffmpeg and are skipped when ffmpeg or ffprobe is missing.
Everything is written to temporary folders.
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clip  # noqa: E402

from PIL import Image  # noqa: E402

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = clip.main(argv)
    return code, out.getvalue(), err.getvalue()


def a_spec(**over):
    spec = {
        "product": "Pocket Garden",
        "version": "2.4.0",
        "open": {"line": "What's new in Pocket Garden?"},
        "end": {"lines": ["Pocket Garden", "Free on iOS and Android"]},
        "scenes": [
            {"caption": "Water reminders follow the weather", "source": "water.png", "seconds": 3.5},
            {"caption": "Share a plant with friends", "source": "share.png", "seconds": 3.5},
        ],
    }
    spec.update(over)
    return spec


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def png(self, name, colour=(200, 60, 60), size=(600, 1200)):
        path = os.path.join(self.tmp, name)
        Image.new("RGB", size, colour).save(path)
        return path

    def write_spec(self, spec, name=None):
        path = os.path.join(self.tmp, name or f"{spec['version']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)
        return path

    def ready_spec(self, **over):
        self.png("water.png", (40, 140, 90))
        self.png("share.png", (60, 90, 200))
        return self.write_spec(a_spec(**over))

    def problems(self, spec, name=None, words=False):
        path = self.write_spec(spec, name)
        return clip.problems(clip.load(path), path, self.tmp, words_only=words)

    def assertProblem(self, problems, text):
        self.assertTrue(any(text in p for p in problems), f"no problem says {text!r}: {problems}")


# ---------------------------------------------------------------- pure parts


class ReadingTest(unittest.TestCase):
    def test_a_caption_is_read_twice_at_three_words_a_second(self):
        self.assertEqual(clip.reading_units("Plan your week in one tap"), 6)
        self.assertAlmostEqual(clip.reading_seconds("Plan your week in one tap"), 4.0)

    def test_punctuation_alone_is_not_a_word(self):
        self.assertEqual(clip.reading_units("Plan & share"), 2)

    def test_text_without_spaces_counts_two_characters_a_word(self):
        self.assertEqual(clip.reading_units("新しい機能"), 3)


class ColourTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(clip.parse_colour("#0E1116"), (14, 17, 22))
        with self.assertRaises(ValueError):
            clip.parse_colour("red")

    def test_contrast(self):
        self.assertAlmostEqual(clip.contrast((255, 255, 255), (0, 0, 0)), 21.0, places=1)
        self.assertAlmostEqual(clip.contrast((90, 90, 90), (90, 90, 90)), 1.0)


class TimelineTest(unittest.TestCase):
    def test_open_scenes_end_in_frames(self):
        segs = clip.timeline(clip.normalise(a_spec()))
        self.assertEqual([s["label"] for s in segs], ["open", "scene-01", "scene-02", "end"])
        self.assertEqual([s["frames"] for s in segs], [60, 105, 105, 75])
        self.assertEqual([s["start"] for s in segs], [0.0, 2.0, 5.5, 9.0])
        self.assertAlmostEqual(clip.total_seconds(segs), 11.5)

    def test_a_film_scene_runs_from_in_to_out(self):
        spec = a_spec(scenes=[{"caption": "Hi", "source": "a.mp4", "in": 2.25, "out": 5.0}])
        segs = clip.timeline(clip.normalise(spec))
        self.assertAlmostEqual(segs[1]["seconds"], 2.75, delta=1 / clip.FPS)

    def test_stills_fall_mid_segment(self):
        segs = clip.timeline(clip.normalise(a_spec()))
        self.assertEqual(clip.still_times(segs, 11.5),
                         [("open", 1.0), ("scene-01", 3.75), ("scene-02", 7.25), ("end", 10.25)])
        every = clip.still_times([], 11.5, every=4)
        self.assertEqual(every, [("every", 0.0), ("every", 4.0), ("every", 8.0)])

    def test_every_must_be_more_than_zero(self):
        with self.assertRaises(ValueError):
            clip.still_times([], 10.0, 0)


class LayoutTest(unittest.TestCase):
    def check_inside(self, size, safe):
        W, H = size
        lay = clip.layout(size, safe, line_h=70)
        top, right, bottom, left = safe
        bx, by, bw, bh = lay["band"]
        tx, ty, tw = lay["text"]
        sx, sy, sw, sh = lay["box"]
        self.assertGreaterEqual(by, round(top * H))
        self.assertLessEqual(by + bh, H - bottom * H)
        self.assertGreaterEqual(tx, left * W)
        self.assertLessEqual(tx + tw, W - right * W)
        self.assertGreaterEqual(sy, by + bh)
        self.assertLessEqual(sy + sh, H)
        self.assertLessEqual(sx + sw, W)
        return lay

    def test_vertical_text_stays_in_the_feed_safe_zone(self):
        self.check_inside((1080, 1920), clip.SAFE_TALL)

    def test_landscape(self):
        self.check_inside((1920, 1080), clip.SAFE_WIDE)

    def test_fit_keeps_the_shape_and_even_sides(self):
        w, h = clip.fit(1206, 2622, 1000, 1300)
        self.assertEqual(h, 1300)
        self.assertEqual(w % 2, 0)
        self.assertAlmostEqual(w / h, 1206 / 2622, places=2)


# ---------------------------------------------------------------- check


class CheckTest(TempDirCase):
    def test_a_good_spec_has_no_problems(self):
        path = self.ready_spec()
        self.assertEqual(clip.problems(clip.load(path), path, self.tmp), [])
        code, out, _ = run_main(["check", path])
        self.assertEqual(code, 0, out)
        self.assertIn("check: ok", out)
        self.assertIn("11.5 s", out)

    def test_every_problem_is_named(self):
        spec = a_spec(scenes=[
            {"caption": "Water reminders now follow the weather where you live", "source": "water.png", "seconds": 3.0},
            {"caption": "Hi", "source": "gone.png", "seconds": 1.0},
        ])
        self.png("water.png")
        found = self.problems(spec)
        self.assertProblem(found, "scene-01: caption needs")
        self.assertProblem(found, "read twice")
        self.assertProblem(found, "scene-02: 1.0 s is too short")
        self.assertProblem(found, "scene-02: no file")
        code, out, _ = run_main(["check", os.path.join(self.tmp, "2.4.0.json"), "--media", self.tmp])
        self.assertEqual(code, 1)
        self.assertEqual(len([line for line in out.splitlines() if line.startswith("scene-")]), 3, out)

    def test_a_caption_too_wide_for_two_lines(self):
        self.png("water.png")
        long = "Supercalifragilistic " * 6
        spec = a_spec(scenes=[{"caption": long.strip(), "source": "water.png", "seconds": 20}], max_seconds=60)
        self.assertProblem(self.problems(spec), "two at most")

    def test_more_scenes_than_fit(self):
        self.png("water.png")
        scenes = [{"caption": f"Change {i}", "source": "water.png", "seconds": 5} for i in range(7)]
        self.assertProblem(self.problems(a_spec(scenes=scenes)), "the most is 30.0 s")

    def test_the_file_is_named_after_its_version(self):
        self.ready_spec()
        found = self.problems(a_spec(), name="2.5.0.json")
        self.assertProblem(found, "name it 2.4.0.json")

    def test_fill_in_marks_and_wrong_versions(self):
        self.png("water.png")
        spec = a_spec(scenes=[{"caption": "New in 2.3.0: <fill in: the words>", "source": "water.png", "seconds": 6}])
        found = self.problems(spec)
        self.assertProblem(found, "fill in")
        self.assertProblem(found, "the version is 2.4.0")

    def test_unknown_keys_and_low_contrast(self):
        self.ready_spec()
        spec = a_spec(theme={"band": "#202020", "text": "#303030"}, colour="blue")
        found = self.problems(spec)
        self.assertProblem(found, "no key colour")
        self.assertProblem(found, "contrast")

    def test_a_scene_is_a_film_or_a_still(self):
        self.png("water.png")
        spec = a_spec(scenes=[{"caption": "Hi there", "source": "water.png"}])
        self.assertProblem(self.problems(spec), "needs seconds")
        spec = a_spec(scenes=[{"caption": "Hi there", "source": "water.png", "seconds": 3, "crop": [0.5, 0, 0.8, 1]}])
        self.assertProblem(self.problems(spec), "crop")

    def test_a_picture_blown_up_past_its_pixels(self):
        self.png("small.png", size=(200, 400))
        spec = a_spec(scenes=[{"caption": "Hi there", "source": "small.png", "seconds": 3}])
        self.assertProblem(self.problems(spec), "looks soft")
        self.png("water.png")
        spec = a_spec(scenes=[{"caption": "Hi there", "source": "water.png", "seconds": 3, "crop": [0, 0, 0.5, 0.5]}])
        self.assertProblem(self.problems(spec), "looks soft")

    def test_a_screen_too_small_for_the_frame(self):
        self.png("tall.png", size=(1200, 2400))
        spec = a_spec(scenes=[{"caption": "Hi there", "source": "tall.png", "seconds": 3}])
        path = self.write_spec(spec)
        self.assertEqual(clip.problems(clip.load(path), path, self.tmp), [])
        wide = clip.problems(clip.load(path), path, self.tmp, size=(1920, 1080))
        self.assertProblem(wide, "too small to read")
        spec["scenes"][0]["crop"] = [0, 0.3, 1, 0.4]
        path = self.write_spec(spec)
        self.assertEqual(clip.problems(clip.load(path), path, self.tmp, size=(1920, 1080)), [])

    def test_a_spec_holds_no_path_from_one_machine(self):
        self.png("water.png")
        self.png("share.png")
        logo = self.png("logo.png", size=(200, 200))
        self.assertProblem(self.problems(a_spec(theme={"logo": logo})), "one machine")
        spec = a_spec(scenes=[{"caption": "Hi there", "source": "~/films/water.png", "seconds": 3}])
        self.assertProblem(self.problems(spec, words=True), "one machine")
        self.assertEqual(self.problems(a_spec(theme={"logo": "logo.png"})), [])

    def test_words_only_skips_the_films(self):
        spec = a_spec(scenes=[{"caption": "Share a plant", "source": "<fill in: a film>", "in": 0, "out": 3}])
        self.assertEqual(self.problems(spec, words=True), [])
        self.assertProblem(self.problems(spec), "fill in")


# ---------------------------------------------------------------- init


class InitTest(TempDirCase):
    def test_init_writes_a_skeleton_that_check_refuses(self):
        code, out, err = run_main(["init", "2.5.0", "--out", self.tmp, "--product", "Pocket Garden"])
        self.assertEqual(code, 0, err)
        path = os.path.join(self.tmp, "2.5.0.json")
        spec = clip.load(path)
        self.assertEqual(spec["version"], "2.5.0")
        self.assertEqual(spec["open"]["line"], "What's new in Pocket Garden?")
        self.assertEqual(len(spec["scenes"]), 3)
        code, out, _ = run_main(["check", path, "--words"])
        self.assertEqual(code, 1)
        self.assertIn("fill in", out)
        self.assertNotIn("read twice", out, "a mark's own length is not a caption's")

    def test_init_never_overwrites(self):
        run_main(["init", "2.5.0", "--out", self.tmp])
        code, _, err = run_main(["init", "2.5.0", "--out", self.tmp])
        self.assertNotEqual(code, 0)
        self.assertIn("exists", err)

    def test_the_next_release_starts_from_the_last(self):
        last = self.write_spec(a_spec(theme={"background": "#101820"}))
        code, _, err = run_main(["init", "2.5.0", "--out", self.tmp, "--from", last, "--scenes", "2"])
        self.assertEqual(code, 0, err)
        spec = clip.load(os.path.join(self.tmp, "2.5.0.json"))
        self.assertEqual(spec["theme"]["background"], "#101820")
        self.assertEqual(spec["open"], a_spec()["open"])
        self.assertEqual(spec["end"], a_spec()["end"])
        self.assertEqual(len(spec["scenes"]), 2)
        self.assertTrue(all("fill in" in s["caption"] for s in spec["scenes"]))

    def test_from_and_product_do_not_mix(self):
        last = self.write_spec(a_spec())
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            clip.main(["init", "2.5.0", "--out", self.tmp, "--from", last, "--product", "Other"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "2.5.0.json")))


# ---------------------------------------------------------------- ffmpeg


def probe_streams(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def max_volume(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.search(r"max_volume: (-?[\d.]+) dB", err).group(1))


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg or ffprobe missing")
class FfmpegTest(TempDirCase):
    SIZE = "270x480"

    def ffmpeg(self, *args):
        subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *args], check=True)

    def render(self, path, *extra):
        out = os.path.join(self.tmp, "clip.mp4")
        code, stdout, err = run_main(["render", path, "--out", out, "--size", self.SIZE, *extra])
        self.assertEqual(code, 0, stdout + err)
        return out, stdout

    def test_render_makes_a_clip_platforms_take(self):
        out, stdout = self.render(self.ready_spec())
        info = probe_streams(out)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        a = next(s for s in info["streams"] if s["codec_type"] == "audio")
        self.assertEqual((v["codec_name"], v["width"], v["height"]), ("h264", 270, 480))
        self.assertEqual(v["avg_frame_rate"], "30/1")
        self.assertEqual(v.get("color_space"), "bt709")
        self.assertEqual(a["codec_name"], "aac")
        self.assertAlmostEqual(float(info["format"]["duration"]), 11.5, delta=0.1)
        with open(out, "rb") as f:
            data = f.read()
        self.assertLess(data.find(b"moov"), data.find(b"mdat"), "moov must come first (faststart)")
        self.assertIn("scene-02", stdout)

    def test_the_opening_card_keeps_the_theme_colour(self):
        out, _ = self.render(self.ready_spec(theme={"background": "#123456"}))
        still = os.path.join(self.tmp, "first.png")
        self.ffmpeg("-ss", "0.5", "-i", out, "-frames:v", "1", still)
        r, g, b = Image.open(still).convert("RGB").getpixel((3, 3))
        for got, want in zip((r, g, b), (0x12, 0x34, 0x56)):
            self.assertLessEqual(abs(got - want), 6, (r, g, b))

    def test_a_film_with_frames_only_on_change_shows_what_was_on_screen(self):
        red, blue = self.png("red.png", (220, 30, 30), (320, 640)), self.png("blue.png", (30, 30, 220), (320, 640))
        listing = os.path.join(self.tmp, "list.txt")
        with open(listing, "w") as f:
            f.write(f"file '{red}'\nduration 3\nfile '{blue}'\nduration 2\nfile '{blue}'\n")
        film = os.path.join(self.tmp, "film.mp4")
        self.ffmpeg("-f", "concat", "-safe", "0", "-i", listing, "-fps_mode", "vfr", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", film)
        counted = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                  "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", film],
                                 capture_output=True, text=True, check=True).stdout
        self.assertLessEqual(int(counted.strip()), 5, "the fixture must have frames only where the picture changes")
        spec = a_spec(scenes=[{"caption": "Red stays red", "source": "film.mp4", "in": 2.0, "out": 4.0}])
        out, _ = self.render(self.write_spec(spec))
        still = os.path.join(self.tmp, "mid.png")
        self.ffmpeg("-ss", "2.4", "-i", out, "-frames:v", "1", still)
        lay = clip.layout_for(clip.normalise(spec), (270, 480))
        img = Image.open(still).convert("RGB")
        bx, by, bw, bh = lay["box"]
        r, g, b = img.getpixel((bx + bw // 2, by + bh // 2))
        self.assertGreater(r, 150, (r, g, b))
        self.assertLess(b, 100, (r, g, b))

    def test_check_finds_an_out_past_the_film(self):
        film = os.path.join(self.tmp, "short.mp4")
        self.ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x640:rate=30:duration=2", "-pix_fmt", "yuv420p", film)
        spec = a_spec(scenes=[{"caption": "Too far", "source": "short.mp4", "in": 0.5, "out": 4.0}])
        self.assertProblem(self.problems(spec), "past the end")

    def test_music_sits_under_and_silence_is_silent(self):
        quiet, _ = self.render(self.ready_spec())
        self.assertLess(max_volume(quiet), -80)
        tone = os.path.join(self.tmp, "bed.wav")
        self.ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:duration=4", tone)
        out, _ = self.render(self.ready_spec(music={"file": "bed.wav"}))
        level = max_volume(out)
        self.assertGreater(level, -40)
        self.assertLess(level, -1)

    def test_stills_one_per_segment_and_a_sheet(self):
        path = self.ready_spec()
        out, _ = self.render(path)
        folder = os.path.join(self.tmp, "stills")
        sheet = os.path.join(self.tmp, "sheet.png")
        code, stdout, err = run_main(["stills", out, "--spec", path, "--every", "5", "--out", folder,
                                      "--sheet", sheet])
        self.assertEqual(code, 0, stdout + err)
        names = sorted(os.listdir(folder))
        self.assertEqual([n.split("_")[0] for n in names],
                         ["end", "every", "every", "every", "open", "scene-01", "scene-02"])
        with Image.open(sheet) as img:
            w, h = img.size
        self.assertGreater(w, h)

    def test_stills_tint_what_a_feed_covers(self):
        path = self.ready_spec()
        out, _ = self.render(path)
        plain, tinted = os.path.join(self.tmp, "plain"), os.path.join(self.tmp, "tinted")
        self.assertEqual(run_main(["stills", out, "--spec", path, "--out", plain])[0], 0)
        code, stdout, err = run_main(["stills", out, "--spec", path, "--out", tinted, "--safe"])
        self.assertEqual(code, 0, stdout + err)
        name = next(n for n in sorted(os.listdir(plain)) if n.startswith("scene-01"))
        a = Image.open(os.path.join(plain, name)).convert("RGB")
        b = Image.open(os.path.join(tinted, name)).convert("RGB")
        W, H = a.size
        middle, low = (W // 2, H // 2), (W // 2, round(H * 0.95))
        self.assertEqual(a.getpixel(middle), b.getpixel(middle), "the safe middle stays as filmed")
        self.assertNotEqual(a.getpixel(low), b.getpixel(low), "the band a feed covers is tinted")

    def test_stills_refuse_a_folder_that_holds_an_earlier_runs_stills(self):
        path = self.ready_spec()
        out, _ = self.render(path)
        folder = os.path.join(self.tmp, "stills")
        self.assertEqual(run_main(["stills", out, "--spec", path, "--out", folder])[0], 0)
        code, _, err = run_main(["stills", out, "--spec", path, "--out", folder])
        self.assertEqual(code, 2)
        self.assertIn("fresh folder", err)


if __name__ == "__main__":
    unittest.main()
