"""Where data and outputs live. docker/run.sh sets both; see README.md.

EXIMO_WORKSPACE  holds data/{raw,clean,processed} (the public downloads and their cleaned, resampled copies)
EXIMO_OUT        converted data (<out>/data) and everything trained or evaluated (<out>/results)
"""
import os

WS = os.environ.get("EXIMO_WORKSPACE", "/workspace")
OUT = os.environ.get("EXIMO_OUT", os.path.join(WS, "out"))
DATA = os.path.join(OUT, "data")
RESULTS = os.path.join(OUT, "results")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
