
# from .messages import (ADMIN_HELP_MESSAGE,
#                        HELP_GROUP_CHAT_MESSAGE,
#                        HELP_MESSAGE,
#                        ADMIN_MENU_TEXT,
#                        MENU_TEXT, ADMIN_RATE_TEXT)
from .messages import *
from .general import get_rate_data, is_previous_message_not_answered_yet
from .stats import Statistics

from .admin_utils import *
from .user_utils import *
from .phone_utils import *

Stats = Statistics()

