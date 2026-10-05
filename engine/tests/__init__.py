"""Test package. Discovery works both as `python -m unittest discover -s engine/tests`
and `python -m unittest discover -s engine/tests -t tools` (run from dnd-adventure/):
the test modules import `fixture`, `lib` and the command modules by bare name, so
engine/tests and engine/ go on sys.path here."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
