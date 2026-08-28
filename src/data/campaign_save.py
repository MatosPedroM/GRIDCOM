"""
src/data/campaign_save.py

Campaign-level player save state — persists across the whole campaign,
not a single shift. Currently covers: difficulty, per-shift grades, and
the persistent campaign budget (EUR). Written at every debrief dismissal
and read back at campaign start (new or continued).

live_state is reserved for a future mid-shift resume feature (saving
inside a real-time PLAYING session, or in Continuous mode) — always None
today. Reserving the field now means that follow-up can land without a
breaking version bump to this schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

from config.constants import CAMPAIGN_STARTING_BUDGET_EUR
from utils.save_paths import campaign_save_path


@dataclass
class CampaignSaveState:
    version: int = 1
    difficulty: str = 'standard'
    shift_grades: dict[int, str] = field(default_factory=dict)
    budget_eur: float = CAMPAIGN_STARTING_BUDGET_EUR
    campaign_start_time_iso: str = ''
    live_state: dict | None = None


def save_campaign(state: CampaignSaveState, slot: int = 0) -> None:
    """Serialise a CampaignSaveState to campaign_save_{slot}.json."""
    path = campaign_save_path(slot)
    data = asdict(state)
    data['shift_grades'] = {str(k): v for k, v in state.shift_grades.items()}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_campaign(slot: int = 0) -> CampaignSaveState:
    """Read back campaign_save_{slot}.json. Raises FileNotFoundError if absent."""
    path = campaign_save_path(slot)
    if not path.exists():
        raise FileNotFoundError(f'No campaign save in slot {slot} — expected {path}')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data['shift_grades'] = {int(k): v for k, v in data.get('shift_grades', {}).items()}
    return CampaignSaveState(**data)


def has_campaign_save(slot: int = 0) -> bool:
    """True if a campaign save exists in the given slot."""
    return campaign_save_path(slot).exists()
