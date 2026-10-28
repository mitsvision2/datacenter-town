"""
Reads where each agent stands on the datacenter, on a 0-100 rubric, so the
dashboard can graph how those positions move over the run.

The probe is an observer, not a participant. It retrieves with touch=False and
writes nothing back, so asking an agent its position every game hour does not
change what that agent retrieves, plans or reflects on afterwards. Without
that, the probe would reset the recency clock on exactly the datacenter
memories it read, and the graph would be measuring its own interference.

Each reading also records the memories it was based on, which is what makes a
move in the line explainable. Results go to
storage/<sim>/experiment/opinions.jsonl (see experiment_logger.py).

The evidence a reading is built from comes from two sources, ranked
separately and merged in time order:

  memories       seq_event and seq_thought, ranked by new_retrieve's
                 composite of recency, relevance and importance, then
                 deduplicated by collapse() and cut to those close enough to
                 the question to be evidence about it.
  spoken lines   RESERVED_N slots for what the agent actually said, ranked by
                 relevance alone (rank_utterances), read straight off the
                 chat nodes because seq_chat is not in new_retrieve's pool.

The second source exists because the first one has the positions stripped out
of it. Measured over a full game day, 0.6% of pool events and 3.2% of pool
thoughts contain any verb of position, against 33% of the agent's own spoken
lines: a summary records that a conversation happened and what it covered,
not what anyone in it wanted. Rating on summaries alone converted being busy
with the datacenter into being in favour of it -- Maya Okonkwo, quoted
pushing the thing for the sake of her funding round, reads 40 on her
summaries and 85 once her own words are in front of the model, and Elena
Chen, who is paid to analyse the load and wants nothing either way, reads 85
on her summaries and 40 on her words.

Three reasons a reading is deliberately withheld rather than guessed at, all
measured on a full game day of eight agents (192 readings):

  asleep         64 of them, 33%, were taken of agents who were in bed. A
                 sleeping agent learns nothing about the datacenter, so those
                 hours can only repeat the last real reading or wander; five of
                 41 consecutive asleep-to-asleep pairs moved by ten points or
                 more, one agent going 50, 70, 50, 70 without waking.
  low relevance  the probe abstained at a mean relevance of 0.39 and scored at
                 a mean of 0.60. Below the floor the same evidence came back
                 as "none" on one hour and 70 on the next -- Marcus Williams at
                 0.333 did exactly that six times against three.
  no memory      an agent that has not stepped has nothing to read.

A withheld reading is logged with a null score and a reason, not dropped. The
chart lifts the pen on a null (dashboard.html), so a gap is visible as a gap
instead of being interpolated through.
"""
import re

from persona.cognitive_modules.retrieve import (
  cos_sim, extract_relevance, new_retrieve)
from persona.prompt_template.gpt_structure import get_embedding
from persona.prompt_template.run_gpt_prompt import (
  STANCE_QUESTION, STANCE_SCALE, STANCE_SCORING_VERSION,
  run_gpt_prompt_datacenter_stance)

# Memories each rating is based on, the same number a normal retrieval uses.
EVIDENCE_N = 30
# Retrieval is asked for more than that because collapse() throws repeats away
# and the prompt should still arrive with EVIDENCE_N distinct statements in it.
# Three times over was enough on every reading of the measured run.
RETRIEVE_N = EVIDENCE_N * 3
# How many of the EVIDENCE_N slots are held for the agent's own spoken lines.
# They have to be reserved rather than won: see rank_utterances for why these
# lines lose a shared ranking every time.
RESERVED_N = 10

# Raw cosine, below which the model's answer stopped depending on the evidence.
# See the module docstring: 0.39 mean when abstaining against 0.59 when
# scoring, so the two populations separate cleanly either side of this.
RELEVANCE_FLOOR = 0.45

# perceive.py writes one event per perception tick for a conversation that is
# still going, and both participants perceive both sides of it, so a single
# chat arrives as a dozen near-identical lines that differ only in who the
# subject is. In the measured run these filled a mean of 19% of the prompt and
# a maximum of 80% of it, and they carry a summary rather than anything that
# was said -- the probe could see that an agent kept talking to opponents but
# never what any of them argued.
_CONVERSING = re.compile(r"^.*? is conversing about ", re.I)


