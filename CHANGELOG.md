# Changelog

Notable changes to Datacenter Town. Newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased: dashboard rework

Branch `danrublop-datacenter-town`. The full write-up, with screenshots, is
[docs/dashboard-update.md](docs/dashboard-update.md).

### Added

- **Reflections tab**: every saved reflection, newest first. Opening one shows the tree
  of memories it was drawn from, with zoom, pan and a minimap.
- **Day view** on the map: one agent's day as snapshots of the town, with
  conversation, whisper and reflection marks. Clicking a snapshot replays from there.
- **Replay controls** for saved runs: play, pause, speed and seek. **Show on map** in
  the readers jumps the replay to that moment.
- **Map navigation**: drag, zoom, and click an agent to follow them.
- **Night on the map** from 22:00 to 06:00, the stance probe's night window. Turn it
  off in Settings.
- **Activity chart**: where each agent spent their time.
- **Gap reasons** on the stance chart: why a reading is missing.
- **Memory tab**: each cited memory's relevance score, and links to whispers and
  conversations.
- `GET /dashboard/activity/`, `timeline/`, `memory/`, `reflections/` and `day/`.
- Whisper deliveries record `node_id`, the memory each whisper became.
- Each movement step records `asleep` per agent, using the stance probe's rule.

### Changed

- **Look**: a flat design with dark mode, one color per agent, peg sprites and agent chips.
- **Where each whisper went** is now the **Whisper trail** tab. It supersedes the chart
  described in the section below:
  - Stance dots show the reading when the person heard it and their latest, not before
    and after, so they don't read as an effect.
  - ■ marks reflections that drew on the whisper.
  - Grey ticks mark conversations where it was not detected.
  - The words list under the chart is removed.
  - Every mark can be opened from the keyboard.
- **Whispers tab**: actions moved into a reader, cancelled whispers are listed,
  "Sent to N of M" shows partial sends, and "Everyone" is now "All agents".
- **Social network**: agents are placed by stance, and each side's stance is shown as
  it was at the time of a talk.
- **Map speech bubbles** are short cues; conversation text is not drawn on the map.
- **Logs are read in full** instead of the last 300 rows, and a live poll sends only
  new rows.
- **When no run is live**, the dashboard shows nothing until you open a run from the menu.
  Interview only works in a live run.
- **Replay is read-only**: it no longer posts positions to the server.

### Fixed

- Agents flickered between walking and standing during replay.

## Unreleased: scheduled whispers and the whisper chart

Branch `yaksh-whisper-scheduler`. The full write-up is
[docs/whisper-scheduling-handoff.md](docs/whisper-scheduling-handoff.md).

### Added

- **Whisper dialog** on the dashboard (the **Whisper** button in the header, the
  **New whisper** button in the Whispers tab, or **Write a whisper** on an agent).
  One dialog can hold several whispers, each with its own people, text and time.
  - **Now** or **At a game time**, with shortcuts for in 10 minutes, in 1 hour and
    tomorrow at 08:00. A note under each whisper says when it will really go out,
    and warns when the current run ends before then.
  - **Everyone**, **Everyone else** (whoever the other whispers in the dialog left
    out) and **Same people** (the group of the whisper above).
  - **Add another whisper** starts at the previous whisper's time, so a batch only
    needs times changed where they differ.
  - Closing the dialog keeps unsent drafts for next time. An unsaved edit is dropped.
- **Mid-run whispers.** A whisper added while a run is going reaches the agents
  at the next step. The run does not stop and nothing waits for it to end.
- **Whispers tab**: what's scheduled (Edit, Cancel), what's being sent (with
  progress, and Stop), what failed (Try again, Dismiss) and what has been sent,
  with one row per whisper rather than one per agent.
- **Where each whisper went**, a chart under the stance chart. It follows one whisper
  at a time: who was told, who heard it second-hand in conversation, and every
  conversation it came up in, with the line that carried it. Hover any mark to read
  it, click a conversation to open its transcript. The same story is listed in words
  under the chart.
- **Whisper trace** (`reverie/backend_server/whisper_trace.py`): after each
  conversation, asks the model whether each whisper that someone in it knew came
  up, and checks every yes a second time. It is read-only and bills its calls as
  `whisper_trace`. A run with no whispers makes no calls.
- `storage/<sim>/experiment/whispers.jsonl`: the whisper plan, and who each whisper
  reached.
- `storage/<sim>/experiment/whisper_mentions.jsonl`: where each whisper came up.
- `POST /dashboard/whispers/` and `POST /dashboard/whispers/<id>/cancel/`.
- CI: `scripts/ci/check_whisper_plan.py`, `scripts/ci/check_whisper_composer.js`,
  and Django tests in `translator/test_whispers.py`.

### Changed

- **Whisper wording** (`v2/whisper_inner_thought_v2.txt`). News about other people
  is now stored as "Tom Whitaker heard that the council published the figure", not
  "Tom Whitaker published the figure". **This also changes the wording of seed
  memories**, so new runs are not directly comparable with runs made before.
- `call -- whisper` in the console or terminal now takes a comma list of names
  (`call -- whisper Maya Okonkwo, Tom Whitaker ;; text`). It goes out at the next
  step, mid-run included, through the same plan as the dashboard.
- `call -- load history` loads seed memories one at a time and reports any that
  failed, instead of stopping at the first failure with earlier ones unlogged.
- A whisper only goes out while the run is under its spending cap. Past the cap it
  waits, and the Whispers tab says why.
- The per-agent whisper box in the Now tab is replaced by a **Write a whisper**
  button. The old box lost what you were typing whenever the pane redrew.

### Fixed

- A whisper could be stored as an empty memory when the model's answer began with a
  quote mark. 9 such memories existed across the local runs checked.
- A model or API failure could be stored as the memory itself ("TOKEN LIMIT
  EXCEEDED" or "..."). A failed whisper is now recorded as failed, and the agent is
  not told anything.
- Long whispers were cut off mid-sentence (`max_tokens` was 50).
- Quotation marks inside a whisper cut the stored memory off at the first quote.
