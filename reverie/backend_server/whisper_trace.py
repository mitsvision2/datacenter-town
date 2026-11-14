"""
Follows a whisper into the conversations that came after it: who brought it up,
to whom, and what they did with it. The dashboard's whisper chart reads this.

An observer, like the stance probe. It reads finished transcripts and the whisper
plan, and never touches an agent's memory, so tracing a run doesn't change it.

Results go to storage/<sim>/experiment/whisper_mentions.jsonl, one row for each
conversation that had someone in it who knew a whisper:

  {"step", "time", "speakers",
   "checked": [ids the judge answered for],
   "failed": [ids it gave no valid answer for],
   "mentions": [{"whisper_id", "speaker", "quote", "how", "new_hearers"}]}

Someone who hears a whisper in conversation counts as knowing it from then on, so
it can be followed as it passes from person to person. A conversation nobody in it
knew about costs nothing: a run with no whispers makes no calls at all.

Measured on gpt-4o-mini over 340 pairs from two runs' real transcripts: 17 of the
18 it flagged were right and it found 17 of the 20 real ones. Those runs were also
used to tune it, so read that as a best case. On 62 checks from a run with whispers
it flagged nothing, correctly, so how often it finds a real one in use is not yet
measured. A mention is good evidence, not proof, which is why the row keeps the line
it relied on, read from the transcript rather than from the model, for anyone to
check. It shows where a whisper came up. It can't show that it changed anyone's mind.
"""
import os

import whisper_plan


def path_for(sim_folder):
  return os.path.join(sim_folder, "experiment", "whisper_mentions.jsonl")


class WhisperTrace:
  def __init__(self, sim_folder, plan):
    self.path = path_for(sim_folder)
    self.plan = plan
    self._size = None
    self._heard = {}

  def forget_unsaved(self, step):
    """A fork starts from saved memory at <step>, so a conversation from that step
    on never happened to its agents, and can't have told them anything."""
    rows = whisper_plan.read(self.path)
    keep = [row for row in rows if row.get("step", 0) < step]
    if len(keep) != len(rows):
      whisper_plan.rewrite(self.path, keep)

  def _heard_in_conversation(self):
    """Who heard each whisper in conversation. Read again only when the file grows."""
    size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
    if size != self._size:
      self._heard = {}
      for row in whisper_plan.read(self.path):
        for mention in row.get("mentions") or []:
          self._heard.setdefault(mention["whisper_id"], set()).update(mention["new_hearers"])
      self._size = size
    return self._heard

  def check(self, conversation, judge):
    """Asks <judge> about each whisper someone in the conversation knew. <judge>
    takes (text, transcript, n_lines) and returns the parsed answer, or None when
    it has no valid one, which is recorded as unchecked and not as "no"."""
    speakers = conversation.get("speakers") or []
    turns = conversation.get("utterances") or []
    if not turns:
      return None
    heard = self._heard_in_conversation()
    known = []
    for whisper in self.plan.whispers():
      holders = set(whisper["received"]) | heard.get(whisper["id"], set())
      if holders & set(speakers):
        known.append((whisper, holders))
    if not known:
      return None

    # One line per turn: the judge's line numbers index into this.
    transcript = "\n".join(f"{i + 1}. {turn[0]}: {' '.join(str(turn[1]).split())}"
                           for i, turn in enumerate(turns))
    row = {"step": conversation.get("step"), "time": conversation.get("time"),
           "speakers": speakers, "checked": [], "failed": [], "mentions": []}
    for whisper, holders in known:
      answer = judge(whisper["text"], transcript, len(turns))
      if answer is None:
        row["failed"].append(whisper["id"])
        continue
      row["checked"].append(whisper["id"])
      if answer["came_up"]:
        speaker, quote = turns[answer["line"] - 1]
        row["mentions"].append({
          "whisper_id": whisper["id"], "speaker": speaker, "quote": quote,
          "how": answer["how"],
          "new_hearers": [name for name in speakers if name not in holders]})
    whisper_plan.append(self.path, [row])
    return row
