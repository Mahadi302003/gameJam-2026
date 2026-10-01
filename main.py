"""
================================================================================
DON'T LOOK AWAY - Psychological Horror Experience
GameJam Theme: "UNSTABLE" (Protagonist's Unreliable Perception)
================================================================================

Controls:
- W, A, S, D       : Move protagonist
- Mouse Cursor     : Aim flashlight beam
- Left-Click / F   : Toggle Flashlight ON / OFF
- E                : Interact (Search furniture, drawers, bookshelves, read notes, open doors)
- R                : Full Restart
- ESC              : Quit
- F1               : Debug HUD Toggle
- F2               : Debug Force Next Instability Event
- F3               : Debug Give Key + ID immediately
"""

import sys
import os
import math
import random
import io
import struct
import wave
import pygame
from assets import AssetManager
from sound import AudioManager

# ==============================================================================
# 1. GAMEPLAY CONFIGURATION & DIFFICULTY TUNING
# ==============================================================================
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
FPS = 60

# World Size
WORLD_WIDTH = 1500
WORLD_HEIGHT = 1050

# Player settings
PLAYER_SPEED = 3.3           # Pixels per frame (WASD movement speed)
PLAYER_SIZE = 24             # Bounding box width/height for collision

# Flashlight mechanics (Narrower, more focused beam for higher tension)
FLASHLIGHT_ANGLE = 54        # Beam cone angle in degrees (tight, focused)
FLASHLIGHT_RANGE = 350       # Beam reach in pixels
FLASHLIGHT_BATTERY = 100.0   # Starting battery percentage (0 to 100)
BATTERY_DRAIN = 0.65         # Battery % drained per second while ON (~155s light)
BATTERY_REFILL = 50.0        # Battery % restored per battery pickup

# Instability System Tuning (0 to 100)
INSTABILITY_RISE_RATE = 0.22 # Base rise in instability per second
INSTABILITY_NOTE_BOOST = 15.0 # Rise when Note is read
INSTABILITY_ID_BOOST = 20.0   # Rise when ID is found
INSTABILITY_KEY_BOOST = 15.0  # Rise when Key is found

# --- Interaction & Discoverability (tweak these if searching feels too easy/hard) ---
INTERACT_RANGE = 46          # Max distance (px) from the EDGE of an object to interact with it
SENSE_RADIUS = 190           # Interactable objects glint in the dark within this distance
HINT_DELAY = 35.0            # Seconds without progress before story objects glint from far away
HINT_SENSE_RADIUS = 620      # How far away the hint glint can be seen
AMBIENT_SIGHT_RADIUS = 96    # Soft dim light around the player so nearby furniture is readable

# Creature mechanics (Freeze in light, move when unlit)
CREATURE_MOVE_DELAY = 1.8    # Base seconds unseen before creature relocates
CREATURE_AGGRO_DELAY = 1.0   # Fast relocation once items are found
CREATURE_ATTACK_DIST = 46    # Proximity threshold for game over in total darkness
BLACKOUT_KILL_TIME = 4.5     # Seconds of total darkness before forced jumpscare

# Game States
STATE_MENU = "MENU"
STATE_INTRO_STORY = "INTRO_STORY"
STATE_PLAYING = "PLAYING"
STATE_READING_NOTE = "READING_NOTE"
STATE_READING_ID = "READING_ID"
STATE_ENDING_ESCAPE = "ENDING_ESCAPE"
STATE_JUMPSCARE = "JUMPSCARE"
STATE_AMBIGUOUS_ENDING = "AMBIGUOUS_ENDING"
STATE_GAME_OVER = "GAME_OVER"


# Room name detection for the banner system (matches GameRoom wall layout)
def get_room_name(x, y):
    """Returns current room name based on world position."""
    if y < 450:
        return "Bedroom" if x < 700 else "Study"
    elif y < 610:
        return "Hallway"
    else:
        return "Storage" if x < 700 else "Foyer"


# ==============================================================================
# 2. AUDIO SYSTEM & PROCEDURAL SYNTHESIS (Zero External Dependency Fallback)
# ==============================================================================
AUDIO_INITIALIZED = False
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    AUDIO_INITIALIZED = True
except Exception:
    AUDIO_INITIALIZED = False


def _synthesize_wav(samples, sample_rate=22050, channels=1):
    """Helper to convert audio samples into a Pygame Sound via BytesIO wave."""
    if not AUDIO_INITIALIZED:
        return None
    try:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            raw = b''.join(struct.pack('<h', max(-32767, min(32767, int(s)))) for s in samples)
            w.writeframes(raw)
        buf.seek(0)
        return pygame.mixer.Sound(buf)
    except Exception:
        return None


def generate_sound(name):
    """Generates procedural sound effects without external files."""
    rate = 22050
    if not AUDIO_INITIALIZED:
        return None

    try:
        if name == "drone":
            duration = int(rate * 3.0)
            samples = []
            for i in range(duration):
                t = i / rate
                s1 = math.sin(2 * math.pi * 55 * t) * 0.5
                s2 = math.sin(2 * math.pi * 110 * t) * 0.3
                s3 = math.sin(2 * math.pi * 165 * t) * 0.15
                noise = (random.random() * 2 - 1) * 0.05
                val = (s1 + s2 + s3 + noise) * 14000
                samples.append(val)
            return _synthesize_wav(samples, rate)

        elif name == "whisper":
            duration = int(rate * 0.45)
            samples = [
                (random.random() * 2 - 1) * math.sin(math.pi * i / duration) * math.exp(-i / (rate * 0.2)) * 12000
                for i in range(duration)
            ]
            return _synthesize_wav(samples, rate)

        elif name == "drawer_open":
            # Wooden drawer or shelf sliding open
            duration = int(rate * 0.35)
            samples = []
            for i in range(duration):
                t = i / rate
                freq = 120 + 30 * math.sin(2 * math.pi * 6 * t)
                s = math.sin(2 * math.pi * freq * t) * 0.4
                noise = (random.random() * 2 - 1) * 0.6
                env = math.sin(math.pi * i / duration)
                val = (s + noise) * env * 12000
                samples.append(val)
            return _synthesize_wav(samples, rate)

        elif name == "click":
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
            duration = int(rate * 1.5)
            samples = []
            for i in range(duration):
                t = i / rate
                freq = max(180, 1500 - t * 650)
                screech = (
                    math.sin(2 * math.pi * freq * t)
                    + 0.6 * math.sin(2 * math.pi * (freq * 1.414) * t)
                    + 0.5 * math.sin(2 * math.pi * (freq * 0.73) * t)
                )
                bass = math.sin(2 * math.pi * 45 * t) * math.exp(-t / 0.4) * 2.0
                noise = (random.random() * 2 - 1) * (0.7 if t < 0.5 else 0.3)
                env = math.exp(-t / 1.0) if t > 0.1 else (t / 0.1)
                val = (screech * 0.45 + bass * 0.35 + noise * 0.3) * env * 24000
                samples.append(val)
            return _synthesize_wav(samples, rate)

    except Exception:
        return None
    return None


# AudioManager is imported from sound.py at the top of main.py


# ==============================================================================
# 3. PROCEDURAL SPRITES & ASSETS
# ==============================================================================
def create_player_surface():
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(surf, (35, 45, 55), (16, 16), 11)
    pygame.draw.circle(surf, (20, 25, 30), (16, 16), 11, 2)
    pygame.draw.circle(surf, (215, 180, 150), (16, 16), 6)
    pygame.draw.circle(surf, (40, 25, 20), (16, 14), 6)
    pygame.draw.rect(surf, (180, 180, 190), (22, 18, 8, 4))
    pygame.draw.rect(surf, (255, 240, 120), (28, 17, 3, 6))
    return surf


def create_creature_poses():
    poses = []
    # Pose 0: Normal tall silhouette, arms down
    s0 = pygame.Surface((44, 56), pygame.SRCALPHA)
    pygame.draw.ellipse(s0, (15, 12, 18), (15, 14, 14, 34))
    pygame.draw.line(s0, (18, 14, 22), (15, 18), (6, 44), 3)
    pygame.draw.line(s0, (18, 14, 22), (29, 18), (38, 44), 3)
    pygame.draw.ellipse(s0, (18, 15, 22), (14, 4, 16, 18))
    pygame.draw.circle(s0, (255, 245, 210), (18, 11), 2)
    pygame.draw.circle(s0, (255, 245, 210), (26, 11), 2)
    poses.append(s0)

    # Pose 1: Head sharply tilted, one claw raised
    s1 = pygame.Surface((44, 56), pygame.SRCALPHA)
    pygame.draw.ellipse(s1, (15, 12, 18), (15, 14, 14, 34))
    pygame.draw.line(s1, (18, 14, 22), (15, 18), (4, 30), 3)
    pygame.draw.line(s1, (18, 14, 22), (29, 18), (38, 46), 3)
    pygame.draw.ellipse(s1, (18, 15, 22), (18, 4, 18, 16))
    pygame.draw.circle(s1, (255, 245, 210), (22, 10), 2)
    pygame.draw.circle(s1, (255, 245, 210), (29, 12), 2)
    poses.append(s1)

    # Pose 2: Predatory crouch, both claws reaching
    s2 = pygame.Surface((44, 56), pygame.SRCALPHA)
    pygame.draw.ellipse(s2, (15, 12, 18), (12, 18, 20, 28))
    pygame.draw.line(s2, (18, 14, 22), (12, 22), (2, 48), 3)
    pygame.draw.line(s2, (18, 14, 22), (32, 22), (42, 48), 3)
    pygame.draw.ellipse(s2, (18, 15, 22), (14, 8, 16, 16))
    pygame.draw.circle(s2, (255, 245, 210), (18, 14), 2)
    pygame.draw.circle(s2, (255, 245, 210), (26, 14), 2)
    poses.append(s2)

    # Pose 3: Towering twisted silhouette
    s3 = pygame.Surface((44, 56), pygame.SRCALPHA)
    pygame.draw.ellipse(s3, (12, 8, 15), (14, 12, 16, 38))
    pygame.draw.line(s3, (15, 10, 18), (14, 16), (2, 34), 3)
    pygame.draw.line(s3, (15, 10, 18), (30, 16), (42, 34), 3)
    pygame.draw.ellipse(s3, (15, 10, 18), (13, 2, 18, 18))
    pygame.draw.circle(s3, (255, 255, 255), (17, 9), 3)
    pygame.draw.circle(s3, (255, 255, 255), (27, 9), 3)
    pygame.draw.circle(s3, (255, 40, 30), (17, 9), 1)
    pygame.draw.circle(s3, (255, 40, 30), (27, 9), 1)
    poses.append(s3)

    return poses


