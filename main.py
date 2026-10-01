"""
================================================================================
DON'T LOOK AWAY - A 2D Top-Down Psychological Horror Game
GameJam Theme: "UNSTABLE" (Protagonist's Unreliable Perception)
================================================================================

Controls:
- W, A, S, D       : Move protagonist
- Mouse Cursor     : Aim flashlight beam
- Left-Click / F   : Toggle Flashlight ON / OFF
- E                : Interact / Open/Close Doors / Pick up Key & Battery / Escape
- R                : Restart game
- ESC              : Quit
"""

import sys
import os
import math
import random
import io
import struct
import wave
import pygame

# ==============================================================================
# 1. GAMEPLAY CONFIGURATION & DIFFICULTY TUNING
# GameJam balance values
# ==============================================================================
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
FPS = 60

# World Size (Expanded Multi-Room House / Asylum Wing)
WORLD_WIDTH = 1500
WORLD_HEIGHT = 1050

# Player settings
PLAYER_SPEED = 3.3           # Pixels per frame (WASD movement speed)
PLAYER_SIZE = 24             # Bounding box width/height for collision

# Flashlight mechanics (Balanced for relaxed exploration)
FLASHLIGHT_ANGLE = 80        # Beam cone angle in degrees (70-90)
FLASHLIGHT_RANGE = 400       # Beam reach in pixels
FLASHLIGHT_BATTERY = 100.0   # Initial battery percentage (0 to 100)
BATTERY_DRAIN = 0.65         # Battery % drained per second (~155s of continuous light)
BATTERY_REFILL = 50.0        # Battery % restored per battery pickup

# Creature mechanics
CREATURE_MOVE_DELAY = 1.8    # Seconds unseen before creature can relocate
CREATURE_AGGRO_DELAY = 1.0   # Faster relocation once key is obtained / aggressive
CREATURE_ATTACK_DIST = 46    # Proximity threshold for game over in darkness
BLACKOUT_KILL_TIME = 4.5     # Seconds of total darkness before forced jumpscare

# Game States
STATE_MENU = "MENU"
STATE_INTRO_STORY = "INTRO_STORY"
STATE_PLAYING = "PLAYING"
STATE_ENDING_SEQUENCE = "ENDING_SEQUENCE"
STATE_JUMPSCARE = "JUMPSCARE"
STATE_AMBIGUOUS_ENDING = "AMBIGUOUS_ENDING"
STATE_GAME_OVER = "GAME_OVER"


# ==============================================================================
# 2. AUDIO SYSTEM & PROCEDURAL SYNTHESIS (Zero External Dependency Fallback)
# ==============================================================================
AUDIO_INITIALIZED = False
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    AUDIO_INITIALIZED = True
except Exception:
    AUDIO_INITIALIZED = False


def _synthesize_wav(samples, sample_rate=22050):
    """Helper to convert audio samples into a Pygame Sound via BytesIO wave."""
    if not AUDIO_INITIALIZED:
        return None
    try:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            raw = b''.join(struct.pack('<h', max(-32767, min(32767, int(s)))) for s in samples)
            w.writeframes(raw)
        buf.seek(0)
        return pygame.mixer.Sound(buf)
    except Exception:
        return None


def generate_sound(name):
    """Generates procedural sound effects if external audio files are missing."""
    rate = 22050
    if not AUDIO_INITIALIZED:
        return None

    try:
        if name == "click":
            duration = int(rate * 0.04)
            samples = [
                math.sin(2 * math.pi * 2400 * i / rate) * math.exp(-i / (rate * 0.007)) * 26000
                + (random.random() * 2 - 1) * math.exp(-i / (rate * 0.005)) * 12000
                for i in range(duration)
            ]
            return _synthesize_wav(samples, rate)

        elif name == "footstep":
            duration = int(rate * 0.07)
            samples = [
                math.sin(2 * math.pi * 75 * i / rate) * math.exp(-i / (rate * 0.02)) * 14000
                + (random.random() * 2 - 1) * math.exp(-i / (rate * 0.015)) * 4000
                for i in range(duration)
            ]
            return _synthesize_wav(samples, rate)

        elif name == "pickup_battery":
            duration = int(rate * 0.22)
            half = duration // 2
            samples = []
            for i in range(half):
                samples.append(math.sin(2 * math.pi * 587 * i / rate) * math.exp(-i / (rate * 0.07)) * 18000)
            for i in range(half):
                samples.append(math.sin(2 * math.pi * 880 * i / rate) * math.exp(-i / (rate * 0.09)) * 22000)
            return _synthesize_wav(samples, rate)

        elif name == "pickup_key":
            duration = int(rate * 0.35)
            samples = [
                (
                    math.sin(2 * math.pi * 784 * i / rate) * 0.5
                    + math.sin(2 * math.pi * 1174 * i / rate) * 0.35
                    + math.sin(2 * math.pi * 1568 * i / rate) * 0.25
                ) * math.exp(-i / (rate * 0.12)) * 26000
                for i in range(duration)
            ]
            return _synthesize_wav(samples, rate)

        elif name == "creature_move":
            duration = int(rate * 0.30)
            samples = [
                (
                    math.sin(2 * math.pi * (110 + 40 * math.sin(2 * math.pi * 8 * i / rate)) * i / rate) * 0.6
                    + (random.random() * 2 - 1) * 0.4
                ) * math.exp(-i / (rate * 0.15)) * 14000
                for i in range(duration)
            ]
            return _synthesize_wav(samples, rate)

        elif name == "door_open":
            duration = int(rate * 0.55)
            samples = [
                (
                    math.sin(2 * math.pi * (150 + 70 * math.sin(2 * math.pi * 14 * i / rate)) * i / rate) * 0.7
                    + (random.random() * 2 - 1) * 0.3
                ) * math.sin(math.pi * i / duration) * 18000
                for i in range(duration)
            ]
            return _synthesize_wav(samples, rate)

        elif name == "heartbeat":
            duration = int(rate * 0.5)
            samples = [0] * duration
            for i in range(int(rate * 0.15)):
                samples[i] += int(math.sin(2 * math.pi * 55 * i / rate) * math.exp(-i / (rate * 0.04)) * 26000)
            offset = int(rate * 0.20)
            for i in range(int(rate * 0.15)):
                if offset + i < duration:
                    samples[offset + i] += int(math.sin(2 * math.pi * 65 * i / rate) * math.exp(-i / (rate * 0.04)) * 22000)
            return _synthesize_wav(samples, rate)

        elif name == "jumpscare":
            duration = int(rate * 1.8)
            samples = []
            for i in range(duration):
                t = i / rate
                freq = max(180, 1600 - t * 700)
                screech = (
                    math.sin(2 * math.pi * freq * t)
                    + 0.6 * math.sin(2 * math.pi * (freq * 1.414) * t)
                    + 0.5 * math.sin(2 * math.pi * (freq * 0.73) * t)
                )
                bass = math.sin(2 * math.pi * 45 * t) * math.exp(-t / 0.4) * 2.0
                noise = (random.random() * 2 - 1) * (0.8 if t < 0.6 else 0.3)
                env = math.exp(-t / 1.1) if t > 0.1 else (t / 0.1)
                val = (screech * 0.5 + bass * 0.35 + noise * 0.35) * env * 28000
                samples.append(val)
            return _synthesize_wav(samples, rate)

    except Exception:
        return None
    return None


