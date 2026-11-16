# Identity drift and reflection prompts: engineering log

Why the stance chart's gaps are not the cosine ranking, and what the tests found
instead: the nightly identity rewrite drops residents' stances, and a long run can
crash on an empty room. Five findings, in the order they were reached.

For *which files changed and why*, see
[identity-drift-change-map.md](identity-drift-change-map.md). This branch is
stacked on `fix/chat-model-prompt-contract`, whose prompt fixes are in
[chat-model-prompt-fixes-change-map.md](chat-model-prompt-fixes-change-map.md).
The stance probe these tests measure is described in
[belief-change-cast-and-probe-log.md](belief-change-cast-and-probe-log.md).

**Nothing here changes how the simulation behaves**, apart from the reflection
parser change in its own commit (`ea95d2b4`). The prompt changes below are
proposals, tested only through the scripts in `scripts/`.

It started from a question about the stance chart: it has gaps, and most
residents' readings pile up at 30. Is cosine ranking of the evidence to blame, and
would a different retrieval or prompt do better? The short answer is no to the
first, and the changes tried did not move the readings. The tests did turn up two
real problems: the nightly identity rewrite drops residents' stances, and a crash
that can end any long run.

---

## Findings

1. The gaps are sleep and abstention, not low relevance. No reading in four runs
   was withheld for low relevance.
2. Rewriting the reflection prompt so insights are about the resident
   (`insight_and_evidence_v2.txt`) makes them attributed but generic, and did not
   improve the probe. Not recommended as written.
3. `revise_identity` drops stances overnight. With the current prompt 13 of 24
   stances survived a night in full runs.
4. One added sentence telling the model to keep standing views fixes that (24 of
   24 survived). It did not change the probe's readings after one night.
5. Any long run can crash when a resident picks a building they know no rooms in.

## 1. Where the gaps come from

Readings in `experiment/opinions.jsonl`, 8-resident town. `baseline-*` ran on
`main @ edac6ebb` for 17 game hours, `fixed-1` on the prompt-fix branch for 27.

| run | scored | asleep | abstained | low_relevance |
|---|---|---|---|---|
| stg-baseline-1 | 77 | 55 | 4 | 0 |
| stg-baseline-2 | 95 | 38 | 3 | 0 |
| stg-baseline-3 | 81 | 53 | 2 | 0 |
| stg-fixed-1 | 131 | 83 | 2 | 0 |

These are our runs, not the ones behind the dashboard chart that prompted the
question, so another cause there is not ruled out. The probe's own notes also
argue selection among spoken lines matters little at one game day
(`belief-change-cast-and-probe-log.md` §11.2).

## 2. Attributed reflection insights (v2)

`scripts/compare_reflection_prompts.py stg-fixed-1` runs the insight prompt in both
versions on the same focal points and retrieved memories: 3 focal points x 5
insights x 8 residents = 120 insights per prompt. v2 asks for one sentence naming
the resident and saying what they want, worry about, believe or have said, and to
describe only views the cited statements show.

| | v1 (current) | v2 |
|---|---|---|
| name the resident | 11% | 100% |
| state the resident's own view (model label, from the sentence alone) | 2% | 80% |
| own view and supported by the statements cited (of 120) | 3 | 83 |
| of those, about the datacenter | 0 | 45 |
| control: wrong citations still judged supported | 23% | 22% |

The control pairs each insight with another insight's citations, so 22-23% is the
error rate of the "supported" label. The labels come from the model that wrote the
insights.

The v2 insights are attributed but generic. They read "wants to ensure community
concerns are addressed" for residents seeded with opposite stances. In a word
count of support and opposition language across each resident's 15 insights,
Maya (supports), Denise (leans in favour), Aisha (conditionally opposes), Elena
and Rachel (undecided) have none; Luis has 4 that mention support, Marcus 1 each
way, and Tom (leans against) 5 that mention negative impacts. The insights are
written from the memory pool, whose existing reflections are impersonal, so v2
mostly relabels them. A few turn "residents are concerned" into "Tom is
concerned"; 3 of Tom's were rated unsupported or partly supported by their
citations.

