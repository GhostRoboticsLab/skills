# The spec

One JSON file per release, named `<version>.json`, kept in the repo's spec folder. `clip.py init` writes the skeleton; `clip.py check` holds it to the rules below. An invented product's spec:

```json
{
  "product": "Pocket Garden",
  "version": "2.4.0",
  "size": [1080, 1920],
  "max_seconds": 30,
  "theme": {
    "background": "#0F1A14", "band": "#1C2B22", "text": "#F2F5F0",
    "muted": "#A9B8AE", "accent": "#7BD88F", "logo": "../assets/logo.png"
  },
  "open": {"line": "What's new in Pocket Garden?", "seconds": 2.0},
  "end": {"lines": ["Pocket Garden", "Free on iOS and Android"], "seconds": 2.5},
  "scenes": [
    {"caption": "Watering follows the weather", "words_by": "the approver",
     "source": "weather.mp4", "in": 0.8, "out": 4.3,
     "note": "Today screen at rest; the rain banner slides in at 1.2 s"},
    {"caption": "Share a plant with a friend", "words_by": "the approver",
     "source": "share.mp4", "in": 0.5, "out": 4.5, "crop": [0, 0.545, 1, 0.455],
     "note": "The share sheet opens at the foot of the screen, under a feed's captions: cropped to it"}
  ]
}
```

## Keys

| Key | What |
|---|---|
| `product`, `version` | The version is shown on the opening card. The file's name must be `<version>.json`, so a copied spec cannot keep the last release's version. |
| `size` | `[width, height]`, both even. Default 1080x1920. `render --size` makes another format: see below. |
| `max_seconds` | The longest the clip may run, cards included. Default 30. |
| `safe` | `[top, right, bottom, left]`, the share of the frame a feed's own buttons and captions cover. Default for a vertical frame: 0.13, 0.15, 0.22, 0.06; otherwise 0.06 all round. Captions and card text stay inside it. The screen runs past it at the bottom, and a picture wider than a phone's at the sides, so it stays large: `stills --safe` tints the covered edges for the reviewer pass. |
| `theme` | `background`, `band` (behind captions), `text`, `muted` (the end card's small lines), `accent` (the version and the caption's bar), as `#RRGGBB`; optional `logo` (a PNG, shown on both cards) and `font` (a `.ttf` or `.otf`; default Pillow's built-in font, which has Latin letters and common punctuation only: a character it lacks is drawn as a box, so set `font` for other scripts and symbols). |
| `open` | `line`: the fixed opening question, the same every release. `seconds`: default 2.0. |
| `end` | `lines`: the product's name, then where to get it. `image`: optional artwork under the lines, such as store badges exactly as the stores ship them. `seconds`: default 2.5. |
| `music` | Optional. `file`, looped under the whole clip at a fixed loudness (`lufs`, default -20) with short fades. Without it the clip carries a silent track. |
| `scenes` | In order, one change each. |
| `note` | Free text for the next person: what was staged and why. Also allowed in each scene. |

A scene:

| Key | What |
|---|---|
| `caption` | The agreed words, verbatim. `\n` forces a line break. |
| `words_by` | Who gave the words: the approver, or the product's own text. |
| `source` | A film (`.mp4`, `.mov`, anything ffmpeg reads) or a still (`.png`, `.jpg`, `.webp`). A kept film, footage the capture could not make, is a film like any other, and its `note` says where it came from. |
| `in`, `out` | For a film: the seconds of the film to show. `clip.py peek` shows the film between two of its seconds as `render` reads it. |
| `seconds` | For a still: how long it shows. |
| `crop` | Optional `[x, y, w, h]`, shares of the source's frame, to show only the part that changed. |

Paths: `logo`, `font` and `end.image` are relative to the spec's folder (they live in the repo). `source` and `music.file` are relative to `--media` (the films live outside the repo); without `--media`, the spec's folder. No path is absolute or starts with `~`: the spec is committed, and such a path holds on one machine only.

## What the clip looks like

1. The opening card: the logo, the opening line, the version under it in the accent colour. It is the first frame, so it is the clip's cover, and it sits in the middle of the safe zone, where a profile grid's crop keeps it.
2. Each scene: its caption on a band at the top of the safe zone, the screen under it, scaled to fit with rounded corners. A film is read at 30 fps before it is cut, so a screen recording that has frames only where the picture changed still shows what was on screen at `in`.
3. The end card: the logo, the product's name, the smaller lines, the optional image.

Hard cuts between segments; each segment is a whole number of frames, so the cuts land where `render` prints them. The file is H.264 High, yuv420p, a constant 30 fps, tagged BT.709, with 48 kHz stereo AAC and the index at the front (faststart), which feeds and stores take.

## Another format

`render --size 1920x1080` makes a wide clip from the same spec when the screen's shape suits both frames. A phone screen in a wide frame comes out too small to read, and `check --size 1920x1080` says so. For that format, copy the spec into a folder of its own (`wide/2.4.0.json`), give each scene a `crop` round its change, fix the paths that were relative to the old folder, and render the copy.

## What `check` names

| Problem | The rule |
|---|---|
| A `<fill in ...>` mark left | Every mark written, or its optional key dropped. |
| A caption too long to read | It needs 2 x (words / 3) seconds: read twice at three words a second. Text without spaces counts two characters a word. |
| A caption too wide | Two lines at most at the caption size, inside the safe zone. |
| A scene too short | 1.5 s or more. |
| Too many scenes | The cards and scenes together within `max_seconds`. |
| A missing or wrong file | Every source, logo, font, image and music file present; `out` within the film. |
| A soft picture | No screen shown at more than 1.25x its own pixels (after `crop`): crop less, or capture larger. |
| A screen too small | The screen fills a fifth of the frame or more: crop to the change, or leave that size out. |
| A path from one machine | No absolute path, and none starting with `~`. |
| Low contrast | Text on band, text and muted and accent on background: 4.5:1 or more (WCAG AA). |
| A wrong version | Any `x.y.z` in the words matches `version`. An operating system's version counts too: write "iOS 17 and later". |
| An unknown key | Usually a typo. |

`check --words` checks only the words, lengths and look, before anything is filmed.
