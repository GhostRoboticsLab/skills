# Filming

How to film a scene that holds up. The project file (`docs/agents/whats-new-clip.md`) names this project's build, seed and capture commands; this file has the rules and the general recipes. Where a flag differs between tool versions, check the tool's `--help` before the first take.

## Every take

- **The release build.** What ships, not a debug build: debug banners, dev labels, frame meters and test menus end up on screen. If only a debug build can be driven, switch every overlay off and check the stills for leftovers.
- **A seeded, repeatable state.** The same test account, sample data and settings at the start of every scene, from the project's seed command, so a retake shows the same screen. Pin anything that drifts between takes: the date and clock, a random seed, a "featured today" item.
- **Settled.** Play the first launch out once before filming: onboarding, permission prompts, tips, rating asks, a keyboard's first-run card. Each would otherwise land in some scene.
- **One look.** The same device or window size, theme and language in every scene, and the product's own theme, the one people see. A clean status bar: a fixed time, full battery, full signal.
- **One take at a time.** Scenes share one device or simulator and one seeded state: film them one after another, never in parallel. Build into a folder of this take's own, since a shared build folder lets another build swap the app under a film.
- **Probe first.** Before a scene's real take, run it once as a dry run that ends by printing every control's label and position, and look at one still of where it ended. It gives the labels and points the real steps need, and shows where a thing lands before a take is spent on it.
- **Real input** through the product's own UI, found by label or role. A shortcut that jumps to a screen skips the transition people see. An OS-level link opener can put its own "Open in ...?" prompt over the app: drive it from the UI test framework instead.
- **Rest on both sides.** Hold a second of stillness before the change and after it, so `in` and `out` have room.
- **Marks, not eyes.** Log the second each step starts, measured from the recording's start, into a file beside the film. Finding cut points by scrubbing a film eats most of a clip's time; with marks, `in` is a step's mark minus a beat. Check each mark with `clip.py peek`, since a driver's log can trail the screen. `peek` reads the film as `render` does. A seek of your own (`ffmpeg -ss`) does not: a screen recording, a simulator's or `adb screenrecord`'s, holds a frame only where the picture changed, so the seek lands on the next change.
- **Nothing private.** No real person's name, email, photo or message on screen, no notifications, no production data. Sign in only to test accounts, and send nothing to anyone.
- **Keep every film**, outside the repo, beside the clip. A film is the only way to render that scene again, with or without its caption.

Before filming, check the scene still matches the product: every seeded setting key and every label a step taps should still exist in the code (search for each). A renamed setting changes a scene silently.

## Web

Playwright records each browser context to WebM, written when the context closes:

```js
// film.mjs: node film.mjs <url> <out-dir>
import { chromium } from 'playwright';

const [url, dir] = process.argv.slice(2);
const size = { width: 430, height: 932 };               // a phone; 1280x800 for a desktop screen
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2, colorScheme: 'dark',
                                           recordVideo: { dir, size } });
const page = await context.newPage();
await page.clock.setFixedTime(new Date('2026-03-02T09:41:00'));   // the same date every take
const t0 = Date.now(), mark = (step) => console.log(((Date.now() - t0) / 1000).toFixed(2), step);
try {
  await page.goto(url);
  await page.getByRole('heading', { name: 'Today' }).waitFor();
  await page.waitForTimeout(1000);                                // rest
  mark('tap Share');
  await page.getByRole('button', { name: 'Share' }).click();
  await page.getByText('Share Basil with').waitFor();
  await page.waitForTimeout(1500);                                // rest
} finally {
  await context.close();
  await browser.close();
}
```

