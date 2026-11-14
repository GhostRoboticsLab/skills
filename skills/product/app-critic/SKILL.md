---
name: app-critic
description: Score the whole product on a scorecard, every score with evidence, and turn what it finds into prioritised stories.
disable-model-invocation: true
---

# App critic

A **critic pass** scores the whole product once per review cycle against the project's written scorecard, then turns the gaps into prioritised stories. Every score from 0 to 10 carries evidence or is not given, and it describes what a user gets today, not what the code intends. Without anchors and evidence a review drifts toward taste and toward the last score; without a priority, findings pile up and the loudest one wins. The pass reads the code, the product and the tracker, and writes only its report. A person decides what enters the backlog.

Project facts live in `docs/agents/scorecard.md` in the user's repo: the categories with what 5, 8 and 10 mean, the evidence that counts, the metric each one moves and its weight, the devices the pass may use, where the report goes, and who decides. If that file is missing, follow [SETUP.md](SETUP.md) first.

## Guard rails

- **Read-only.** The report and its screenshots, under the report folder the scorecard names, are the only files the pass writes. Code, commits and the tracker stay as they were: no issue, comment, label or board move. On a device, launch the product and take screenshots, within the scorecard's device rules.
- **Anchors, not the last score.** Each score is read off its category's 5, 8 and 10. The last review's score is looked at only after the new one is written.
- **Links for claims.** A claim about a competitor or the market carries a link; a claim about users carries a metric and its source.
- **Plain gaps.** Whatever was not checked is listed with the reason.
- **Recorded decisions stand.** A product rule or a recorded owner decision is scored as given. A finding that would change one becomes an owner call that names it.

## 1. Open the pass

Read `docs/agents/scorecard.md`, then the last review where the scorecard says reviews are posted. From it, note the date, the commit and live version it scored, its open owner calls and its Not checked list. If this cycle already has a critic pass, tell the user and stop: it is the expensive review, one per cycle.

Name what is under review: main's commit and version, and the live version users get (a store build, a deployed site, a published package). Start the report from [TEMPLATE.md](TEMPLATE.md) at the path the scorecard names and fill its header.

**Done when:** the report file exists with its header filled (main's commit; the live version, "none live" or "not reachable"; the last review's link or "first review: this one is the baseline"), and no other critic pass exists for this cycle.

## 2. Gather the evidence

For each category, collect what the scorecard says counts. Each item goes into the report's Evidence list with an id (`E1`, `E2`) and one of:

- a file and line, for what the code does;
- a screenshot path, for what a user sees. Take them in one pass per device and share them across categories;
- a metric with its source, its date range and where it was measured;
- a link, for a live page, a listing or a competitor;
- the tracker's state, read only: what merged since the last review, what is already open.

You may dispatch read-only scanners, one per group of related categories, on a cheap model. Start each with a fresh context. Give it its categories with their anchors and evidence kinds and the guard rails above, and ask it for evidence items plus what it could not check, never for scores. You do the scoring.

**Done when:** every category has at least one evidence item, or a line under Not checked saying why it has none.

## 3. Score

For each category, read its evidence against its anchors and write Now:

- 0 to 10 in steps of 0.5. Between anchors, place it by how far the evidence goes toward the next one; below 5, by how much of what 5 asks for is there, with 0 when the category is absent.
- No evidence, no score: the row says "not scored" and the category goes under Not checked. Overall is the mean of the scored categories, naming how many of how many.
- Score the live version, what a user gets today. When main differs, the row also says what main adds. When the live version cannot be reached (a URL that does not answer, no store access), score main at its newest release tag, say so in the header, and list the gap under Not checked.
- Write every Now before you fill Last; then fill Last and Change.
- A change of 1 or more names what moved it: a merged change, a release, a new measurement, or a fresh read of the anchors.

**Done when:** every row has a Now that cites evidence ids (or "not scored"), Last and Change are filled, every change of 1 or more names its cause, and every number says where it was measured ("Numbers say where" in TEMPLATE.md).

## 4. Turn findings into stories

A **finding** is a gap between a category's Now and its next anchor, or something broken. For each one:

1. Search the tracker, read only. An open item that covers it goes under Already on the tracker, linked, with what this pass adds.
2. Size it S, M or L. Split an XL first, and score its parts.
3. **Priority** = impact (1 to 5, on its category's metric) x the metric's weight x confidence (0.5 a hunch, 0.75 some evidence, 1 measured) / effort (S 1, M 2, L 4).
4. Put it under an epic, one per theme, reusing an open epic when one fits. The story says what the user gets, cites its finding's evidence, and ends in a **Done when** a person can check.

Aim for stories that lift a category to its next anchor, kept buildable.

An **owner call** is a finding that needs money, a release, a taste call, or a change to a product rule or recorded decision. It goes under Owner calls instead of a story: what, why, two or three options, your recommendation, and the exact action the owner takes. Only new asks: an open one is linked, not repeated.

**Done when:** every finding sits in exactly one place (a story, Already on the tracker, or Owner calls), every story shows its four priority inputs, its size and a checkable Done when, and every owner call has at least two options and a recommendation.

## 5. Read it cold

Read the report as a stranger holding only the report and the scorecard:

- For each score: would that stranger, from its evidence and the anchors alone, land within 0.5 of it? If not, fix the score or gather more evidence.
- Each path and link opens.
- Not checked lists every category not scored and every kind of evidence skipped, each with why.
- No `<...>` from the template is left.

**Done when:** all four hold.

## 6. Hand it to a person

Give the person who decides (named in the scorecard) the report's path, the top stories, the owner calls, and the command that posts the report where reviews live, ready for them to run or to tell you to run. Post, file and move nothing until they say so. Which stories enter the backlog is theirs to pick.

**Done when:** the person has the report's path, the post command and the owner calls, and the tracker holds nothing this pass wrote.
