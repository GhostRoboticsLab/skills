# Capture recipes

How to drive and record each surface with real input. The project file (`docs/agents/hand-test.md`) says which surface and tools apply; this file has the commands. Where a flag differs between versions, check the tool's `--help` before the first take.

## For every surface

The rules for a take are in SKILL.md, step 2. Two more belong to the capture itself:

- Switch off debug overlays and performance meters: they cover what the person must see.
- Check the working tree with a checksum before the dry run and after the last take: getting BEFORE must change no saved file.

The working tree checksum, from the repo root:

```sh
tree_sum() { { git rev-parse HEAD; git diff HEAD --binary; git ls-files -o --exclude-standard -z | xargs -0 shasum; } | shasum; }
before=$(tree_sum)                                    # before the dry run
[ "$before" = "$(tree_sum)" ] && echo "tree unchanged" # after the last take
```

It covers the commit, every tracked change and the contents of untracked files.

Build BEFORE in its own worktree outside the repo, so the checkout you work in never moves:

```sh
git worktree add ../handtest-base <base sha>
# build or serve it there
git worktree remove ../handtest-base
```

After each take, find the moment with `handtest.py find-change`. A clock or status bar that ticks can outrank the change; leave it out with `--crop W:H:X:Y`. It compares brightness, so a change of colour alone, at about the same brightness, needs a lower `--level` (3 in place of 10).

## Web

Playwright records video per browser context (WebM, no sound), written when the context closes:

```js
// take.mjs: node take.mjs <url> <out-dir>
import { chromium } from 'playwright';

const [url, dir] = process.argv.slice(2);
const browser = await chromium.launch();
const size = { width: 1280, height: 800 };
const context = await browser.newContext({ viewport: size, recordVideo: { dir, size } });
const page = await context.newPage();
try {
  await page.goto(url);
  await page.getByRole('switch', { name: 'Sync over Wi-Fi only' }).click(); // the moment
  await page.getByText('On').first().waitFor();                            // real state
  await page.waitForTimeout(2000);                                         // hold after the moment
} finally {
  await context.close();
  await browser.close();
}
```

- BEFORE and AFTER: serve the base build and the head build on two ports, and run the same script against each.
- A still for the board: `await page.screenshot({ path: 'before.png' })` at the moment.
- One still with no input: `chrome --headless --user-data-dir=<scratch dir> --window-size=1280,800 --screenshot=out.png <url>`. The binary's name varies (`google-chrome`, `chromium`, or the app bundle's path on macOS). The scratch profile keeps the user's own profile untouched.
- Set back: close the context; drop any test data the script created.

No recorder or driver (only headless screenshots, a CI box, a static page): take one still per state, reaching each state by URL, then turn the stills into a clip:

```sh
ffmpeg -loop 1 -framerate 30 -t 2 -i closed.png -loop 1 -framerate 30 -t 3 -i open.png \
  -filter_complex "[0:v][1:v]concat=n=2:v=1[v]" -map "[v]" -c:v libx264 -pix_fmt yuv420p take.mp4
```

The moment is where the second still starts (2 s here). Say in the README's Notes that each state was reached without input.

## Android

| Job | Command |
|---|---|
| Screenshot | `adb exec-out screencap -p > shot.png` |
| Video, no sound | `adb shell screenrecord /sdcard/take.mp4` (stop with Ctrl+C; 3 minutes at most), then `adb pull /sdcard/take.mp4` and `adb shell rm /sdcard/take.mp4` |
| Video with the app's sound (Android 11+) | `scrcpy --no-control --record=take.mkv` (scrcpy 2 or later; check `scrcpy --help` for hiding the mirror window) |
| Launch | `adb shell monkey -p <package> -c android.intent.category.LAUNCHER 1` |
| Stop | `adb shell am force-stop <package>` |
| Clear data (the app under test only) | `adb shell pm clear <package>` |
| Install over the other build, keeping data | `adb install -r app.apk` |
| Tap, swipe | `adb shell input tap X Y`, `adb shell input swipe X1 Y1 X2 Y2 300` |

