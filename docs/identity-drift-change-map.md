# Identity drift and reflection prompts: change map

Every file touched by the identity-drift experiments, what changed in it, and
what checks it. For *why* any of it was done, and every number behind it, see
[identity-drift-engineering-log.md](identity-drift-engineering-log.md).

`git diff --stat` is the authority on line counts; this file exists for the part
git cannot tell you: which change is load-bearing, and what proves it.
**9 files: 1 modified, 8 new.** Two commits on top of
`fix/chat-model-prompt-contract` (`4bcc661c`): `ea95d2b4`, the parser fix, and the
experiments commit. The prompt fixes underneath are in
[chat-model-prompt-fixes-change-map.md](chat-model-prompt-fixes-change-map.md).

**What this branch is.** A parser fix for the live reflection path, plus the
scripts and write-up behind the finding that the nightly identity rewrite drops
residents' stances. The keep-views prompt that fixes that is a *proposal*: it is
applied only inside the scripts, and `plan.py` is untouched.

## Suggested review order

1. `run_gpt_prompt.py`, the parser in `run_gpt_prompt_insight_and_guidance`. The
   only change to a live path, and it is its own commit (`ea95d2b4`), so it can be
   cherry-picked onto the fix branch without the rest.
2. The same function's two other edits (the `template` option and the name input).
   Inert by default.
3. `scripts/test_revise_identity.py` and `scripts/run_identity_ab.py`. They apply
   the keep-views sentence by wrapping `plan.ChatGPT_single_request`. Read the two
   docstrings first; each states what it holds fixed.
4. `scripts/analyze_identity_ab.py`. How the six-run A/B is scored.
5. `scripts/compare_reflection_prompts.py`, `scripts/probe_with_added_insights.py`
   and `v2/insight_and_evidence_v2.txt`. The reflection experiment, a negative
   result.
6. The engineering log.

## Backend: agent behaviour

| File | What changed | Checked by |
|---|---|---|
| `reverie/backend_server/persona/prompt_template/run_gpt_prompt.py`, `run_gpt_prompt_insight_and_guidance`, clean-up | Reads insights by splitting on the `(because of ...)` tags instead of on line breaks. When the model wrote all five insights on one line, the old code read them as one insight with the first tag's evidence and lost the rest. Text before a tag is that insight, with a leading `N.` removed; text after the last tag is a cut-off line and is dropped; no tags still raises, so the fail-safe is unchanged. | Four canned replies: numbered lines with a cut-off last line and a two-sentence insight, one line with no numbering, a cut-off final line, and an unparseable reply (still falls back). Run ad hoc; see Open items. |
| same function, signature and prompt input | New optional `template` argument (default `None`, which keeps the path it had) and the resident's name as a third prompt input. | The v1 prompt renders byte-identically with the extra input, because the v1 template has no third placeholder (checked with `generate_prompt`). The v2 template uses it. |

## Prompt templates (not live)

| File | What it is |
|---|---|
| `reverie/backend_server/persona/prompt_template/v2/insight_and_evidence_v2.txt` | The v2 insight prompt: one sentence per insight, naming the resident and saying what they want, worry about, believe or have said, and only views the cited statements show. Nothing loads it unless a caller passes `template=`; only `scripts/compare_reflection_prompts.py` does. |

## Scripts: none of them changes agent state

Each docstring says what it holds fixed and what it measures. All run from
`reverie/backend_server`.

| File | What it does | What it writes |
|---|---|---|
| `scripts/compare_reflection_prompts.py` | Runs the v1 and v2 insight prompts on the same focal points and retrieved memories of a finished run, and labels the insights. | Only `--out`. Loads saved personas; retrieval uses `touch=False`. |
| `scripts/probe_with_added_insights.py` | Reads each resident's stance with and without the v2 insights stored as thoughts. | Only `--out`. The thoughts exist in RAM only. |
| `scripts/test_revise_identity.py` | Rewinds each resident to midnight at the end of day 1 and runs the real `revise_identity` under the current prompt and the keep-views prompt, with and without an injected change of mind. | Only `--out`. Memories are cut in RAM; the keep-views sentence is applied by wrapping `ChatGPT_single_request`. |
| `scripts/run_identity_ab.py` | Starts one headless run of the 8-resident town for the A/B, under either prompt. | A real run: `stg-<name>` in `storage/`, `logs/<name>/`, and `temp_storage/dashboard/runs/<name>/` (git-ignored). Also guards the empty-room crash for that run (below). |
| `scripts/analyze_identity_ab.py` | Compares finished A/B runs: does each stance survive the rewrite, and do day-2 readings follow the starting direction. Read-only. | Only `--out`, if given. |

`run_identity_ab.py` keeps each run's dashboard files in their own folder because
runs sharing `temp_storage/dashboard/state.json` raced on it and one crashed at
startup.

## Checks and config

- Team CI checks, all passing on this tree: `check_repo.py`, `compileall` over
  `reverie/backend_server`, `environment/frontend_server` and `scripts`,
  `check_retrieval.py`, `check_opinion_probe.py`, `test_stance_rubric.py`,
  `check_memory_categories.py`. The Django and Node dashboard checks were not run;
  no frontend file changed.
- `analyze_identity_ab.py` was run on the six finished runs and reproduces the
  numbers in the engineering log exactly. The other four were each run end to end
  on a short real run: `compare_reflection_prompts.py` and
  `probe_with_added_insights.py` on three residents, `test_revise_identity.py`
  with one rewrite per prompt, and `run_identity_ab.py` for one step (v2, histories
  loaded, saved). Those were smoke tests; the full-size numbers in the log came from
  earlier runs of the same code.
- No change to `.github/workflows/ci.yml`, `utils.py.example` or any config.

## Behaviour that did not change

- `plan.py`, `revise_identity` and every live prompt template. The keep-views
  sentence exists only inside the scripts.
- The v1 insight prompt text, for the reason in the table above.
- Parsing of ordinary insight output (one numbered insight per line, each with its
  tag) gives the same result as before.
- The stance probe, retrieval, the dashboard, and the earlier prompt fixes.

The parser change does alter one case: a reply with several insights on one line,
which used to come back as a single insight, now comes back as several. That is
the intended fix and it adds thoughts to memory that were previously lost, so runs
made before this commit are not strictly comparable on reflection counts.

## Not committed

- The runs and their outputs (`stg-*`, `logs/`, the per-run dashboard folders) stay
  local. The identity A/B itself is six local runs, `ab-v1-1..3` and `ab-v2-2..4`.
- The extra checkout used to run the A/B.

## Open items

- **The parser cases are not a CI check.** They ran ad hoc. Wiring them into
  `ci.yml` is a small follow-up and was left for the team because it changes CI.
- **The keep-views prompt is a proposal.** It changes agent behaviour, so runs
  before and after would not be comparable (see the pull request template). The
  team should decide whether holding the old stance in 3 of 15 change-of-mind
  rewrites is acceptable.
- **The empty-room crash is only worked around, in `run_identity_ab.py`.** A repo
  fix would give `run_gpt_prompt_action_arena` a real room to fall back to.
- **Not tested:** whether identity drift changes what residents say on day 2,
  drift over more than one night, and any model other than gpt-4o-mini.
- **`chat-model-prompt-fixes-change-map.md` still says its live comparison is in
  progress.** A matched baseline-against-fixed comparison was not run. The six runs
  here used the fixed code and had no failed calls and no prompt-related crash, but
  they have no baseline arm.

## Verified at

Branch `experiment/identity-drift`, on `fix/chat-model-prompt-contract @ 4bcc661c`.
Parser commit `ea95d2b4`.