`scripts/probe_with_added_insights.py` stores the v2 insights as thoughts and
reads each resident's stance with and without them (all added at once as the
newest memories, an approximation of v2 running all day):

| resident (starting stance) | as saved | with v2 insights |
|---|---|---|
| Maya (supports) | 70 | 45 |
| Luis (conditional support) | 65 | 65-70 |
| Denise, Rachel, Elena, Aisha, Tom, Marcus | 30 | 30 |

Spearman against the starting direction: +0.66 as saved, +0.60 with the insights
(n=8, six tied). Maya's drop came from one new insight, "worries about addressing
community concerns...": the probe reads "worries" as opposition. The v2 prompt
lists "worries" among the things to write about.

The v2 template stays in `v2/insight_and_evidence_v2.txt` for these scripts only.
The live reflection prompt is unchanged.

## 3. The nightly identity rewrite

`revise_identity` (`plan.py`) rewrites each resident's `currently` at every day
boundary, and that text goes into every hourly prompt. Its prompt asks for a status
reflecting yesterday's thoughts and says nothing about keeping standing views.
After one night in `stg-fixed-1`, explicit position wording in the eight identities
fell from 13 phrases to 2 (a crude word count).

`scripts/test_revise_identity.py` rewinds each resident to midnight at the end of
day 1 and runs the real `revise_identity` 5 times under two prompts (40 rewrites
each). v2 adds one sentence before the format line:

> If yesterday's status states a position or concern (for example that {n}
> supports, opposes or is undecided about something), say it again in today's
> status, unless the thoughts above show {n} has changed their mind. Then add what
> {n} plans to do today.

| | stance kept | dropped | changed to another stance |
|---|---|---|---|
| current prompt | 24 | 12 | 4 |
| keep-views | 40 | 0 | 0 |

Under the current prompt Rachel's "undecided" survived 0 of 5 rewrites, and
Aisha's "conditionally opposes" came back as "supports" once.

Does keep-views freeze opinions? Three thoughts saying the resident changed
position were added for Maya, Marcus and Tom (5 rewrites per prompt each):

| resident (start, injected change) | current prompt | keep-views |
|---|---|---|
| Maya (supports, now doubts) | undecided x2, opposes x2, none x1 | opposes x5 |
| Marcus (opposes, now supports) | supports x5 | supports x4, held opposes x1 |
| Tom (opposes, now supports) | supports x4, undecided x1 | supports x3, held opposes x2 |

Keep-views followed the change 12 times of 15 and held the old stance 3 times. The
current prompt held it 0 times but went undecided 3 times and dropped the stance
once. Whether holding 3 of 15 is a problem depends on the study; the injected
change is three maximally important memories in one night, blunter than a real one.

## 4. Full runs

`scripts/run_identity_ab.py` runs the 8-resident town headless from 07:00 on day 1
to 12:00 on day 2 (10,440 steps, one midnight), on gpt-4o-mini in staging. Three
runs per prompt; the code is the prompt-fix branch plus the parser fix.
`scripts/analyze_identity_ab.py` compares them. rho is the Spearman correlation of
the probe's readings with each resident's starting direction (day 1 is 12:00 to
midnight, day 2 is 06:00 to 13:00 after the rewrite).

| run | identity kept / dropped / changed | rho day 1 | rho day 2 |
|---|---|---|---|
| ab-v1-1 (current) | 5 / 2 / 1 | +0.61 | +0.61 |
| ab-v1-2 (current) | 3 / 3 / 2 | +0.44 | +0.63 |
| ab-v1-3 (current) | 5 / 3 / 0 | +0.70 | +0.70 |
| ab-v2-2 (keep-views) | 8 / 0 / 0 | +0.83 | +0.85 |
| ab-v2-3 (keep-views) | 8 / 0 / 0 | +0.96 | +0.98 |
| ab-v2-4 (keep-views) | 8 / 0 / 0 | +0.91 | +0.86 |