class AudioManager:
    """Manages audio loading from disk with procedural fallback."""
    def __init__(self):
        self.sounds = {}
        sound_names = [
            "click", "footstep", "pickup_battery", "pickup_key",
            "creature_move", "door_open", "heartbeat", "jumpscare"
        ]
        sound_dir = os.path.join("assets", "sounds")

        for name in sound_names:
            sound_obj = None
            for ext in [".wav", ".ogg", ".mp3"]:
                path = os.path.join(sound_dir, f"{name}{ext}")
                if os.path.exists(path) and AUDIO_INITIALIZED:
                    try:
                        sound_obj = pygame.mixer.Sound(path)
                        break
                    except Exception:
                        sound_obj = None

            if sound_obj is None and AUDIO_INITIALIZED:
                sound_obj = generate_sound(name)

            self.sounds[name] = sound_obj

    def play(self, name, volume=1.0):
        """Safely plays a sound. Never crashes if sound is None."""
        if not AUDIO_INITIALIZED:
            return
        snd = self.sounds.get(name)
        if snd:
            try:
                snd.set_volume(volume)
                snd.play()
            except Exception:
                pass


# ==============================================================================
# 3. PROCEDURAL SPRITES & ASSET OVERRIDE LOADER
# ==============================================================================
def create_player_surface():
    """Top-down pixel art protagonist with coat and flashlight holder."""
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(surf, (35, 45, 55), (16, 16), 11)
    pygame.draw.circle(surf, (20, 25, 30), (16, 16), 11, 2)
    pygame.draw.circle(surf, (215, 180, 150), (16, 16), 6)
    pygame.draw.circle(surf, (40, 25, 20), (16, 14), 6)
    pygame.draw.rect(surf, (180, 180, 190), (22, 18, 8, 4))
    pygame.draw.rect(surf, (255, 240, 120), (28, 17, 3, 6))
    return surf


def create_creature_surface():
    """Unnaturally tall, emaciated silhouette with piercing glowing eyes."""
    surf = pygame.Surface((44, 56), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (10, 0, 5, 80), (4, 4, 36, 48))
    pygame.draw.ellipse(surf, (15, 12, 18), (15, 14, 14, 34))
    pygame.draw.line(surf, (18, 14, 22), (15, 18), (6, 44), 3)
    pygame.draw.line(surf, (18, 14, 22), (29, 18), (38, 44), 3)
    pygame.draw.line(surf, (25, 20, 30), (6, 44), (4, 50), 2)
    pygame.draw.line(surf, (25, 20, 30), (38, 44), (40, 50), 2)
    pygame.draw.ellipse(surf, (18, 15, 22), (14, 4, 16, 18))
    pygame.draw.circle(surf, (255, 245, 210), (18, 11), 2)
    pygame.draw.circle(surf, (255, 245, 210), (26, 11), 2)
    pygame.draw.circle(surf, (255, 60, 40), (18, 11), 1)
    pygame.draw.circle(surf, (255, 60, 40), (26, 11), 1)
    return surf


def create_jumpscare_surface():
    """Full-screen terrifying visage for the climactic jumpscare sequence."""
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    surf.fill((10, 5, 10))
    cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    pygame.draw.ellipse(surf, (25, 20, 25), (cx - 160, cy - 230, 320, 420))
    pygame.draw.ellipse(surf, (10, 8, 12), (cx - 140, cy - 210, 280, 380))
    pygame.draw.ellipse(surf, (5, 2, 5), (cx - 100, cy - 110, 75, 95))
    pygame.draw.ellipse(surf, (5, 2, 5), (cx + 25, cy - 110, 75, 95))
    pygame.draw.circle(surf, (255, 255, 255), (cx - 62, cy - 65), 10)
    pygame.draw.circle(surf, (255, 255, 255), (cx + 62, cy - 65), 10)
    pygame.draw.circle(surf, (240, 20, 20), (cx - 62, cy - 65), 6)
    pygame.draw.circle(surf, (240, 20, 20), (cx + 62, cy - 65), 6)
    pygame.draw.polygon(surf, (4, 2, 5), [
        (cx - 70, cy + 30), (cx + 70, cy + 30),
        (cx + 90, cy + 190), (cx - 90, cy + 190)
    ])
    for i in range(-5, 6):
        tx = cx + i * 13
        pygame.draw.polygon(surf, (230, 220, 200), [(tx - 4, cy + 30), (tx + 4, cy + 30), (tx, cy + 55)])
        pygame.draw.polygon(surf, (230, 220, 200), [(tx - 4, cy + 190), (tx + 4, cy + 190), (tx, cy + 165)])
    pygame.draw.line(surf, (15, 12, 18), (40, SCREEN_HEIGHT), (cx - 180, cy + 40), 16)
    pygame.draw.line(surf, (15, 12, 18), (SCREEN_WIDTH - 40, SCREEN_HEIGHT), (cx + 180, cy + 40), 16)
    return surf


