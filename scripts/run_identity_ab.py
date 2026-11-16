"""Runs one headless day-and-a-bit of the 8-resident town for the identity A/B.

Run from reverie/backend_server, because that is where utils.py and the relative
storage paths resolve from:

  cd reverie/backend_server
  python3 ../../scripts/run_identity_ab.py <v1|v2> <name> <steps>

The A/B used 10440 steps: 07:00 on day 1 to 12:00 on day 2, which crosses
midnight once, where revise_identity rewrites every resident's identity. The run
starts from base_the_ville_datacenter_n8, seeds the residents' histories, runs
<steps> steps and saves. It is named stg-<name> (run_env staging), writes its log
to logs/<name>/, and keeps its dashboard files under
temp_storage/dashboard/runs/<name>, so any number of runs can go at once from one
checkout without racing on temp_storage/dashboard/state.json.

  v1  revise_identity exactly as it is in plan.py.
  v2  the same prompt with one sentence added telling the model to keep the
      resident's standing views unless the thoughts show they changed their mind
      (the wording scripts/test_revise_identity.py tests). Applied by wrapping
      ChatGPT_single_request here, so plan.py is not changed.

The script also guards one crash that is not about either prompt. A resident who
has only seen a building from outside knows no rooms in it, so the room prompt is
empty, the model answers "}" and the parsed room is "". The step then dies with a
KeyError in execute.py (address "the Ville:<sector>:" is not on the map). When the
room comes back empty the guard picks a shared room that exists on the map. It was
added after ab-v2-1 crashed this way at step 4554, so the first five runs of the A/B
did not have it; it only changes a step that would otherwise crash.

Runs are headless and read no commands: the history load, the run and the save
are queued from here.
"""
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "reverie", "backend_server"))
sys.stdin = open(os.devnull)

import utils  # noqa: E402

VARIANT, NAME, STEPS = sys.argv[1], sys.argv[2], int(sys.argv[3])
utils.log_dir = f"logs/{NAME}"
utils.fs_temp_storage = f"{utils.fs_temp_storage}/dashboard/runs/{NAME}"
os.makedirs(f"{utils.fs_temp_storage}/dashboard", exist_ok=True)

import run_env  # noqa: E402
from reverie import ReverieServer  # noqa: E402
from persona.cognitive_modules import plan  # noqa: E402

if VARIANT == "v2":
  TAG = "Follow this format below:\nStatus: <new status>"
  KEEP = ("If yesterday's status states a position or concern (for example that "
          "{n} supports, opposes or is undecided about something), say it again "
          "in today's status, unless the thoughts above show {n} has changed "
          "their mind. Then add what {n} plans to do today.\n\n")
  original = plan.ChatGPT_single_request

  def single(prompt):
    name = re.match(r"(.+?)'s status from ", prompt)
    if TAG in prompt and name:
      prompt = prompt.replace(TAG, KEEP.format(n=name.group(1)) + TAG)
    return original(prompt)

  plan.ChatGPT_single_request = single
elif VARIANT != "v1":
  raise SystemExit("variant must be v1 or v2")

original_arena = plan.run_gpt_prompt_action_arena


def arena(act_desp, persona, maze, act_world, act_sector):
  out = original_arena(act_desp, persona, maze, act_world, act_sector)
  if out[0]:
    return out
  prefix = f"{act_world}:{act_sector}:"
  rooms = sorted({k[len(prefix):].split(":")[0] for k in maze.address_tiles
                  if k.startswith(prefix)})
  shared = [r for r in rooms if r and "'s room" not in r and "bathroom" not in r]
  return ((shared or rooms or [""])[0], out[1])


plan.run_gpt_prompt_action_arena = arena

rs = ReverieServer("base_the_ville_datacenter_n8", run_env.run_name(NAME))
rs.curr_time = rs.curr_time.replace(hour=7, minute=0)
rs.open_server(initial_commands=[
  "call -- load history the_ville/agent_history_init_datacenter_n8.csv",
  f"run {STEPS}",
  "fin",
])
