from phids.api.ui_state.state.models import DraftState
from phids.api.ui_state.state.convert import build_sim_config, from_sim_config

draft = DraftState.default()
config = build_sim_config(draft)
print("Config built.")
new_draft = from_sim_config(config)
print("Draft reconstructed from config.")
