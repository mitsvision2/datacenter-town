# Chat-model prompt fixes: change map

The simulation's prompts were written for 2023 completion models (text-davinci).
On gpt-4o-mini some answers are cut off by token limits sized for those models,
and some parsers reject valid replies. This branch fixes the prompts marked
*Corrupts data*, *Can crash* and *Flawed output* in the prompt list shared with
the team. Prompt wording is unchanged apart from one pronoun.

**4 files modified, about 70 lines.** `git diff --stat main` is the authority on
line counts.

## Suggested review order

1. `run_gpt_prompt.py`, `run_gpt_prompt_insight_and_guidance`: reflection.
   This is where opinions form, so it has the biggest effect on study data.
2. `run_gpt_prompt.py`, `run_gpt_prompt_decide_to_talk` and
   `run_gpt_prompt_decide_to_react`: whether residents talk and whether they
   wait for each other.
3. `gpt_structure.py`, `GPT_request`: one system message that applies to all 16
   text-completion prompts.
4. The rest of `run_gpt_prompt.py`: fallbacks and parsing.
5. `plan.py` and `v2/planning_thought_on_convo_v1.txt`: small wording fixes.

## What was broken, and the fix

| Prompt (list status) | Problem on gpt-4o-mini | Fix |
|---|---|---|
| `insight_and_guidance` (Corrupts data) | `max_tokens` 150 cuts off the last insight. One bad line made the parser reject the whole reply, so the reflection was dropped. `reflect.py` now skips the "this is blank" result (8562d994), which counted 39 in one 8-resident day. Separately, `split(". ")[-1]` kept only the last sentence of a multi-sentence insight. | `max_tokens` 500. Skip lines without a complete `(because of …)`. Strip the leading `N.` with a regex. Raise if nothing parses. The fallback is unchanged, so failures still log `skipping unparsed insight batch`. |
| `decide_to_talk` (Corrupts data) | The prompt asks for reasoning, then yes/no, but `max_tokens` is 20, so the answer never arrived and the fallback "yes" was always used. Every pair of nearby residents talked. | `max_tokens` 300; take the last `yes`/`no` in the reply. |
| `decide_to_react` (Corrupts data) | Same cut-off; the fallback "3" (do neither) was always used. | `max_tokens` 300; take the last `option 1/2/3`. |
| `pronunciatio`, `act_obj_desc`, `summarize_conversation`, `event_poignancy`, `chat_poignancy`, `agent_chat_summarize_relationship`, `summarize_ideas` (Can crash) | If every retry was rejected, the function returned `None`, which crashes the step (`TypeError: 'NoneType' object is not subscriptable`). | Return the function's existing `fail_safe`. |
| `event_triple`, `act_obj_event_triple` (Flawed output) | `split(",")` breaks on objects that contain commas ("plates, utensils, and glasses"). The fallback became a garbled triple (`Name, Name, is`), because the caller already prepends the subject. | `split(",", 1)`; the fallback is `("is", "idle")`. |
| `focal_pt` (Flawed output) | gpt-4o-mini returns a real JSON list where the parser expected a string. The chat path failed every time and the text backup cost 3 extra calls. | The chat clean-up accepts a list or a string; validate uses the chat clean-up. |
| `planning_thought_on_convo` (Flawed output) | The template says "for her planning" for every resident. | "needs to remember for their planning". |
| All 16 text-completion prompts | Chat models restate the prompt's trailing stub ("<Name> is …") that completion models simply continued. 5c643e33 handled this for the hourly schedule only. | `GPT_request` sends a system message to continue the text and output only the continuation. The hourly-schedule strip stays and becomes a no-op. |
| `revise_identity` status (Not yet tested) | The prompt asks for `Status: <new status>`, and the label was stored in `scratch.currently`. That field is what `outcomes.jsonl` logs. | Strip a leading `Status:`. |

## Files

| File | What changed |
|---|---|
| `reverie/backend_server/persona/prompt_template/run_gpt_prompt.py` | The fixes in the table above, inside each function's clean-up, validate and fail-safe. |
| `reverie/backend_server/persona/prompt_template/gpt_structure.py` | `GPT_request`: system message added before the user prompt. Both the OpenAI and Anthropic paths in `llm/client.py` already handle system messages. |
| `reverie/backend_server/persona/cognitive_modules/plan.py` | `import re`; `revise_identity` strips the `Status:` label. |
| `reverie/backend_server/persona/prompt_template/v2/planning_thought_on_convo_v1.txt` | Pronoun fix. |

## Behaviour that did not change

- **Prompt wording:** unchanged except the pronoun fix. No prompt was rewritten or reformatted.
- **Prompts marked Working:** untouched, as are dead prompt functions and unused templates. These are flagged in the prompt list, not deleted.
- **`reflect.py`:** untouched; the team's `BLANK_INSIGHTS` skip stays as it is.
- **Existing team fixes:** the stance probe, `extract_json_output`, the whisper clock in `_load_whispers`, the task-decomp fix and the hourly-schedule strip are all unchanged.

**Comparability:** this does change agent behaviour. Residents now decide whether to talk instead of always talking, reflection produces insights, and memories no longer hold garbled triples. Runs made before this branch are not directly comparable with runs after it on conversation counts or stance.

## How it was tested

- **Team CI checks**, all pass: `check_repo.py`, `compileall`, `check_retrieval.py`, `check_opinion_probe.py`, `test_stance_rubric.py` and `check_memory_categories.py`. The Django and Node dashboard checks were not run, since no frontend files changed.
- **Offline parser checks, 13 of 13 pass.** Canned model replies were fed through the real `run_gpt_prompt` functions with the LLM call stubbed, using personas from `base_the_ville_datacenter_n8`. The cases cover:
  - reasoning ending in yes or no
  - "Option 2: …"
  - an insight list with a cut-off last line and a two-sentence insight
  - an unparseable insight reply, which falls back as before
  - focal points as a JSON list and as a string
  - triples whose object contains commas
  - unusable triple replies, which give a clean fallback
  - a rejected poignancy reply, which returns the default instead of `None`
- **Live comparison, in progress.** Four staging runs on gpt-4o-mini, fork `base_the_ville_datacenter_n8`, start 07:00:
  - `stg-baseline-1/2/3` run on `main @ edac6ebb` to midnight.
  - `stg-fixed-1` runs on this branch to 10:00 on day 2, with one `call -- interview` at 22:00. That covers the `revise_identity` and interview prompts.
  - Each run is compared on crashes, `skipping unparsed insight batch` count, `decide_to_talk`/`decide_to_react` outcomes, and fallback rate.
  - Results will be added here.

## Open items

- **Live comparison results.** See above.
- **Not covered by this branch:**
  - `reflect.py: generate_insights_and_evidence` drops a whole insight batch if the model cites an evidence number outside the list. It's rare, and it now logs `skipping unparsed insight batch`.
  - The prompts marked Not yet tested (`new_decomp_schedule`, `memo_on_convo`, `safety_score`, `generate_next_convo_line`, the other `revise_identity` prompts) have no known bug. The live run is their first exercise.
- **Parallel runs (unrelated to this branch):** two runs from one checkout share `temp_storage/dashboard/state.json` and its `.tmp` file. One run crashed at startup with `FileNotFoundError` in `dashboard_bridge.write_state`. The test runs above worked around it with a separate `fs_temp_storage` per run.

## Verified at

Branch `fix/chat-model-prompt-contract`, based on `main @ edac6ebb`.