- Identity: current prompt 13 of 24 kept, 8 dropped, 3 changed; keep-views 24 of 24.
- Readings: no run got worse after the night; the six day-1 to day-2 changes run
  from -0.05 to +0.19 with no pattern by prompt.
- The arms differ on day 1 already (mean +0.58 against +0.90), before the prompts
  differ. That is run-to-run variation, and three runs per arm cannot show an
  effect smaller than it.
- The probe does not read `currently` (`stance_iss`), so a stance missing from the
  identity does not reach it directly. That is the likely reason for no change.
- The share of day-2 readings at exactly 30 ranged from 22% to 68% with no link to
  the prompt.

Cost: $0.76-0.95 per full run, with no failed calls.

## 5. A crash on long runs

`ab-v2-1` stopped at step 4554 (19:39 on day 1) with
`KeyError: "the Ville:artist's co-living space:"` in `execute.py`. It is not
caused by either prompt: replaying the decision 40 times gave `}` every time with
and without the "output only the continuation" system message.

Cause. Marcus knew 5 places at the start and 10 at the crash: perception adds a
building to a resident's spatial memory when they pass it, before they know any
rooms in it. When the model later picks that sector, the room prompt is
`{...}` with nothing inside, the model answers `}`, and
`run_gpt_prompt_action_arena` accepts it (it only checks that the reply contains
`}` and no comma) and parses the room as `""`. The address is not on the map. This is how the original
memory grows, so any resident in any run can hit it. At the start of the town
no resident has a sector with no known rooms, so it is not a data fault in the
base.

`run_identity_ab.py` works around it for runs: when the room comes back empty it
uses a shared room that exists on the map. A fix in the repo could do the same in
`run_gpt_prompt_action_arena`. The existing fallback, "kitchen", is not a safe
choice: nothing guarantees the building has one. The first five runs of the A/B did not have the
workaround and `ab-v2-4` replaced `ab-v2-1` with it.

## Not tested

- Whether identity drift changes what residents say and do on day 2 (the lines they
  speak). That is where `currently` matters, and it was not measured.
- More than one night. The original concern was drift building up over days.
- A model other than gpt-4o-mini. Every label comes from the model that wrote the
  text being labelled.
- Why six of eight residents read exactly 30; the probe's notes put it down to
  round-number bias on a 1-100 scale. Nothing here addresses it.

## Proposals, not applied

- Add the keep-views sentence to the status prompt in `revise_identity`, before
  `Follow this format below:`. It changes agent behaviour, so runs before and
  after are not comparable (see the pull request template). Decide first whether
  holding the old stance 3 times in 15 is acceptable for the study.
- Make the room step fall back to a real room instead of crashing.

## Reproduce

From `reverie/backend_server`, with a finished run `<sim>`:

```
python3 ../../scripts/compare_reflection_prompts.py <sim> --out insights.json
python3 ../../scripts/probe_with_added_insights.py <sim> insights.json probe.json
python3 ../../scripts/test_revise_identity.py <sim> identity.json 5
python3 ../../scripts/run_identity_ab.py v1 ab-v1-1 10440    # and v2, several names
python3 ../../scripts/analyze_identity_ab.py ab-v1-1 ab-v2-2 ...
```

Each script's docstring says what it holds fixed and what it measures. Sections 2
and 3 ran on `stg-fixed-1`, a 27-hour run on the prompt-fix branch; the runs
themselves are not tracked (`stg-*` stay local).

## Verified at

Branch `experiment/identity-drift`. Team CI checks `check_repo.py`,
`check_retrieval.py` and `compileall` pass. The scripts were run end to end on the
runs named above.
