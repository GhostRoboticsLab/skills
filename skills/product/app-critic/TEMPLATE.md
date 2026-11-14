# The review's template

What one critic pass writes. Copy the template to the path `docs/agents/scorecard.md` names, fill it section by section as the steps go, and leave no `<...>`. The category rows come from the scorecard, in its order.

## Rules for the words

- **The headline** is one sentence a person can act on: the state of the product and the biggest reason for it.
- **What a user gets.** Every row describes the live product in a user's words. Code reasons go in the evidence, not the row.
- **Evidence ids.** Every score, story and owner call cites ids from the Evidence list. An id points at one thing: a file and line, a screenshot, a metric with its source, or a link.
- **Numbers say where.** Each measured number names its device, browser or machine and its date range.
- **Paths.** A file is named from the repo's root, a screenshot from the report's own folder. Where the report is posted outside the repo, attach the screenshots.
- **Priority** is written to one decimal. A finding that goes to Owner calls leaves impact, confidence, size and priority as a dash.
- **Proposals.** Stories here are proposals until a person accepts them; mark each one `new` or link the tracker item it extends.

## The template

```markdown
# Review <date>: <overall> / 10

<The headline: one sentence.>

**Main:** <commit> (<version>) · **Live:** <where users get it, and its version | none live | not reachable: main at its newest release tag stands in> · **Last review:** <link | first review: this one is the baseline>

## Scorecard

| Category | Last | Now | Change | Why, in a user's words | Evidence |
|---|---|---|---|---|---|
| <category> | <score or none> | <score or not scored> | <+0.5, 0, -1 ...> | <what a user gets; what main adds, if it differs> | <E1, E4> |
| **Overall** | | | | <the mean of N scored categories of M> | |

Lowest three: <category> <score>, <category> <score>, <category> <score>.

## What moved

- <category>: <last> to <now>, because <the merged change, the release, the new measurement, or a fresh read of the anchors> (<evidence id or link>).
- Live and main: <what main holds that users do not have yet | the same>.

## What was reviewed

- Main at <commit>; the live product at <version>, from <store page, URL, package page>.
- Devices: <device, OS, build type, language and theme, the date>.
- Data: <source, date range, read-only>.
- Scanners: <how many, which categories each covered | none>.
- The tracker, as of <date>.

## Findings

| # | Finding | Category | Metric | Impact (1 to 5) | Confidence | Size | Priority | Goes to |
|---|---|---|---|---|---|---|---|---|
| F1 | <the gap, in a user's words> | <category> | <metric> | <1 to 5> | <0.5, 0.75, 1> | <S, M, L> | <impact x weight x confidence / effort> | <S1, a tracker link, or O1> |

Priority = impact x the metric's weight (<weights from the scorecard>) x confidence / effort (S 1, M 2, L 4).

## Epics and stories

### <Epic: the outcome, in a user's words> (<new | tracker link>)

- **S1 <story title: what the user gets>** (new; Priority <p>, Size <S|M|L>; from F1; evidence <E2>)
  <One or two sentences: who, what they get, why it matters on the metric.>
  Done when: <a condition a person can check on the product or in a test>.

## Already on the tracker

- F<n>: <link>. This pass adds: <new evidence or a changed priority | nothing new>.

## Owner calls

- **O1 <the question>** Why now: <the finding and its evidence>. Options: (a) <...>, (b) <...>, (c) <...>. Recommendation: <one option, and why>. Action: <exactly what the owner does to decide or unblock it>.

## Not checked

- <category or kind of evidence>: <why: no device, no access to the data, out of this pass's budget, a rule forbids it>. Next time: <what would make it checkable | not expected>.

## Evidence

- E1: <file:line | screenshot path | metric, source, date range, where measured | link>. <What it shows, in one line.>

## Next review

<the date, or the trigger: a release, a milestone>
```

## After the person decides

The review file stays as it was handed over. Their choices (which stories entered the backlog, how each owner call was answered) go where the scorecard says reviews are posted, so the next pass reads them in step 1.