def canonical(embedding_key):
  """The part of a statement that carries information, lowercased.

  Strips the "<someone> is conversing about " opener so that the same
  conversation seen from either side, and at every tick it ran for, collapses
  onto one entry.
  """
  return _CONVERSING.sub("", embedding_key or "").strip().lower()


def collapse(nodes):
  """Drops repeats of a statement the prompt already carries, keeping the
  first -- which, on retrieval's output, is the best-ranked one.

  Exact canonical matches only. Paraphrases that are merely similar are left
  in: deciding that two differently-worded thoughts say the same thing is a
  judgement the probe should not be making silently on the evidence it then
  rates.
  """
  seen, kept = set(), []
  for node in nodes:
    key = canonical(node.embedding_key)
    if key in seen:
      continue
    seen.add(key)
    kept += [node]
  return kept


def is_asleep(persona):
  """Whether the agent is in bed at the moment of the probe.

  Reads the current action rather than the clock, because agents keep their own
  schedules and revise_identity rewrites them nightly -- there is no hour of
  the day at which the whole cast is reliably asleep or reliably up.
  """
  return "sleep" in (persona.scratch.act_description or "").lower()


_EMBEDDINGS = {}


def embed(text):
  """get_embedding with an in-process cache, keyed by the text itself.

  Deliberately not cached into persona.a_mem.embeddings, which is where the
  simulation keeps its own: that dict is written out with the agent, so
  putting the probe's embeddings in it would make the observer mutate the
  state it is observing -- the same invariant touch=False protects. The cost
  of keeping it in memory instead is re-embedding once per process, a few
  hundred short strings for a game day of eight agents.
  """
  if text not in _EMBEDDINGS:
    _EMBEDDINGS[text] = get_embedding(text)
  return _EMBEDDINGS[text]


def own_utterances(persona):
  """What this agent actually said in its conversations, newest first.

  Chat nodes carry the whole exchange in <filling>, as [speaker, line] pairs,
  and seq_chat is not in new_retrieve's candidate pool (retrieve.py:232) --
  Stanford left a note on the line above it that the raw conversation could
  be retrieved too, "but for now". So these lines are unreachable by normal
  retrieval, and the probe reads them itself rather than widening the pool:
  widening it would change what every agent retrieves while planning and
  reflecting, which is a change to the simulation and not to the observer.

  This matters because the pool the probe can otherwise see has had the
  positions stripped out of it. Measured over a full game day, 0.6% of pool
  events and 3.2% of pool thoughts contain any verb of position, against
  33% of the agent's own spoken lines: the summaries record that a
  conversation happened and what it covered, not what anyone wanted.

  Only this agent's own turns. What was said to them is already in the pool
  as a perceived event, and taking both sides would double the tokens to
  re-import the near-duplicate problem collapse() exists to remove.

  Returns [(created, line)], deduplicated by line. <created> is the parent
  chat node's timestamp, so every turn of one conversation shares it -- the
  resolution here is per conversation, not per turn.
  """
  seen, out = set(), []
  for node in persona.a_mem.seq_chat:
    for turn in node.filling or []:
      if not isinstance(turn, (list, tuple)) or len(turn) != 2:
        continue
      speaker, line = turn
      line = (line or "").strip()
      if speaker != persona.scratch.name or not line:
        continue
      if line.lower() in seen:
        continue
      seen.add(line.lower())
      out += [(node.created, line)]
  return out


def rank_utterances(utterances, n):
  """The n spoken lines closest to the stance question, by raw cosine.

  Relevance alone, where new_retrieve also uses recency and importance, for
  two reasons. There is no per-line recency or importance to use: both would
  have to be inherited from the parent chat node, which is one value for
  every turn of a conversation and so cannot order them. And because these
  lines hold reserved slots rather than competing for ranked ones, there is
  nothing for a second component to trade off against.

  Raw cosine, not new_retrieve's normalized score, because the absolute
  values are the finding. Measured over a game day, own utterances score a
  median 0.24 against the stance question where the statements already in the
  prompt score 0.51 -- the pool's statements are model-written summaries in
  the same register as the question, while an utterance is conversational and
  spends most of its tokens on greeting and hedging. Only 61 of 431
  utterances outscored the weakest statement already in the prompt, and for
  one agent none of 97 did. In a shared ranking these lines lose every slot,
  every time, which is why they get reserved ones instead.

  Cosine is no judge of whether a line states a position: 35% of the top ten
  do, against a 33% base rate, which is chance. It is a good judge of whether
  the line is about the datacenter at all -- 78% of the top ten, against 29%
  across all utterances, 34% for the most recent ten and 26% for a random
  ten. Topicality is the job being asked of it. The position density comes
  from the base rate, which is fifty times the pool's.

  Ranking by relevance and not recency is also what keeps a trajectory
  readable. Recency as a decaying weight tracks what the agent last thought
  about, so an agent who argued a position and then got busy would have its
  evidence fade and its line drift toward the middle -- reporting a drop in
  attention as a change of mind. Over a long run the risk runs the other way,
  the top n collapsing onto whichever week the agent talked about this most,
  so probe() records the time span these lines were drawn from.
  """
  question = embed(STANCE_QUESTION)
  ranked = sorted(((cos_sim(embed(line), question), created, line)
                   for created, line in utterances),
                  key=lambda row: row[0], reverse=True)
  return [(created, line) for _, created, line in ranked[:n]]


