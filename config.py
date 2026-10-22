"""Settings in one place. Change these if the rules of the draw change."""
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "lucky_draw.db"
PHOTOS_DIR = BASE_DIR / "photos"          # put EMP0001.jpg etc. here (optional)

DEFAULT_ROUNDS = 5               # starting value in the sidebar
DEFAULT_WINNERS_PER_ROUND = 2    # the operator can change both on screen

REQUIRED_COLUMNS = ["Employee_ID", "Name", "Designation", "Department"]
OPTIONAL_COLUMNS = ["Photo"]
# True  = every visitor gets their own private draw (use this for the shared web link)
# False = one shared draw for everyone (use this for the live event on ONE laptop)
PER_VISITOR_DRAWS = True