# Default categories

Starting points for the scorecard [SETUP.md](SETUP.md) writes. Adapt every row to the product: replace the generic evidence with the sources this repo really has, and tighten an anchor wherever the product has a sharper bar. A category that does not apply is dropped, never scored 0. A category that applies and has nothing yet scores 0: every 5 below describes a small working state.

## An app (iOS, Android, desktop)

| Category | 5 means | 8 means | 10 means | Evidence that counts | Metric |
|---|---|---|---|---|---|
| Concept | a familiar idea, done competently | clearly different from every rival in a market scan | the one-sentence reason people install it | a market scan, each rival linked | installs |
| Content | enough for a week of use | enough for months, with few gaps | fresh content on a schedule, and no dead ends | counts of what there is (levels, lessons, recipes, tracks), an audit of gaps and broken items | day-7 retention |
| Core loop | the main task works, with friction | the main task in three taps or fewer, smooth | people do it every day unprompted | a device walkthrough, the taps from launch to the main task | day-7 retention |
| Retention | a reason or two to come back | streaks, reminders and progress all work | every day has a reason, and a missed day is forgiven | the analytics funnel, the list of return mechanics | day-7 retention |
| Onboarding | new users find their way eventually | first value inside a minute | a new user gets value within 30 seconds and knows why to return | a fresh install on a device, timed | day-7 retention |
| Visuals | consistent | premium in screenshots | better than the category's best | device screenshots beside the rivals' | installs |
| Engineering | works, with some crashes or stutter | crash-free for 99.5% of users or more, smooth on a mid-range device, CI green | crash-free for 99.9% or more, smooth on every target device | crash reports, frame rate per device, CI history | rating |
| Accessibility and languages | most controls labelled | screen readers pass, AA contrast, every shipped language complete | languages reviewed by native speakers, reduced motion respected everywhere | a screen-reader walk, contrast checks, missing-string checks | rating |
| Privacy | the claims are mostly true | every claim is true and kept in step with what the code sends | minimal data, plain switches, a plain page | each claim (policy, store privacy labels, listing) checked against what the code sends | rating |
| Store listing | a listing with real screenshots, in one language | keywords, screenshots and copy that sell, in every shipped language | top results for the category's keywords, strong conversion | the listing's text and screenshots, keyword ranks, the store console's conversion | installs |
| Growth | one share path, and it works | share cards, links, a reason to invite | a loop that brings new users on its own | the share paths, referral data | installs |
| Monetisation | one product on sale, and the purchase works | products live, a shop that sells | revenue grows with users and never sells an unfair edge | the store console's products, the purchase funnel | revenue |

Default metric weights, for a product still finding its audience: installs 4, day-7 retention 3, rating 2, revenue 1. Weight highest what the owners need most this season: a product with a steady audience may raise revenue.

## A website or web app

Keep Concept, Content, Core loop, Retention, Visuals, Privacy and Growth (and Monetisation if it sells). Change the rest:

| Category | Becomes | Evidence that counts |
|---|---|---|
| Onboarding | First visit: value on a cold load, before any sign-up | a fresh browser profile, timed |
| Engineering | Speed and errors: load time and error rate per browser | field performance data, error tracking, CI history |
| Store listing | Discovery: search results, link previews, the landing page | search console data, rank checks, preview renders |
| Accessibility and languages | The same, checked with an automated audit plus a keyboard-only walk | audit output, a walk's notes |

Metrics: where the app set says installs, read visitors or sign-ups; for day-7 retention, return visits; for rating, task success or satisfaction; for revenue, conversion.

## Anything else

These sets have run on an app and on a website. A command-line tool or a library has no default set yet. Draft its categories the same way: what a user gets, what 5, 8 and 10 mean, the evidence that counts, and one metric each.
