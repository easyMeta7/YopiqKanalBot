"""
Trading Journal - Shared State Manager for Bot Handlers
"""
from typing import Dict, Any

# Registration flows
pending_register: Dict[int, Dict[str, Any]] = {}     # user_id -> {"stage": ..., "home": ..., "channel_id": ..., "title": ...}
pending_contact: Dict[int, Dict[str, Any]] = {}      # user_id -> {"stage": ..., "channel_id": ..., "channel_title": ...}
onboarding: Dict[int, Dict[str, Any]] = {}           # user_id -> {"stage": ..., "name": ...}

# UI and Navigation
reply_menu_states: Dict[int, Dict[str, Any]] = {}    # chat_id -> {"screen": ..., "choices": ..., "rows": ...}

# Channel health cache
channel_health: Dict[int, tuple] = {}                # channel_id -> (timestamp, is_alive)