def pool_relevance(persona):
  """Raw cosine from every retrievable memory to the stance question.

  new_retrieve min-max normalizes relevance within each call
  (retrieve.py:244), so whichever node it ranks first scores 1.0 whether its
  true similarity was 0.8 or 0.1. There is no absolute floor anywhere in the
  ranking, and the rescaled score cannot supply one because it is relative to
  whatever candidates happened to exist. extract_relevance returns the raw
  cosines, from before that rescaling.

  Same node set and same focal point as the probe's retrieval, so these are
  the cosines that ranking was built from. {} when the agent has no memory.
  """
  nodes = [n for n in persona.a_mem.seq_event + persona.a_mem.seq_thought
           if "idle" not in n.embedding_key]
  return extract_relevance(persona, nodes, STANCE_QUESTION) if nodes else {}


def measure_relevance(raw, retrieved):
  """How close the prompt's memories actually are to the stance question.

  Takes pool_relevance's raw cosines and the nodes the prompt ended up with.

  Returns {"shown", "best"}: the closest memory the model was actually given,
  and the closest one in the whole memory stream. "shown" is what says whether
  a reading had anything to work from at all, and is what RELEVANCE_FLOOR is
  applied to. The gap between the two says whether a relevant memory existed
  and lost its place in the top EVIDENCE_N to recency and importance, which are
  weighted equally with relevance (gw = [1, 1, 1]). On the measured run that
  gap was 0.0000 for five of eight agents and never above 0.15, so nothing
  relevant is being crowded out at EVIDENCE_N = 30.
  """
  if not raw:
    return {"shown": None, "best": None}
  shown = [raw[node.node_id] for node in retrieved if node.node_id in raw]
  # cos_sim hands back numpy floats, which land in the log file as whatever
  # json.dumps makes of them.
  return {"shown": float(max(shown)) if shown else None,
          "best": float(max(raw.values()))}


def quoted_span(quoted):
  """The window the quoted lines were drawn from, for the log.

  Instrumentation, not a gate. Ranking spoken lines by relevance alone is
  safe while a run is short -- measured over one game day the top ten spanned
  very nearly the full waking range for every agent -- but the top n of a
  year's conversations would be drawn from whichever week the agent argued
  about this most, and the reading would then be of a position it had since
  moved off. Two agents already tilt early, 2 of 10 and 1 of 10 in the later
  half of their day, so the failure mode is visible rather than theoretical.
  Recording the span means a multi-day run shows it collapsing instead of
  having to be guessed at.
  """
  if not quoted:
    return {"n": 0, "first": None, "last": None}
  created = sorted(created for created, _ in quoted)
  return {"n": len(quoted),
          "first": created[0].strftime("%Y-%m-%d %H:%M:%S"),
          "last": created[-1].strftime("%Y-%m-%d %H:%M:%S")}


