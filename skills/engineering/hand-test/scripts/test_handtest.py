"""Tests for handtest.py.

Run from the repository root:
    uv run --with 'pillow>=10.1' python3 -m unittest discover -s skills/engineering/hand-test/scripts -v

The pure parts need only Pillow. The integration tests make tiny clips with
ffmpeg's lavfi sources and are skipped when ffmpeg or ffprobe is missing.
Everything is written to temporary folders.
"""

import array
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handtest as ht  # noqa: E402

from PIL import Image  # noqa: E402

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
HAVE_GIT = bool(shutil.which("git"))


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ht.main(argv)
    return code, out.getvalue(), err.getvalue()


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def make_ready_folder(self, id_="142", topic="sync-switch"):
        """An evidence folder that passes check: init, marks filled, media present."""
        code, _, err = run_main([
            "init", "--out", self.tmp, "--id", id_, "--topic", topic,
            "--title", "The sync switch shows its state",
            "--base", "a1b2c3d4e5f6a7b8", "--head", "0f9e8d7c6b5a4938",
            "--date", "2026-11-14",
        ])
        self.assertEqual(code, 0, err)
        folder = os.path.join(self.tmp, ht.folder_name(id_, topic))
        for name in ("README.md", "PACKAGE.md"):
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(re.sub(r"<fill in[^>]*>", "done", text))
        with open(os.path.join(folder, ht.video_name(id_, topic)), "wb") as f:
            f.write(b"video")
        Image.new("RGB", (8, 8)).save(os.path.join(folder, ht.board_name(id_, topic)))
        return folder


# ---------------------------------------------------------------- names


class NamesTest(unittest.TestCase):
    def test_names_follow_the_pattern(self):
        self.assertEqual(ht.folder_name("142", "sync-switch"), "142_sync-switch_HANDTEST")
        self.assertEqual(ht.video_name("142", "sync-switch"), "142_sync-switch.mp4")
        self.assertEqual(ht.board_name("142", "sync-switch"), "142_sync-switch_BEFORE_AFTER.png")

    def test_folder_name_parses_back(self):
        self.assertEqual(ht.parse_folder_name("PR-7_dark-mode_HANDTEST"), ("PR-7", "dark-mode"))
        self.assertIsNone(ht.parse_folder_name("142_sync-switch"))
        self.assertIsNone(ht.parse_folder_name("142_Sync_Switch_HANDTEST"))

    def test_bad_ids_and_topics_are_refused(self):
        for id_, topic in [("1_2", "a"), ("142", "Sync"), ("142", "sync_switch"),
                           ("142", "sync-switch-v2-"), ("", "a"), ("142", "")]:
            with self.assertRaises(ValueError, msg=(id_, topic)):
                ht.folder_name(id_, topic)


# ---------------------------------------------------------------- pair maths