The video's clock starts with the context, a little before `t0`: check one mark with `clip.py peek`. Playwright's video is small (the viewport's CSS pixels). For a sharp scene, take `page.screenshot()` stills at full device scale and make still scenes, or record the screen with the desktop recipe.

Without Playwright, and without leave to install it: drive the page with the project's own end-to-end tests, take a screenshot after each step, and make still scenes (`seconds` in place of `in` and `out`).

## Android

| Job | Command |
|---|---|
| Video | `adb shell screenrecord --size 1080x2400 /sdcard/scene.mp4` (Ctrl+C stops it; 3 minutes at most), `adb pull`, then `adb shell rm` the file |
| Video with the app's sound (Android 11+) | `scrcpy --no-control --record=scene.mp4` (scrcpy 2 or later) |
| Launch, stop | `adb shell monkey -p <package> -c android.intent.category.LAUNCHER 1`, `adb shell am force-stop <package>` |
| Clean status bar | System UI demo mode: `adb shell settings put global sysui_demo_allowed 1`, then `adb shell am broadcast -a com.android.systemui.demo -e command enter` and `... -e command clock -e hhmm 0941`. It changes a system setting: ask first, and leave it after with `-e command exit`. |
| Taps by label | The project's UI test framework (Espresso, Flutter `integration_test`, Maestro), or `uiautomator dump` and the node's bounds |

Touch only the app under test. A shared device belongs to other people too: no uninstalls, no clearing other apps, no settings left changed.

## iOS simulator

| Job | Command |
|---|---|
| Video | `xcrun simctl io booted recordVideo --codec=h264 scene.mp4` (Ctrl+C stops it) |
| Clean status bar | `xcrun simctl status_bar booted override --time 9:41 --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3` |
| Theme | `xcrun simctl ui booted appearance dark` (or `light`) |
| Install, launch | `xcrun simctl install booted App.app`, `xcrun simctl launch booted <bundle id>` |

`simctl` sends no taps: drive the scene with XCUITest, Flutter `integration_test`, Detox or Maestro, and start the recording before the test. iOS draws no touch indicators in a recording; if a tap must show, the product draws its own in a build flag that never ships. A simulator recording has frames only where the screen changed; `clip.py` reads films at 30 fps before cutting, so `in` lands on what was on screen, and `clip.py peek` shows a film the same way.

## Desktop

| OS | Record with ffmpeg |
|---|---|
| macOS | `ffmpeg -f avfoundation -list_devices true -i ""` for the screen's index, then `ffmpeg -f avfoundation -framerate 30 -i "<index>:none" scene.mkv` (the terminal needs Screen Recording permission: ask the user) |
| Linux (X11) | `ffmpeg -f x11grab -framerate 30 -video_size 1920x1080 -i :0.0 scene.mkv` |
| Windows | `ffmpeg -f gdigrab -framerate 30 -i title="<window title>" scene.mkv` |

Use the spec's `crop` to show only the window. Moving the user's real pointer interrupts them: ask before a take that does.

## Terminal

VHS types into a real shell and writes a film:

```
Output scene.mp4
Set Theme "Dracula"
Set FontSize 28
Set Width 1080
Set Height 1080
Type "pocket water --plan"
Enter
Sleep 3s
```

Run `vhs scene.tape`. Use the same theme, size and font for every scene.

## What the capture cannot film

A simulator has no camera and no second device, and a browser recorder sees one tab. A change that needs one (a camera view, augmented reality, a hand-off between two devices, a piece of hardware) is shown from a **kept film**: footage made another way, used as that scene's `source` like any other film.

- Look for footage that exists first. The AFTER recording of a hand test, or a film made while the release was tested, already shows the real build.
- Else film it on a real device, with a build of this release, in the theme and language of the other scenes. On a shared device, ask first, and film a test copy of the app installed beside the one its owner uses, never that one.
- Say in the scene's `note` where the film came from: who filmed it, on which build and device.
- None of the checks above hold for it: no marks, no seeded state, no labels checked against the code. So pick `in` and `out` with `clip.py peek`, and look at its stills for the release's version, the theme and the people in it (below).
- A landscape film in a vertical frame runs wide, past the side edges a feed covers: give the scene a `crop` round what matters.
- Its own sound is never used: `render` takes a film's picture only.

## People in the picture

When a scene shows real people (footage of the product in use, a shared screen):

- Blur the faces of everyone in the background.
- The people a scene is about see the clip and agree before it is posted.
