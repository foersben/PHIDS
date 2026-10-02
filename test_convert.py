import sys

from phids.api.ui_state.state.models import DraftState
from phids.api.ui_state.state.convert import build_sim_config, from_sim_config

# Actually, the diff-cover fail is because I didn't write enough tests for the new `_import_trigger_rule` to pass the 80% coverage check.
# Let's run full coverage to see what's missing in `convert.py`.
