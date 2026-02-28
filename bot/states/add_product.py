"""FSM states for the /add product flow."""

from aiogram.fsm.state import State, StatesGroup


class AddProductStates(StatesGroup):
    """Multi-step states for adding a new product to the watchlist."""

    waiting_name = State()          # Waiting for product name
    waiting_link = State()          # Waiting for marketplace link
    waiting_more_links = State()    # Ask if user wants to add more links
    waiting_alert_type = State()    # Choose alert type(s)
    waiting_target_price = State()  # Input target price (for TARGET_PRICE rule)
