"""
map.py - Level layout definitions, room metadata and convenient re-exports.
Provides room boundaries and helper utilities for team members (UI, AI, Audio).
"""

from level import Level, GameRoom, InteractiveDoor

# Room definitions with boundaries (for UI room banners, ambient sound triggers, or monster AI)
ROOMS = {
    "bedroom": {
        "name": "Bedroom",
        "bounds": (160, 96, 320, 288),
        "description": "A dark, chilly bedroom with a messy bed and a wardrobe."
    },
    "bathroom": {
        "name": "Bathroom",
        "bounds": (480, 96, 264, 288),
        "description": "Cold white tiles, a porcelain bathtub and a fogged mirror."
    },
    "kitchen": {
        "name": "Kitchen & Dining",
        "bounds": (744, 96, 576, 288),
        "description": "Terracotta floors, humming refrigerator, and a dining table."
    },
    "corridor": {
        "name": "Central Hallway",
        "bounds": (160, 384, 1160, 96),
        "description": "The narrow, dimly lit central hallway connecting the rooms."
    },
    "storage": {
        "name": "Storage Room",
        "bounds": (160, 480, 390, 276),
        "description": "Compact utility room with wooden planks, sheeted crates, and tools."
    },
    "foyer": {
        "name": "Entry Vestibule",
        "bounds": (550, 480, 180, 400),
        "description": "Narrow entry hall leading down to the heavy locked security exit door."
    },
    "living": {
        "name": "Living Room & Study",
        "bounds": (730, 480, 590, 360),
        "description": "Herringbone parquet floor, bookshelves, sofa and an eerie portrait."
    }
}

def get_room_at(x, y):
    """Returns the room key for a given (x, y) world position."""
    for room_id, info in ROOMS.items():
        rx, ry, rw, rh = info["bounds"]
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            return room_id
    return "corridor"
