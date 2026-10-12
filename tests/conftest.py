"""Shared test configuration.

Hypothesis runs 200 examples per property locally and 1000 in CI (HYPOTHESIS_PROFILE=ci),
as docs/TESTING.md section 1 asks. Deadlines are off: CI machines vary in speed and a slow
example is not a wrong one.
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

settings.register_profile("dev", max_examples=200, deadline=None)
settings.register_profile(
    "ci", max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
