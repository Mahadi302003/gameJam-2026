"""
================================================================================
test_sounds.py  —  DON'T LOOK AWAY  |  Sound Tester
================================================================================
Run this AFTER generate_assets.py to hear every sound effect.

    python3 test_sounds.py

Controls:
    1–9, 0, -, =   Play a specific sound
    SPACE           Play next sound in list
    R               Replay the last sound
    ESC / Q         Quit

No game logic — just audio preview.
================================================================================
"""

import math
import os
import sys
import time
import pygame

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

SCREEN_W, SCREEN_H = 640, 480
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("DON'T LOOK AWAY — Sound Tester")
clock = pygame.time.Clock()

# Fonts
font_big  = pygame.font.SysFont("couriernew", 26, bold=True)
font_med  = pygame.font.SysFont("couriernew", 18, bold=True)
font_sm   = pygame.font.SysFont("couriernew", 14)

# ---------------------------------------------------------------------------
# Sound list — edit order / add names here freely
# ---------------------------------------------------------------------------
SOUND_DIR = os.path.join("assets", "sounds")

SOUNDS = [
    ("click",           "Flashlight toggle click"),
    ("footstep",        "Floorboard creak (footstep)"),
    ("pickup_battery",  "Battery pickup chime"),
    ("pickup_key",      "Key pickup shimmer"),
    ("creature_move",   "Creature repositioning"),
    ("door_open",       "Door creak & settle"),
    ("heartbeat",       "Heartbeat (blackout)"),
    ("whisper",         "Whisper texture"),
    ("ambient_hum",     "Ambient drone loop"),
    ("jumpscare",       "Jumpscare sting"),
    ("static_burst",    "Static burst (bonus)"),
    ("low_drone_sting", "Low drone sting (bonus)"),
]

# Map keyboard shortcut → index
HOTKEYS = {
    pygame.K_1: 0,  pygame.K_2: 1,  pygame.K_3: 2,
    pygame.K_4: 3,  pygame.K_5: 4,  pygame.K_6: 5,
    pygame.K_7: 6,  pygame.K_8: 7,  pygame.K_9: 8,
    pygame.K_0: 9,  pygame.K_MINUS: 10, pygame.K_EQUALS: 11,
}

# ---------------------------------------------------------------------------
# Load sounds
# ---------------------------------------------------------------------------
def load_sound(name):
    for ext in (".wav", ".ogg", ".mp3"):
        path = os.path.join(SOUND_DIR, name + ext)
        if os.path.exists(path):
            try:
                return pygame.mixer.Sound(path), path
            except Exception as e:
                return None, f"ERROR loading {path}: {e}"
    return None, f"NOT FOUND  (run generate_assets.py first)"


loaded = []
for name, label in SOUNDS:
    snd, info = load_sound(name)
    loaded.append({"name": name, "label": label, "snd": snd, "info": info})

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
current_idx   = 0
last_played   = -1
status_msg    = "Press SPACE to play the first sound"
status_color  = (200, 200, 200)
playing_name  = ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
COLORS = {
    "bg":       (10, 8, 14),
    "panel":    (20, 18, 28),
    "border":   (80, 40, 60),
    "title":    (240, 220, 200),
    "active":   (255, 200, 80),
    "ok":       (80, 220, 120),
    "err":      (220, 70, 70),
    "dim":      (100, 90, 110),
    "key":      (140, 200, 255),
}

def draw_text(surface, text, font, color, x, y, center=False):
    surf = font.render(text, True, color)
    if center:
        x -= surf.get_width() // 2
    surface.blit(surf, (x, y))
    return surf.get_height()