class PairMathTest(unittest.TestCase):
    def test_auto_layout_reads_the_shape(self):
        self.assertEqual(ht.choose_layout(1080, 2400), "side")
        self.assertEqual(ht.choose_layout(1920, 1080), "stacked")
        self.assertEqual(ht.choose_layout(800, 800), "side")
        self.assertEqual(ht.choose_layout(1920, 1080, "side"), "side")
        self.assertEqual(ht.choose_layout(1080, 2400, "stacked"), "stacked")
        with self.assertRaises(ValueError):
            ht.choose_layout(10, 10, "diagonal")

    def test_sync_moments_meet_on_the_same_output_time(self):
        start_b, start_a, lead = ht.sync_offsets(6.9, 6.5)
        self.assertAlmostEqual(start_b, 0.4)
        self.assertAlmostEqual(start_a, 0.0)
        self.assertAlmostEqual(lead, 6.5)
        self.assertAlmostEqual(6.9 - start_b, 6.5 - start_a)

    def test_sync_offsets_keep_the_lead(self):
        start_b, start_a, lead = ht.sync_offsets(6.9, 6.5, lead=3.0)
        self.assertAlmostEqual(start_b, 3.9)
        self.assertAlmostEqual(start_a, 3.5)
        self.assertAlmostEqual(lead, 3.0)

    def test_sync_offsets_clamp_a_lead_longer_than_the_recording(self):
        start_b, start_a, lead = ht.sync_offsets(1.0, 2.5, lead=3.0)
        self.assertAlmostEqual((start_b, start_a, lead), (0.0, 1.5, 1.0))
        with self.assertRaises(ValueError):
            ht.sync_offsets(-1.0, 2.0)

    def test_pair_runs_until_the_longer_side_ends_unless_a_tail_cuts_it(self):
        self.assertAlmostEqual(ht.pair_duration(3.0, 2.5, lead=1.0), 3.0)
        self.assertAlmostEqual(ht.pair_duration(3.0, 2.5, lead=1.0, tail=1.0), 2.0)
        self.assertAlmostEqual(ht.pair_duration(3.0, 2.5, lead=1.0, tail=9.0), 3.0)

    def test_fit_keeps_the_shape_and_even_sizes(self):
        self.assertEqual(ht.fit(1080, 2400, 900, 800), (360, 800))
        w, h = ht.fit(1920, 1080, 1000, 600)
        self.assertLessEqual(w, 1000)
        self.assertLessEqual(h, 600)
        self.assertEqual((w % 2, h % 2), (0, 0))
        self.assertAlmostEqual(w / h, 1920 / 1080, delta=0.02)

    def assert_inside(self, rect, canvas):
        x, y, w, h = rect
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + w, canvas[0])
        self.assertLessEqual(y + h, canvas[1])

    def assert_badge_on_its_side(self, badge, video):
        bx, by, bw, bh = badge
        vx, vy, vw, vh = video
        self.assertAlmostEqual(bx + bw / 2, vx + vw / 2, delta=1)
        self.assertLessEqual(by + bh, vy)

    def test_side_layout_puts_before_left_with_badges_over_their_own_side(self):
        lay = ht.pair_layout("side", (1080, 2400), (1080, 2400))
        self.assertEqual(lay["canvas"], (1920, 1080))
        b, a = lay["before"], lay["after"]
        self.assertLessEqual(b[0] + b[2], a[0])
        self.assertLessEqual(b[0] + b[2], 1920 / 2)
        self.assertGreaterEqual(a[0], 1920 / 2)
        for key in ("before", "after", "badge_before", "badge_after", "caption", "header"):
            self.assert_inside(lay[key], lay["canvas"])
        self.assert_badge_on_its_side(lay["badge_before"], b)
        self.assert_badge_on_its_side(lay["badge_after"], a)

    def test_stacked_layout_puts_before_on_top(self):
        lay = ht.pair_layout("stacked", (1920, 1080), (1920, 1080))
        self.assertEqual(lay["canvas"], (1080, 1920))
        b, a = lay["before"], lay["after"]
        self.assertLessEqual(b[1] + b[3], lay["badge_after"][1])
        for key in ("before", "after", "badge_before", "badge_after", "caption", "header"):
            self.assert_inside(lay[key], lay["canvas"])
        self.assert_badge_on_its_side(lay["badge_before"], b)
        self.assert_badge_on_its_side(lay["badge_after"], a)

    def test_mmss(self):
        self.assertEqual(ht.mmss(7.0), "0:07")
        self.assertEqual(ht.mmss(65.4), "1:05")
        self.assertEqual(ht.mmss(0), "0:00")


# ---------------------------------------------------------------- board and text