def probe(persona, with_metadata=False):
  """Reads one persona's position on the datacenter.

  Returns (score, rationale, evidence, relevance, withheld, quoted). <score>
  is 0 to STANCE_SCALE, or None when the reading was withheld or the model
  gave no usable rating; <evidence> is the node ids the rating was based on;
  <relevance> is measure_relevance's reading of how much those nodes had to do
  with the question; <withheld> names the reason a null score is null, or is
  None when the model was actually asked; and <quoted> is quoted_span's record
  of the spoken lines that went in beside the memories.

  The evidence block is built from two sources that are ranked separately and
  then merged in time order: the retrievable memories, ranked by
  new_retrieve's composite score, and the agent's own spoken lines, ranked by
  relevance alone (see rank_utterances for why they cannot share one
  ranking). RESERVED_N slots go to the spoken lines when there are that many,
  and the reservation is a ceiling rather than a quota -- an agent who has
  said less gives the unused slots back to the memories, and early in a run,
  before anyone has spoken, the prompt is exactly what it was before.
  """
  def result(score, rationale, evidence, relevance, withheld, quoted,
             category=None, conditions=None):
    if with_metadata:
      return {"score": score, "rationale": rationale, "evidence": evidence,
              "relevance": relevance, "withheld": withheld, "quoted": quoted,
              "category": category, "conditions": conditions or [],
              "scoring_version": STANCE_SCORING_VERSION}
    return score, rationale, evidence, relevance, withheld, quoted

  if is_asleep(persona):
    # Before retrieval, which embeds the question and so costs a call.
    return result(None, f"{persona.scratch.name} is asleep.", [],
            {"shown": None, "best": None}, "asleep", quoted_span([]))

  if not any("idle" not in node.embedding_key
             for node in persona.a_mem.seq_event + persona.a_mem.seq_thought):
    return result(None, "No retrievable memories yet.", [],
                  {"shown": None, "best": None}, "no_memory", quoted_span([]))

  quoted = rank_utterances(own_utterances(persona), RESERVED_N)

  retrieved = new_retrieve(persona, [STANCE_QUESTION], RETRIEVE_N,
                           touch=False)[STANCE_QUESTION]
  raw = pool_relevance(persona)
  # A statement that is not close enough to the datacenter is not evidence
  # about the datacenter, and until now only the closest one in the prompt was
  # ever tested: the floor below decided whether to ask at all and then every
  # statement went in regardless of its own cosine. Measured over the last
  # eight prompts of a game day, 35% of the 240 statements sat below the floor
  # and 14% below 0.35 -- 27 of Luis Hernandez's 30, and 21 of Rachel Nguyen's
  # with one at 0.108. Dropping them can leave a prompt short of EVIDENCE_N,
  # which is the honest outcome: there were not that many relevant memories.
  # The gate is unchanged by this, because at least one statement survives
  # exactly when the old max-based test passed.
  retrieved = [node for node in collapse(retrieved)
               if raw.get(node.node_id, 0.0) >= RELEVANCE_FLOOR]
  retrieved = retrieved[:EVIDENCE_N - len(quoted)]
  evidence = [node.node_id for node in retrieved]
  relevance = measure_relevance(raw, retrieved)

  shown = relevance["shown"]
  if shown is None:
    # Asking anyway produces a number, and that number is the prompt's opinion
    # of the name rather than the agent's opinion of the datacenter. Spoken
    # lines are not allowed to lift this gate even when there are ten of them:
    # they sit at a median cosine of 0.24, so RELEVANCE_FLOOR cannot be
    # applied to them, and no separate floor for them has been measured yet.
    best = relevance["best"]
    return result(None, f"Nothing in {persona.scratch.name}'s memory is close "
            f"enough to the datacenter to rate"
            f"{'' if best is None else f' (relevance {best:.2f})'}.",
            evidence, relevance, "low_relevance", quoted_span(quoted))

  # Oldest first, each line dated, memories and spoken lines interleaved.
  # Retrieval returns these ranked by score, and a shuffled undated list is
  # unreadable as a trajectory: the model cannot tell what this agent thought
  # an hour ago from what it thought yesterday, which is the one distinction
  # the graph exists to show. Spoken lines are marked as spoken so the prompt
  # can tell the model to weigh this person's own words above a summary of a
  # conversation they were in.
  lines = [(node.created, node.embedding_key) for node in retrieved]
  lines += [(created, f'{persona.scratch.name} said: "{line}"')
            for created, line in quoted]
  statements = "\n".join(
    f'{created.strftime("%B %d, %H:%M")} -- {text}'
    for created, text in sorted(lines, key=lambda row: row[0]))
  rating = run_gpt_prompt_datacenter_stance(
    persona, statements, with_metadata=True)[0]
  return result(rating["score"], rating["rationale"], evidence, relevance,
                rating["withheld"], quoted_span(quoted), rating["category"],
                rating["conditions"])
