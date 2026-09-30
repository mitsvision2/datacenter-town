"""
Staging vs production runs, chosen by run_env in utils.py.

staging: every chat call uses staging_chat_model (default gpt-4o-mini), a
  run gets a spending cap of staging_budget_usd when none is set, and new
  run names start with "stg-". For trying code cheaply: a different model
  behaves differently, so staging results aren't comparable with
  production runs.
production: the models and settings in utils.py as they are.
"""
import utils

RUN_ENV = getattr(utils, "run_env", "production")
if RUN_ENV not in ("staging", "production"):
  raise ValueError(f'run_env in utils.py must be "staging" or "production", '
                   f'not {RUN_ENV!r}')
STAGING = RUN_ENV == "staging"
STAGING_CHAT_MODEL = getattr(utils, "staging_chat_model", "gpt-4o-mini")
STAGING_BUDGET_USD = getattr(utils, "staging_budget_usd", 1.00)
STAGING_PREFIX = "stg-"


def chat_model(requested):
  """The model a chat call actually uses."""
  return STAGING_CHAT_MODEL if STAGING else requested


def run_name(name):
  """Staging runs are named stg-<name>, so they're easy to tell apart."""
  if STAGING and not name.startswith(STAGING_PREFIX):
    return STAGING_PREFIX + name
  return name
