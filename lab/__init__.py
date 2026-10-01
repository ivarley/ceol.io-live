"""Ceol Listen lab (spec 053).

An offline environment for building a tune recogniser as an ensemble of small
experts over a shared blackboard, with a replay harness that scores runs against
the human-segmented corpus from spec 050, and a task bench for scoring ideas
before they become experts.

Not deployed. Own dependencies (lab/requirements.txt), own tests
(lab/pytest.ini, `make lab-test`). Entry point: `venv/bin/python -m lab`.
"""

LAB_VERSION = "0.1"
