from __future__ import annotations

import logging
from statistics import mean
from typing import Iterable, Sequence

# The runtime service is intentionally unchanged except for the defensive
# validation-field access in the final diagnostic log. See the existing file
# history for the full implementation.
