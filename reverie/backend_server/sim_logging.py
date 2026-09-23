"""
Shared runtime logging for datacenter-town.

Configure via utils.py:
  log_level = "INFO"          # DEBUG | INFO | WARNING | ERROR
  log_to_file = True
  log_dir = "logs"            # relative to backend_server cwd, or absolute

Usage:
  from sim_logging import get_logger
  log = get_logger("reverie")
  log.info("step started", extra={...})  # or plain: log.info("step %s", step)
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_CONFIGURED = False


def _resolve_level():
  try:
    from utils import log_level
    name = str(log_level).upper()
  except Exception:
    name = "INFO"
  return getattr(logging, name, logging.INFO)


def _resolve_log_dir():
  try:
    from utils import log_dir
    path = log_dir
  except Exception:
    path = "logs"
  if not os.path.isabs(path):
    # Prefer backend_server/logs when running from that cwd.
    path = os.path.abspath(path)
  return path


def _want_file():
  try:
    from utils import log_to_file
    return bool(log_to_file)
  except Exception:
    return True


def setup_logging(force=False):
  """Idempotent root logger setup for console (+ optional rotating file)."""
  global _CONFIGURED
  if _CONFIGURED and not force:
    return
  level = _resolve_level()
  root = logging.getLogger()
  root.setLevel(level)

  # Avoid duplicate handlers on reload.
  for h in list(root.handlers):
    root.removeHandler(h)

  fmt = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
  )

  console = logging.StreamHandler(sys.stdout)
  console.setLevel(level)
  console.setFormatter(fmt)
  root.addHandler(console)

  if _want_file():
    log_dir = _resolve_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, "datacenter-town.log")
    fh = RotatingFileHandler(
      file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    root.info("Logging to file: %s (level=%s)", file_path, logging.getLevelName(level))

  _CONFIGURED = True


def get_logger(name="datacenter-town"):
  setup_logging()
  return logging.getLogger(name)
