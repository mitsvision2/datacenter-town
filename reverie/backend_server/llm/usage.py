"""
Per-call API usage log, one JSON line per request, read by the web dashboard
to show calls, tokens and estimated cost. Prices live on the dashboard side
(environment/frontend_server/translator/dashboard.py) so a price correction
re-costs every past call.

The simulation sets `context` so each call is attributed to the run, agent
and step it was made for.
"""
import json
import os
import threading
import time

USAGE_FILE = os.path.join(
  os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
  "logs", "api_usage.jsonl")

# sim: run folder name. persona: agent whose turn it is (None outside steps).
# source: "step" during runs, else the command that triggered the call.
context = {"sim": None, "persona": None, "source": None, "step": None}
_lock = threading.Lock()


def record(kind, provider, model, input_tokens=0, output_tokens=0,
           cached_tokens=0, secs=0.0, ok=True, error=None):
  row = {"ts": round(time.time(), 3), "kind": kind, "provider": provider,
         "model": model, "in": input_tokens or 0, "out": output_tokens or 0,
         "cached": cached_tokens or 0, "secs": round(secs, 2), "ok": ok}
  row.update(context)
  if error is not None:
    row["error"] = f"{type(error).__name__}: {error}"[:300]
    row["status"] = getattr(error, "status_code", None)
  try:
    with _lock:
      os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
      with open(USAGE_FILE, "a") as f:
        f.write(json.dumps(row) + "\n")
  except OSError:
    pass  # usage tracking must never break a simulation step
