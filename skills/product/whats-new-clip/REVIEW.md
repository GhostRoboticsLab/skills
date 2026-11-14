# The reviewer pass

Read this with the clip's stills (`clip.py stills <clip> --spec <spec> --every 1 --safe --sheet ...`), its spec and its sheet. The tinted edges are what a feed covers with its own buttons, names and captions; they are on the stills only, never in the clip. Judge the picture as a stranger scrolling past would: what is on screen, not what was meant. Every item holds for every still of every format, or it is a finding.

## Each scene

1. **It shows its caption.** The still from the middle of the scene shows what the caption says, with the change itself visible: not the screen before it happens, not covered by a sheet, a keyboard, a toast or a finger, and not under a tinted edge.
2. **One change.** The scene shows the one change its caption names, and nothing else new competes with it.
3. **The release, and only the release.** Everything on screen is in the build that ships: no feature switched off for this release, nothing from the next one, no "coming soon" shown as if it shipped, no other version's number.
4. **Nothing private or unfinished.** No debug banner, dev label, frame meter or test menu; no real person's name, email, photo or message; no notification; no placeholder text, error, crash or spinner where the moment should be.
5. **One look.** The same device or window, theme and language as every other scene, and a clean status bar. A kept film (FILMING.md) was made another way, so nothing checked it: it passes every item here by eye.
6. **Sharp.** No soft, blocky or stretched picture. `check` stops a picture blown up past its pixels or too small for the frame; a blurry film, and the product's own text at the size people will watch, still need your eye.
7. **People.** Bystanders' faces are blurred, and the people a scene is about have agreed.

## The words

8. **Verbatim.** Each caption is exactly the agreed words, as the spec's `words_by` says, and true of this release.
9. **Readable.** Every caption is whole, on its band, inside the frame, and can be read twice before its scene ends. `check` holds the arithmetic; watching the clip once, muted, at full speed is the real test.
10. **Muted.** The clip makes its point with the sound off. Music, if any, is licensed for where the clip will be posted and sits under, never over.

## The cards

11. **The opening card** is the clip's first frame (its cover): the fixed opening line, the version under it, inside the safe zone.
12. **The end card** says where to get the product. Store badges appear exactly as the stores ship them, unaltered, and only for stores where this release is live, with any trademark line the store asks for.

## A finding

Fix it at its cause, then render and pull the stills again:

| Finding | Fix |
|---|---|
| Wrong state, overlay, private data, wrong look | Film the scene again (step 4) |
| The moment falls outside the scene | Move `in` and `out`, picked from `clip.py peek` of the film |
| The change sits under a tinted edge | Give the scene a `crop` round the change, about as wide as it is tall, so the change sits inside the lines |
| The words are wrong, untrue or too long | Back to the approver with a new line (step 2) |
| A green check and a wrong picture | Report it to the user: the spec or the tool missed it |

## The hand-over

What the approver gets, in one message:

- The clip, each format, as a link or a path relative to the clips folder; never a machine's absolute path.
- The sheet, inline where the channel shows images, with one line saying its tinted edges are what a feed covers.
- The scenes as a numbered list: caption, who gave the words, what it shows.
- What was staged: the build, the seeded state, anything switched on for filming, and any kept film with where it came from.
- The length and the formats.
- The ask: "an OK, or what to change".
