"""Make the repo importable for the test run without requiring an install (so a bare
``pytest`` from the repo root works); ``pip install -e .`` also works."""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, os.path.join(_ROOT, "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