class BoardTest(TempDirCase):
    def test_board_layout_keeps_full_resolution_before_left(self):
        lay = ht.board_layout((1080, 2400), (1080, 2300), header_h=200, badge_size=(260, 70), margin=48)
        b, a = lay["before"], lay["after"]
        self.assertEqual(b[2:], (1080, 2400))
        self.assertEqual(a[2:], (1080, 2300))
        self.assertLess(b[0], a[0])
        self.assertGreaterEqual(b[1], 200)
        W, H = lay["canvas"]
        self.assertEqual(W, 48 * 3 + 1080 * 2)
        self.assertGreaterEqual(H, b[1] + 2400)
        for side in ("before", "after"):
            bx, by, bw, bh = lay["badge_" + side]
            vx, vy, vw, vh = lay[side]
            self.assertAlmostEqual(bx + bw / 2, vx + vw / 2, delta=1)
            self.assertLessEqual(by + bh, vy)
            self.assertGreaterEqual(by, 200)

    def test_wrap_fits_the_width(self):
        fnt = ht.font(30)
        text = "Look at the three switches: before, on and off look the same. " * 3
        lines = ht.wrap(text, fnt, 400)
        self.assertGreater(len(lines), 2)
        for line in lines:
            self.assertLessEqual(fnt.getlength(line), 400)
        self.assertEqual(" ".join(lines).split(), text.split())

    def test_intro_refuses_text_too_long_for_its_card(self):
        img = ht.render_intro((1920, 1080), "Title", [("WHAT CHANGES", "A short line.")], "PR 1")
        self.assertEqual(img.size, (1920, 1080))
        with self.assertRaises(ValueError):
            ht.render_intro((1920, 1080), "Title", [("WHAT CHANGES", "word " * 3000)], "")

    def test_board_command_writes_the_board(self):
        before = os.path.join(self.tmp, "b.png")
        after = os.path.join(self.tmp, "a.png")
        Image.new("RGB", (300, 600), (200, 30, 30)).save(before)
        Image.new("RGB", (300, 600), (30, 200, 30)).save(after)
        out = os.path.join(self.tmp, "x_BEFORE_AFTER.png")
        code, _, err = run_main(["board", "--before", before, "--after", after,
                                 "--title", "Title", "--caption", "Caption", "--out", out])
        self.assertEqual(code, 0, err)
        img = Image.open(out).convert("RGB")
        W, H = img.size
        self.assertGreater(W, 600)
        # Each side shows its own picture at full size: sample the middle of each half.
        left = img.getpixel((W // 4, H - 50))
        right = img.getpixel((3 * W // 4, H - 50))
        self.assertGreater(left[0], 150)
        self.assertGreater(right[1], 150)


# ---------------------------------------------------------------- marks, paths, check


class CheckTest(TempDirCase):
    def test_find_marks_names_the_lines(self):
        text = "a\n<fill in: what changes>\nb <fill in> c\n"
        self.assertEqual(ht.find_marks(text), [2, 3])

    def test_absolute_paths_are_found_and_urls_are_not(self):
        bad = ["/Users/someone/x", "see /home/a/b", "C:\\Users\\x", "D:/shared", "~/shared/x",
               "/Volumes/Disk/y", "/private/tmp/z", "/var/folders/q", "$HOME/x", "%USERPROFILE%\\x"]
        for text in bad:
            self.assertTrue(ht.find_abs_paths(text), text)
        good = ["https://example.com/home/page", "release-1.4/142_x_HANDTEST/", "a/b/c.png",
                "BEFORE/AFTER", "1920x1080, 30 fps", "previous/"]
        for text in good:
            self.assertFalse(ht.find_abs_paths(text), text)

    def test_a_ready_folder_passes(self):
        folder = self.make_ready_folder()
        self.assertEqual(ht.check_folder(folder), [])
        code, out, _ = run_main(["check", folder])
        self.assertEqual(code, 0)

    def test_every_problem_is_named(self):
        folder = self.make_ready_folder()
        with open(os.path.join(folder, "README.md"), "a", encoding="utf-8") as f:
            f.write("\nMeasured: <fill in: numbers>\nRaw files in /Users/someone/raw\n")
        os.remove(os.path.join(folder, ht.board_name("142", "sync-switch")))
        with open(os.path.join(folder, "142_sync-switch_v2.mp4"), "wb") as f:
            f.write(b"v")
        problems = ht.check_folder(folder)
        text = "\n".join(problems)
        self.assertIn("fill in", text)
        self.assertIn("README.md", text)
        self.assertIn("absolute path", text)
        self.assertIn("missing", text)
        self.assertIn("142_sync-switch_BEFORE_AFTER.png", text)
        self.assertIn("more than one video", text)
        self.assertIn("142_sync-switch_v2.mp4", text)
        code, _, err = run_main(["check", folder])
        self.assertEqual(code, 1)
        self.assertIn("absolute path", err)

    def test_two_boards_and_a_stray_file_are_refused(self):
        folder = self.make_ready_folder()
        Image.new("RGB", (4, 4)).save(os.path.join(folder, "still_0003.00s.png"))
        with open(os.path.join(folder, "notes.txt"), "w") as f:
            f.write("x")
        os.makedirs(os.path.join(folder, "raw"))
        text = "\n".join(ht.check_folder(folder))
        self.assertIn("more than one board", text)
        self.assertIn("notes.txt", text)
        self.assertIn("raw", text)

    def test_a_folder_name_off_the_pattern_is_refused(self):
        folder = self.make_ready_folder()
        renamed = os.path.join(self.tmp, "142_sync-switch_HANDTEST_v2")
        os.rename(folder, renamed)
        self.assertTrue(any("folder name" in p for p in ht.check_folder(renamed)))

    def test_a_bad_status_is_refused(self):
        folder = self.make_ready_folder()
        path = os.path.join(folder, "handtest.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["status"] = "approved"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.assertTrue(any("status" in p for p in ht.check_folder(folder)))


# ---------------------------------------------------------------- init, times, archive, verdict


class InitTest(TempDirCase):
    def test_init_fills_what_it_knows_and_marks_the_rest(self):
        code, out, err = run_main([
            "init", "--out", self.tmp, "--id", "142", "--topic", "sync-switch",
            "--title", "The sync switch shows its state",
            "--base", "a1b2c3d4e5f6a7b8", "--head", "0f9e8d7c6b5a4938", "--date", "2026-11-14",
            "--ok", "Mark the PR ready.",
        ])
        self.assertEqual(code, 0, err)
        folder = os.path.join(self.tmp, "142_sync-switch_HANDTEST")
        with open(os.path.join(folder, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        with open(os.path.join(folder, "PACKAGE.md"), encoding="utf-8") as f:
            package = f.read()
        with open(os.path.join(folder, "handtest.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("142", readme)
        self.assertIn("The sync switch shows its state", readme)
        self.assertIn("a1b2c3d4", readme)
        self.assertIn("0f9e8d7c", readme)
        self.assertIn("2026-11-14", readme)
        self.assertTrue(ht.find_marks(readme))
        self.assertTrue(ht.find_marks(package))
        self.assertIn("Mark the PR ready.", package)
        self.assertIn("142_sync-switch_HANDTEST/", package)
        self.assertFalse(ht.find_abs_paths(readme + package))
        self.assertEqual(data["status"], "pending")
        self.assertEqual((data["id"], data["topic"]), ("142", "sync-switch"))

    def test_init_names_the_group_folder_with_or_without_the_evidence_root(self):
        group = os.path.join(self.tmp, "release-1.4")
        argv = ["init", "--out", group, "--id", "142", "--topic", "sync-switch", "--title", "T"]
        env = {k: v for k, v in os.environ.items() if k != "HANDTEST_ROOT"}
        with mock.patch.dict(os.environ, env, clear=True):
            code, out, err = run_main(argv)
        self.assertEqual(code, 0, err)
        package = os.path.join(group, "142_sync-switch_HANDTEST", "PACKAGE.md")
        with open(package, encoding="utf-8") as f:
            self.assertIn("`release-1.4/142_sync-switch_HANDTEST/`", f.read())
        self.assertIn("note:", out)
        os.remove(package)
        with mock.patch.dict(os.environ, {"HANDTEST_ROOT": self.tmp}):
            code, out, err = run_main(argv)
        self.assertEqual(code, 0, err)
        with open(package, encoding="utf-8") as f:
            self.assertIn("`release-1.4/142_sync-switch_HANDTEST/`", f.read())
        self.assertNotIn("note:", out)

    def test_init_again_keeps_what_is_there(self):
        argv = ["init", "--out", self.tmp, "--id", "7", "--topic", "a", "--title", "T", "--date", "2026-01-01"]
        self.assertEqual(run_main(argv)[0], 0)
        path = os.path.join(self.tmp, "7_a_HANDTEST", "README.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mine")
        self.assertEqual(run_main(argv)[0], 0)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "mine")

    @unittest.skipUnless(HAVE_GIT, "git missing")
    def test_init_refuses_a_folder_inside_a_git_work_tree(self):
        subprocess.run(["git", "init", "-q", self.tmp], check=True)
        argv = ["init", "--out", self.tmp, "--id", "7", "--topic", "a", "--title", "T"]
        code, _, err = run_main(argv)
        self.assertEqual(code, 2)
        self.assertIn("inside a git work tree", err)
        self.assertEqual(run_main(argv + ["--allow-in-repo"])[0], 0)

    def test_fill_times_writes_the_video_times(self):
        run_main(["init", "--out", self.tmp, "--id", "7", "--topic", "a", "--title", "T"])
        folder = os.path.join(self.tmp, "7_a_HANDTEST")
        ht.fill_times(folder, 6.0, 9.5)
        for name in ("README.md", "PACKAGE.md"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn(ht.MARK_TOGETHER, text)
            self.assertNotIn(ht.MARK_CHANGE, text)
            self.assertIn("0:06", text)
            self.assertIn("0:09", text)
        with open(os.path.join(folder, "handtest.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["video"], {"together_from": 6.0, "change_at": 9.5})


    def test_fill_times_says_when_the_video_has_no_sound(self):
        run_main(["init", "--out", self.tmp, "--id", "7", "--topic", "a", "--title", "T"])
        folder = os.path.join(self.tmp, "7_a_HANDTEST")
        readme = os.path.join(folder, "README.md")
        ht.fill_times(folder, 6.0, 9.5, sound=False)
        with open(readme, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("one video at 30 fps (no sound) and one board", text)
        self.assertNotIn("on the left", text)
        ht.fill_times(folder, 6.0, 9.5, sound=True)
        with open(readme, encoding="utf-8") as f:
            self.assertIn("(BEFORE's sound on the left, AFTER's on the right)", f.read())

    def test_fill_times_again_updates_a_redo(self):
        run_main(["init", "--out", self.tmp, "--id", "7", "--topic", "a", "--title", "T"])
        folder = os.path.join(self.tmp, "7_a_HANDTEST")
        ht.fill_times(folder, 6.0, 9.5)
        ht.fill_times(folder, 8.0, 12.2)
        with open(os.path.join(folder, "PACKAGE.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("together from 0:08; the change shows at 0:12", text)
        self.assertNotIn("0:06", text)


class ArchiveTest(TempDirCase):
    def test_archive_moves_the_take_into_previous_with_one_stamp(self):
        folder = self.make_ready_folder()
        code, _, err = run_main(["archive", folder, "--stamp", "20261114-1830"])
        self.assertEqual(code, 0, err)
        prev = sorted(os.listdir(os.path.join(folder, "previous")))
        self.assertEqual(prev, [
            "20261114-1830_142_sync-switch.mp4",
            "20261114-1830_142_sync-switch_BEFORE_AFTER.png",
            "20261114-1830_README.md",
        ])
        left = sorted(os.listdir(folder))
        self.assertEqual(left, ["PACKAGE.md", "handtest.json", "previous"])

    def test_archive_takes_the_stamp_from_the_newest_mtime(self):
        folder = self.make_ready_folder()
        when = time.mktime((2026, 11, 13, 22, 25, 0, 0, 0, -1))
        for name in os.listdir(folder):
            os.utime(os.path.join(folder, name), (when, when))
        self.assertEqual(run_main(["archive", folder])[0], 0)
        prev = os.listdir(os.path.join(folder, "previous"))
        self.assertTrue(all(n.startswith("20261113-222500_") for n in prev), prev)

    def test_archive_sets_the_status_back_to_pending_and_never_overwrites(self):
        folder = self.make_ready_folder()
        run_main(["verdict", folder, "--not-ok", "--by", "Reviewer", "--note", "covered",
                  "--at", "2026-11-14T10:00:00Z"])
        self.assertEqual(run_main(["archive", folder, "--stamp", "s1"])[0], 0)
        with open(os.path.join(folder, "handtest.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(len(data["verdicts"]), 1)
        self.assertEqual(data["previous"][0]["stamp"], "s1")
        # A second take with the same stamp must not overwrite the first.
        with open(os.path.join(folder, ht.video_name("142", "sync-switch")), "wb") as f:
            f.write(b"take 2")
        code, _, err = run_main(["archive", folder, "--stamp", "s1"])
        self.assertEqual(code, 2)
        self.assertIn("already", err)


class VerdictTest(TempDirCase):
    def test_ok_and_not_ok_are_recorded_with_who_and_when(self):
        folder = self.make_ready_folder()
        code, _, err = run_main(["verdict", folder, "--not-ok", "--by", "Reviewer",
                                 "--note", "The switch is covered.", "--at", "2026-11-14T10:00:00Z"])
        self.assertEqual(code, 0, err)
        code, _, err = run_main(["verdict", folder, "--ok", "--by", "Reviewer", "--at", "2026-11-15T09:00:00Z"])
        self.assertEqual(code, 0, err)
        with open(os.path.join(folder, "handtest.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["status"], "ok")
        self.assertEqual([v["verdict"] for v in data["verdicts"]], ["not-ok", "ok"])
        self.assertEqual(data["verdicts"][0]["note"], "The switch is covered.")
        self.assertEqual(data["verdicts"][1]["by"], "Reviewer")
        self.assertEqual(data["verdicts"][1]["at"], "2026-11-15T09:00:00Z")

    def test_ok_is_refused_until_check_passes(self):
        run_main(["init", "--out", self.tmp, "--id", "7", "--topic", "a", "--title", "T"])
        folder = os.path.join(self.tmp, "7_a_HANDTEST")
        code, out, err = run_main(["verdict", folder, "--ok", "--by", "Reviewer"])
        self.assertEqual(code, 1)
        self.assertIn("problem", err)
        self.assertNotIn("Recorded", out)
        with open(os.path.join(folder, "handtest.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual((data["status"], data["verdicts"]), ("pending", []))
        # A person can say Not OK to anything they were shown.
        code, _, err = run_main(["verdict", folder, "--not-ok", "--by", "Reviewer", "--note", "No video."])
        self.assertEqual(code, 0, err)

    def test_not_ok_needs_a_note(self):
        folder = self.make_ready_folder()
        code, _, err = run_main(["verdict", folder, "--not-ok", "--by", "Reviewer"])
        self.assertEqual(code, 2)
        self.assertIn("--note", err)


class ReportTest(TempDirCase):
    def test_report_lists_pending_first_and_embeds_the_boards(self):
        ok = self.make_ready_folder("140", "first-run")
        pending = self.make_ready_folder("142", "sync-switch")
        run_main(["verdict", ok, "--ok", "--by", "Reviewer", "--at", "2026-11-14T10:00:00Z"])
        with open(os.path.join(pending, "handtest.json"), encoding="utf-8") as f:
            data = json.load(f)
        data["title"] = "Switch <b>state</b> & more"
        with open(os.path.join(pending, "handtest.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        code, out, err = run_main(["report", self.tmp, "--title", "Release 1.4"])
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.tmp, "REPORT.md"), encoding="utf-8") as f:
            md = f.read()
        with open(os.path.join(self.tmp, "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertLess(md.index("142_sync-switch"), md.index("140_first-run"))
        self.assertIn("142_sync-switch_HANDTEST/142_sync-switch.mp4", md)
        self.assertIn("1 pending", md)
        self.assertLess(page.index("142_sync-switch"), page.index("140_first-run"))
        self.assertIn("data:image/jpeg;base64,", page)
        self.assertIn("&lt;b&gt;state&lt;/b&gt; &amp; more", page)
        self.assertNotIn("<b>state</b>", page)
        self.assertNotRegex(page, r'src="(https?:)?//')
        self.assertFalse(ht.find_abs_paths(md + page))

    def test_report_links_only_the_files_that_exist(self):
        run_main(["init", "--out", self.tmp, "--id", "7", "--topic", "a", "--title", "T"])
        self.make_ready_folder("9", "b")
        self.assertEqual(run_main(["report", self.tmp])[0], 0)
        with open(os.path.join(self.tmp, "REPORT.md"), encoding="utf-8") as f:
            md = f.read()
        self.assertNotIn("7_a_HANDTEST/7_a.mp4", md)
        self.assertNotIn("7_a_BEFORE_AFTER.png", md)
        self.assertIn("no video yet", md)
        self.assertIn("no board yet", md)
        self.assertIn("[video](9_b_HANDTEST/9_b.mp4)", md)


# ---------------------------------------------------------------- stills and find-change maths


class ChangeMathTest(unittest.TestCase):
    def test_still_times(self):
        self.assertEqual(ht.still_times(10.0, at=[3, 1.5]), [1.5, 3.0])
        self.assertEqual(ht.still_times(5.0, every=2.0), [0.0, 2.0, 4.0])
        self.assertEqual(ht.still_times(10.0, every=2.0, start=3.0, end=7.0), [3.0, 5.0, 7.0])
        self.assertEqual(ht.still_times(4.0, at=[1, 9]), [1.0])
        self.assertEqual(ht.still_name(7.5), "still_0007.50s.png")

    def test_rank_changes_reports_the_frame_where_the_change_shows(self):
        diffs = [0.1, 0.2, 40.0, 3.0, 0.1]
        ranked = ht.rank_changes(diffs, t0=1.0, fps=30, top=2)
        self.assertAlmostEqual(ranked[0][0], 1.0 + 3 / 30)
        self.assertEqual(ranked[0][1], 40.0)
        self.assertAlmostEqual(ranked[1][0], 1.0 + 4 / 30)

    def test_first_move_finds_the_start_of_a_fade(self):
        diffs = [0.0, 0.1, 5.0, 20.0, 40.0, 10.0]
        self.assertAlmostEqual(ht.first_move(diffs, t0=2.0, fps=30), 2.0 + 3 / 30)
        self.assertIsNone(ht.first_move([0.0, 0.0], t0=0, fps=30))


# ---------------------------------------------------------------- integration with ffmpeg


def lavfi_clip(path, size, duration, box_at, tone=None):
    """A dark clip where a white box appears at box_at seconds, with an optional tone."""
    w, h = size
    video = (f"color=c=0x202020:s={w}x{h}:r=30:d={duration},"
             f"drawbox=x={w // 4}:y={h // 4}:w={w // 2}:h={h // 2}:color=white:t=fill:"
             f"enable='gte(t,{box_at})'")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", video]
    if tone:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={tone}:duration={duration}:sample_rate=48000"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if tone:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(path)
    subprocess.run(cmd, check=True)


def frame_at(video, t, out_png):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video,
                    "-frames:v", "1", out_png], check=True)
    return Image.open(out_png).convert("L")


def centre_level(img, rect):
    x, y, w, h = rect
    return img.getpixel((x + w // 2, y + h // 2))


def channel_rms(video, start, dur):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start}", "-t", f"{dur}", "-i", video,
                          "-f", "s16le", "-ac", "2", "-ar", "48000", "-"],
                         check=True, capture_output=True).stdout
    samples = array.array("h", raw)
    left, right = samples[0::2], samples[1::2]

    def rms(xs):
        return (sum(x * x for x in xs) / max(1, len(xs))) ** 0.5
    return rms(left), rms(right)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg or ffprobe missing")
class FfmpegTest(TempDirCase):
    def test_pair_lines_up_the_moment_splits_the_sound_and_freezes_the_shorter_side(self):
        before = os.path.join(self.tmp, "before.mp4")
        after = os.path.join(self.tmp, "after.mp4")
        lavfi_clip(before, (180, 320), 4.0, box_at=2.0, tone=440)
        lavfi_clip(after, (180, 320), 2.5, box_at=1.0)
        out = os.path.join(self.tmp, "7_a.mp4")
        code, stdout, err = run_main([
            "pair", "--before", before, "--after", after, "--sync-before", "2.0", "--sync-after", "1.0",
            "--title", "A box appears", "--what", "A white box appears in the middle.",
            "--caption", "Watch the middle.", "--intro-seconds", "1", "--out", out])
        self.assertEqual(code, 0, err)
        info = ht.probe(out)
        self.assertEqual((info["width"], info["height"]), (1920, 1080))
        self.assertAlmostEqual(info["fps"], 30.0, delta=0.01)
        # intro 1 s, lead clamped to 1.0 s, longer side runs 3.0 s after its start
        self.assertAlmostEqual(info["duration"], 4.0, delta=0.1)
        self.assertEqual(info["channels"], 2)
        self.assertIn("0:01", stdout)
        lay = ht.pair_layout("side", (180, 320), (180, 320))
        moment = 1.0 + 1.0
        before_frame = frame_at(out, moment - 0.3, os.path.join(self.tmp, "f1.png"))
        after_frame = frame_at(out, moment + 0.15, os.path.join(self.tmp, "f2.png"))
        frozen = frame_at(out, 3.85, os.path.join(self.tmp, "f3.png"))
        for side in ("before", "after"):
            self.assertLess(centre_level(before_frame, lay[side]), 80, side)
            self.assertGreater(centre_level(after_frame, lay[side]), 200, side)
        self.assertGreater(centre_level(frozen, lay["after"]), 200)
        left, right = channel_rms(out, 1.2, 2.0)
        self.assertGreater(left, 1000)
        self.assertLess(right, 50)
        intro_left, _ = channel_rms(out, 0.0, 0.9)
        self.assertLess(intro_left, 50)

    def test_pair_stacks_landscape_recordings(self):
        before = os.path.join(self.tmp, "b.mp4")
        after = os.path.join(self.tmp, "a.mp4")
        lavfi_clip(before, (320, 180), 1.5, box_at=0.5)
        lavfi_clip(after, (320, 180), 1.5, box_at=0.5)
        out = os.path.join(self.tmp, "p.mp4")
        code, _, err = run_main(["pair", "--before", before, "--after", after,
                                 "--sync-before", "0.5", "--sync-after", "0.5", "--title", "T",
                                 "--what", "W", "--intro-seconds", "1", "--out", out])
        self.assertEqual(code, 0, err)
        info = ht.probe(out)
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertEqual(info["channels"], 0)

    def test_pair_fills_the_times_in_an_evidence_folder(self):
        folder = self.make_ready_folder("7", "a")
        os.remove(os.path.join(folder, "7_a.mp4"))
        with open(os.path.join(folder, "README.md"), "a", encoding="utf-8") as f:
            f.write(f"\nFrom {ht.MARK_TOGETHER}, change at {ht.MARK_CHANGE}.\n")
        before = os.path.join(self.tmp, "b.mp4")
        after = os.path.join(self.tmp, "a.mp4")
        lavfi_clip(before, (180, 320), 2.0, box_at=1.0)
        lavfi_clip(after, (180, 320), 2.0, box_at=1.0)
        code, _, err = run_main(["pair", "--before", before, "--after", after,
                                 "--sync-before", "1.0", "--sync-after", "1.0", "--title", "T",
                                 "--what", "W", "--intro-seconds", "2",
                                 "--out", os.path.join(folder, "7_a.mp4")])
        self.assertEqual(code, 0, err)
        with open(os.path.join(folder, "README.md"), encoding="utf-8") as f:
            self.assertIn("From 0:02, change at 0:03.", f.read())

    def test_find_change_names_the_frame_the_box_appears(self):
        clip = os.path.join(self.tmp, "c.mp4")
        lavfi_clip(clip, (180, 320), 3.0, box_at=1.5)
        code, out, err = run_main(["find-change", clip, "--from", "0.5", "--to", "2.5", "--top", "3"])
        self.assertEqual(code, 0, err)
        first = re.search(r"([0-9.]+) s", out.split("\n", 1)[1])
        self.assertAlmostEqual(float(first.group(1)), 1.5, delta=0.034)

    def test_ffmpeg_never_reads_the_callers_input(self):
        # ffmpeg polls stdin for keys. In a loop that pipes file names to this tool, it would eat them.
        clip = os.path.join(self.tmp, "a.mp4")
        lavfi_clip(clip, (320, 640), 2, 1.0)
        with mock.patch.object(ht.subprocess, "run", wraps=subprocess.run) as run:
            self.assertEqual(run_main(["find-change", clip, "--from", "0.5", "--to", "1.5"])[0], 0)
            self.assertEqual(run_main(["stills", clip, "--at", "1.2", "--out", os.path.join(self.tmp, "s")])[0], 0)
        calls = [c.args[0] for c in run.call_args_list if c.args[0][0] == "ffmpeg"]
        self.assertGreaterEqual(len(calls), 2)
        for argv in calls:
            self.assertIn("-nostdin", argv)

    def test_find_change_sees_a_small_switch_flip(self):
        clip = os.path.join(self.tmp, "small.mp4")
        video = ("color=c=0xf0f0f0:s=540x1100:r=30:d=3,"
                 "drawbox=x=440:y=200:w=36:h=36:color=0xd8d8d8:t=fill:enable='lt(t,1.5)',"
                 "drawbox=x=480:y=200:w=36:h=36:color=0xd8d8d8:t=fill:enable='gte(t,1.5)'")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", video, "-c:v", "libx264",
                        "-preset", "ultrafast", "-pix_fmt", "yuv420p", clip], check=True)
        code, out, err = run_main(["find-change", clip, "--from", "0.5", "--to", "2.5"])
        self.assertEqual(code, 0, out + err)
        first = re.search(r"([0-9.]+) s", out.split("\n", 1)[1])
        self.assertAlmostEqual(float(first.group(1)), 1.5, delta=0.034)

    def test_find_change_says_so_when_nothing_moves(self):
        clip = os.path.join(self.tmp, "c.mp4")
        lavfi_clip(clip, (180, 320), 2.0, box_at=5.0)
        code, out, _ = run_main(["find-change", clip, "--from", "0", "--to", "1.5"])
        self.assertEqual(code, 1)
        self.assertIn("no change", out.lower())

    def test_stills_writes_one_png_per_time(self):
        clip = os.path.join(self.tmp, "c.mp4")
        lavfi_clip(clip, (180, 320), 3.0, box_at=1.5)
        out_dir = os.path.join(self.tmp, "stills")
        code, out, err = run_main(["stills", clip, "--out", out_dir, "--every", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn(os.path.join(out_dir, "still_0001.00s.png"), out)
        self.assertEqual(sorted(os.listdir(out_dir)),
                         ["still_0000.00s.png", "still_0001.00s.png", "still_0002.00s.png"])
        img = Image.open(os.path.join(out_dir, "still_0002.00s.png")).convert("L")
        self.assertGreater(img.getpixel((90, 160)), 200)


if __name__ == "__main__":
    unittest.main()