def create_painting_surfaces():
    """Generates the Normal and Corrupted (Unstable) painting portraits."""
    w, h = 64, 40
    surf_normal = pygame.Surface((w, h))
    surf_normal.fill((110, 80, 50))
    pygame.draw.rect(surf_normal, (50, 40, 35), (4, 4, w - 8, h - 8))
    pygame.draw.circle(surf_normal, (160, 140, 120), (w // 2, h // 2 - 2), 10)
    pygame.draw.circle(surf_normal, (70, 50, 40), (w // 2, h // 2 - 6), 10)
    pygame.draw.rect(surf_normal, (30, 25, 20), (w // 2 - 5, h // 2 - 3, 2, 2))
    pygame.draw.rect(surf_normal, (30, 25, 20), (w // 2 + 1, h // 2 - 3, 2, 2))

    surf_corrupt = pygame.Surface((w, h))
    surf_corrupt.fill((90, 60, 35))
    pygame.draw.rect(surf_corrupt, (35, 20, 25), (4, 4, w - 8, h - 8))
    pygame.draw.circle(surf_corrupt, (190, 175, 160), (w // 2, h // 2 - 2), 10)
    pygame.draw.circle(surf_corrupt, (40, 20, 25), (w // 2, h // 2 - 6), 10)
    pygame.draw.circle(surf_corrupt, (255, 255, 255), (w // 2 - 4, h // 2 - 3), 3)
    pygame.draw.circle(surf_corrupt, (255, 255, 255), (w // 2 + 4, h // 2 - 3), 3)
    pygame.draw.circle(surf_corrupt, (180, 0, 0), (w // 2 - 4, h // 2 - 3), 1)
    pygame.draw.circle(surf_corrupt, (180, 0, 0), (w // 2 + 4, h // 2 - 3), 1)
    pygame.draw.arc(surf_corrupt, (50, 10, 15), (w // 2 - 5, h // 2, 10, 6), math.pi, 2 * math.pi, 2)
    return surf_normal, surf_corrupt


# ==============================================================================
# 4. INTERACTIVE DOOR CLASS
# Room doors are OPEN BY DEFAULT so the player can immediately enter and explore!
# ==============================================================================
class InteractiveDoor:
    """An interactive door. Interior room doors start OPEN by default."""
    def __init__(self, x, y, width, height, is_exit=False, is_open=True, name="Door"):
        self.closed_rect = pygame.Rect(x, y, width, height)
        self.is_open = is_open
        self.is_exit = is_exit
        self.name = name

    def toggle(self):
        if not self.is_exit:
            self.is_open = not self.is_open

    def get_solid_collider(self):
        """Returns collider rectangle if closed; None if open (passable)."""
        if self.is_open:
            return None
        return self.closed_rect

    def draw(self, surface, cam_x, cam_y):
        sx = self.closed_rect.x - cam_x
        sy = self.closed_rect.y - cam_y
        w, h = self.closed_rect.width, self.closed_rect.height

        if self.is_exit:
            # Heavy Exit Door (Closed & locked until key is found)
            color = (65, 85, 65) if self.is_open else (90, 45, 45)
            pygame.draw.rect(surface, color, (sx, sy, w, h))
            pygame.draw.rect(surface, (25, 25, 25), (sx, sy, w, h), 2)
            pygame.draw.circle(surface, (220, 190, 80), (sx + w // 2, sy + h // 2), 4)
        else:
            if not self.is_open:
                # Closed door
                pygame.draw.rect(surface, (110, 80, 55), (sx, sy, w, h))
                pygame.draw.rect(surface, (55, 38, 25), (sx, sy, w, h), 2)
                knob_x = sx + (w - 8 if w > h else w // 2)
                knob_y = sy + (h // 2 if w > h else h - 8)
                pygame.draw.circle(surface, (215, 185, 75), (knob_x, knob_y), 3)
            else:
                # Open door swung to the wall, leaving doorway clear!
                swung_rect = (sx - 4, sy - h, 8, h + 4) if w > h else (sx - w, sy - 4, w + 4, 8)
                pygame.draw.rect(surface, (95, 68, 44), swung_rect)
                pygame.draw.rect(surface, (45, 30, 20), swung_rect, 1)


# ==============================================================================
# 5. MULTI-ROOM ENVIRONMENT & LEVEL LAYOUT
# ==============================================================================
class GameRoom:
    """Manages the multi-room layout with open doorways so player can enter immediately."""
    def __init__(self):
        self.house_rect = pygame.Rect(100, 80, 1300, 880)

        # Static Walls
        self.static_walls = [
            # Outer North
            pygame.Rect(100, 80, 1300, 18),
            # Outer South
            pygame.Rect(100, 942, 1300, 18),
            # Outer West
            pygame.Rect(100, 80, 18, 880),
            # Outer East
            pygame.Rect(1382, 80, 18, 880),

            # Dividing Wall: Bedroom vs Study (Vertical, top half)
            pygame.Rect(690, 80, 18, 360),
            # Dividing Wall: Storage vs Foyer (Vertical, bottom half)
            pygame.Rect(690, 600, 18, 360),

            # Hallway North Wall (with wide open doorways at x=360 and x=980)
            pygame.Rect(100, 440, 260, 18),
            pygame.Rect(430, 440, 550, 18),
            pygame.Rect(1050, 440, 350, 18),

            # Hallway South Wall (with wide open doorways at x=360 and x=980)
            pygame.Rect(100, 600, 260, 18),
            pygame.Rect(430, 600, 550, 18),
            pygame.Rect(1050, 600, 350, 18),
        ]

        # Room doors are OPEN BY DEFAULT so the player can enter immediately!
        self.doors = [
            InteractiveDoor(360, 440, 70, 18, is_exit=False, is_open=True, name="Bedroom Door"),
            InteractiveDoor(980, 440, 70, 18, is_exit=False, is_open=True, name="Study Door"),
            InteractiveDoor(360, 600, 70, 18, is_exit=False, is_open=True, name="Storage Door"),
            InteractiveDoor(980, 600, 70, 18, is_exit=False, is_open=True, name="Foyer Door"),
            # Main Exit Door is locked (Requires Key)
            InteractiveDoor(980, 942, 80, 18, is_exit=True, is_open=False, name="Main Exit Door"),
        ]

        # Furniture Colliders
        # 1. Bedroom (Top-Left)
        self.bed_rect = pygame.Rect(140, 110, 120, 160)
        self.nightstand_rect = pygame.Rect(270, 110, 45, 45)
        self.wardrobe_rect = pygame.Rect(610, 110, 60, 150)

        # UNSTABLE: Moving Chair in Bedroom
        self.chair_initial_pos = (400, 200)
        self.chair_altered_pos = (310, 310)
        self.chair_pos = list(self.chair_initial_pos)
        self.chair_rect = pygame.Rect(self.chair_pos[0], self.chair_pos[1], 28, 28)
        self.chair_has_moved = False

        # 2. Study & Gallery (Top-Right)
        self.study_desk_rect = pygame.Rect(1140, 120, 160, 75)
        self.bookshelf_1 = pygame.Rect(730, 110, 140, 36)
        self.bookshelf_2 = pygame.Rect(730, 170, 140, 36)
        self.study_table = pygame.Rect(940, 260, 90, 50)

        # UNSTABLE: Changing Portrait on North Wall of Study
        self.painting_rect = pygame.Rect(1000, 82, 64, 40)
        self.painting_normal, self.painting_corrupt = create_painting_surfaces()
        self.painting_seen_once = False
        self.painting_altered = False

        # 3. Storage Room (Bottom-Left)
        self.storage_crate_1 = pygame.Rect(140, 650, 70, 70)
        self.storage_crate_2 = pygame.Rect(140, 820, 90, 70)
        self.storage_shelf = pygame.Rect(520, 820, 140, 40)

        # Environmental Clue Graffiti on North Wall of Storage
        self.clue_text = "DON'T LET IT GO DARK."
        self.clue_pos = (440, 624)

        # 4. Exit Foyer (Bottom-Right)
        self.foyer_table = pygame.Rect(730, 700, 50, 90)
        self.foyer_shelf = pygame.Rect(1280, 680, 45, 90)

        # Key (Located clearly in the Study on the desk)
        self.has_key = False
        self.key_rect = pygame.Rect(1200, 150, 24, 24)
        self.key_collected = False

        # 3 Batteries
        self.batteries = [
            {"rect": pygame.Rect(280, 120, 18, 18), "collected": False, "room": "Bedroom"},
            {"rect": pygame.Rect(165, 835, 18, 18), "collected": False, "room": "Storage"},
            {"rect": pygame.Rect(1292, 700, 18, 18), "collected": False, "room": "Foyer"},
        ]

    def get_solid_colliders(self):
        """Returns all solid bounding boxes player cannot pass through."""
        colliders = list(self.static_walls)
        for d in self.doors:
            c = d.get_solid_collider()
            if c:
                colliders.append(c)

        colliders.extend([
            self.bed_rect, self.nightstand_rect, self.wardrobe_rect, self.chair_rect,
            self.study_desk_rect, self.bookshelf_1, self.bookshelf_2, self.study_table,
            self.storage_crate_1, self.storage_crate_2, self.storage_shelf,
            self.foyer_table, self.foyer_shelf
        ])
        return colliders

    def draw_environment(self, surface, cam_x, cam_y, font_sm):
        """Renders floorboards, walls, furniture, and environmental clues."""
        # Floorboards
        floor_color_1 = (40, 32, 26)
        floor_color_2 = (35, 28, 22)
        for y in range(self.house_rect.top, self.house_rect.bottom, 24):
            sy = y - cam_y
            if -30 <= sy <= SCREEN_HEIGHT + 30:
                color = floor_color_1 if ((y // 24) % 2 == 0) else floor_color_2
                sx = self.house_rect.left - cam_x
                pygame.draw.rect(surface, color, (sx, sy, self.house_rect.width, 24))
                pygame.draw.line(surface, (24, 18, 14), (sx, sy), (sx + self.house_rect.width, sy), 1)

        # Static Walls
        for w in self.static_walls:
            sx = w.x - cam_x
            sy = w.y - cam_y
            pygame.draw.rect(surface, (55, 48, 44), (sx, sy, w.w, w.h))
            pygame.draw.rect(surface, (30, 25, 22), (sx, sy, w.w, w.h), 2)

        # Interactive Doors
        for d in self.doors:
            d.draw(surface, cam_x, cam_y)

        # Environmental Clue: Wall scratch in Storage Room
        clue_sx = self.clue_pos[0] - cam_x
        clue_sy = self.clue_pos[1] - cam_y
        clue_surf = font_sm.render(self.clue_text, True, (130, 85, 75))
        surface.blit(clue_surf, (clue_sx, clue_sy))

        # --- BEDROOM FURNITURE ---
        bx, by = self.bed_rect.x - cam_x, self.bed_rect.y - cam_y
        pygame.draw.rect(surface, (75, 52, 38), (bx, by, self.bed_rect.w, self.bed_rect.h))
        pygame.draw.rect(surface, (135, 125, 115), (bx + 6, by + 6, self.bed_rect.w - 12, self.bed_rect.h - 12))
        pygame.draw.rect(surface, (175, 170, 160), (bx + 10, by + 10, self.bed_rect.w - 20, 32))
        pygame.draw.rect(surface, (90, 70, 60), (bx + 6, by + 65, self.bed_rect.w - 12, self.bed_rect.h - 71))

        nx, ny = self.nightstand_rect.x - cam_x, self.nightstand_rect.y - cam_y
        pygame.draw.rect(surface, (85, 60, 42), (nx, ny, self.nightstand_rect.w, self.nightstand_rect.h))
        pygame.draw.rect(surface, (45, 32, 22), (nx, ny, self.nightstand_rect.w, self.nightstand_rect.h), 2)

        wx, wy = self.wardrobe_rect.x - cam_x, self.wardrobe_rect.y - cam_y
        pygame.draw.rect(surface, (68, 44, 28), (wx, wy, self.wardrobe_rect.w, self.wardrobe_rect.h))
        pygame.draw.rect(surface, (38, 24, 15), (wx, wy, self.wardrobe_rect.w, self.wardrobe_rect.h), 2)
        pygame.draw.line(surface, (20, 10, 8), (wx + self.wardrobe_rect.w // 2, wy + 4),
                         (wx + self.wardrobe_rect.w // 2, wy + self.wardrobe_rect.h - 4), 2)

        cx, cy = self.chair_rect.x - cam_x, self.chair_rect.y - cam_y
        pygame.draw.rect(surface, (105, 72, 48), (cx, cy, self.chair_rect.w, self.chair_rect.h))
        pygame.draw.rect(surface, (55, 38, 24), (cx, cy, self.chair_rect.w, self.chair_rect.h), 2)
        if self.chair_has_moved:
            pygame.draw.rect(surface, (75, 48, 28), (cx + 2, cy + self.chair_rect.h - 6, self.chair_rect.w - 4, 4))
        else:
            pygame.draw.rect(surface, (75, 48, 28), (cx + 2, cy + 2, self.chair_rect.w - 4, 4))

        # --- STUDY FURNITURE ---
        dx, dy = self.study_desk_rect.x - cam_x, self.study_desk_rect.y - cam_y
        pygame.draw.rect(surface, (95, 68, 46), (dx, dy, self.study_desk_rect.w, self.study_desk_rect.h))
        pygame.draw.rect(surface, (55, 38, 26), (dx, dy, self.study_desk_rect.w, self.study_desk_rect.h), 2)
        pygame.draw.rect(surface, (195, 190, 175), (dx + 15, dy + 15, 24, 28))
        pygame.draw.rect(surface, (185, 180, 165), (dx + 48, dy + 20, 28, 24))

        for b in [self.bookshelf_1, self.bookshelf_2]:
            bx, by = b.x - cam_x, b.y - cam_y
            pygame.draw.rect(surface, (78, 52, 34), (bx, by, b.w, b.h))
            pygame.draw.rect(surface, (45, 30, 20), (bx, by, b.w, b.h), 2)
            for i in range(5):
                pygame.draw.rect(surface, (140 + i * 15, 60 + i * 10, 40), (bx + 8 + i * 24, by + 4, 18, b.h - 8))

        stx, sty = self.study_table.x - cam_x, self.study_table.y - cam_y
        pygame.draw.rect(surface, (88, 62, 42), (stx, sty, self.study_table.w, self.study_table.h))

        px, py = self.painting_rect.x - cam_x, self.painting_rect.y - cam_y
        painting_surf = self.painting_corrupt if self.painting_altered else self.painting_normal
        surface.blit(painting_surf, (px, py))

        # --- STORAGE FURNITURE ---
        for crate in [self.storage_crate_1, self.storage_crate_2]:
            cx, cy = crate.x - cam_x, crate.y - cam_y
            pygame.draw.rect(surface, (82, 60, 42), (cx, cy, crate.w, crate.h))
            pygame.draw.rect(surface, (48, 34, 22), (cx, cy, crate.w, crate.h), 2)
            pygame.draw.line(surface, (48, 34, 22), (cx, cy), (cx + crate.w, cy + crate.h), 2)

        sx, sy = self.storage_shelf.x - cam_x, self.storage_shelf.y - cam_y
        pygame.draw.rect(surface, (70, 48, 32), (sx, sy, self.storage_shelf.w, self.storage_shelf.h))

        # --- FOYER FURNITURE ---
        fx, fy = self.foyer_table.x - cam_x, self.foyer_table.y - cam_y
        pygame.draw.rect(surface, (85, 60, 42), (fx, fy, self.foyer_table.w, self.foyer_table.h))
        fx, fy = self.foyer_shelf.x - cam_x, self.foyer_shelf.y - cam_y
        pygame.draw.rect(surface, (75, 50, 35), (fx, fy, self.foyer_shelf.w, self.foyer_shelf.h))

        # --- KEY ITEM (Glows with gold shine on the Study desk) ---
        if not self.key_collected:
            kx = self.key_rect.centerx - cam_x
            ky = self.key_rect.centery - cam_y
            # Subtle pulsating aura
            pulse = math.sin(pygame.time.get_ticks() / 250.0) * 3
            pygame.draw.circle(surface, (255, 230, 80), (int(kx), int(ky - 3)), int(6 + pulse), 1)
            pygame.draw.circle(surface, (255, 215, 60), (int(kx), int(ky - 3)), 4)
            pygame.draw.rect(surface, (255, 215, 60), (int(kx - 1), int(ky - 1), 3, 9))
            pygame.draw.rect(surface, (255, 215, 60), (int(kx + 1), int(ky + 3), 3, 2))

        # --- BATTERY ITEMS ---
        for bat in self.batteries:
            if not bat["collected"]:
                r = bat["rect"]
                bx, by = r.x - cam_x, r.y - cam_y
                pygame.draw.rect(surface, (50, 185, 100), (bx, by + 2, r.w, r.h - 4))
                pygame.draw.rect(surface, (220, 220, 220), (bx + r.w - 2, by + r.h // 2 - 2, 3, 4))
                pygame.draw.rect(surface, (20, 40, 20), (bx, by + 2, r.w, r.h - 4), 1)


# ==============================================================================
# 6. CREATURE CONTROLLER (Stalking & Freeze Mechanic)
# ==============================================================================
class Creature:
    """The creature freezes in the flashlight beam, and repositions across the house when unseen."""
    def __init__(self):
        self.sprite = create_creature_surface()
        self.width = 40
        self.height = 52

        # Predefined stalking positions across the house
        self.positions = [
            (580, 240),   # Stage 1: Lurking by the bedroom wardrobe
            (520, 520),   # Stage 2: Lurking in the dark central hallway
            (880, 260),   # Stage 3: Inside the study near the bookshelves
            (360, 780),   # Stage 4: Inside the storage room shadows
            (980, 780),   # Stage 5: In the exit foyer near the exit door!
        ]
        self.stage = 0
        self.pos = list(self.positions[0])
        self.rect = pygame.Rect(self.pos[0] - self.width // 2, self.pos[1] - self.height // 2, self.width, self.height)

        self.is_active = False
        self.is_illuminated = False
        self.is_frozen = False
        self.unseen_timer = 0.0

    def update_position(self, player_pos, is_aggressive=False):
        """Advances to next stalk position or stalks around player's blind spots."""
        if not self.is_active:
            return

        if not is_aggressive:
            if self.stage < len(self.positions) - 1:
                self.stage += 1
                self.pos = list(self.positions[self.stage])
            else:
                self._reposition_near_player(player_pos)
        else:
            self._reposition_near_player(player_pos)

        self.rect.center = (int(self.pos[0]), int(self.pos[1]))

    def _reposition_near_player(self, player_pos):
        """Positions the stalker 140-200px away from the player in shadow."""
        px, py = player_pos
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(140, 200)
        nx = max(140, min(1340, px + math.cos(angle) * dist))
        ny = max(120, min(900, py + math.sin(angle) * dist))
        self.pos = [nx, ny]

    def draw(self, surface, cam_x, cam_y):
        if self.is_active:
            draw_x = self.pos[0] - cam_x - self.sprite.get_width() // 2
            draw_y = self.pos[1] - cam_y - self.sprite.get_height() // 2
            surface.blit(self.sprite, (draw_x, draw_y))


# ==============================================================================
# 7. MAIN GAME ENGINE
# ==============================================================================
class GameEngine:
    """The central game engine orchestrating gameplay, camera, lighting, audio, and story."""
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("DON'T LOOK AWAY")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("couriernew", 42, bold=True)
        self.font_narrator = pygame.font.SysFont("couriernew", 20, bold=True)
        self.font_msg = pygame.font.SysFont("couriernew", 22, bold=True)
        self.font_hud = pygame.font.SysFont("couriernew", 16, bold=True)
        self.font_sm = pygame.font.SysFont("couriernew", 14, bold=True)

        # Audio manager
        self.audio = AudioManager()

        # Lighting darkness surface
        self.darkness_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        # Visual assets
        self.player_sprite = create_player_surface()
        self.jumpscare_sprite = create_jumpscare_surface()

        # Narrative Story Intro Lines
        self.story_lines = [
            "They told you it was just stress.",
            "Just exhaustion playing tricks on your mind.",
            "",
            "You locked the doors, but you can still hear the floorboards creak.",
            "You feel eyes watching you from the shadow.",
            "",
            "Your perception is slipping. Reality feels... unstable.",
            "",
            "Find the key. Conserve your light.",
            "And whatever you do...",
            "DON'T LOOK AWAY."
        ]

        self.reset_game()

    def reset_game(self):
        """Resets all states to allow instant restart."""
        self.state = STATE_MENU
        self.state_timer = 0.0

        # Intro Story Fade Timer
        self.intro_timer = 0.0

        # Player spawns in the Central Hallway outside the open rooms!
        self.player_x = 520.0
        self.player_y = 520.0
        self.player_angle = 0.0
        self.player_rect = pygame.Rect(int(self.player_x - PLAYER_SIZE // 2),
                                       int(self.player_y - PLAYER_SIZE // 2),
                                       PLAYER_SIZE, PLAYER_SIZE)

        # Camera
        self.cam_x = int(self.player_x - SCREEN_WIDTH // 2)
        self.cam_y = int(self.player_y - SCREEN_HEIGHT // 2)

        # Flashlight & Battery
        self.battery = FLASHLIGHT_BATTERY
        self.flashlight_on = True
        self.battery_dead_time = 0.0

        # World & Creature
        self.room = GameRoom()
        self.creature = Creature()

        # Story & Instability Triggers
        self.game_time = 0.0
        self.ending_phase = 0
        self.ending_timer = 0.0

        # Message Banner System
        self.current_message = ""
        self.message_timer = 0.0
        self.message_duration = 0.0

        # Screen Shake
        self.shake_amount = 0

        # Timers
        self.footstep_timer = 0.0
        self.heartbeat_timer = 0.0

    def toggle_flashlight(self):
        """Toggles flashlight ON / OFF with mouse click or F key."""
        if self.battery <= 0.0:
            self.audio.play("click", 0.7)
            self.flashlight_on = False
            return

        self.flashlight_on = not self.flashlight_on
        self.audio.play("click", 0.85)

    def show_message(self, text, duration=3.5):
        """Queues a narrative or objective message at the top of the screen."""
        self.current_message = text
        self.message_duration = duration
        self.message_timer = duration

    # --------------------------------------------------------------------------
    # INPUT & MOVEMENT HANDLING
    # --------------------------------------------------------------------------
    def handle_input(self, dt):
        """Processes WASD movement and collision against walls & furniture."""
        keys = pygame.key.get_pressed()
        dx = 0.0
        dy = 0.0

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1.0

        if dx != 0.0 and dy != 0.0:
            inv_len = 1.0 / math.sqrt(2.0)
            dx *= inv_len
            dy *= inv_len

        # Footsteps
        is_moving = (dx != 0.0 or dy != 0.0)
        if is_moving:
            self.footstep_timer += dt
            if self.footstep_timer >= 0.38:
                self.audio.play("footstep", 0.45)
                self.footstep_timer = 0.0
        else:
            self.footstep_timer = 0.30

        # Horizontal movement & collision
        move_dist_x = dx * PLAYER_SPEED
        self.player_x += move_dist_x
        self.player_rect.centerx = int(self.player_x)
        colliders = self.room.get_solid_colliders()
        for c in colliders:
            if self.player_rect.colliderect(c):
                if move_dist_x > 0:
                    self.player_rect.right = c.left
                elif move_dist_x < 0:
                    self.player_rect.left = c.right
                self.player_x = float(self.player_rect.centerx)

        # Vertical movement & collision
        move_dist_y = dy * PLAYER_SPEED
        self.player_y += move_dist_y
        self.player_rect.centery = int(self.player_y)
        for c in colliders:
            if self.player_rect.colliderect(c):
                if move_dist_y > 0:
                    self.player_rect.bottom = c.top
                elif move_dist_y < 0:
                    self.player_rect.top = c.bottom
                self.player_y = float(self.player_rect.centery)

    def handle_interaction(self):
        """Interacts with Doors, Key, Batteries, or Exit upon pressing [E]."""
        px, py = self.player_x, self.player_y

        # 1. Check Interactive Doors
        for d in self.room.doors:
            dist = math.hypot(px - d.closed_rect.centerx, py - d.closed_rect.centery)
            if dist < 65:
                if d.is_exit:
                    if self.room.has_key:
                        d.is_open = True
                        self.state = STATE_ENDING_SEQUENCE
                        self.ending_phase = 1
                        self.ending_timer = 0.0
                        self.audio.play("door_open", 0.9)
                        self.show_message("YOU CAN LEAVE.", 3.0)
                        return
                    else:
                        self.show_message("THE DOOR IS LOCKED. FIND THE KEY.", 3.0)
                        return
                else:
                    d.toggle()
                    self.audio.play("door_open", 0.8)
                    return

        # 2. Check Key pickup
        if not self.room.key_collected:
            dist_to_key = math.hypot(px - self.room.key_rect.centerx, py - self.room.key_rect.centery)
            if dist_to_key < 55:
                self.room.key_collected = True
                self.room.has_key = True
                self.audio.play("pickup_key", 0.9)
                self.show_message("KEY FOUND. THE MAIN EXIT IS UNLOCKED.", 4.5)
                return

        # 3. Check Battery pickup
        for bat in self.room.batteries:
            if not bat["collected"]:
                dist_to_bat = math.hypot(px - bat["rect"].centerx, py - bat["rect"].centery)
                if dist_to_bat < 50:
                    bat["collected"] = True
                    self.battery = min(100.0, self.battery + BATTERY_REFILL)
                    self.audio.play("pickup_battery", 0.85)
                    self.show_message(f"BATTERY FOUND (+{int(BATTERY_REFILL)}%)", 3.0)
                    return

    # --------------------------------------------------------------------------
    # FLASHLIGHT & VISIBILITY
    # --------------------------------------------------------------------------
    def is_point_in_flashlight(self, world_pos):
        """Returns True if world_pos is inside the illuminated cone."""
        if not self.flashlight_on:
            return False

        tx, ty = world_pos
        dx = tx - self.player_x
        dy = ty - self.player_y
        dist = math.hypot(dx, dy)

        if dist > FLASHLIGHT_RANGE:
            return False

        angle_to_target = math.atan2(dy, dx)
        diff = (angle_to_target - self.player_angle + math.pi) % (2 * math.pi) - math.pi
        half_angle = math.radians(FLASHLIGHT_ANGLE / 2.0)

        return abs(diff) <= half_angle

    # --------------------------------------------------------------------------
    # STORY & PSYCHOLOGICAL INSTABILITY PROGRESSION
    # --------------------------------------------------------------------------
    def update_story_and_instability(self, dt):
        """Executes the scripted psychological instability sequence."""
        self.game_time += dt

        # Initial narrative prompts in game
        if self.game_time < 0.2:
            self.show_message("I KNOW IT'S HERE. FIND THE KEY.", 4.0)

        # EVENT 1: The Bedroom Chair moves when player looks away
        if self.game_time >= 7.0 and not self.room.chair_has_moved:
            if not self.is_point_in_flashlight(self.room.chair_initial_pos):
                self.room.chair_has_moved = True
                self.room.chair_pos = list(self.room.chair_altered_pos)
                self.room.chair_rect.topleft = self.room.chair_pos

        # EVENT 2: The Study Painting alters when looked away
        if not self.room.painting_seen_once:
            if self.is_point_in_flashlight(self.room.painting_rect.center):
                self.room.painting_seen_once = True
        elif not self.room.painting_altered:
            if not self.is_point_in_flashlight(self.room.painting_rect.center):
                self.room.painting_altered = True

        # EVENT 3: Creature awakens after initial exploration
        if self.game_time >= 10.0 and not self.creature.is_active:
            self.creature.is_active = True

        # Battery drain logic (Only drains while flashlight is ON)
        if self.flashlight_on:
            self.battery = max(0.0, self.battery - BATTERY_DRAIN * dt)
            if self.battery <= 0.0:
                self.flashlight_on = False
                self.audio.play("click", 1.0)
                self.show_message("...", 4.0)

        # Battery dead / Blackout logic
        if self.battery <= 0.0 and not self.flashlight_on:
            self.battery_dead_time += dt
            self.heartbeat_timer += dt
            if self.heartbeat_timer >= 0.70:
                self.audio.play("heartbeat", 0.8)
                self.heartbeat_timer = 0.0

            if self.battery_dead_time >= BLACKOUT_KILL_TIME:
                self.trigger_jumpscare()

    # --------------------------------------------------------------------------
    # CREATURE BEHAVIOR & FREEZE MECHANIC
    # --------------------------------------------------------------------------
    def update_creature(self, dt):
        """The creature freezes in the flashlight beam, and moves when unlit."""
        if not self.creature.is_active:
            return

        in_beam = self.is_point_in_flashlight(self.creature.pos)
        self.creature.is_illuminated = in_beam

        if in_beam:
            # FREEZE COMPLETELY!
            self.creature.is_frozen = True
            self.creature.unseen_timer = 0.0
        else:
            # Unseen: moves closer
            self.creature.is_frozen = False
            self.creature.unseen_timer += dt

            is_aggressive = self.room.has_key
            threshold = CREATURE_AGGRO_DELAY if is_aggressive else CREATURE_MOVE_DELAY

            if self.creature.unseen_timer >= threshold:
                self.creature.unseen_timer = 0.0
                self.creature.update_position((self.player_x, self.player_y), is_aggressive)
                self.audio.play("creature_move", 0.6)

        # Proximity game-over in darkness
        dist_to_player = math.hypot(self.player_x - self.creature.pos[0],
                                    self.player_y - self.creature.pos[1])
        if dist_to_player < CREATURE_ATTACK_DIST and not in_beam:
            self.trigger_jumpscare()

    def trigger_jumpscare(self):
        """Initiates the jumpscare horror climax."""
        self.state = STATE_JUMPSCARE
        self.state_timer = 0.0
        self.audio.play("jumpscare", 1.0)
        self.shake_amount = 24

    # --------------------------------------------------------------------------
    # UPDATE LOOP (STATE MACHINE)
    # --------------------------------------------------------------------------
    def update(self, dt):
        """Updates camera, player aim, state machine, and timers."""
        # Camera smoothly tracks player
        target_cam_x = int(self.player_x - SCREEN_WIDTH / 2)
        target_cam_y = int(self.player_y - SCREEN_HEIGHT / 2)
        self.cam_x = max(0, min(WORLD_WIDTH - SCREEN_WIDTH, target_cam_x))
        self.cam_y = max(0, min(WORLD_HEIGHT - SCREEN_HEIGHT, target_cam_y))

        # Aim flashlight towards mouse cursor in screen space
        mx, my = pygame.mouse.get_pos()
        player_screen_x = self.player_x - self.cam_x
        player_screen_y = self.player_y - self.cam_y
        self.player_angle = math.atan2(my - player_screen_y, mx - player_screen_x)

        # Screen shake dampening
        if self.shake_amount > 0:
            self.shake_amount = max(0, self.shake_amount - int(45 * dt))

        # Message timer countdown
        if self.message_timer > 0.0:
            self.message_timer -= dt
            if self.message_timer <= 0.0:
                self.current_message = ""

        # State dispatch
        if self.state == STATE_INTRO_STORY:
            self.intro_timer += dt

        elif self.state == STATE_PLAYING:
            self.handle_input(dt)
            self.update_story_and_instability(dt)
            self.update_creature(dt)

        elif self.state == STATE_ENDING_SEQUENCE:
            self.ending_timer += dt
            if self.ending_timer >= 2.2 and self.ending_phase == 1:
                self.ending_phase = 2
                self.show_message("...THERE'S NOTHING THERE.", 3.0)

            elif self.ending_timer >= 4.8 and self.ending_phase == 2:
                self.ending_phase = 3
                self.show_message("...", 2.0)

            elif self.ending_timer >= 6.2:
                self.trigger_jumpscare()

        elif self.state == STATE_JUMPSCARE:
            self.state_timer += dt
            self.shake_amount = random.randint(14, 26)
            if self.state_timer >= 2.5:
                self.state = STATE_AMBIGUOUS_ENDING
                self.state_timer = 0.0

        elif self.state == STATE_AMBIGUOUS_ENDING:
            self.state_timer += dt

    # --------------------------------------------------------------------------
    # LIGHTING & SHADOW RENDERING
    # --------------------------------------------------------------------------
    def render_lighting(self, surface):
        """Renders ambient darkness and cuts out the flashlight beam with soft halo."""
        ambient_darkness = 246 if self.flashlight_on else 253
        self.darkness_surf.fill((6, 6, 10, ambient_darkness))

        px = int(self.player_x - self.cam_x)
        py = int(self.player_y - self.cam_y)

        # Personal halo around protagonist
        personal_radius = 42 if self.flashlight_on else 12
        pygame.draw.circle(self.darkness_surf, (0, 0, 0, 0), (px, py), personal_radius)

        # Flashlight cone punch-through
        if self.flashlight_on:
            cone_points = [(px, py)]
            half_angle = math.radians(FLASHLIGHT_ANGLE / 2.0)
            segments = 32
            for i in range(segments + 1):
                cur_ang = (self.player_angle - half_angle) + (2 * half_angle * i / segments)
                bx = px + math.cos(cur_ang) * FLASHLIGHT_RANGE
                by = py + math.sin(cur_ang) * FLASHLIGHT_RANGE
                cone_points.append((bx, by))

            pygame.draw.polygon(self.darkness_surf, (0, 0, 0, 0), cone_points)

        surface.blit(self.darkness_surf, (0, 0))

        # Soft warm light tint in beam
        if self.flashlight_on:
            beam_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(beam_overlay, (255, 245, 210, 16), cone_points)
            surface.blit(beam_overlay, (0, 0))

    # --------------------------------------------------------------------------
    # DRAW LOOP
    # --------------------------------------------------------------------------
    def draw(self):
        """Draws current frame based on active game state."""
        ox = random.randint(-self.shake_amount, self.shake_amount) if self.shake_amount > 0 else 0
        oy = random.randint(-self.shake_amount, self.shake_amount) if self.shake_amount > 0 else 0

        canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        canvas.fill((10, 8, 12))

        # ----------------- MENU STATE -----------------
        if self.state == STATE_MENU:
            canvas.fill((12, 10, 16))
            t1 = self.font_title.render("DON'T LOOK AWAY", True, (240, 230, 220))
            canvas.blit(t1, (SCREEN_WIDTH // 2 - t1.get_width() // 2, 160))

            t2 = self.font_msg.render("A Psychological Horror Experience", True, (160, 140, 130))
            canvas.blit(t2, (SCREEN_WIDTH // 2 - t2.get_width() // 2, 225))

            t_theme = self.font_hud.render("[ Theme: UNSTABLE ]", True, (180, 80, 80))
            canvas.blit(t_theme, (SCREEN_WIDTH // 2 - t_theme.get_width() // 2, 270))

            ctrl1 = self.font_hud.render("WASD : Move   |   Mouse : Aim   |   Click/F : Flashlight ON/OFF", True, (180, 180, 180))
            ctrl2 = self.font_hud.render("E : Open/Close Doors & Interact   |   R : Restart", True, (160, 160, 160))
            canvas.blit(ctrl1, (SCREEN_WIDTH // 2 - ctrl1.get_width() // 2, 360))
            canvas.blit(ctrl2, (SCREEN_WIDTH // 2 - ctrl2.get_width() // 2, 395))

            blink = int(pygame.time.get_ticks() / 500) % 2 == 0
            if blink:
                t_start = self.font_msg.render("PRESS [SPACE] TO BEGIN", True, (255, 220, 100))
                canvas.blit(t_start, (SCREEN_WIDTH // 2 - t_start.get_width() // 2, 470))

        # ----------------- INTRO STORY SCREEN (FADE IN NARRATOR) -----------------
        elif self.state == STATE_INTRO_STORY:
            canvas.fill((8, 6, 10))

            # Smooth fade in factor
            fade_factor = min(1.0, self.intro_timer / 1.4)
            text_alpha = int(255 * fade_factor)

            # Draw eerie border box
            box_rect = pygame.Rect(70, 50, SCREEN_WIDTH - 140, SCREEN_HEIGHT - 100)
            pygame.draw.rect(canvas, (25, 20, 25), box_rect)
            pygame.draw.rect(canvas, (75, 45, 45), box_rect, 2)

            # Header
            head_surf = self.font_hud.render("PROLOGUE — AN UNSTABLE PERCEPTION", True, (170, 75, 75))
            canvas.blit(head_surf, (SCREEN_WIDTH // 2 - head_surf.get_width() // 2, 75))

            # Narrative lines
            start_y = 135
            for i, line in enumerate(self.story_lines):
                if line:
                    is_last = (i >= len(self.story_lines) - 2)
                    color = (245, 120, 120) if is_last else (int(215 * fade_factor), int(210 * fade_factor), int(205 * fade_factor))
                    line_surf = self.font_narrator.render(line, True, color)
                    canvas.blit(line_surf, (SCREEN_WIDTH // 2 - line_surf.get_width() // 2, start_y))
                start_y += 34

            # Blinking continue prompt
            if self.intro_timer > 1.2:
                blink = int(pygame.time.get_ticks() / 500) % 2 == 0
                if blink:
                    t_wake = self.font_msg.render("[ PRESS SPACE TO WAKE UP ]", True, (255, 220, 100))
                    canvas.blit(t_wake, (SCREEN_WIDTH // 2 - t_wake.get_width() // 2, SCREEN_HEIGHT - 95))

        # ----------------- PLAYING & STORY STATES -----------------
        elif self.state in [STATE_PLAYING, STATE_ENDING_SEQUENCE]:
            # 1. Environment
            self.room.draw_environment(canvas, self.cam_x, self.cam_y, self.font_sm)

            # 2. Creature
            self.creature.draw(canvas, self.cam_x, self.cam_y)

            # 3. Player Sprite
            deg = -math.degrees(self.player_angle)
            rotated_player = pygame.transform.rotate(self.player_sprite, deg)
            screen_px = int(self.player_x - self.cam_x)
            screen_py = int(self.player_y - self.cam_y)
            rect = rotated_player.get_rect(center=(screen_px, screen_py))
            canvas.blit(rotated_player, rect.topleft)

            # 4. Lighting & Flashlight Beam
            self.render_lighting(canvas)

            # 5. Glowing eyes when frozen in beam
            if self.creature.is_active and self.creature.is_illuminated:
                cx = self.creature.pos[0] - self.cam_x
                cy = self.creature.pos[1] - self.cam_y
                pygame.draw.circle(canvas, (255, 255, 255), (int(cx - 4), int(cy - 14)), 2)
                pygame.draw.circle(canvas, (255, 255, 255), (int(cx + 4), int(cy - 14)), 2)
                pygame.draw.circle(canvas, (255, 60, 40), (int(cx - 4), int(cy - 14)), 1)
                pygame.draw.circle(canvas, (255, 60, 40), (int(cx + 4), int(cy - 14)), 1)

            # 6. HUD: Battery Indicator & Flashlight Status
            hud_bg = pygame.Surface((270, 52), pygame.SRCALPHA)
            hud_bg.fill((15, 15, 20, 190))
            canvas.blit(hud_bg, (20, 20))

            bat_bars = int(self.battery / 10.0)
            bar_str = "█" * bat_bars + "░" * (10 - bat_bars)
            bat_color = (100, 230, 120) if self.battery > 25 else (240, 70, 60)
            status_str = "ON" if self.flashlight_on else "OFF"
            bat_txt = self.font_hud.render(f"FLASHLIGHT [{bar_str}] {int(self.battery)}%", True, bat_color)
            toggle_txt = self.font_sm.render(f"Status: {status_str} [Click/F to Toggle]", True, (180, 180, 190))
            canvas.blit(bat_txt, (30, 28))
            canvas.blit(toggle_txt, (30, 48))

            # 7. Interaction Prompts
            px, py = self.player_x, self.player_y
            prompt = ""

            for d in self.room.doors:
                if math.hypot(px - d.closed_rect.centerx, py - d.closed_rect.centery) < 65:
                    if d.is_exit:
                        prompt = "[E] Open Exit Door" if self.room.has_key else "[E] Examine Locked Exit Door"
                    else:
                        prompt = "[E] Close Door" if d.is_open else f"[E] Open {d.name}"
                    break

            if not prompt and not self.room.key_collected:
                if math.hypot(px - self.room.key_rect.centerx, py - self.room.key_rect.centery) < 55:
                    prompt = "[E] Pick up Key"

            if not prompt:
                for b in self.room.batteries:
                    if not b["collected"] and math.hypot(px - b["rect"].centerx, py - b["rect"].centery) < 50:
                        prompt = "[E] Pick up Battery"
                        break

            if prompt:
                p_surf = self.font_hud.render(prompt, True, (255, 240, 150))
                p_bg = pygame.Surface((p_surf.get_width() + 18, p_surf.get_height() + 8), pygame.SRCALPHA)
                p_bg.fill((0, 0, 0, 195))
                bx = SCREEN_WIDTH // 2 - p_bg.get_width() // 2
                canvas.blit(p_bg, (bx, SCREEN_HEIGHT - 65))
                canvas.blit(p_surf, (bx + 9, SCREEN_HEIGHT - 61))

            # 8. Narrative / Objective Message Banner
            if self.current_message:
                m_surf = self.font_msg.render(self.current_message, True, (245, 245, 245))
                m_bg = pygame.Surface((m_surf.get_width() + 28, m_surf.get_height() + 14), pygame.SRCALPHA)
                m_bg.fill((10, 10, 15, 220))
                pygame.draw.rect(m_bg, (180, 50, 50), (0, 0, m_bg.get_width(), m_bg.get_height()), 1)
                mx = SCREEN_WIDTH // 2 - m_bg.get_width() // 2
                canvas.blit(m_bg, (mx, 26))
                canvas.blit(m_surf, (mx + 14, 33))

        # ----------------- JUMPSCARE STATE -----------------
        elif self.state == STATE_JUMPSCARE:
            if random.random() < 0.35:
                canvas.fill((220, 20, 20))
            elif random.random() < 0.2:
                canvas.fill((255, 255, 255))
            else:
                canvas.fill((5, 5, 8))

            canvas.blit(self.jumpscare_sprite, (0, 0))
            t_scare = self.font_msg.render("YOU SHOULD HAVE LOOKED BACK.", True, (255, 255, 255))
            canvas.blit(t_scare, (SCREEN_WIDTH // 2 - t_scare.get_width() // 2, SCREEN_HEIGHT - 75))

        # ----------------- AMBIGUOUS ENDING STATE -----------------
        elif self.state == STATE_AMBIGUOUS_ENDING:
            canvas.fill((4, 4, 6))
            alpha_factor = min(1.0, self.state_timer / 2.0)
            text_color = (int(220 * alpha_factor), int(215 * alpha_factor), int(210 * alpha_factor))

            t_end = self.font_msg.render("There was never anyone else in the room.", True, text_color)
            canvas.blit(t_end, (SCREEN_WIDTH // 2 - t_end.get_width() // 2, SCREEN_HEIGHT // 2 - 40))

            if self.state_timer >= 2.5:
                sub_color = (150, 150, 150)
                t_sub = self.font_hud.render("Press [R] to Play Again   |   [ESC] to Quit", True, sub_color)
                canvas.blit(t_sub, (SCREEN_WIDTH // 2 - t_sub.get_width() // 2, SCREEN_HEIGHT // 2 + 30))

        # Blit canvas to screen with shake offset
        self.screen.fill((0, 0, 0))
        self.screen.blit(canvas, (ox, oy))
        pygame.display.flip()

    # --------------------------------------------------------------------------
    # MAIN APPLICATION RUN LOOP
    # --------------------------------------------------------------------------
    def run(self):
        """Main game loop handling events and constant 60 FPS tick."""
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

                    elif event.key == pygame.K_r:
                        self.reset_game()
                        self.state = STATE_PLAYING

                    elif event.key == pygame.K_SPACE:
                        if self.state == STATE_MENU:
                            # Move to narrative prologue story screen
                            self.state = STATE_INTRO_STORY
                            self.intro_timer = 0.0
                        elif self.state == STATE_INTRO_STORY:
                            # Wake up into gameplay!
                            self.state = STATE_PLAYING
                            self.show_message("FIND THE KEY TO ESCAPE.", 4.0)

                    elif event.key == pygame.K_e:
                        if self.state == STATE_PLAYING:
                            self.handle_interaction()

                    elif event.key == pygame.K_f:
                        if self.state == STATE_PLAYING:
                            self.toggle_flashlight()

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.state == STATE_MENU:
                        self.state = STATE_INTRO_STORY
                        self.intro_timer = 0.0
                    elif self.state == STATE_INTRO_STORY:
                        self.state = STATE_PLAYING
                        self.show_message("FIND THE KEY TO ESCAPE.", 4.0)
                    elif self.state == STATE_PLAYING:
                        if event.button in [1, 3]:  # Left or Right Click toggles flashlight
                            self.toggle_flashlight()

            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    game = GameEngine()
    game.run()