Finding by label: `adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml`, then read the `node` elements' `text`, `content-desc`, `package` and `bounds="[x1,y1][x2,y2]"`, keep only nodes whose `package` is the app under test, and tap the centre of the bounds.

Before every tap, check the app under test is in front: `adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'` must name its package. If anything else is in front (a launcher, a notification shade, another app), stop the step and say what was there.

- Each `uiautomator dump` switches accessibility on for a moment, which costs frames. Keep dumps out of a moment where timing matters: find the element before it, hold during it.
- Set back: force-stop the app and remove files you pushed. Leave every other app and setting alone.

## iOS simulator

| Job | Command |
|---|---|
| List and boot | `xcrun simctl list devices`, `xcrun simctl boot <udid>` |
| Install, launch, stop | `xcrun simctl install booted App.app`, `xcrun simctl launch booted <bundle id>`, `xcrun simctl terminate booted <bundle id>` |
| Screenshot | `xcrun simctl io booted screenshot shot.png` |
| Video, no sound | `xcrun simctl io booted recordVideo --codec=h264 take.mp4` (stop with Ctrl+C) |

`simctl` sends no taps. Drive the app with the project's UI test framework, finding elements by accessibility label: XCUITest (`app.buttons["Save"].tap()`, then `app.staticTexts["Saved"].waitForExistence(timeout: 5)`), Flutter `integration_test`, Detox or Maestro. Start the recording before the test and stop it after.

- A real iPhone or iPad: screen recording over USB is manual (QuickTime Player's movie recording). Ask the user to record, and give them the steps from PACKAGE.md.
- Set back: terminate the app; restore any simulator setting you changed (`xcrun simctl ui booted appearance light` after `dark`).

## Desktop

| OS | Record the screen with ffmpeg |
|---|---|
| macOS | `ffmpeg -f avfoundation -list_devices true -i ""` to find the screen's index, then `ffmpeg -f avfoundation -framerate 30 -i "<index>:none" take.mkv` (the terminal needs Screen Recording permission: ask the user) |
| Linux (X11) | `ffmpeg -f x11grab -framerate 30 -video_size 1920x1080 -i :0.0 take.mkv` |
| Windows | `ffmpeg -f gdigrab -framerate 30 -i desktop take.mkv`, or `-i title="<window title>"` for one window |

- Crop to the app's window afterwards with `ffmpeg -i take.mkv -vf crop=W:H:X:Y cropped.mp4`.
- Drive the app through its test driver or the OS accessibility API, by element name (pywinauto or WinAppDriver on Windows, System Events UI scripting on macOS, AT-SPI on Linux). Moving the user's real pointer interrupts them: ask before a take that does.
- Set back: quit the app and restore its settings file from a copy made before the take.

## Terminal

VHS types into a real shell and writes a video:

```
Output take.mp4
Set FontSize 22
Set Width 1280
Set Height 720
Type "mytool sync --dry-run"
Enter
Sleep 3s
```

Run `vhs take.tape`. For BEFORE and AFTER, use two tapes that differ only in the binary's path. If your VHS has `Wait` (check `vhs manual`), wait on the output instead of sleeping before the moment.

asciinema also works: `asciinema rec take.cast`, then `agg take.cast take.gif` and `ffmpeg -i take.gif -pix_fmt yuv420p take.mp4`.

## Sound

- Record the app's own output, never a room microphone.
- Android 11+: scrcpy records the device's sound.
- macOS and Windows desktops need a loopback audio device to record app sound. That is an install: ask the user.
- Playwright records no sound; record the browser with the desktop recipe and a loopback device.
- A sound-only change still needs a picture. Draw the waveform:

  ```sh
  ffmpeg -i take.wav -filter_complex "[0:a]showwaves=s=960x540:mode=cline:rate=30[v]" -map "[v]" -map 0:a -c:v libx264 -pix_fmt yuv420p -c:a aac take.mp4
  ```

  `pair` then plays BEFORE in the left ear and AFTER in the right. Its default HOW TO WATCH line tells the approver to use headphones.
