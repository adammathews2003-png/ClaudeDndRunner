"""Test package. Discovery works both as `python -m unittest discover -s tools/tests`
and `python -m unittest discover -s tools/tests -t tools` (run from dnd-adventure/):
the test modules import `fixture`, `lib` and the command modules by bare name, so
tools/tests and tools/ go on sys.path here."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