def create_jumpscare_surface():
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
    w, h = 64, 40
    try:
        assets = AssetManager.get_instance()
        p_norm = assets.sprites.get('portrait_normal')
        p_corr = assets.sprites.get('portrait_corrupt')
    except Exception:
        p_norm, p_corr = None, None

    if p_norm and p_corr:
        s0 = pygame.Surface((w, h))
        s0.fill((110, 80, 50))
        pygame.draw.rect(s0, (40, 28, 20), (2, 2, w - 4, h - 4), 2)
        norm_sc = pygame.transform.scale(p_norm, (w - 8, h - 8))
        s0.blit(norm_sc, (4, 4))

        s1 = s0.copy()
        pygame.draw.circle(s1, (255, 255, 255), (w // 2 - 4, h // 2 - 3), 3)
        pygame.draw.circle(s1, (255, 255, 255), (w // 2 + 4, h // 2 - 3), 3)
        pygame.draw.circle(s1, (220, 0, 0), (w // 2 - 4, h // 2 - 3), 1)
        pygame.draw.circle(s1, (220, 0, 0), (w // 2 + 4, h // 2 - 3), 1)

        s2 = pygame.Surface((w, h))
        s2.fill((90, 65, 40))
        pygame.draw.rect(s2, (25, 18, 15), (2, 2, w - 4, h - 4), 2)
        corr_sc = pygame.transform.scale(p_corr, (w - 8, h - 8))
        s2.blit(corr_sc, (4, 4))

        s3 = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.line(s3, (40, 20, 20), (8, 6), (56, 34), 2)
        pygame.draw.line(s3, (40, 20, 20), (14, 32), (50, 10), 2)
        pygame.draw.line(s3, (50, 15, 15), (28, 4), (36, 36), 1)
        return [s0, s1, s2, s3]

    # Fallback procedural
    s0 = pygame.Surface((w, h))
    s0.fill((110, 80, 50))
    pygame.draw.rect(s0, (50, 40, 35), (4, 4, w - 8, h - 8))
    pygame.draw.circle(s0, (160, 140, 120), (w // 2, h // 2 - 2), 10)
    pygame.draw.circle(s0, (70, 50, 40), (w // 2, h // 2 - 6), 10)
    pygame.draw.rect(s0, (30, 25, 20), (w // 2 - 5, h // 2 - 3, 2, 2))
    pygame.draw.rect(s0, (30, 25, 20), (w // 2 + 1, h // 2 - 3, 2, 2))

    s1 = pygame.Surface((w, h))
    s1.fill((100, 70, 45))
    pygame.draw.rect(s1, (45, 30, 30), (4, 4, w - 8, h - 8))
    pygame.draw.circle(s1, (180, 160, 140), (w // 2, h // 2 - 2), 10)
    pygame.draw.circle(s1, (50, 30, 30), (w // 2, h // 2 - 6), 10)
    pygame.draw.circle(s1, (255, 255, 255), (w // 2 - 4, h // 2 - 3), 3)
    pygame.draw.circle(s1, (255, 255, 255), (w // 2 + 4, h // 2 - 3), 3)
    pygame.draw.circle(s1, (180, 0, 0), (w // 2 - 4, h // 2 - 3), 1)
    pygame.draw.circle(s1, (180, 0, 0), (w // 2 + 4, h // 2 - 3), 1)

    s2 = pygame.Surface((w, h))
    s2.fill((70, 45, 30))
    pygame.draw.rect(s2, (20, 15, 20), (4, 4, w - 8, h - 8))
    pygame.draw.ellipse(s2, (5, 5, 8), (w // 2 - 10, h // 2 - 12, 20, 24))

    s3 = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.line(s3, (40, 20, 20), (8, 6), (56, 34), 2)
    pygame.draw.line(s3, (40, 20, 20), (14, 32), (50, 10), 2)
    pygame.draw.line(s3, (50, 15, 15), (28, 4), (36, 36), 1)
    return [s0, s1, s2, s3]


# ==============================================================================
# 4. INTERACTIVE DOORS
# ==============================================================================
class InteractiveDoor:
    """Interior room doors start OPEN by default. The Exit door is locked."""
    def __init__(self, x, y, width, height, is_exit=False, is_open=True, name="Door"):
        self.closed_rect = pygame.Rect(x, y, width, height)
        self.is_open = is_open
        self.is_exit = is_exit
        self.name = name

    def toggle(self):
        if not self.is_exit:
            self.is_open = not self.is_open

    def get_solid_collider(self):
        if self.is_open:
            return None
        return self.closed_rect

    def draw(self, surface, cam_x, cam_y, assets=None):
        if assets is None:
            try:
                assets = AssetManager.get_instance()
            except Exception:
                assets = None

        sx = self.closed_rect.x - cam_x
        sy = self.closed_rect.y - cam_y
        w, h = self.closed_rect.width, self.closed_rect.height

        # Visual jambs
        pygame.draw.rect(surface, (35, 25, 20), (sx - 3, sy, 4, h))
        pygame.draw.rect(surface, (35, 25, 20), (sx + w - 1, sy, 4, h))

        if self.is_exit:
            exit_spr = assets.sprites.get('exit_door') if assets else None
            if exit_spr:
                scaled_exit = pygame.transform.scale(exit_spr, (w, max(h, 44)))
                surface.blit(scaled_exit, (sx, sy - 8))
            else:
                color = (65, 85, 65) if self.is_open else (90, 45, 45)
                pygame.draw.rect(surface, color, (sx, sy, w, h))
                pygame.draw.rect(surface, (25, 25, 25), (sx, sy, w, h), 2)
                pygame.draw.circle(surface, (220, 190, 80), (sx + w // 2, sy + h // 2), 4)

            sign = assets.sprites.get('exit_sign_red') if assets else None
            if sign:
                surface.blit(sign, (sx + (w - sign.get_width()) // 2, sy - 24))
        else:
            if not self.is_open:
                door_spr = assets.sprites.get('door_wood') if assets else None
                if door_spr:
                    scaled_d = pygame.transform.scale(door_spr, (w, max(h, 28)))
                    surface.blit(scaled_d, (sx, sy))
                else:
                    pygame.draw.rect(surface, (110, 80, 55), (sx, sy, w, h))
                    pygame.draw.rect(surface, (55, 38, 25), (sx, sy, w, h), 2)
                    knob_x = sx + (w - 8 if w > h else w // 2)
                    knob_y = sy + (h // 2 if w > h else h - 8)
                    pygame.draw.circle(surface, (215, 185, 75), (knob_x, knob_y), 3)
            else:
                open_spr = assets.sprites.get('door_dark_open') if assets else None
                if open_spr:
                    scaled_o = pygame.transform.scale(open_spr, (24, max(h, 28)))
                    surface.blit(scaled_o, (sx - 18, sy - 6))
                else:
                    swung_rect = (sx - 4, sy - h, 8, h + 4) if w > h else (sx - w, sy - 4, w + 4, 8)
                    pygame.draw.rect(surface, (95, 68, 44), swung_rect)
                    pygame.draw.rect(surface, (45, 30, 20), swung_rect, 1)


# ==============================================================================
# 5. MULTI-ROOM ENVIRONMENT & SEARCHABLE FURNITURE
# ==============================================================================
class GameRoom:
    """Manages rooms, searchable furniture, dynamic objects, and items."""
    def __init__(self):
        self.assets = AssetManager.get_instance()
        self.house_rect = pygame.Rect(100, 80, 1300, 880)
        self._build_floor_cache()

        # Static Walls
        self.static_walls = [
            pygame.Rect(100, 80, 1300, 18),
            pygame.Rect(100, 942, 1300, 18),
            pygame.Rect(100, 80, 18, 880),
            pygame.Rect(1382, 80, 18, 880),
            pygame.Rect(690, 80, 18, 360),
            pygame.Rect(690, 600, 18, 360),
            pygame.Rect(100, 440, 260, 18),
            pygame.Rect(430, 440, 550, 18),
            pygame.Rect(1050, 440, 350, 18),
            pygame.Rect(100, 600, 260, 18),
            pygame.Rect(430, 600, 550, 18),
            pygame.Rect(1050, 600, 350, 18),
        ]

        # Room doors are OPEN by default
        self.doors = [
            InteractiveDoor(360, 440, 70, 18, is_exit=False, is_open=True, name="Bedroom Door"),
            InteractiveDoor(980, 440, 70, 18, is_exit=False, is_open=True, name="Study Door"),
            InteractiveDoor(360, 600, 70, 18, is_exit=False, is_open=True, name="Storage Door"),
            InteractiveDoor(980, 600, 70, 18, is_exit=False, is_open=True, name="Foyer Door"),
            # Main Exit Door is locked
            InteractiveDoor(980, 942, 80, 18, is_exit=True, is_open=False, name="Main Exit Door"),
        ]

        # --- SEARCHABLE FURNITURE & OBJECTS ---
        # 1. Bedroom (Top-Left)
        self.bed_rect = pygame.Rect(140, 110, 120, 160)
        self.nightstand_rect = pygame.Rect(270, 110, 45, 45)
        self.wardrobe_rect = pygame.Rect(610, 110, 60, 150)
        self.nightstand_searched = False
        self.wardrobe_searched = False

        # UNSTABLE: Moving Chair
        self.chair_stage = 0
        self.chair_positions = [(400, 200), (310, 310), (280, 230), (360, 370)]
        self.chair_pos = list(self.chair_positions[0])
        self.chair_rect = pygame.Rect(self.chair_pos[0], self.chair_pos[1], 28, 28)

        # UNSTABLE: Painting (4 states)
        self.painting_rect = pygame.Rect(1000, 82, 64, 40)
        self.painting_surfs = create_painting_surfaces()
        self.painting_state = 0

        # UNSTABLE: Vanishing Study Cup
        self.cup_visible = True
        self.cup_pos = (1160, 135)

        # UNSTABLE: Appearing Shoes by Bed
        self.shoes_visible = False
        self.shoes_pos = (265, 230)

        # UNSTABLE: Fake Door in Hallway
        self.fake_door_visible = False
        self.fake_door_rect = pygame.Rect(100, 500, 18, 65)

        # UNSTABLE: False Glinting Key
        self.false_key_visible = False
        self.false_key_rect = pygame.Rect(580, 550, 18, 18)
        self.false_key_used = False

        # UNSTABLE: Bed Lump
        self.bed_lump = False

        # UNSTABLE: Wall Graffiti lines
        self.graffiti_lines = [
            {"text": "DON'T LET IT GO DARK.", "pos": (440, 624), "visible": True},
            {"text": "STOP LOOKING", "pos": (140, 410), "visible": False},
            {"text": "LOOK BEHIND YOU", "pos": (880, 410), "visible": False},
            {"text": "IT WAS ALWAYS ME.", "pos": (450, 920), "visible": False},
        ]

        # 2. Study & Gallery (Top-Right)
        self.study_desk_rect = pygame.Rect(1140, 120, 160, 75)
        self.study_desk_searched = False

        # Bookshelves (Where the Key is hidden inside a hollow book!)
        self.bookshelf_1 = pygame.Rect(730, 110, 140, 36)
        self.bookshelf_2 = pygame.Rect(730, 170, 140, 36)
        self.bookshelf_searched = False
        self.study_table = pygame.Rect(940, 260, 90, 50)

        # 3. Storage Room (Bottom-Left)
        self.storage_crate_1 = pygame.Rect(140, 650, 70, 70)
        self.storage_crate_1_searched = False
        self.storage_crate_2 = pygame.Rect(140, 820, 90, 70)

        # Storage Shelf (Where the ID Card is hidden behind binders!)
        self.storage_shelf = pygame.Rect(520, 820, 140, 40)
        self.storage_shelf_searched = False
        self.storage_crate_2_searched = False
        self.bookshelf_2_searched = False
        self.foyer_table_searched = False

        # 4. Exit Foyer (Bottom-Right)
        self.foyer_table = pygame.Rect(730, 700, 50, 90)
        self.foyer_shelf = pygame.Rect(1280, 680, 45, 90)

        # COLLECTIBLE 1: Note on Bedroom Nightstand
        self.note_rect = pygame.Rect(280, 125, 24, 20)
        self.note_read = False

        # COLLECTIBLE 2: Resident ID Card (Hidden in Storage Shelf!)
        self.id_revealed = False
        self.id_collected = False

        # COLLECTIBLE 3: Real Key (Hidden inside Study Bookshelf!)
        self.key_revealed = False
        self.key_collected = False
        self.has_key = False

        # Batteries (Hidden in furniture/crates)
        self.batteries = [
            {"rect": pygame.Rect(280, 112, 18, 18), "collected": False, "revealed": False, "room": "Bedroom"},
            {"rect": pygame.Rect(165, 680, 18, 18), "collected": False, "revealed": False, "room": "Storage"},
            {"rect": pygame.Rect(1292, 700, 18, 18), "collected": False, "revealed": True, "room": "Foyer"},
        ]

    def reset_to_tidy_state(self):
        """Resets furniture to pristine normal positions."""
        self.chair_stage = 0
        self.chair_pos = list(self.chair_positions[0])
        self.chair_rect.topleft = self.chair_pos
        self.painting_state = 0
        self.cup_visible = True
        self.shoes_visible = False
        self.fake_door_visible = False
        self.bed_lump = False

    def _build_floor_cache(self):
        self.floor_cache = pygame.Surface((self.house_rect.width, self.house_rect.height))
        self.floor_cache.fill((30, 24, 20))

        def tile_box(tex, rx, ry, rw, rh):
            if not tex:
                return
            tw, th = tex.get_size()
            for y in range(0, rh, th):
                for x in range(0, rw, tw):
                    sub_w = min(tw, rw - x)
                    sub_h = min(th, rh - y)
                    self.floor_cache.blit(tex, (rx + x, ry + y), (0, 0, sub_w, sub_h))

        # Relative to house_rect.topleft (100, 80)
        # Bedroom: top-left (0, 0, 590, 360)
        tile_box(self.assets.floors.get('bedroom'), 0, 0, 590, 360)
        # Study / Living: top-right (590, 0, 710, 360)
        tile_box(self.assets.floors.get('living'), 590, 0, 710, 360)
        # Hallway: middle (0, 360, 1300, 160)
        tile_box(self.assets.floors.get('corridor'), 0, 360, 1300, 160)
        # Storage: bottom-left (0, 520, 590, 360)
        tile_box(self.assets.floors.get('storage'), 0, 520, 590, 360)
        # Foyer: bottom-right (590, 520, 710, 360)
        tile_box(self.assets.floors.get('living_dark'), 590, 520, 710, 360)

    def get_solid_colliders(self):
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

    def draw_environment(self, surface, cam_x, cam_y, font_sm, font_hand, instability_breathing=0):
        bx_off = math.sin(instability_breathing) * 1.5 if instability_breathing > 0 else 0
        by_off = math.cos(instability_breathing) * 1.5 if instability_breathing > 0 else 0

        # 1. Floorboards from cache
        if hasattr(self, 'floor_cache'):
            surface.blit(self.floor_cache, (self.house_rect.x - cam_x, self.house_rect.y - cam_y))
        else:
            floor_color_1 = (40, 32, 26)
            floor_color_2 = (35, 28, 22)
            for y in range(self.house_rect.top, self.house_rect.bottom, 24):
                sy = y - cam_y
                if -30 <= sy <= SCREEN_HEIGHT + 30:
                    color = floor_color_1 if ((y // 24) % 2 == 0) else floor_color_2
                    sx = self.house_rect.left - cam_x
                    pygame.draw.rect(surface, color, (sx, sy, self.house_rect.width, 24))

        # 2. Subtle Floor Decals, Blood & Clutter
        blood_scratch = self.assets.sprites.get('blood_scratches')
        if blood_scratch:
            surface.blit(blood_scratch, (280 - cam_x, 620 - cam_y))
            surface.blit(blood_scratch, (630 - cam_x, 780 - cam_y))

        blood_hand = self.assets.sprites.get('blood_handprint')
        if blood_hand:
            surface.blit(blood_hand, (230 - cam_x, 520 - cam_y))
            surface.blit(blood_hand, (530 - cam_x, 260 - cam_y))

        blood_drip = self.assets.sprites.get('blood_drips')
        if blood_drip:
            surface.blit(blood_drip, (720 - cam_x, 435 - cam_y))

        doormat = self.assets.sprites.get('entry_doormat')
        if doormat:
            surface.blit(doormat, (985 - cam_x, 915 - cam_y))

        # 3. Static Walls
        brick_tile = self.assets.walls.get('brick')
        tw, th = brick_tile.get_size() if brick_tile else (32, 32)
        for w in self.static_walls:
            sx = w.x - cam_x + bx_off
            sy = w.y - cam_y + by_off
            if brick_tile:
                for y in range(0, w.h, th):
                    for x in range(0, w.w, tw):
                        sub_w = min(tw, w.w - x)
                        sub_h = min(th, w.h - y)
                        surface.blit(brick_tile, (sx + x, sy + y), (0, 0, sub_w, sub_h))
            else:
                pygame.draw.rect(surface, (55, 48, 44), (sx, sy, w.w, w.h))
            pygame.draw.rect(surface, (25, 18, 14), (sx, sy, w.w, w.h), 2)

        # 4. Interactive Doors
        for d in self.doors:
            d.draw(surface, cam_x, cam_y, self.assets)

        # 5. Fake Door Wrongness
        if self.fake_door_visible:
            fdx = self.fake_door_rect.x - cam_x
            fdy = self.fake_door_rect.y - cam_y
            pygame.draw.rect(surface, (60, 40, 35), (fdx, fdy, self.fake_door_rect.w, self.fake_door_rect.h))
            pygame.draw.rect(surface, (30, 15, 15), (fdx, fdy, self.fake_door_rect.w, self.fake_door_rect.h), 2)
            pygame.draw.circle(surface, (180, 150, 60), (fdx + 10, fdy + self.fake_door_rect.h // 2), 3)

        # 6. Graffiti Lines
        for g in self.graffiti_lines:
            if g["visible"]:
                gx = g["pos"][0] - cam_x
                gy = g["pos"][1] - cam_y
                gsurf = font_hand.render(g["text"], True, (140, 75, 75))
                surface.blit(gsurf, (gx, gy))

        # --- BEDROOM ---
        bx, by = self.bed_rect.x - cam_x, self.bed_rect.y - cam_y
        bed_spr = self.assets.sprites.get('bed_unmade' if self.bed_lump else 'bed_brown')
        if bed_spr:
            scaled_bed = pygame.transform.scale(bed_spr, (self.bed_rect.w, self.bed_rect.h))
            surface.blit(scaled_bed, (bx, by))
        else:
            pygame.draw.rect(surface, (75, 52, 38), (bx, by, self.bed_rect.w, self.bed_rect.h))
            pygame.draw.rect(surface, (135, 125, 115), (bx + 6, by + 6, self.bed_rect.w - 12, self.bed_rect.h - 12))

        # Nightstand
        nx, ny = self.nightstand_rect.x - cam_x, self.nightstand_rect.y - cam_y
        pygame.draw.rect(surface, (65, 45, 32), (nx, ny, self.nightstand_rect.w, self.nightstand_rect.h))
        pygame.draw.rect(surface, (35, 22, 16), (nx, ny, self.nightstand_rect.w, self.nightstand_rect.h), 2)
        clock_spr = self.assets.sprites.get('alarm_clock')
        if clock_spr:
            surface.blit(clock_spr, (nx + 6, ny + 8))
        pygame.draw.rect(surface, (62, 44, 30), (nx + 4, ny + 24, self.nightstand_rect.w - 8, 16))
        pygame.draw.rect(surface, (35, 24, 16), (nx + 4, ny + 24, self.nightstand_rect.w - 8, 16), 1)
        pygame.draw.circle(surface, (215, 185, 75), (nx + self.nightstand_rect.w // 2, ny + 32), 3)
        if self.nightstand_searched:
            pygame.draw.rect(surface, (8, 5, 3), (nx + 4, ny + 38, self.nightstand_rect.w - 8, 5))

        # Note on Nightstand (if unread)
        if not self.note_read:
            note_spr = self.assets.sprites.get('note_paper')
            if note_spr:
                surface.blit(note_spr, (self.note_rect.x - cam_x, self.note_rect.y - cam_y))
            else:
                ntx, nty = self.note_rect.x - cam_x, self.note_rect.y - cam_y
                pygame.draw.rect(surface, (230, 225, 210), (ntx, nty, self.note_rect.w, self.note_rect.h))

        # Wardrobe
        wx, wy = self.wardrobe_rect.x - cam_x, self.wardrobe_rect.y - cam_y
        wardrobe_key = 'wardrobe_eyes' if (self.wardrobe_searched or self.has_key) else 'wardrobe_closed'
        wardrobe_spr = self.assets.sprites.get(wardrobe_key)
        if wardrobe_spr:
            scaled_w = pygame.transform.scale(wardrobe_spr, (self.wardrobe_rect.w, self.wardrobe_rect.h))
            surface.blit(scaled_w, (wx, wy))
        else:
            pygame.draw.rect(surface, (68, 44, 28), (wx, wy, self.wardrobe_rect.w, self.wardrobe_rect.h))

        # Moving Chair
        cx, cy = self.chair_rect.x - cam_x, self.chair_rect.y - cam_y
        chair_key = 'dining_chair_fallen' if self.chair_stage >= 3 else 'dining_chair'
        chair_spr = self.assets.sprites.get(chair_key)
        if chair_spr:
            scaled_chair = pygame.transform.scale(chair_spr, (self.chair_rect.w, self.chair_rect.h))
            surface.blit(scaled_chair, (cx, cy))
        else:
            pygame.draw.rect(surface, (105, 72, 48), (cx, cy, self.chair_rect.w, self.chair_rect.h))

        if self.shoes_visible:
            sx, sy = self.shoes_pos[0] - cam_x, self.shoes_pos[1] - cam_y
            pygame.draw.ellipse(surface, (30, 20, 15), (sx, sy, 8, 14))
            pygame.draw.ellipse(surface, (30, 20, 15), (sx + 11, sy, 8, 14))

        # --- STUDY ---
        dx, dy = self.study_desk_rect.x - cam_x, self.study_desk_rect.y - cam_y
        pygame.draw.rect(surface, (85, 58, 38), (dx, dy, self.study_desk_rect.w, self.study_desk_rect.h))
        pygame.draw.rect(surface, (45, 28, 18), (dx, dy, self.study_desk_rect.w, self.study_desk_rect.h), 2)
        note_spr = self.assets.sprites.get('note_paper')
        if note_spr:
            surface.blit(note_spr, (dx + 15, dy + 15))
            surface.blit(note_spr, (dx + 48, dy + 20))
        for i in range(2):
            drx = dx + 12 + i * 76
            pygame.draw.rect(surface, (70, 49, 33), (drx, dy + self.study_desk_rect.h - 22, 60, 17))
            pygame.draw.rect(surface, (40, 27, 18), (drx, dy + self.study_desk_rect.h - 22, 60, 17), 1)
            pygame.draw.circle(surface, (215, 185, 75), (drx + 30, dy + self.study_desk_rect.h - 14), 3)

        if self.cup_visible:
            cup_spr = self.assets.sprites.get('mug_blue')
            if cup_spr:
                surface.blit(cup_spr, (self.cup_pos[0] - cam_x - 8, self.cup_pos[1] - cam_y - 8))
            else:
                cpx, cpy = self.cup_pos[0] - cam_x, self.cup_pos[1] - cam_y
                pygame.draw.circle(surface, (210, 200, 190), (int(cpx), int(cpy)), 5)

        # Bookshelves
        book_spr = self.assets.sprites.get('bookshelf')
        for b in [self.bookshelf_1, self.bookshelf_2]:
            bx, by = b.x - cam_x, b.y - cam_y
            if book_spr:
                bw_spr = pygame.transform.scale(book_spr, (b.w, b.h))
                surface.blit(bw_spr, (bx, by))
            else:
                pygame.draw.rect(surface, (78, 52, 34), (bx, by, b.w, b.h))
                pygame.draw.rect(surface, (45, 30, 20), (bx, by, b.w, b.h), 2)
            if b is self.bookshelf_1:
                odd_color = (95, 85, 40) if self.bookshelf_searched else (185, 150, 55)
                odd_y = by + (12 if self.bookshelf_searched else 7)
                pygame.draw.rect(surface, odd_color, (bx + 8 + 2 * 24, odd_y, 18, b.h - 8))

        stx, sty = self.study_table.x - cam_x, self.study_table.y - cam_y
        ct_spr = self.assets.sprites.get('coffee_table')
        if ct_spr:
            scaled_ct = pygame.transform.scale(ct_spr, (self.study_table.w, self.study_table.h))
            surface.blit(scaled_ct, (stx, sty))
        else:
            pygame.draw.rect(surface, (88, 62, 42), (stx, sty, self.study_table.w, self.study_table.h))

        # Painting
        px, py = self.painting_rect.x - cam_x, self.painting_rect.y - cam_y
        surface.blit(self.painting_surfs[self.painting_state], (px, py))

        # --- STORAGE ROOM ---
        crate_spr = self.assets.sprites.get('sheet_table')
        for crate in [self.storage_crate_1, self.storage_crate_2]:
            cx, cy = crate.x - cam_x, crate.y - cam_y
            if crate_spr:
                sc_crate = pygame.transform.scale(crate_spr, (crate.w, crate.h))
                surface.blit(sc_crate, (cx, cy))
            else:
                pygame.draw.rect(surface, (82, 60, 42), (cx, cy, crate.w, crate.h))
            searched_flag = self.storage_crate_1_searched if crate is self.storage_crate_1 else self.storage_crate_2_searched
            if searched_flag:
                pygame.draw.rect(surface, (14, 10, 7), (cx + 5, cy + 5, crate.w - 10, 9))

        sx, sy = self.storage_shelf.x - cam_x, self.storage_shelf.y - cam_y
        shelf_spr = self.assets.sprites.get('kitchen_shelf')
        if shelf_spr:
            sc_shelf = pygame.transform.scale(shelf_spr, (self.storage_shelf.w, self.storage_shelf.h))
            surface.blit(sc_shelf, (sx, sy))
        else:
            pygame.draw.rect(surface, (70, 48, 32), (sx, sy, self.storage_shelf.w, self.storage_shelf.h))
        for i in range(7):
            binder_y = sy + 5
            if i == 3:
                binder_y += 10 if self.storage_shelf_searched else 6
            binder_color = (70, 90, 120) if i % 2 == 0 else (150, 130, 95)
            pygame.draw.rect(surface, binder_color, (sx + 6 + i * 19, binder_y, 14, self.storage_shelf.h - 10))

        spiderweb = self.assets.sprites.get('spiderweb')
        if spiderweb:
            surface.blit(spiderweb, (115 - cam_x, 615 - cam_y))

        # --- FOYER ---
        fx, fy = self.foyer_table.x - cam_x, self.foyer_table.y - cam_y
        shoe_cab = self.assets.sprites.get('shoe_cabinet')
        if shoe_cab:
            sc_cab = pygame.transform.scale(shoe_cab, (self.foyer_table.w, self.foyer_table.h))
            surface.blit(sc_cab, (fx, fy))
        else:
            pygame.draw.rect(surface, (85, 60, 42), (fx, fy, self.foyer_table.w, self.foyer_table.h))
        pygame.draw.rect(surface, (190, 185, 170), (fx + 9, fy + 14, 30, 22))
        pygame.draw.line(surface, (110, 100, 90), (fx + 13, fy + 22), (fx + 35, fy + 22), 1)

        fx, fy = self.foyer_shelf.x - cam_x, self.foyer_shelf.y - cam_y
        disp_cab = self.assets.sprites.get('display_cabinet')
        if disp_cab:
            sc_disp = pygame.transform.scale(disp_cab, (self.foyer_shelf.w, self.foyer_shelf.h))
            surface.blit(sc_disp, (fx, fy))
        else:
            pygame.draw.rect(surface, (75, 50, 35), (fx, fy, self.foyer_shelf.w, self.foyer_shelf.h))

        # --- REVEALED KEY (Inside Bookshelf 1) ---
        if self.key_revealed and not self.key_collected:
            kx = self.bookshelf_1.centerx - cam_x
            ky = self.bookshelf_1.centery - cam_y
            key_spr = self.assets.sprites.get('key_item')
            if key_spr:
                surface.blit(key_spr, (kx - key_spr.get_width() // 2, ky - key_spr.get_height() // 2))
            else:
                pulse = math.sin(pygame.time.get_ticks() / 240.0) * 3
                pygame.draw.circle(surface, (255, 230, 80), (int(kx), int(ky - 3)), int(6 + pulse), 1)
                pygame.draw.circle(surface, (255, 215, 60), (int(kx), int(ky - 3)), 4)
                pygame.draw.rect(surface, (255, 215, 60), (int(kx - 1), int(ky - 1), 3, 9))

        # --- FALSE KEY ---
        if self.false_key_visible and not self.false_key_used:
            fkx = self.false_key_rect.centerx - cam_x
            fky = self.false_key_rect.centery - cam_y
            key_spr = self.assets.sprites.get('key_item')
            if key_spr:
                surface.blit(key_spr, (fkx - key_spr.get_width() // 2, fky - key_spr.get_height() // 2))
            else:
                pygame.draw.circle(surface, (220, 200, 100), (int(fkx), int(fky - 3)), 4)
                pygame.draw.rect(surface, (220, 200, 100), (int(fkx - 1), int(fky - 1), 3, 8))

        # --- BATTERIES (if revealed and uncollected) ---
        for bat in self.batteries:
            if bat["revealed"] and not bat["collected"]:
                r = bat["rect"]
                bx, by = r.x - cam_x, r.y - cam_y
                bat_spr = self.assets.sprites.get('battery_item')
                if bat_spr:
                    surface.blit(bat_spr, (bx, by))
                else:
                    pygame.draw.rect(surface, (50, 185, 100), (bx, by + 2, r.w, r.h - 4))
                    pygame.draw.rect(surface, (220, 220, 220), (bx + r.w - 2, by + r.h // 2 - 2, 3, 4))
                    pygame.draw.rect(surface, (20, 40, 20), (bx, by + 2, r.w, r.h - 4), 1)


# ==============================================================================
# 6. CREATURE CONTROLLER (Stalking & Dynamic Poses)
# ==============================================================================
class MonsterSpriteSet:
    """Loads the hand-made pixel monster poses used by the stalking creature.

    The old procedural creature is deliberately NOT used: rendering both the
    procedural sprite and the art asset made the monster look doubled/tacky.
    """
    def __init__(self):
        self.sprites = []
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "monster")
        for i in range(4):
            path = os.path.join(base, f"monster{i}.png")
            try:
                sprite = pygame.image.load(path).convert_alpha()
                self.sprites.append(sprite)
            except Exception as exc:
                print(f"[MonsterSpriteSet] Could not load {path}: {exc}")
        if not self.sprites:
            # Transparent fallback; never resurrect the old procedural monster.
            self.sprites = [pygame.Surface((1, 1), pygame.SRCALPHA)]


class Creature:
    """The creature freezes in the flashlight beam, and repositions across the house when unseen."""
    def __init__(self, positions=None):
        # Use ONLY the supplied pixel-art monster. The old procedural sprite
        # remains in the source as a fallback for reference, but is never drawn.
        self.sprite_set = MonsterSpriteSet()
        self.pose_index = 0
        self.stage_scales = [0.22, 0.28, 0.35, 0.43, 0.50]
        self.width = 40
        self.height = 52

        # Predefined stalking positions across the house
        if isinstance(positions, dict):
            self.positions = list(positions.values())
        elif positions:
            self.positions = list(positions)
        else:
            self.positions = [
                (580, 240),   # Stage 0: FAR (Bedroom wardrobe shadow)
                (520, 520),   # Stage 1: MID (Central hallway)
                (880, 260),   # Stage 2: CLOSE (Study doorway)
                (360, 780),   # Stage 3: VERY_CLOSE (Storage room shadows)
                (980, 780),   # Stage 4: BEHIND_PLAYER (Exit Foyer)
            ]
        self.stage = 0
        self.pos = list(self.positions[0])
        self.rect = pygame.Rect(self.pos[0] - self.width // 2, self.pos[1] - self.height // 2, self.width, self.height)

        self.is_active = False
        self.is_illuminated = False
        self.is_frozen = False
        self.unseen_timer = 0.0

    def update_position(self, player_pos, is_aggressive=False):
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

        self.pose_index = min(self.stage, len(self.sprite_set.sprites) - 1)
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))

    def _reposition_near_player(self, player_pos):
        px, py = player_pos
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(140, 210)
        nx = max(140, min(1340, px + math.cos(angle) * dist))
        ny = max(120, min(900, py + math.sin(angle) * dist))
        self.pos = [nx, ny]

    def draw(self, surface, cam_x, cam_y):
        if not self.is_active:
            return

        sprite = self.sprite_set.sprites[self.pose_index]
        scale = self.stage_scales[min(self.stage, len(self.stage_scales) - 1)]
        w = max(1, int(sprite.get_width() * scale))
        h = max(1, int(sprite.get_height() * scale))
        scaled = pygame.transform.scale(sprite, (w, h))

        # Treat the creature position as its visual centre, just like the old
        # controller did, while keeping the hand-made pose as the only monster.
        draw_x = int(self.pos[0] - cam_x - scaled.get_width() / 2)
        draw_y = int(self.pos[1] - cam_y - scaled.get_height() / 2)
        surface.blit(scaled, (draw_x, draw_y))


# ==============================================================================
# 6b. COCKROACH ANIMATION (Environmental Scare)
# ==============================================================================
class Cockroach:
    """A small cockroach that idles along walls and scurries away when illuminated."""
    def __init__(self, x, y, frames):
        self.x, self.y = float(x), float(y)
        self.frames = frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.fleeing = False
        self.flee_angle = 0.0
        self.flee_speed = 0.0
        self.flee_timer = 0.0
        self.visible = True
        self.idle_angle = random.uniform(0, 2 * math.pi)
        self.idle_timer = random.uniform(0.5, 3.0)

    def update(self, dt, is_illuminated):
        if not self.visible:
            return
        self.frame_timer += dt
        if self.frame_timer >= 0.07:
            self.frame_timer = 0.0
            self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))

        if is_illuminated and not self.fleeing:
            self.fleeing = True
            self.flee_angle = random.uniform(0, 2 * math.pi)
            self.flee_speed = random.uniform(110, 190)
            self.flee_timer = random.uniform(0.5, 1.0)

        if self.fleeing:
            self.x += math.cos(self.flee_angle) * self.flee_speed * dt
            self.y += math.sin(self.flee_angle) * self.flee_speed * dt
            self.flee_timer -= dt
            if self.flee_timer <= 0:
                self.visible = False
        else:
            self.idle_timer -= dt
            if self.idle_timer <= 0:
                self.idle_angle = random.uniform(0, 2 * math.pi)
                self.idle_timer = random.uniform(1.5, 5.0)
            self.x += math.cos(self.idle_angle) * 6 * dt
            self.y += math.sin(self.idle_angle) * 6 * dt

    def draw(self, surface, cam_x, cam_y):
        if not self.visible or not self.frames:
            return
        frame = self.frames[self.frame_index]
        sx = int(self.x - cam_x - frame.get_width() // 2)
        sy = int(self.y - cam_y - frame.get_height() // 2)
        if self.fleeing:
            rot = pygame.transform.rotate(frame, -math.degrees(self.flee_angle) + 90)
            rect = rot.get_rect(center=(sx + frame.get_width() // 2, sy + frame.get_height() // 2))
            surface.blit(rot, rect.topleft)
        else:
            rot = pygame.transform.rotate(frame, -math.degrees(self.idle_angle) + 90)
            rect = rot.get_rect(center=(sx + frame.get_width() // 2, sy + frame.get_height() // 2))
            surface.blit(rot, rect.topleft)


# ==============================================================================
# 7. EVENT DIRECTOR (Reality Instability System)
# ==============================================================================
class EventDirector:
    def __init__(self, engine):
        self.engine = engine
        self.events_fired = set()
        self.event_cooldown = 0.0
        self.event_log = []

    def log(self, name):
        self.event_log.append(f"{name} (Instability: {int(self.engine.instability)}%)")
        if len(self.event_log) > 6:
            self.event_log.pop(0)

    def trigger_next_event(self, force=False):
        inst = self.engine.instability
        room = self.engine.room

        # Event 1: Chair Shift 1
        if "chair_1" not in self.events_fired and (inst >= 8 or force):
            if force or not self.engine.is_point_in_flashlight(room.chair_pos):
                room.chair_stage = 1
                room.chair_pos = list(room.chair_positions[1])
                room.chair_rect.topleft = room.chair_pos
                self._safety_nudge_player(room.chair_rect)
                self.events_fired.add("chair_1")
                self.engine.flicker_frames = 2
                self.engine.audio.play("whisper", 0.6)
                self.log("Chair Shift 1")
                return True

        # Event 2: Painting Change 1
        if "painting_1" not in self.events_fired and (inst >= 16 or force):
            if force or not self.engine.is_point_in_flashlight(room.painting_rect.center):
                room.painting_state = 1
                self.events_fired.add("painting_1")
                self.engine.flicker_frames = 2
                self.engine.audio.play("whisper", 0.6)
                self.log("Painting Eyes Stare")
                return True

        # Event 3: False Key Appears
        if "false_key" not in self.events_fired and (inst >= 24 or force):
            if force or not self.engine.is_point_in_flashlight(room.false_key_rect.center):
                room.false_key_visible = True
                self.events_fired.add("false_key")
                self.engine.flicker_frames = 2
                self.log("False Key Appears")
                return True

        # Event 4: Chair Shift 2 (Turned toward bed)
        if "chair_2" not in self.events_fired and (inst >= 32 or force):
            if force or not self.engine.is_point_in_flashlight(room.chair_pos):
                room.chair_stage = 2
                room.chair_pos = list(room.chair_positions[2])
                room.chair_rect.topleft = room.chair_pos
                self._safety_nudge_player(room.chair_rect)
                self.events_fired.add("chair_2")
                self.engine.flicker_frames = 3
                self.engine.audio.play("whisper", 0.6)
                self.log("Chair Turned to Bed")
                self.engine.show_thought("THE CHAIR WASN'T THERE.")
                return True

        # Event 5: Vanishing Object (Cup)
        if "vanish_cup" not in self.events_fired and (inst >= 40 or force):
            if force or not self.engine.is_point_in_flashlight(room.cup_pos):
                room.cup_visible = False
                self.events_fired.add("vanish_cup")
                self.engine.flicker_frames = 2
                self.log("Cup Vanished")
                return True

        # Event 6: Appearing Shoes by Bed
        if "shoes" not in self.events_fired and (inst >= 48 or force):
            if force or not self.engine.is_point_in_flashlight(room.shoes_pos):
                room.shoes_visible = True
                self.events_fired.add("shoes")
                self.engine.flicker_frames = 2
                self.engine.audio.play("whisper", 0.7)
                self.log("Shoes by Bed Appeared")
                return True

        # Event 7: Wall Graffiti ("STOP LOOKING")
        if "graffiti_stop" not in self.events_fired and (inst >= 55 or force):
            g = room.graffiti_lines[1]
            if force or not self.engine.is_point_in_flashlight(g["pos"]):
                g["visible"] = True
                self.events_fired.add("graffiti_stop")
                self.log("Graffiti 'STOP LOOKING'")
                return True

        # Event 8: Fake Door in Hallway
        if "fake_door" not in self.events_fired and (inst >= 62 or force):
            if force or not self.engine.is_point_in_flashlight(room.fake_door_rect.center):
                room.fake_door_visible = True
                self.events_fired.add("fake_door")
                self.engine.flicker_frames = 3
                self.log("Fake Door Appeared")
                return True

        # Event 9: Painting Change 2 (Void Face)
        if "painting_2" not in self.events_fired and (inst >= 70 or force):
            if force or not self.engine.is_point_in_flashlight(room.painting_rect.center):
                room.painting_state = 2
                self.events_fired.add("painting_2")
                self.engine.flicker_frames = 2
                self.engine.audio.play("whisper", 0.8)
                self.log("Painting Void Face")
                return True

        # Event 10: Bed Lump
        if "bed_lump" not in self.events_fired and (inst >= 78 or force):
            if force or not self.engine.is_point_in_flashlight(room.bed_rect.center):
                room.bed_lump = True
                self.events_fired.add("bed_lump")
                self.engine.flicker_frames = 2
                self.log("Body Lump on Bed")
                self.engine.show_thought("AM I SURE?")
                return True

        # Event 11: Final Wall Writing ("IT WAS ALWAYS ME.")
        if "graffiti_me" not in self.events_fired and (inst >= 86 or force):
            g = room.graffiti_lines[3]
            if force or not self.engine.is_point_in_flashlight(g["pos"]):
                g["visible"] = True
                self.events_fired.add("graffiti_me")
                self.log("Graffiti 'IT WAS ALWAYS ME.'")
                return True

        # Event 12: Final Shifts
        if "final_shifts" not in self.events_fired and (inst >= 92 or force):
            if force or not self.engine.is_point_in_flashlight(room.chair_pos):
                room.chair_stage = 3
                room.chair_pos = list(room.chair_positions[3])
                room.chair_rect.topleft = room.chair_pos
                self._safety_nudge_player(room.chair_rect)
                room.painting_state = 3
                self.events_fired.add("final_shifts")
                self.engine.flicker_frames = 4
                self.engine.audio.play("whisper", 0.9)
                self.log("Chair Facing Door / Painting Scratched")
                self.engine.show_thought("I DIDN'T MOVE THAT.")
                return True

        return False

    def _safety_nudge_player(self, rect):
        p_rect = self.engine.player_rect
        if p_rect.colliderect(rect):
            self.engine.player_x += 35
            self.engine.player_rect.centerx = int(self.engine.player_x)

    def update(self, dt):
        self.event_cooldown -= dt
        if self.event_cooldown <= 0.0:
            if self.trigger_next_event():
                self.event_cooldown = random.uniform(6.0, 11.0)


# ==============================================================================
# 8. MAIN GAME ENGINE
# ==============================================================================
class GameEngine:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("DON'T LOOK AWAY")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("couriernew", 42, bold=True)
        self.font_narrator = pygame.font.SysFont("couriernew", 19, bold=True)
        self.font_msg = pygame.font.SysFont("couriernew", 20, bold=True)
        self.font_hud = pygame.font.SysFont("couriernew", 16, bold=True)
        self.font_card = pygame.font.SysFont("couriernew", 15, bold=True)
        self.font_hand = pygame.font.SysFont("georgia", 17, italic=True)
        self.font_sm = pygame.font.SysFont("couriernew", 14, bold=True)

        self.audio = AudioManager()
        self.darkness_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        self.player_sprite = create_player_surface()
        # Full-screen hand-made jumpscare art supplied for the ending.
        self.jumpscare_sprite = self.load_jumpscare_image()

        # Pre-built vignette for sanity effects (radial dark edges)
        self.vignette_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        max_r = int(math.hypot(cx, cy))
        for r in range(max_r, 0, -3):
            t = r / max_r
            alpha = int(max(0, min(255, (t - 0.35) * 390)))
            pygame.draw.circle(self.vignette_surf, (0, 0, 0, alpha), (cx, cy), r)
        self.sanity_inversion_timer = random.uniform(5.0, 10.0)
        self.font_banner = pygame.font.SysFont("couriernew", 24, bold=True)

        self.dust_particles = [
            {"x": random.uniform(0, SCREEN_WIDTH), "y": random.uniform(0, SCREEN_HEIGHT),
             "speed": random.uniform(0.3, 0.9), "angle": random.uniform(0, 2 * math.pi)}
            for _ in range(25)
        ]

        self.story_lines = [
            "They told you it was just stress.",
            "Just exhaustion playing tricks on your mind.",
            "",
            "You locked the doors, but you can still hear the floorboards creak.",
            "You feel eyes watching you from the shadow.",
            "",
            "Your perception is slipping. Reality feels... unstable.",
            "",
            "Search the room. Find your ID. Find the key.",
            "And whatever you do...",
            "DON'T LOOK AWAY."
        ]

        self.debug_mode = False
        self.reset_game()

    def load_jumpscare_image(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "jumpscare.png")
        try:
            source = pygame.image.load(path).convert()
            sw, sh = source.get_size()
            # Cover the screen without stretching the artwork's aspect ratio.
            scale = max(SCREEN_WIDTH / sw, SCREEN_HEIGHT / sh)
            nw, nh = int(sw * scale), int(sh * scale)
            source = pygame.transform.smoothscale(source, (nw, nh))
            x = (nw - SCREEN_WIDTH) // 2
            y = (nh - SCREEN_HEIGHT) // 2
            return source.subsurface((x, y, SCREEN_WIDTH, SCREEN_HEIGHT)).copy()
        except Exception as exc:
            print(f"[Game] Could not load jumpscare art: {exc}")
            fallback = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fallback.fill((4, 4, 6))
            return fallback

    def reset_game(self):
        self.state = STATE_MENU
        self.state_timer = 0.0
        self.intro_timer = 0.0


        # Player spawn in Central Hallway
        self.player_x = 520.0
        self.player_y = 520.0
        self.player_angle = 0.0
        self.player_rect = pygame.Rect(int(self.player_x - PLAYER_SIZE // 2),
                                       int(self.player_y - PLAYER_SIZE // 2),
                                       PLAYER_SIZE, PLAYER_SIZE)

        self.cam_x = int(self.player_x - SCREEN_WIDTH // 2)
        self.cam_y = int(self.player_y - SCREEN_HEIGHT // 2)

        self.battery = FLASHLIGHT_BATTERY
        self.flashlight_on = True
        self.battery_dead_time = 0.0

        self.hint_timer = 0.0      # seconds since the last useful action
        self.searches_done = 0     # how many useful actions so far (hides the tutorial tip)

        self.instability = 0.0
        self.room = GameRoom()
        self.creature = Creature()
        self.director = EventDirector(self)

        self.game_time = 0.0
        self.ending_phase = 0
        self.ending_timer = 0.0

        self.target_message = ""
        self.displayed_chars = 0.0
        self.message_timer = 0.0
        self.is_thought = False

        self.shake_amount = 0
        self.flicker_frames = 0
        self.peripheral_timer = random.uniform(8.0, 16.0)
        self.peripheral_eyes = None

        self.footstep_timer = 0.0
        self.extra_footsteps = 0
        self.extra_footstep_timer = 0.0
        self.was_moving = False
        self.heartbeat_timer = 0.0

        self.audio.stop_drone()

        # Room banner state
        self.current_room_name = ""
        self.room_banner_text = ""
        self.room_banner_timer = 0.0

        # Cockroach ambient scares
        self.cockroaches = self._create_cockroaches()

        # Sanity effect timer
        self.sanity_inversion_timer = random.uniform(5.0, 10.0)

    def _create_cockroaches(self):
        """Spawn cockroaches in dark corners using the loaded animation frames."""
        try:
            assets = AssetManager.get_instance()
            frames = assets.cockroach_frames
            if not frames:
                return []
        except Exception:
            return []
        return [
            Cockroach(185, 640, frames),   # Storage room corner
            Cockroach(625, 150, frames),   # Near bedroom wardrobe
            Cockroach(1210, 410, frames),  # Study hallway edge
            Cockroach(420, 870, frames),   # Storage room floor
            Cockroach(1300, 700, frames),  # Foyer shelf shadow
        ]

    def toggle_flashlight(self):
        if self.battery <= 0.0:
            self.audio.play("click", 0.7)
            self.flashlight_on = False
            return
        self.flashlight_on = not self.flashlight_on
        self.audio.play("click", 0.85)

    def show_message(self, text, duration=3.5, is_thought=False):
        self.target_message = text
        self.displayed_chars = 0.0
        self.message_timer = duration
        self.is_thought = is_thought

    def show_thought(self, text):
        self.show_message(text, 3.5, is_thought=True)

    def handle_input(self, dt):
        keys = pygame.key.get_pressed()
        dx, dy = 0.0, 0.0

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1.0

        if dx != 0.0 and dy != 0.0:
            inv = 1.0 / math.sqrt(2.0)
            dx *= inv
            dy *= inv

        is_moving = (dx != 0.0 or dy != 0.0)
        if is_moving:
            self.footstep_timer += dt
            if self.footstep_timer >= 0.38:
                self.audio.play("footstep", 0.45)
                self.footstep_timer = 0.0
            self.was_moving = True
        else:
            if self.was_moving:
                if self.instability > 35 and random.random() < 0.40:
                    self.extra_footsteps = 2
                    self.extra_footstep_timer = 0.35
                self.was_moving = False
            self.footstep_timer = 0.30

        if self.extra_footsteps > 0:
            self.extra_footstep_timer -= dt
            if self.extra_footstep_timer <= 0:
                self.audio.play("footstep", 0.35)
                self.extra_footsteps -= 1
                self.extra_footstep_timer = 0.32

        move_x = dx * PLAYER_SPEED
        self.player_x += move_x
        self.player_rect.centerx = int(self.player_x)
        colliders = self.room.get_solid_colliders()
        for c in colliders:
            if self.player_rect.colliderect(c):
                if move_x > 0:
                    self.player_rect.right = c.left
                elif move_x < 0:
                    self.player_rect.left = c.right
                self.player_x = float(self.player_rect.centerx)

        move_y = dy * PLAYER_SPEED
        self.player_y += move_y
        self.player_rect.centery = int(self.player_y)
        for c in colliders:
            if self.player_rect.colliderect(c):
                if move_y > 0:
                    self.player_rect.bottom = c.top
                elif move_y < 0:
                    self.player_rect.top = c.bottom
                self.player_y = float(self.player_rect.centery)

    # --------------------------------------------------------------------------
    # INTERACTION SYSTEM
    # Every object the player can use is described once in get_interactables().
    # The [E] prompt, the glint markers, the highlight AND the actual action all
    # come from this single list, so what you see is always what you get.
    # --------------------------------------------------------------------------
    def mark_progress(self):
        """Call whenever the player does something useful (resets the hint timer)."""
        self.hint_timer = 0.0
        self.searches_done += 1

    def dist_to_rect(self, rect):
        """Distance from the player to the nearest EDGE of a rectangle (not its centre)."""
        nx = max(rect.left, min(self.player_x, rect.right))
        ny = max(rect.top, min(self.player_y, rect.bottom))
        return math.hypot(self.player_x - nx, self.player_y - ny)

    def get_interactables(self):
        """Builds the list of everything currently usable. kind: story / flavor / item / exit / door."""
        r = self.room
        items = []

        def add(key, rect, label, action, kind):
            items.append({"key": key, "rect": rect, "label": label, "action": action, "kind": kind})

        # --- Bedroom ---
        if not r.note_read:
            add("nightstand", r.nightstand_rect, "Read the Note", self.act_nightstand, "story")
        elif not r.nightstand_searched:
            add("nightstand", r.nightstand_rect, "Open Nightstand Drawer", self.act_nightstand, "story")
        if not r.wardrobe_searched:
            add("wardrobe", r.wardrobe_rect, "Open Wardrobe", self.act_wardrobe, "flavor")

        # --- Study ---
        if not r.bookshelf_searched:
            add("bookshelf_1", r.bookshelf_1, "Search Bookshelf", self.act_bookshelf_1, "story")
        elif r.key_revealed and not r.key_collected:
            add("bookshelf_1", r.bookshelf_1, "Take the Key", self.act_bookshelf_1, "story")
        if not r.bookshelf_2_searched:
            add("bookshelf_2", r.bookshelf_2, "Search Bookshelf", self.act_bookshelf_2, "flavor")
        if not r.study_desk_searched:
            add("desk", r.study_desk_rect, "Open Desk Drawers", self.act_desk, "flavor")

        # --- Storage ---
        if not r.storage_shelf_searched:
            add("storage_shelf", r.storage_shelf, "Search Storage Shelf", self.act_storage_shelf, "story")
        elif r.id_revealed and not r.id_collected:
            add("storage_shelf", r.storage_shelf, "Pick up ID Card", self.act_storage_shelf, "story")
        if not r.storage_crate_1_searched:
            add("crate_1", r.storage_crate_1, "Open Wooden Crate", self.act_crate_1, "story")
        if not r.storage_crate_2_searched:
            add("crate_2", r.storage_crate_2, "Open Wooden Crate", self.act_crate_2, "flavor")

        # --- Foyer ---
        if not r.foyer_table_searched:
            add("foyer_table", r.foyer_table, "Check the Table", self.act_foyer_table, "flavor")

        # --- Hallucinations that can be interacted with ---
        if r.false_key_visible and not r.false_key_used:
            add("false_key", r.false_key_rect.inflate(30, 30), "Pick up Key", self.act_false_key, "item")
        if r.fake_door_visible:
            add("fake_door", r.fake_door_rect.inflate(30, 30), "Open Door", self.act_fake_door, "item")

        # --- Batteries ---
        for i, bat in enumerate(r.batteries):
            if bat["revealed"] and not bat["collected"]:
                add("battery_%d" % i, bat["rect"].inflate(30, 30), "Pick up Battery",
                    (lambda b=bat: self.act_battery(b)), "item")

        # --- Doors ---
        for d in r.doors:
            if d.is_exit:
                ready = r.has_key and r.id_collected
                label = "Unlock Exit Door" if ready else "Try Exit Door"
                add("door_" + d.name, d.closed_rect, label, (lambda dd=d: self.act_door(dd)),
                    "exit" if ready else "door")
            else:
                label = ("Close " if d.is_open else "Open ") + d.name
                add("door_" + d.name, d.closed_rect, label, (lambda dd=d: self.act_door(dd)), "door")
        return items

    def get_current_target(self):
        """The nearest usable object within INTERACT_RANGE (or None)."""
        best, best_score = None, 1e9
        for it in self.get_interactables():
            d = self.dist_to_rect(it["rect"])
            if d > INTERACT_RANGE:
                continue
            score = d + (25 if it["kind"] == "door" else 0)  # doors never steal the prompt from furniture
            if score < best_score:
                best, best_score = it, score
        return best

    def handle_interaction(self):
        target = self.get_current_target()
        if target:
            target["action"]()

    # ---- Actions ----
    def act_nightstand(self):
        r = self.room
        if not r.note_read:
            self.state = STATE_READING_NOTE
            self.audio.play("whisper", 0.7)
            self.mark_progress()
        elif not r.nightstand_searched:
            r.nightstand_searched = True
            r.batteries[0]["revealed"] = True
            self.audio.play("drawer_open", 0.8)
            self.show_message("OPENED THE DRAWER: A SPARE BATTERY!", 3.5)
            self.mark_progress()

    def act_wardrobe(self):
        self.room.wardrobe_searched = True
        self.audio.play("drawer_open", 0.7)
        self.show_thought("EMPTY HANGERS... SCRATCH MARKS ON THE INSIDE OF THE DOORS.")
        self.mark_progress()

    def act_bookshelf_1(self):
        r = self.room
        if not r.bookshelf_searched:
            r.bookshelf_searched = True
            r.key_revealed = True
            self.audio.play("drawer_open", 0.9)
            self.show_message("A HOLLOW BOOK... THE KEY WAS HIDDEN INSIDE! [E] TO TAKE IT", 4.5)
            self.mark_progress()
        elif r.key_revealed and not r.key_collected:
            r.key_collected = True
            r.has_key = True
            self.instability = min(100.0, self.instability + INSTABILITY_KEY_BOOST)
            self.audio.play("pickup_key", 0.9)
            self.show_message("KEY ACQUIRED.", 3.5)
            self.mark_progress()

    def act_bookshelf_2(self):
        self.room.bookshelf_2_searched = True
        self.audio.play("drawer_open", 0.6)
        self.show_thought("JUST DUST. ...ONE BOOK ON THE OTHER SHELF STICKS OUT.")
        self.mark_progress()

    def act_desk(self):
        self.room.study_desk_searched = True
        self.audio.play("drawer_open", 0.8)
        self.show_thought("SHREDDED PATIENT LOGS AND MEDICATION SLIPS. NO KEY.")
        self.mark_progress()

    def act_storage_shelf(self):
        r = self.room
        if not r.storage_shelf_searched:
            r.storage_shelf_searched = True
            r.id_revealed = True
            self.state = STATE_READING_ID
            self.state_timer = 0.0
            self.audio.play("pickup_key", 0.8)
            self.mark_progress()
        elif r.id_revealed and not r.id_collected:
            self.state = STATE_READING_ID
            self.state_timer = 0.0

    def act_crate_1(self):
        self.room.storage_crate_1_searched = True
        self.room.batteries[1]["revealed"] = True
        self.audio.play("drawer_open", 0.8)
        self.show_message("OPENED THE CRATE: A SPARE BATTERY!", 3.5)
        self.mark_progress()

    def act_crate_2(self):
        self.room.storage_crate_2_searched = True
        self.audio.play("drawer_open", 0.7)
        self.show_thought("EMPTY. ONLY STRAW... AND SOMETHING THAT LOOKS LIKE CLAW MARKS.")
        self.mark_progress()

    def act_foyer_table(self):
        self.room.foyer_table_searched = True
        self.audio.play("drawer_open", 0.5)
        self.show_thought("THE VISITOR LOG. NO NAMES FOR MONTHS. NOBODY COMES HERE.")
        self.mark_progress()

    def act_false_key(self):
        self.room.false_key_used = True
        self.room.false_key_visible = False
        self.audio.play("whisper", 0.9)
        self.flicker_frames = 4
        self.show_message("...IT WASN'T REAL.", 3.5, is_thought=True)

    def act_fake_door(self):
        self.room.fake_door_visible = False
        self.audio.play("whisper", 0.8)
        self.flicker_frames = 3
        self.show_message("...THERE'S NOTHING THERE.", 3.5, is_thought=True)

    def act_battery(self, bat):
        bat["collected"] = True
        self.battery = min(100.0, self.battery + BATTERY_REFILL)
        self.audio.play("pickup_battery", 0.85)
        self.show_message(f"BATTERY COLLECTED (+{int(BATTERY_REFILL)}%)", 3.0)
        self.mark_progress()

    def act_door(self, d):
        if d.is_exit:
            if self.room.has_key and self.room.id_collected:
                # SUCCESSFUL ESCAPE & PLOT TWIST SEQUENCE!
                d.is_open = True
                self.state = STATE_ENDING_ESCAPE
                self.ending_phase = 1
                self.ending_timer = 0.0
                self.audio.play("door_open", 0.9)
            elif not self.room.has_key:
                self.show_message("THE DOOR IS LOCKED. I NEED THE KEY.", 3.0)
            else:
                self.show_message("I CAN'T LEAVE WITHOUT MY ID.", 3.0)
        else:
            d.toggle()
            self.audio.play("door_open", 0.8)

    # ---- Objective text + visual cues ----
    def get_objective_text(self):
        r = self.room
        if r.has_key and r.id_collected:
            return "OBJECTIVE: GO TO THE EXIT DOOR (BOTTOM OF THE HOUSE)"
        if r.has_key:
            return "OBJECTIVE: FIND YOUR RESIDENT ID"
        if r.id_collected:
            return "OBJECTIVE: FIND THE KEY"
        return "OBJECTIVE: FIND THE KEY + YOUR ID"

    def count_searched(self):
        r = self.room
        flags = [r.nightstand_searched, r.wardrobe_searched, r.bookshelf_searched, r.bookshelf_2_searched,
                 r.study_desk_searched, r.storage_shelf_searched, r.storage_crate_1_searched,
                 r.storage_crate_2_searched, r.foyer_table_searched]
        return sum(1 for f in flags if f), len(flags)

    def draw_glint(self, surface, sx, sy, color, alpha, size):
        """A small pulsing 4-point sparkle, drawn ABOVE the darkness so it is visible in the dark."""
        s = pygame.Surface((70, 70), pygame.SRCALPHA)
        c = 35
        pygame.draw.circle(s, (color[0], color[1], color[2], max(0, alpha // 6)), (c, c), int(size * 2.4))
        pts = [(c, c - size * 1.7), (c + size * 0.38, c - size * 0.38), (c + size * 1.7, c),
               (c + size * 0.38, c + size * 0.38), (c, c + size * 1.7), (c - size * 0.38, c + size * 0.38),
               (c - size * 1.7, c), (c - size * 0.38, c - size * 0.38)]
        pygame.draw.polygon(s, (color[0], color[1], color[2], alpha), pts)
        surface.blit(s, (sx - c, sy - c))

    def draw_interaction_cues(self, surface):
        """Glints on searchable objects, edge arrows when you are lost, and a highlight on the current target."""
        if self.state != STATE_PLAYING or self.battery <= 0.0:
            return
        t = pygame.time.get_ticks() / 1000.0
        target = self.get_current_target()
        hint_on = self.hint_timer >= HINT_DELAY
        player_sx = self.player_x - self.cam_x
        player_sy = self.player_y - self.cam_y
        colors = {"story": (255, 225, 110), "flavor": (225, 215, 190), "item": (120, 255, 165), "exit": (170, 255, 190)}

        for it in self.get_interactables():
            kind = it["kind"]
            if kind == "door":
                continue
            rect = it["rect"]
            dist = self.dist_to_rect(rect)
            if kind == "exit":
                radius = 900
            elif kind == "story" and hint_on:
                radius = HINT_SENSE_RADIUS
            else:
                radius = SENSE_RADIUS
            if dist > radius:
                continue

            strength = 1.0 - dist / radius
            alpha = int(70 + 185 * strength)
            sx = rect.centerx - self.cam_x
            sy = rect.centery - self.cam_y
            pulse = 0.5 + 0.5 * math.sin(t * 3.2 + rect.x * 0.01)
            size = (5 if kind == "flavor" else 7) + 3 * pulse
            on_screen = -30 <= sx <= SCREEN_WIDTH + 30 and -30 <= sy <= SCREEN_HEIGHT + 30

            if on_screen:
                self.draw_glint(surface, int(sx), int(sy), colors.get(kind, (255, 255, 255)), alpha, size)
            elif (hint_on and kind == "story") or kind == "exit":
                # Off-screen guide arrow at the screen edge, pointing toward the object
                ang = math.atan2(sy - player_sy, sx - player_sx)
                ax = max(26, min(SCREEN_WIDTH - 26, SCREEN_WIDTH / 2 + math.cos(ang) * 900))
                ay = max(26, min(SCREEN_HEIGHT - 26, SCREEN_HEIGHT / 2 + math.sin(ang) * 900))
                tip = (ax + math.cos(ang) * 12, ay + math.sin(ang) * 12)
                left = (ax + math.cos(ang + 2.5) * 11, ay + math.sin(ang + 2.5) * 11)
                right = (ax + math.cos(ang - 2.5) * 11, ay + math.sin(ang - 2.5) * 11)
                arrow_alpha = int(120 + 100 * pulse)
                arr = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                pygame.draw.polygon(arr, (*colors.get(kind, (255, 255, 255)), arrow_alpha), [tip, left, right])
                surface.blit(arr, (0, 0))

        # Highlight + floating [E] badge on the object you are about to use
        if target and target["kind"] != "door":
            rect = target["rect"]
            sx = rect.x - self.cam_x
            sy = rect.y - self.cam_y
            pulse = 0.5 + 0.5 * math.sin(t * 6.0)
            glow = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 240, 150, int(110 + 100 * pulse)), glow.get_rect(), 2)
            surface.blit(glow, (sx - 8, sy - 8))
            badge = pygame.Rect(0, 0, 24, 24)
            badge.center = (sx + rect.w // 2, sy - 20)
            pygame.draw.rect(surface, (20, 18, 14), badge)
            pygame.draw.rect(surface, (255, 240, 150), badge, 2)
            e_surf = self.font_hud.render("E", True, (255, 240, 150))
            surface.blit(e_surf, (badge.centerx - e_surf.get_width() // 2, badge.centery - e_surf.get_height() // 2))

    def is_point_in_flashlight(self, world_pos):
        if not self.flashlight_on:
            return False
        tx, ty = world_pos
        dx = tx - self.player_x
        dy = ty - self.player_y
        dist = math.hypot(dx, dy)
        if dist > FLASHLIGHT_RANGE:
            return False
        angle = math.atan2(dy, dx)
        diff = (angle - self.player_angle + math.pi) % (2 * math.pi) - math.pi
        return abs(diff) <= math.radians(FLASHLIGHT_ANGLE / 2.0)

    def update_instability(self, dt):
        rate = INSTABILITY_RISE_RATE
        if self.battery < 25.0:
            rate *= 2.2
        self.instability = min(100.0, self.instability + rate * dt)

        vol = 0.20 + (self.instability / 100.0) * 0.40
        self.audio.set_drone_volume(vol)
        self.audio.set_tension(self.instability / 100.0)
        self.director.update(dt)

        if random.random() < (self.instability / 100.0) * 0.015:
            self.flicker_frames = random.randint(1, 3)

        self.peripheral_timer -= dt
        if self.peripheral_timer <= 0:
            self.peripheral_timer = random.uniform(12.0, 22.0)
            if self.instability >= 30 and random.random() < 0.65:
                ang = self.player_angle + random.choice([-1.2, 1.2])
                dist = random.uniform(220, 320)
                self.peripheral_eyes = [
                    self.player_x + math.cos(ang) * dist,
                    self.player_y + math.sin(ang) * dist,
                    0.7
                ]

        if self.peripheral_eyes:
            self.peripheral_eyes[2] -= dt
            if self.is_point_in_flashlight((self.peripheral_eyes[0], self.peripheral_eyes[1])) or self.peripheral_eyes[2] <= 0:
                self.peripheral_eyes = None

    def update_creature(self, dt):
        if not self.creature.is_active:
            if self.game_time >= 15.0 or self.instability >= 20.0:
                self.creature.is_active = True
            return

        in_beam = self.is_point_in_flashlight(self.creature.pos)
        self.creature.is_illuminated = in_beam

        if in_beam:
            self.creature.is_frozen = True
            self.creature.unseen_timer = 0.0
            if self.creature.stage >= 3:
                self.shake_amount = max(self.shake_amount, 2)
        else:
            self.creature.is_frozen = False
            self.creature.unseen_timer += dt

            is_aggro = (self.room.has_key and self.room.id_collected)
            threshold = CREATURE_AGGRO_DELAY if is_aggro else CREATURE_MOVE_DELAY

            if self.creature.unseen_timer >= threshold:
                self.creature.unseen_timer = 0.0
                self.creature.update_position((self.player_x, self.player_y), is_aggro)
                self.flicker_frames = 2
                cdist = math.hypot(self.player_x - self.creature.pos[0], self.player_y - self.creature.pos[1])
                self.audio.play_at_distance("creature_move", cdist, max_distance=800.0, volume=0.8)

        # Danger only in total darkness when battery hits 0
        if not self.flashlight_on:
            dist = math.hypot(self.player_x - self.creature.pos[0], self.player_y - self.creature.pos[1])
            if dist < CREATURE_ATTACK_DIST:
                self.trigger_jumpscare()

    def trigger_jumpscare(self):
        """Start the scripted jumpscare sequence with the supplied artwork."""
        if self.state == STATE_JUMPSCARE or self.state == STATE_AMBIGUOUS_ENDING:
            return
        self.state = STATE_JUMPSCARE
        self.state_timer = 0.0
        # The sequence starts with a hard blackout and the scare sound at t=0.
        self.audio.stop_all()
        self.audio.play("jumpscare", volume=1.0)
        self.shake_amount = 0

    def update(self, dt):
        self.audio.update()
        target_cam_x = int(self.player_x - SCREEN_WIDTH / 2)
        target_cam_y = int(self.player_y - SCREEN_HEIGHT / 2)
        self.cam_x = max(0, min(WORLD_WIDTH - SCREEN_WIDTH, target_cam_x))
        self.cam_y = max(0, min(WORLD_HEIGHT - SCREEN_HEIGHT, target_cam_y))

        mx, my = pygame.mouse.get_pos()
        player_screen_x = self.player_x - self.cam_x
        player_screen_y = self.player_y - self.cam_y
        self.player_angle = math.atan2(my - player_screen_y, mx - player_screen_x)

        if self.shake_amount > 0:
            self.shake_amount = max(0, self.shake_amount - int(35 * dt))
        if self.flicker_frames > 0:
            self.flicker_frames -= 1

        if self.message_timer > 0.0:
            self.message_timer -= dt
            self.displayed_chars = min(float(len(self.target_message)), self.displayed_chars + 38.0 * dt)
            if self.message_timer <= 0.0:
                self.target_message = ""

        for p in self.dust_particles:
            p["x"] = (p["x"] + math.cos(p["angle"]) * p["speed"]) % SCREEN_WIDTH
            p["y"] = (p["y"] + math.sin(p["angle"]) * p["speed"]) % SCREEN_HEIGHT

        # State Dispatch
        if self.state == STATE_INTRO_STORY:
            self.intro_timer += dt

        elif self.state == STATE_PLAYING:
            self.game_time += dt
            self.hint_timer += dt
            self.handle_input(dt)
            self.update_instability(dt)
            self.update_creature(dt)
            self.update_room_banner(dt)
            self.update_cockroaches(dt)

            if self.flashlight_on:
                self.battery = max(0.0, self.battery - BATTERY_DRAIN * dt)
                if self.battery <= 0.0:
                    self.flashlight_on = False
                    self.audio.play("click", 1.0)
                    self.show_thought("...")

            if self.battery <= 0.0 and not self.flashlight_on:
                self.battery_dead_time += dt
                self.heartbeat_timer += dt
                if self.heartbeat_timer >= 0.65:
                    self.audio.play("heartbeat", 0.9)
                    self.heartbeat_timer = 0.0

                if self.battery_dead_time >= BLACKOUT_KILL_TIME:
                    self.trigger_jumpscare()

        elif self.state == STATE_READING_NOTE:
            self.creature.is_frozen = True

        elif self.state == STATE_READING_ID:
            self.state_timer += dt
            self.creature.is_frozen = True
            if self.state_timer >= 4.5:
                self.state = STATE_PLAYING
                self.room.id_collected = True
                self.instability = min(100.0, self.instability + INSTABILITY_ID_BOOST)
                self.show_thought("THIS IS MY ROOM.")

        elif self.state == STATE_ENDING_ESCAPE:
            self.ending_timer += dt
            self.shake_amount = 0  # No screen shake during successful escape!

            if self.ending_timer >= 2.5 and self.ending_phase == 1:
                self.ending_phase = 2
                self.audio.stop_drone()

            elif self.ending_timer >= 6.5 and self.ending_phase == 2:
                self.ending_phase = 3

            elif self.ending_timer >= 12.0 and self.ending_phase == 3:
                self.ending_phase = 4

        elif self.state == STATE_JUMPSCARE:
            self.state_timer += dt
            # 0.00-0.05 black; 0.05-0.40 monster; 0.40-0.70 black;
            # 0.70-2.00 first line; then fade into the final line.
            if 0.15 <= self.state_timer < 0.40:
                self.shake_amount = random.randint(7, 14)
            else:
                self.shake_amount = 0
            if self.state_timer >= 3.2:
                self.state = STATE_AMBIGUOUS_ENDING
                self.state_timer = 0.0

        elif self.state == STATE_AMBIGUOUS_ENDING:
            self.state_timer += dt
            self.shake_amount = 0

    # --------------------------------------------------------------------------
    # LIGHTING & SHADOW (Smaller Beam + Ambient Halo when OFF)
    # --------------------------------------------------------------------------
    def render_lighting(self, surface):
        flicker_active = (self.flicker_frames > 0)
        ambient_darkness = 254 if (not self.flashlight_on or flicker_active) else 246
        self.darkness_surf.fill((6, 6, 10, ambient_darkness))

        px = int(self.player_x - self.cam_x)
        py = int(self.player_y - self.cam_y)

        # Ambient personal halo: When ON: 34px. When OFF: 22px (soft small halo around character)
        personal_radius = 34 if self.flashlight_on else 22
        # Soft dim pool of light so nearby furniture is readable (disappears when the battery is dead)
        if self.battery > 0.0:
            ring_max = AMBIENT_SIGHT_RADIUS if self.flashlight_on else 56
            for ring_r in range(ring_max, personal_radius, -4):
                t_ring = (ring_max - ring_r) / max(1.0, (ring_max - personal_radius))
                ring_alpha = int(ambient_darkness - (ambient_darkness - 168) * t_ring)
                pygame.draw.circle(self.darkness_surf, (6, 6, 10, ring_alpha), (px, py), ring_r)
        pygame.draw.circle(self.darkness_surf, (0, 0, 0, 0), (px, py), personal_radius)

        # Flashlight cone (tighter 54 deg beam)
        if self.flashlight_on and not flicker_active:
            beam_range = FLASHLIGHT_RANGE * (0.85 if self.battery < 25.0 else 1.0)
            cone_points = [(px, py)]
            half_angle = math.radians(FLASHLIGHT_ANGLE / 2.0)
            segments = 32
            for i in range(segments + 1):
                cur_ang = (self.player_angle - half_angle) + (2 * half_angle * i / segments)
                bx = px + math.cos(cur_ang) * beam_range
                by = py + math.sin(cur_ang) * beam_range
                cone_points.append((bx, by))

            pygame.draw.polygon(self.darkness_surf, (0, 0, 0, 0), cone_points)

        surface.blit(self.darkness_surf, (0, 0))

        # Floating dust particles in beam
        if self.flashlight_on and not flicker_active:
            for p in self.dust_particles:
                dx = p["x"] - px
                dy = p["y"] - py
                if math.hypot(dx, dy) < FLASHLIGHT_RANGE:
                    p_ang = math.atan2(dy, dx)
                    p_diff = (p_ang - self.player_angle + math.pi) % (2 * math.pi) - math.pi
                    if abs(p_diff) <= math.radians(FLASHLIGHT_ANGLE / 2.0):
                        pygame.draw.circle(surface, (255, 250, 220), (int(p["x"]), int(p["y"])), 1)

    # --------------------------------------------------------------------------
    # OVERLAYS: NOTE & ID CARD
    # --------------------------------------------------------------------------
    def draw_note_overlay(self, surface):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 190))
        surface.blit(dim, (0, 0))

        # Give the note enough room for the longer handwritten message and
        # wrap each sentence so it never runs over the paper's edge.
        nw, nh = 570, 310
        nx = SCREEN_WIDTH // 2 - nw // 2
        ny = SCREEN_HEIGHT // 2 - nh // 2
        pygame.draw.rect(surface, (235, 230, 215), (nx, ny, nw, nh))
        pygame.draw.rect(surface, (160, 150, 130), (nx, ny, nw, nh), 2)

        note_font = pygame.font.SysFont("georgia", 15, italic=True)
        note_lines = [
            "You told us again last night that someone was in the room.",
            "Nobody was there. We put the furniture back where you like it.",
            "Please take your evening tablets.",
            "Please stop writing on the walls.",
            "",
            "- Night Staff"
        ]

        def wrap_note_line(text, font, max_width):
            if not text:
                return [""]
            words = text.split()
            wrapped = []
            current = words[0]
            for word in words[1:]:
                candidate = current + " " + word
                if font.size(candidate)[0] <= max_width:
                    current = candidate
                else:
                    wrapped.append(current)
                    current = word
            wrapped.append(current)
            return wrapped

        start_y = ny + 25
        line_gap = 27
        max_text_width = nw - 50
        for line in note_lines:
            for wrapped in wrap_note_line(line, note_font, max_text_width):
                if wrapped:
                    tsurf = note_font.render(wrapped, True, (40, 30, 30))
                    surface.blit(tsurf, (nx + 25, start_y))
                start_y += line_gap

        prompt = self.font_hud.render("[ PRESS E OR SPACE TO PUT DOWN ]", True, (255, 220, 100))
        surface.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, ny + nh + 18))

    def draw_id_card_overlay(self, surface):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 190))
        surface.blit(dim, (0, 0))

        cw, ch = 390, 240
        cx = SCREEN_WIDTH // 2 - cw // 2
        cy = SCREEN_HEIGHT // 2 - ch // 2

        pygame.draw.rect(surface, (230, 228, 225), (cx, cy, cw, ch))
        pygame.draw.rect(surface, (70, 95, 140), (cx, cy, cw, 34))
        pygame.draw.rect(surface, (40, 45, 55), (cx, cy, cw, ch), 2)

        h1 = self.font_card.render("ST. ALDRIC RESIDENCE  -  RESIDENT ID", True, (255, 255, 255))
        surface.blit(h1, (cx + 15, cy + 8))

        px, py = cx + 20, cy + 50
        pygame.draw.rect(surface, (20, 20, 25), (px, py, 80, 100))
        pygame.draw.circle(surface, (70, 60, 65), (px + 40, py + 36), 18)
        pygame.draw.ellipse(surface, (70, 60, 65), (px + 15, py + 55, 50, 45))
        for _ in range(12):
            rx1 = px + random.randint(22, 58)
            ry1 = py + random.randint(20, 52)
            rx2 = px + random.randint(22, 58)
            ry2 = py + random.randint(20, 52)
            pygame.draw.line(surface, (180, 20, 20), (rx1, ry1), (rx2, ry2), 2)
            pygame.draw.line(surface, (20, 10, 10), (rx1, ry1), (rx2, ry2), 2)

        tx = cx + 118
        surface.blit(self.font_card.render("NAME:", True, (50, 50, 55)), (tx, cy + 52))
        pygame.draw.rect(surface, (20, 20, 20), (tx + 50, cy + 55, 140, 12))
        for _ in range(6):
            pygame.draw.line(surface, (180, 30, 30), (tx + 48, cy + 60), (tx + 190, cy + 60), 2)

        surface.blit(self.font_card.render("RESIDENT #:  0412-R", True, (40, 40, 45)), (tx, cy + 78))
        surface.blit(self.font_card.render("LOCATION:    ROOM 4", True, (160, 40, 40)), (tx, cy + 104))
        surface.blit(self.font_card.render("STATUS:      MONITORED", True, (40, 40, 45)), (tx, cy + 130))

        foot = self.font_hud.render("IF FOUND, PLEASE RETURN TO NIGHT STAFF.", True, (100, 100, 110))
        surface.blit(foot, (cx + cw // 2 - foot.get_width() // 2, cy + 195))

        prompt = self.font_hud.render("[ PRESS E OR SPACE TO KEEP ]", True, (255, 220, 100))
        surface.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, cy + ch + 18))

    # --------------------------------------------------------------------------
    # SANITY VISUAL POST-PROCESSING
    # --------------------------------------------------------------------------
    def apply_sanity_effects(self, canvas):
        """Layer increasingly disturbing visual effects as instability rises."""
        inst = self.instability
        if inst < 30 or self.state != STATE_PLAYING:
            return

        # Chromatic aberration at 30%+ — split RGB channels and offset
        if inst >= 30:
            offset = max(1, int((inst - 30) / 18))  # 1px at 30%, up to 4px at 100%
            r_surf = canvas.copy()
            b_surf = canvas.copy()
            r_surf.fill((255, 0, 0), special_flags=pygame.BLEND_MULT)
            b_surf.fill((0, 0, 255), special_flags=pygame.BLEND_MULT)
            canvas.fill((0, 255, 0), special_flags=pygame.BLEND_MULT)
            canvas.blit(r_surf, (-offset, 0), special_flags=pygame.BLEND_ADD)
            canvas.blit(b_surf, (offset, 0), special_flags=pygame.BLEND_ADD)

        # Brief color inversion flashes at 70%+ (1 frame every few seconds)
        if inst >= 70:
            self.sanity_inversion_timer -= 1.0 / FPS
            if self.sanity_inversion_timer <= 0:
                self.sanity_inversion_timer = random.uniform(3.5, 8.0) * (1.5 - inst / 200.0)
                inv = pygame.Surface(canvas.get_size())
                inv.fill((255, 255, 255))
                inv.blit(canvas, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
                canvas.blit(inv, (0, 0))

        # Vignette (dark edges) at 50%+ — gets progressively stronger
        if inst >= 50:
            strength = (inst - 50) / 50.0  # 0.0 at 50%, 1.0 at 100%
            vig = self.vignette_surf.copy()
            vig.set_alpha(int(140 * strength))
            canvas.blit(vig, (0, 0))

    # --------------------------------------------------------------------------
    # ROOM NAME BANNER
    # --------------------------------------------------------------------------
    def update_room_banner(self, dt):
        """Detects room transitions and triggers a fading banner."""
        new_room = get_room_name(self.player_x, self.player_y)
        if new_room != self.current_room_name:
            self.current_room_name = new_room
            self.room_banner_text = new_room.upper()
            self.room_banner_timer = 2.8  # seconds to display
        if self.room_banner_timer > 0:
            self.room_banner_timer -= dt

    def draw_room_banner(self, surface):
        """Draws a cinematic fading room name banner at the top of the screen."""
        if self.room_banner_timer <= 0 or not self.room_banner_text:
            return
        # Fade in for 0.4s, hold, fade out for 0.8s
        t = self.room_banner_timer
        if t > 2.4:
            alpha = int(255 * (2.8 - t) / 0.4)   # fade in
        elif t < 0.8:
            alpha = int(255 * t / 0.8)            # fade out
        else:
            alpha = 255

        alpha = max(0, min(255, alpha))
        text = f"── {self.room_banner_text} ──"
        txt_surf = self.font_banner.render(text, True, (220, 210, 200))
        txt_surf.set_alpha(alpha)
        bg = pygame.Surface((txt_surf.get_width() + 40, txt_surf.get_height() + 12), pygame.SRCALPHA)
        bg.fill((10, 10, 15, int(alpha * 0.65)))
        bx = SCREEN_WIDTH // 2 - bg.get_width() // 2
        surface.blit(bg, (bx, 148))
        surface.blit(txt_surf, (bx + 20, 154))

    # --------------------------------------------------------------------------
    # COCKROACH UPDATES
    # --------------------------------------------------------------------------
    def update_cockroaches(self, dt):
        """Update all cockroach positions and check if they're in the flashlight beam."""
        for roach in self.cockroaches:
            lit = self.is_point_in_flashlight((roach.x, roach.y))
            roach.update(dt, lit)

    def draw_cockroaches(self, surface):
        """Draw all visible cockroaches."""
        for roach in self.cockroaches:
            roach.draw(surface, self.cam_x, self.cam_y)

    # --------------------------------------------------------------------------
    # DRAW LOOP
    # --------------------------------------------------------------------------
    def draw(self):
        ox = random.randint(-self.shake_amount, self.shake_amount) if self.shake_amount > 0 else 0
        oy = random.randint(-self.shake_amount, self.shake_amount) if self.shake_amount > 0 else 0

        canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        canvas.fill((10, 8, 12))

        # ----------------- MENU -----------------
        if self.state == STATE_MENU:
            canvas.fill((12, 10, 16))
            t1 = self.font_title.render("DON'T LOOK AWAY", True, (240, 230, 220))
            canvas.blit(t1, (SCREEN_WIDTH // 2 - t1.get_width() // 2, 160))

            t2 = self.font_msg.render("A Psychological Horror Experience", True, (160, 140, 130))
            canvas.blit(t2, (SCREEN_WIDTH // 2 - t2.get_width() // 2, 225))

            t_theme = self.font_hud.render("[ Theme: UNSTABLE ]", True, (180, 80, 80))
            canvas.blit(t_theme, (SCREEN_WIDTH // 2 - t_theme.get_width() // 2, 270))

            ctrl1 = self.font_hud.render("WASD : Move   |   Mouse : Aim   |   Click/F : Flashlight ON/OFF", True, (180, 180, 180))
            ctrl2 = self.font_hud.render("E : Search Furniture & Interact   |   R : Restart", True, (160, 160, 160))
            canvas.blit(ctrl1, (SCREEN_WIDTH // 2 - ctrl1.get_width() // 2, 360))
            canvas.blit(ctrl2, (SCREEN_WIDTH // 2 - ctrl2.get_width() // 2, 395))

            blink = int(pygame.time.get_ticks() / 500) % 2 == 0
            if blink:
                t_start = self.font_msg.render("PRESS [SPACE] TO BEGIN", True, (255, 220, 100))
                canvas.blit(t_start, (SCREEN_WIDTH // 2 - t_start.get_width() // 2, 470))

        # ----------------- PROLOGUE STORY SCREEN -----------------
        elif self.state == STATE_INTRO_STORY:
            canvas.fill((8, 6, 10))
            fade = min(1.0, self.intro_timer / 1.4)
            box_rect = pygame.Rect(70, 50, SCREEN_WIDTH - 140, SCREEN_HEIGHT - 100)
            pygame.draw.rect(canvas, (25, 20, 25), box_rect)
            pygame.draw.rect(canvas, (75, 45, 45), box_rect, 2)

            head_surf = self.font_hud.render("PROLOGUE — AN UNSTABLE PERCEPTION", True, (170, 75, 75))
            canvas.blit(head_surf, (SCREEN_WIDTH // 2 - head_surf.get_width() // 2, 75))

            start_y = 135
            for i, line in enumerate(self.story_lines):
                if line:
                    is_last = (i >= len(self.story_lines) - 2)
                    color = (245, 120, 120) if is_last else (int(215 * fade), int(210 * fade), int(205 * fade))
                    line_surf = self.font_narrator.render(line, True, color)
                    canvas.blit(line_surf, (SCREEN_WIDTH // 2 - line_surf.get_width() // 2, start_y))
                start_y += 34

            if self.intro_timer > 1.2:
                blink = int(pygame.time.get_ticks() / 500) % 2 == 0
                if blink:
                    t_wake = self.font_msg.render("[ PRESS SPACE TO WAKE UP ]", True, (255, 220, 100))
                    canvas.blit(t_wake, (SCREEN_WIDTH // 2 - t_wake.get_width() // 2, SCREEN_HEIGHT - 95))

        # ----------------- PLAYING & STORY -----------------
        elif self.state in [STATE_PLAYING, STATE_READING_NOTE, STATE_READING_ID]:
            b_val = (pygame.time.get_ticks() / 1000.0) * 1.8 if self.instability > 60 else 0
            self.room.draw_environment(canvas, self.cam_x, self.cam_y, self.font_sm, self.font_hand, b_val)
            self.creature.draw(canvas, self.cam_x, self.cam_y)
            self.draw_cockroaches(canvas)

            if self.peripheral_eyes and not self.is_point_in_flashlight((self.peripheral_eyes[0], self.peripheral_eyes[1])):
                pex = int(self.peripheral_eyes[0] - self.cam_x)
                pey = int(self.peripheral_eyes[1] - self.cam_y)
                pygame.draw.circle(canvas, (240, 240, 255), (pex - 3, pey), 2)
                pygame.draw.circle(canvas, (240, 240, 255), (pex + 3, pey), 2)

            deg = -math.degrees(self.player_angle)
            rotated = pygame.transform.rotate(self.player_sprite, deg)
            spx = int(self.player_x - self.cam_x)
            spy = int(self.player_y - self.cam_y)
            rect = rotated.get_rect(center=(spx, spy))
            canvas.blit(rotated, rect.topleft)

            self.render_lighting(canvas)
            self.draw_room_banner(canvas)

            # Glints / highlight / guide arrows (drawn above the darkness)
            self.draw_interaction_cues(canvas)

            # HUD
            hud_bg = pygame.Surface((310, 68), pygame.SRCALPHA)
            hud_bg.fill((15, 15, 20, 195))
            canvas.blit(hud_bg, (20, 20))

            key_x = "[X]" if self.room.has_key else "[ ]"
            id_x = "[X]" if self.room.id_collected else "[ ]"
            obj_txt = self.font_hud.render(f"KEY: {key_x}   ID: {id_x}", True, (255, 225, 120))
            canvas.blit(obj_txt, (30, 26))

            bat_bars = int(self.battery / 10.0)
            bar_str = "█" * bat_bars + "░" * (10 - bat_bars)
            bat_color = (100, 230, 120) if self.battery > 25 else (240, 70, 60)
            bat_txt = self.font_hud.render(f"FLASHLIGHT [{bar_str}] {int(self.battery)}%", True, bat_color)
            status_str = "ON" if self.flashlight_on else "OFF"
            toggle_txt = self.font_sm.render(f"Status: {status_str} [Click to Toggle]", True, (180, 180, 190))
            canvas.blit(bat_txt, (30, 46))
            canvas.blit(toggle_txt, (30, 64))

            # Objective + search progress panel
            n_done, n_total = self.count_searched()
            obj_panel = pygame.Surface((470, 44), pygame.SRCALPHA)
            obj_panel.fill((15, 15, 20, 170))
            canvas.blit(obj_panel, (20, 94))
            canvas.blit(self.font_sm.render(self.get_objective_text(), True, (255, 225, 120)), (30, 99))
            if self.hint_timer >= HINT_DELAY and self.state == STATE_PLAYING:
                hint_line = "HINT: FOLLOW THE GLINTS AND ARROWS - STORY OBJECTS ARE MARKED"
                hint_col = (255, 200, 120) if int(pygame.time.get_ticks() / 600) % 2 == 0 else (200, 150, 90)
            else:
                hint_line = f"FURNITURE SEARCHED: {n_done}/{n_total}   (WALK CLOSE + [E])"
                hint_col = (170, 170, 180)
            canvas.blit(self.font_sm.render(hint_line, True, hint_col), (30, 118))

            # Tutorial tip until the player has done something useful
            if self.searches_done == 0 and self.game_time < 90 and self.state == STATE_PLAYING:
                tip_a = self.font_sm.render("TIP: GLINTING FURNITURE CAN BE SEARCHED.", True, (255, 240, 170))
                tip_b = self.font_sm.render("WALK CLOSE AND PRESS [E].", True, (255, 240, 170))
                tw = max(tip_a.get_width(), tip_b.get_width()) + 24
                tip_bg = pygame.Surface((tw, 52), pygame.SRCALPHA)
                tip_bg.fill((15, 15, 20, 185))
                tx = SCREEN_WIDTH - tw - 20
                canvas.blit(tip_bg, (tx, 20))
                canvas.blit(tip_a, (tx + 12, 26))
                canvas.blit(tip_b, (tx + 12, 46))

            # Contextual Interaction Prompt (same source of truth as the real action)
            current_target = self.get_current_target()
            prompt = ("[E] " + current_target["label"]) if current_target else ""

            if prompt and self.state == STATE_PLAYING:
                p_surf = self.font_hud.render(prompt, True, (255, 240, 150))
                p_bg = pygame.Surface((p_surf.get_width() + 18, p_surf.get_height() + 8), pygame.SRCALPHA)
                p_bg.fill((0, 0, 0, 195))
                bx = SCREEN_WIDTH // 2 - p_bg.get_width() // 2
                canvas.blit(p_bg, (bx, SCREEN_HEIGHT - 65))
                canvas.blit(p_surf, (bx + 9, SCREEN_HEIGHT - 61))

            # Narrative / Thought Typewriter Box
            if self.target_message:
                revealed = self.target_message[:int(self.displayed_chars)]
                color = (255, 180, 180) if self.is_thought else (245, 245, 245)
                m_surf = self.font_msg.render(revealed, True, color)
                m_bg = pygame.Surface((m_surf.get_width() + 28, m_surf.get_height() + 14), pygame.SRCALPHA)
                m_bg.fill((10, 10, 15, 220))
                b_color = (180, 50, 50) if self.is_thought else (80, 80, 95)
                pygame.draw.rect(m_bg, b_color, (0, 0, m_bg.get_width(), m_bg.get_height()), 1)
                mx = SCREEN_WIDTH // 2 - m_bg.get_width() // 2
                canvas.blit(m_bg, (mx, SCREEN_HEIGHT - 105))
                canvas.blit(m_surf, (mx + 14, SCREEN_HEIGHT - 98))

            if self.state == STATE_READING_NOTE:
                self.draw_note_overlay(canvas)
            elif self.state == STATE_READING_ID:
                self.draw_id_card_overlay(canvas)

            # Debug HUD (F1)
            if self.debug_mode:
                dbg_bg = pygame.Surface((340, 140), pygame.SRCALPHA)
                dbg_bg.fill((0, 0, 0, 210))
                canvas.blit(dbg_bg, (SCREEN_WIDTH - 360, 20))
                dbg_lines = [
                    f"[DEBUG HUD - F1 to toggle]",
                    f"Instability: {self.instability:.1f}%",
                    f"Creature Stage: {self.creature.stage} (Frozen: {self.creature.is_frozen})",
                    f"F2: Force Next Event | F3: Give Items",
                    f"Recent Events:",
                ]
                for i, dl in enumerate(dbg_lines):
                    dtxt = self.font_sm.render(dl, True, (255, 120, 120) if i == 0 else (220, 220, 220))
                    canvas.blit(dtxt, (SCREEN_WIDTH - 350, 26 + i * 16))
                for j, el in enumerate(self.director.event_log[-3:]):
                    etxt = self.font_sm.render(f"- {el}", True, (255, 200, 100))
                    canvas.blit(etxt, (SCREEN_WIDTH - 350, 98 + j * 15))

        # ----------------- SUCCESSFUL ESCAPE & PLOT TWIST ENDING -----------------
        elif self.state == STATE_ENDING_ESCAPE:
            canvas.fill((15, 15, 18))

            if self.ending_phase == 1:
                # Door unlatches, soft warm white light shines in
                light_fade = min(1.0, self.ending_timer / 2.2)
                glow_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                glow_surf.fill((255, 250, 240, int(180 * light_fade)))
                canvas.blit(glow_surf, (0, 0))
                t1 = self.font_title.render("THE DOOR UNLATCHES.", True, (40, 40, 45))
                canvas.blit(t1, (SCREEN_WIDTH // 2 - t1.get_width() // 2, SCREEN_HEIGHT // 2 - 20))

            elif self.ending_phase == 2:
                # Step into clean, brightly-lit medical care corridor
                canvas.fill((235, 235, 240))  # Sterile clean white/pale grey
                # Clean floor tiles
                for y in range(0, SCREEN_HEIGHT, 60):
                    pygame.draw.line(canvas, (215, 215, 220), (0, y), (SCREEN_WIDTH, y), 2)
                for x in range(0, SCREEN_WIDTH, 80):
                    pygame.draw.line(canvas, (215, 215, 220), (x, 0), (x, SCREEN_HEIGHT), 2)

                # Wall with Room 4 door
                pygame.draw.rect(canvas, (180, 185, 195), (SCREEN_WIDTH // 2 - 120, 100, 240, 360))
                pygame.draw.rect(canvas, (100, 105, 115), (SCREEN_WIDTH // 2 - 120, 100, 240, 360), 3)

                # Brass room sign: ROOM 4
                pygame.draw.rect(canvas, (215, 190, 80), (SCREEN_WIDTH // 2 - 60, 140, 120, 45))
                pygame.draw.rect(canvas, (140, 110, 30), (SCREEN_WIDTH // 2 - 60, 140, 120, 45), 2)
                r_txt = self.font_hud.render("ROOM 4", True, (40, 35, 20))
                canvas.blit(r_txt, (SCREEN_WIDTH // 2 - r_txt.get_width() // 2, 153))

                # Note the unengaged door lock:
                u_txt = self.font_msg.render("The door swings gently open. There was never a lock.", True, (70, 70, 80))
                canvas.blit(u_txt, (SCREEN_WIDTH // 2 - u_txt.get_width() // 2, 510))

            elif self.ending_phase >= 3:
                # Clean Observation Whiteboard
                canvas.fill((20, 20, 24))
                board_rect = pygame.Rect(SCREEN_WIDTH // 2 - 280, 70, 560, 380)
                pygame.draw.rect(canvas, (245, 245, 250), board_rect)
                pygame.draw.rect(canvas, (70, 95, 140), board_rect, 4)

                bh = self.font_hud.render("ST. ALDRIC RESIDENCE  -  NIGHT OBSERVATION LOG", True, (60, 80, 120))
                canvas.blit(bh, (SCREEN_WIDTH // 2 - bh.get_width() // 2, 90))

                log_lines = [
                    "RESIDENT: #0412 (ROOM 4)",
                    "STATUS: Acute nocturnal disorientation. Harmless.",
                    "",
                    "OBSERVATION NOTES:",
                    "- Resident reported being stalked by an entity in darkness.",
                    "- Emptied bookshelves looking for a 'key' to escape.",
                    "- Rearranged room chair multiple times during episode.",
                    "",
                    "DIRECTIVE: Room door must remain unlocked per hospital rules.",
                    "Night staff have placed a flashlight beside his bed."
                ]
                ly = 135
                for l in log_lines:
                    color = (180, 40, 40) if "DIRECTIVE" in l else (40, 45, 55)
                    fnt = self.font_sm if len(l) > 40 else self.font_hud
                    lt = fnt.render(l, True, color)
                    canvas.blit(lt, (board_rect.x + 25, ly))
                    ly += 24

                # Plot twist reflection
                if self.ending_phase == 4:
                    tw1 = self.font_msg.render("There was no creature.", True, (240, 220, 210))
                    tw2 = self.font_narrator.render("You were running from your own shadow.", True, (200, 160, 160))
                    canvas.blit(tw1, (SCREEN_WIDTH // 2 - tw1.get_width() // 2, 480))
                    canvas.blit(tw2, (SCREEN_WIDTH // 2 - tw2.get_width() // 2, 520))

                    t_sub = self.font_hud.render("Press [R] to Play Again   |   [ESC] to Quit", True, (160, 160, 160))
                    canvas.blit(t_sub, (SCREEN_WIDTH // 2 - t_sub.get_width() // 2, 580))

        # ----------------- JUMPSCARE (Scripted) -----------------
        elif self.state == STATE_JUMPSCARE:
            t = self.state_timer
            canvas.fill((3, 3, 5))

            if t < 0.05:
                # Hard blackout before the image hits.
                pass
            elif t < 0.40:
                # Full-screen supplied monster, with a very short punch-in.
                zoom = 1.0 if t < 0.15 else 1.0 + min(0.18, (t - 0.15) / 0.25 * 0.18)
                sw = max(1, int(SCREEN_WIDTH * zoom))
                sh = max(1, int(SCREEN_HEIGHT * zoom))
                img = pygame.transform.smoothscale(self.jumpscare_sprite, (sw, sh))
                ox = (SCREEN_WIDTH - sw) // 2
                oy = (SCREEN_HEIGHT - sh) // 2
                if t >= 0.15:
                    ox += random.randint(-10, 10)
                    oy += random.randint(-8, 8)
                canvas.blit(img, (ox, oy))

                # One deliberate flash at the impact moment, rather than random
                # flashing every frame (which was making the old scare muddy).
                if 0.15 <= t < 0.20:
                    flash_alpha = int(210 * (1.0 - (t - 0.15) / 0.05))
                    flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                    flash.fill((220, 35, 35, flash_alpha))
                    canvas.blit(flash, (0, 0))
            elif t < 0.70:
                # Monster is gone. Let the silence/blackness land.
                pass
            elif t < 2.00:
                # First message appears after the black beat.
                fade = min(1.0, (t - 0.70) / 0.18)
                text = self.font_msg.render("YOU SHOULD HAVE LOOKED BACK.", True, (255, 255, 255))
                text.set_alpha(int(255 * fade))
                canvas.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT - 75))
            else:
                # Fade from the first line into the final realization.
                fade = min(1.0, (t - 2.00) / 0.65)
                text1 = self.font_msg.render("YOU SHOULD HAVE LOOKED BACK.", True, (255, 255, 255))
                text1.set_alpha(int(255 * (1.0 - fade)))
                canvas.blit(text1, (SCREEN_WIDTH // 2 - text1.get_width() // 2, SCREEN_HEIGHT - 75))

<<<<<<< HEAD
                final_lines = [
                    "There was no shadow.",
                    "There was no creature.",
                    "You were running from yourself."
                ]
                line_gap = 30
                total_h = (len(final_lines) - 1) * line_gap
                start_y = SCREEN_HEIGHT // 2 - total_h // 2
                for i, line in enumerate(final_lines):
                    text2 = self.font_msg.render(line, True, (220, 215, 210))
                    text2.set_alpha(int(255 * fade))
                    canvas.blit(text2, (SCREEN_WIDTH // 2 - text2.get_width() // 2, start_y + i * line_gap))
=======
                text2 = self.font_msg.render("There was never anyone else in the room.", True, (220, 215, 210))
                text2.set_alpha(int(255 * fade))
                canvas.blit(text2, (SCREEN_WIDTH // 2 - text2.get_width() // 2, SCREEN_HEIGHT // 2 - 30))
>>>>>>> ce92908b7253be319a1663faaae5e73172fea28c

        # ----------------- AMBIGUOUS ENDING (Blackout Death) -----------------
        elif self.state == STATE_AMBIGUOUS_ENDING:
            canvas.fill((4, 4, 6))

            final_lines = [
                "There was no shadow.",
                "There was no creature.",
                "Every sound was yours.",
                "You were running from yourself."
            ]
            line_gap = 30
            total_h = (len(final_lines) - 1) * line_gap
            start_y = SCREEN_HEIGHT // 2 - total_h // 2
            for i, line in enumerate(final_lines):
                t_end = self.font_msg.render(line, True, (220, 215, 210))
                canvas.blit(t_end, (SCREEN_WIDTH // 2 - t_end.get_width() // 2, start_y + i * line_gap))

            if self.state_timer >= 2.5:
                t_sub = self.font_hud.render("Press [R] to Play Again   |   [ESC] to Quit", True, (160, 160, 160))
                canvas.blit(t_sub, (SCREEN_WIDTH // 2 - t_sub.get_width() // 2, SCREEN_HEIGHT // 2 + 35))

        # Apply instability-driven visual distortion
        self.apply_sanity_effects(canvas)

        self.screen.fill((0, 0, 0))
        self.screen.blit(canvas, (ox, oy))
        pygame.display.flip()

    # --------------------------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------------------------
    def run(self):
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
                        self.audio.start_drone()

                    elif event.key == pygame.K_F1:
                        self.debug_mode = not self.debug_mode

                    elif event.key == pygame.K_F2:
                        self.director.trigger_next_event(force=True)

                    elif event.key == pygame.K_F3:
                        self.room.has_key = True
                        self.room.key_collected = True
                        self.room.key_revealed = True
                        self.room.id_collected = True
                        self.room.id_revealed = True
                        self.show_message("[DEBUG] GAVE KEY AND ID", 2.5)

                    elif event.key == pygame.K_SPACE:
                        if self.state == STATE_MENU:
                            self.state = STATE_INTRO_STORY
                            self.intro_timer = 0.0
                        elif self.state == STATE_INTRO_STORY:
                            self.state = STATE_PLAYING
                            self.audio.start_drone()
                            self.show_message("FIND THE KEY. FIND MY ID.", 4.0)
                        elif self.state == STATE_READING_NOTE:
                            self.state = STATE_PLAYING
                            self.room.note_read = True
                            self.instability = min(100.0, self.instability + INSTABILITY_NOTE_BOOST)
                            self.show_thought("...I DIDN'T WRITE ON THE WALLS.")
                        elif self.state == STATE_READING_ID:
                            self.state = STATE_PLAYING
                            self.room.id_collected = True
                            self.instability = min(100.0, self.instability + INSTABILITY_ID_BOOST)
                            self.show_thought("THIS IS MY ROOM.")

                    elif event.key == pygame.K_e:
                        if self.state == STATE_PLAYING:
                            self.handle_interaction()
                        elif self.state == STATE_READING_NOTE:
                            self.state = STATE_PLAYING
                            self.room.note_read = True
                            self.instability = min(100.0, self.instability + INSTABILITY_NOTE_BOOST)
                            self.show_thought("...I DIDN'T WRITE ON THE WALLS.")
                        elif self.state == STATE_READING_ID:
                            self.state = STATE_PLAYING
                            self.room.id_collected = True
                            self.instability = min(100.0, self.instability + INSTABILITY_ID_BOOST)
                            self.show_thought("THIS IS MY ROOM.")

                    elif event.key == pygame.K_f:
                        if self.state == STATE_PLAYING:
                            self.toggle_flashlight()

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.state == STATE_MENU:
                        self.state = STATE_INTRO_STORY
                        self.intro_timer = 0.0
                    elif self.state == STATE_INTRO_STORY:
                        self.state = STATE_PLAYING
                        self.audio.start_drone()
                        self.show_message("FIND THE KEY. FIND MY ID.", 4.0)
                    elif self.state in [STATE_READING_NOTE, STATE_READING_ID]:
                        if self.state == STATE_READING_NOTE:
                            self.room.note_read = True
                            self.instability = min(100.0, self.instability + INSTABILITY_NOTE_BOOST)
                            self.show_thought("...I DIDN'T WRITE ON THE WALLS.")
                        else:
                            self.room.id_collected = True
                            self.instability = min(100.0, self.instability + INSTABILITY_ID_BOOST)
                            self.show_thought("THIS IS MY ROOM.")
                        self.state = STATE_PLAYING
                    elif self.state == STATE_PLAYING:
                        if event.button in [1, 3]:
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