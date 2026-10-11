"""
Reads where each agent stands on the datacenter, on a 1-100 scale, so the
dashboard can graph how those positions move over the run.

The probe is an observer, not a participant. It retrieves with touch=False and
writes nothing back, so asking an agent its position every game hour does not
change what that agent retrieves, plans or reflects on afterwards. Without
that, the probe would reset the recency clock on exactly the datacenter
memories it read, and the graph would be measuring its own interference.

Each reading also records the memories it was based on, which is what makes a
move in the line explainable. Results go to
storage/<sim>/experiment/opinions.jsonl (see experiment_logger.py).
"""
from persona.cognitive_modules.retrieve import new_retrieve
from persona.prompt_template.run_gpt_prompt import (
  STANCE_QUESTION, STANCE_SCALE, run_gpt_prompt_datacenter_stance)

# Memories each rating is based on, the same number a normal retrieval uses.
EVIDENCE_N = 30


def probe(persona):
  """Reads one persona's position on the datacenter.

  Returns (score, rationale, evidence) where score is 1 to STANCE_SCALE, or
  None when the model gave no usable rating, and evidence is the node ids the
  rating was based on.
  """
  retrieved = new_retrieve(persona, [STANCE_QUESTION], EVIDENCE_N,
                           touch=False)[STANCE_QUESTION]
  # Oldest first, each line dated. Retrieval returns these ranked by score, and
  # a shuffled undated list is unreadable as a trajectory: the model cannot tell
  # what this agent thought an hour ago from what it thought yesterday, which is
  # the one distinction the graph exists to show.
  retrieved = sorted(retrieved, key=lambda node: node.created)
  statements = "\n".join(
    f'{node.created.strftime("%B %d, %H:%M")} -- {node.embedding_key}'
    for node in retrieved)
  score, rationale = run_gpt_prompt_datacenter_stance(persona, statements)[0]
  return score, rationale, [node.node_id for node in retrieved]