def play_sound(idx):
    global last_played, status_msg, status_color, playing_name
    pygame.mixer.stop()
    entry = loaded[idx]
    if entry["snd"]:
        entry["snd"].play()
        last_played  = idx
        playing_name = entry["name"]
        status_msg   = f"▶  Playing: {entry['name']}"
        status_color = COLORS["ok"]
    else:
        status_msg   = f"✗  {entry['info']}"
        status_color = COLORS["err"]
        playing_name = ""


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
running = True
while running:
    dt = clock.tick(60) / 1000.0

    # ---- Events ----
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False

            elif event.key == pygame.K_SPACE:
                play_sound(current_idx)
                current_idx = (current_idx + 1) % len(SOUNDS)

            elif event.key == pygame.K_r:
                if last_played >= 0:
                    play_sound(last_played)

            elif event.key in HOTKEYS:
                idx = HOTKEYS[event.key]
                if idx < len(SOUNDS):
                    current_idx = idx
                    play_sound(idx)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Click on a row to play it
            mouse_y = event.pos[1]
            row_top = 130
            row_h   = 26
            for i in range(len(SOUNDS)):
                if row_top + i * row_h <= mouse_y < row_top + (i + 1) * row_h:
                    current_idx = i
                    play_sound(i)
                    break

    # ---- Draw ----
    screen.fill(COLORS["bg"])

    # Title
    pygame.draw.rect(screen, COLORS["panel"], (0, 0, SCREEN_W, 60))
    pygame.draw.line(screen, COLORS["border"], (0, 60), (SCREEN_W, 60), 2)
    draw_text(screen, "DON'T LOOK AWAY — Sound Tester",
              font_big, COLORS["title"], SCREEN_W // 2, 16, center=True)

    # Instructions bar
    pygame.draw.rect(screen, (15, 14, 22), (0, 61, SCREEN_W, 24))
    draw_text(screen,
              "SPACE = next   1-0/-/= = hotkey   R = replay   Click row   ESC = quit",
              font_sm, COLORS["dim"], 12, 65)

    # Sound list
    row_top = 100
    row_h   = 26

    # Header
    draw_text(screen, "#   NAME                    STATUS", font_sm, COLORS["dim"], 20, row_top - 18)
    pygame.draw.line(screen, COLORS["border"], (12, row_top - 2), (SCREEN_W - 12, row_top - 2), 1)

    for i, entry in enumerate(loaded):
        ry = row_top + i * row_h

        # Highlight current selection
        if i == current_idx % len(SOUNDS):
            pygame.draw.rect(screen, (30, 25, 45), (10, ry, SCREEN_W - 20, row_h - 2))
            pygame.draw.rect(screen, COLORS["border"], (10, ry, SCREEN_W - 20, row_h - 2), 1)

        # Row number / hotkey
        key_labels = ["1","2","3","4","5","6","7","8","9","0","-","="]
        key_str = f"[{key_labels[i]}]" if i < len(key_labels) else "   "

        name_color = COLORS["active"] if entry["name"] == playing_name else COLORS["title"]
        ok_color   = COLORS["ok"] if entry["snd"] else COLORS["err"]
        ok_str     = "✓ READY" if entry["snd"] else "✗ MISSING"

        draw_text(screen, key_str,        font_sm,  COLORS["key"], 16,  ry + 6)
        draw_text(screen, entry["name"],  font_med, name_color,    65,  ry + 4)
        draw_text(screen, entry["label"], font_sm,  COLORS["dim"], 285, ry + 7)
        draw_text(screen, ok_str,         font_sm,  ok_color,      530, ry + 7)

    # Status bar at bottom
    bar_y = SCREEN_H - 50
    pygame.draw.line(screen, COLORS["border"], (0, bar_y), (SCREEN_W, bar_y), 1)
    pygame.draw.rect(screen, COLORS["panel"], (0, bar_y + 1, SCREEN_W, 50))
    draw_text(screen, status_msg, font_med, status_color, SCREEN_W // 2, bar_y + 14, center=True)

    # Pulsing dot when something is playing
    if playing_name and pygame.mixer.get_busy():
        pulse_r = int(55 + 30 * abs(math.sin(time.time() * 4)))
        pygame.draw.circle(screen, (pulse_r, 220, 80), (22, bar_y + 24), 6)
    elif playing_name and not pygame.mixer.get_busy():
        playing_name = ""

    pygame.display.flip()

pygame.quit()
sys.exit()
