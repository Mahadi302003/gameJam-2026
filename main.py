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


class AudioManager:
    """Manages audio loading from disk with procedural fallback."""
    def __init__(self):
        self.sounds = {}
        sound_names = [
            "drone", "whisper", "drawer_open", "click", "footstep", "pickup_battery",
            "pickup_key", "creature_move", "door_open", "heartbeat", "jumpscare"
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

        self.drone_channel = None

    def start_drone(self):
        if not AUDIO_INITIALIZED:
            return
        snd = self.sounds.get("drone")
        if snd:
            try:
                self.drone_channel = snd.play(loops=-1)
                if self.drone_channel:
                    self.drone_channel.set_volume(0.25)
            except Exception:
                pass

    def set_drone_volume(self, vol):
        if self.drone_channel:
            try:
                self.drone_channel.set_volume(max(0.0, min(1.0, vol)))
            except Exception:
                pass

    def stop_drone(self):
        if self.drone_channel:
            try:
                self.drone_channel.stop()
            except Exception:
                pass

    def play(self, name, volume=1.0):
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
    # State 0: Normal portrait
    s0 = pygame.Surface((w, h))
    s0.fill((110, 80, 50))
    pygame.draw.rect(s0, (50, 40, 35), (4, 4, w - 8, h - 8))
    pygame.draw.circle(s0, (160, 140, 120), (w // 2, h // 2 - 2), 10)
    pygame.draw.circle(s0, (70, 50, 40), (w // 2, h // 2 - 6), 10)
    pygame.draw.rect(s0, (30, 25, 20), (w // 2 - 5, h // 2 - 3, 2, 2))
    pygame.draw.rect(s0, (30, 25, 20), (w // 2 + 1, h // 2 - 3, 2, 2))

    # State 1: Eyes shifted facing player
    s1 = pygame.Surface((w, h))
    s1.fill((100, 70, 45))
    pygame.draw.rect(s1, (45, 30, 30), (4, 4, w - 8, h - 8))
    pygame.draw.circle(s1, (180, 160, 140), (w // 2, h // 2 - 2), 10)
    pygame.draw.circle(s1, (50, 30, 30), (w // 2, h // 2 - 6), 10)
    pygame.draw.circle(s1, (255, 255, 255), (w // 2 - 4, h // 2 - 3), 3)
    pygame.draw.circle(s1, (255, 255, 255), (w // 2 + 4, h // 2 - 3), 3)
    pygame.draw.circle(s1, (180, 0, 0), (w // 2 - 4, h // 2 - 3), 1)
    pygame.draw.circle(s1, (180, 0, 0), (w // 2 + 4, h // 2 - 3), 1)

    # State 2: Face replaced by dark blank oval void
    s2 = pygame.Surface((w, h))
    s2.fill((70, 45, 30))
    pygame.draw.rect(s2, (20, 15, 20), (4, 4, w - 8, h - 8))
    pygame.draw.ellipse(s2, (5, 5, 8), (w // 2 - 10, h // 2 - 12, 20, 24))

    # State 3: Scratched wall
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

    def draw(self, surface, cam_x, cam_y):
        sx = self.closed_rect.x - cam_x
        sy = self.closed_rect.y - cam_y
        w, h = self.closed_rect.width, self.closed_rect.height

        if self.is_exit:
            color = (65, 85, 65) if self.is_open else (90, 45, 45)
            pygame.draw.rect(surface, color, (sx, sy, w, h))
            pygame.draw.rect(surface, (25, 25, 25), (sx, sy, w, h), 2)
            pygame.draw.circle(surface, (220, 190, 80), (sx + w // 2, sy + h // 2), 4)
        else:
            if not self.is_open:
                pygame.draw.rect(surface, (110, 80, 55), (sx, sy, w, h))
                pygame.draw.rect(surface, (55, 38, 25), (sx, sy, w, h), 2)
                knob_x = sx + (w - 8 if w > h else w // 2)
                knob_y = sy + (h // 2 if w > h else h - 8)
                pygame.draw.circle(surface, (215, 185, 75), (knob_x, knob_y), 3)
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
        self.house_rect = pygame.Rect(100, 80, 1300, 880)

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
            sx = w.x - cam_x + bx_off
            sy = w.y - cam_y + by_off
            pygame.draw.rect(surface, (55, 48, 44), (sx, sy, w.w, w.h))
            pygame.draw.rect(surface, (30, 25, 22), (sx, sy, w.w, w.h), 2)

        # Interactive Doors
        for d in self.doors:
            d.draw(surface, cam_x, cam_y)

        # Fake Door Wrongness
        if self.fake_door_visible:
            fdx = self.fake_door_rect.x - cam_x
            fdy = self.fake_door_rect.y - cam_y
            pygame.draw.rect(surface, (60, 40, 35), (fdx, fdy, self.fake_door_rect.w, self.fake_door_rect.h))
            pygame.draw.rect(surface, (30, 15, 15), (fdx, fdy, self.fake_door_rect.w, self.fake_door_rect.h), 2)
            pygame.draw.circle(surface, (180, 150, 60), (fdx + 10, fdy + self.fake_door_rect.h // 2), 3)

        # Graffiti Lines
        for g in self.graffiti_lines:
            if g["visible"]:
                gx = g["pos"][0] - cam_x
                gy = g["pos"][1] - cam_y
                gsurf = font_hand.render(g["text"], True, (140, 75, 75))
                surface.blit(gsurf, (gx, gy))

        # --- BEDROOM ---
        bx, by = self.bed_rect.x - cam_x, self.bed_rect.y - cam_y
        pygame.draw.rect(surface, (75, 52, 38), (bx, by, self.bed_rect.w, self.bed_rect.h))
        pygame.draw.rect(surface, (135, 125, 115), (bx + 6, by + 6, self.bed_rect.w - 12, self.bed_rect.h - 12))
        pygame.draw.rect(surface, (175, 170, 160), (bx + 10, by + 10, self.bed_rect.w - 20, 32))
        pygame.draw.rect(surface, (90, 70, 60), (bx + 6, by + 65, self.bed_rect.w - 12, self.bed_rect.h - 71))
        if self.bed_lump:
            pygame.draw.ellipse(surface, (65, 48, 42), (bx + 20, by + 80, self.bed_rect.w - 40, 55))
            pygame.draw.ellipse(surface, (110, 85, 75), (bx + 25, by + 85, self.bed_rect.w - 50, 45), 2)

        # Nightstand
        nx, ny = self.nightstand_rect.x - cam_x, self.nightstand_rect.y - cam_y
        pygame.draw.rect(surface, (85, 60, 42), (nx, ny, self.nightstand_rect.w, self.nightstand_rect.h))
        pygame.draw.rect(surface, (45, 32, 22), (nx, ny, self.nightstand_rect.w, self.nightstand_rect.h), 2)

        # Note on Nightstand (if unread)
        if not self.note_read:
            ntx, nty = self.note_rect.x - cam_x, self.note_rect.y - cam_y
            pygame.draw.rect(surface, (230, 225, 210), (ntx, nty, self.note_rect.w, self.note_rect.h))
            pygame.draw.rect(surface, (180, 170, 150), (ntx, nty, self.note_rect.w, self.note_rect.h), 1)
            for i in range(3):
                pygame.draw.line(surface, (90, 80, 70), (ntx + 3, nty + 4 + i * 5), (ntx + self.note_rect.w - 3, nty + 4 + i * 5), 1)

        # Wardrobe
        wx, wy = self.wardrobe_rect.x - cam_x, self.wardrobe_rect.y - cam_y
        pygame.draw.rect(surface, (68, 44, 28), (wx, wy, self.wardrobe_rect.w, self.wardrobe_rect.h))
        pygame.draw.rect(surface, (38, 24, 15), (wx, wy, self.wardrobe_rect.w, self.wardrobe_rect.h), 2)
        pygame.draw.line(surface, (20, 10, 8), (wx + self.wardrobe_rect.w // 2, wy + 4),
                         (wx + self.wardrobe_rect.w // 2, wy + self.wardrobe_rect.h - 4), 2)

        # Moving Chair
        cx, cy = self.chair_rect.x - cam_x, self.chair_rect.y - cam_y
        pygame.draw.rect(surface, (105, 72, 48), (cx, cy, self.chair_rect.w, self.chair_rect.h))
        pygame.draw.rect(surface, (55, 38, 24), (cx, cy, self.chair_rect.w, self.chair_rect.h), 2)
        if self.chair_stage == 2:
            pygame.draw.rect(surface, (75, 48, 28), (cx + self.chair_rect.w - 6, cy + 2, 4, self.chair_rect.h - 4))
        elif self.chair_stage == 3:
            pygame.draw.rect(surface, (75, 48, 28), (cx + 2, cy + 2, self.chair_rect.w - 4, 4))
        else:
            pygame.draw.rect(surface, (75, 48, 28), (cx + 2, cy + self.chair_rect.h - 6, self.chair_rect.w - 4, 4))

        if self.shoes_visible:
            sx, sy = self.shoes_pos[0] - cam_x, self.shoes_pos[1] - cam_y
            pygame.draw.ellipse(surface, (30, 20, 15), (sx, sy, 8, 14))
            pygame.draw.ellipse(surface, (30, 20, 15), (sx + 11, sy, 8, 14))

        # --- STUDY ---
        dx, dy = self.study_desk_rect.x - cam_x, self.study_desk_rect.y - cam_y
        pygame.draw.rect(surface, (95, 68, 46), (dx, dy, self.study_desk_rect.w, self.study_desk_rect.h))
        pygame.draw.rect(surface, (55, 38, 26), (dx, dy, self.study_desk_rect.w, self.study_desk_rect.h), 2)
        pygame.draw.rect(surface, (195, 190, 175), (dx + 15, dy + 15, 24, 28))
        pygame.draw.rect(surface, (185, 180, 165), (dx + 48, dy + 20, 28, 24))

        if self.cup_visible:
            cpx, cpy = self.cup_pos[0] - cam_x, self.cup_pos[1] - cam_y
            pygame.draw.circle(surface, (210, 200, 190), (int(cpx), int(cpy)), 5)
            pygame.draw.circle(surface, (60, 45, 35), (int(cpx), int(cpy)), 3)

        # Bookshelves
        for b in [self.bookshelf_1, self.bookshelf_2]:
            bx, by = b.x - cam_x, b.y - cam_y
            pygame.draw.rect(surface, (78, 52, 34), (bx, by, b.w, b.h))
            pygame.draw.rect(surface, (45, 30, 20), (bx, by, b.w, b.h), 2)
            for i in range(5):
                pygame.draw.rect(surface, (140 + i * 15, 60 + i * 10, 40), (bx + 8 + i * 24, by + 4, 18, b.h - 8))

        stx, sty = self.study_table.x - cam_x, self.study_table.y - cam_y
        pygame.draw.rect(surface, (88, 62, 42), (stx, sty, self.study_table.w, self.study_table.h))

        # Painting
        px, py = self.painting_rect.x - cam_x, self.painting_rect.y - cam_y
        surface.blit(self.painting_surfs[self.painting_state], (px, py))

        # --- STORAGE ROOM ---
        for crate in [self.storage_crate_1, self.storage_crate_2]:
            cx, cy = crate.x - cam_x, crate.y - cam_y
            pygame.draw.rect(surface, (82, 60, 42), (cx, cy, crate.w, crate.h))
            pygame.draw.rect(surface, (48, 34, 22), (cx, cy, crate.w, crate.h), 2)
            pygame.draw.line(surface, (48, 34, 22), (cx, cy), (cx + crate.w, cy + crate.h), 2)

        sx, sy = self.storage_shelf.x - cam_x, self.storage_shelf.y - cam_y
        pygame.draw.rect(surface, (70, 48, 32), (sx, sy, self.storage_shelf.w, self.storage_shelf.h))

        # --- FOYER ---
        fx, fy = self.foyer_table.x - cam_x, self.foyer_table.y - cam_y
        pygame.draw.rect(surface, (85, 60, 42), (fx, fy, self.foyer_table.w, self.foyer_table.h))
        fx, fy = self.foyer_shelf.x - cam_x, self.foyer_shelf.y - cam_y
        pygame.draw.rect(surface, (75, 50, 35), (fx, fy, self.foyer_shelf.w, self.foyer_shelf.h))

        # --- REVEALED KEY (Inside Bookshelf 1) ---
        if self.key_revealed and not self.key_collected:
            kx = self.bookshelf_1.centerx - cam_x
            ky = self.bookshelf_1.centery - cam_y
            pulse = math.sin(pygame.time.get_ticks() / 240.0) * 3
            pygame.draw.circle(surface, (255, 230, 80), (int(kx), int(ky - 3)), int(6 + pulse), 1)
            pygame.draw.circle(surface, (255, 215, 60), (int(kx), int(ky - 3)), 4)
            pygame.draw.rect(surface, (255, 215, 60), (int(kx - 1), int(ky - 1), 3, 9))

        # --- FALSE KEY ---
        if self.false_key_visible and not self.false_key_used:
            fkx = self.false_key_rect.centerx - cam_x
            fky = self.false_key_rect.centery - cam_y
            pygame.draw.circle(surface, (220, 200, 100), (int(fkx), int(fky - 3)), 4)
            pygame.draw.rect(surface, (220, 200, 100), (int(fkx - 1), int(fky - 1), 3, 8))

        # --- BATTERIES (if revealed and uncollected) ---
        for bat in self.batteries:
            if bat["revealed"] and not bat["collected"]:
                r = bat["rect"]
                bx, by = r.x - cam_x, r.y - cam_y
                pygame.draw.rect(surface, (50, 185, 100), (bx, by + 2, r.w, r.h - 4))
                pygame.draw.rect(surface, (220, 220, 220), (bx + r.w - 2, by + r.h // 2 - 2, 3, 4))
                pygame.draw.rect(surface, (20, 40, 20), (bx, by + 2, r.w, r.h - 4), 1)


# ==============================================================================
# 6. CREATURE CONTROLLER (Stalking & Dynamic Poses)
# ==============================================================================
class Creature:
    def __init__(self):
        self.poses = create_creature_poses()
        self.pose_index = 0
        self.width = 40
        self.height = 52

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

        self.pose_index = (self.pose_index + 1) % len(self.poses)
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))

    def _reposition_near_player(self, player_pos):
        px, py = player_pos
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(140, 210)
        nx = max(140, min(1340, px + math.cos(angle) * dist))
        ny = max(120, min(900, py + math.sin(angle) * dist))
        self.pos = [nx, ny]

    def draw(self, surface, cam_x, cam_y):
        if self.is_active:
            sprite = self.poses[self.pose_index]
            draw_x = self.pos[0] - cam_x - sprite.get_width() // 2
            draw_y = self.pos[1] - cam_y - sprite.get_height() // 2
            surface.blit(sprite, (draw_x, draw_y))


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
        self.jumpscare_sprite = create_jumpscare_surface()

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

    def handle_interaction(self):
        px, py = self.player_x, self.player_y

        # 1. Search Bedroom Nightstand
        if math.hypot(px - self.room.nightstand_rect.centerx, py - self.room.nightstand_rect.centery) < 55:
            if not self.room.note_read:
                self.state = STATE_READING_NOTE
                self.audio.play("whisper", 0.7)
                return
            elif not self.room.nightstand_searched:
                self.room.nightstand_searched = True
                self.room.batteries[0]["revealed"] = True
                self.audio.play("drawer_open", 0.8)
                self.show_message("SEARCHED NIGHTSTAND: FOUND A SPARE BATTERY!", 3.5)
                return

        # 2. Check Wardrobe in Bedroom
        if math.hypot(px - self.room.wardrobe_rect.centerx, py - self.room.wardrobe_rect.centery) < 65:
            self.audio.play("drawer_open", 0.7)
            self.show_thought("EMPTY HANGERS... SCRATCH MARKS ON THE INSIDE DOORS.")
            return

        # 3. Search Study Bookshelf (Hollow book holds the Key!)
        if math.hypot(px - self.room.bookshelf_1.centerx, py - self.room.bookshelf_1.centery) < 60:
            if not self.room.bookshelf_searched:
                self.room.bookshelf_searched = True
                self.room.key_revealed = True
                self.audio.play("drawer_open", 0.9)
                self.show_message("A HOLLOW BOOK... THE KEY WAS HIDDEN INSIDE!", 4.0)
                return
            elif self.room.key_revealed and not self.room.key_collected:
                self.room.key_collected = True
                self.room.has_key = True
                self.instability = min(100.0, self.instability + INSTABILITY_KEY_BOOST)
                self.audio.play("pickup_key", 0.9)
                self.show_message("KEY ACQUIRED.", 3.5)
                return

        # 4. Search Study Desk Drawers
        if math.hypot(px - self.room.study_desk_rect.centerx, py - self.room.study_desk_rect.centery) < 65:
            self.audio.play("drawer_open", 0.8)
            self.show_thought("SEARCHED DESK: SHREDDED PATIENT LOGS AND MEDICATION SLIPS.")
            return

        # 5. Search Storage Shelf (Where ID Card is tucked!)
        if math.hypot(px - self.room.storage_shelf.centerx, py - self.room.storage_shelf.centery) < 60:
            if not self.room.storage_shelf_searched:
                self.room.storage_shelf_searched = True
                self.room.id_revealed = True
                self.state = STATE_READING_ID
                self.state_timer = 0.0
                self.audio.play("pickup_key", 0.8)
                return
            elif self.room.id_revealed and not self.room.id_collected:
                self.state = STATE_READING_ID
                self.state_timer = 0.0
                return

        # 6. Search Storage Wooden Crate 1
        if math.hypot(px - self.room.storage_crate_1.centerx, py - self.room.storage_crate_1.centery) < 55:
            if not self.room.storage_crate_1_searched:
                self.room.storage_crate_1_searched = True
                self.room.batteries[1]["revealed"] = True
                self.audio.play("drawer_open", 0.8)
                self.show_message("SEARCHED CRATE: FOUND A SPARE BATTERY!", 3.5)
                return

        # 7. False Key interaction
        if self.room.false_key_visible and not self.room.false_key_used:
            if math.hypot(px - self.room.false_key_rect.centerx, py - self.room.false_key_rect.centery) < 50:
                self.room.false_key_used = True
                self.room.false_key_visible = False
                self.audio.play("whisper", 0.9)
                self.flicker_frames = 4
                self.show_message("...IT WASN'T REAL.", 3.5, is_thought=True)
                return

        # 8. Fake Door interaction
        if self.room.fake_door_visible:
            if math.hypot(px - self.room.fake_door_rect.centerx, py - self.room.fake_door_rect.centery) < 65:
                self.room.fake_door_visible = False
                self.audio.play("whisper", 0.8)
                self.flicker_frames = 3
                self.show_message("...THERE'S NOTHING THERE.", 3.5, is_thought=True)
                return

        # 9. Batteries pickup (only if revealed)
        for bat in self.room.batteries:
            if bat["revealed"] and not bat["collected"] and math.hypot(px - bat["rect"].centerx, py - bat["rect"].centery) < 50:
                bat["collected"] = True
                self.battery = min(100.0, self.battery + BATTERY_REFILL)
                self.audio.play("pickup_battery", 0.85)
                self.show_message(f"BATTERY COLLECTED (+{int(BATTERY_REFILL)}%)", 3.0)
                return

        # 10. Interactive Doors & Exit Door
        for d in self.room.doors:
            dist = math.hypot(px - d.closed_rect.centerx, py - d.closed_rect.centery)
            if dist < 65:
                if d.is_exit:
                    if self.room.has_key and self.room.id_collected:
                        # SUCCESSFUL ESCAPE & PLOT TWIST SEQUENCE!
                        d.is_open = True
                        self.state = STATE_ENDING_ESCAPE
                        self.ending_phase = 1
                        self.ending_timer = 0.0
                        self.audio.play("door_open", 0.9)
                        return
                    elif not self.room.has_key:
                        self.show_message("THE DOOR IS LOCKED.", 3.0)
                        return
                    elif not self.room.id_collected:
                        self.show_message("I CAN'T LEAVE WITHOUT MY ID.", 3.0)
                        return
                else:
                    d.toggle()
                    self.audio.play("door_open", 0.8)
                    return

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
                self.audio.play("creature_move", 0.6)

        # Danger only in total darkness when battery hits 0
        if not self.flashlight_on:
            dist = math.hypot(self.player_x - self.creature.pos[0], self.player_y - self.creature.pos[1])
            if dist < CREATURE_ATTACK_DIST:
                self.trigger_jumpscare()

    def trigger_jumpscare(self):
        """Only triggered if caught in pitch darkness when battery reaches 0%."""
        self.state = STATE_JUMPSCARE
        self.state_timer = 0.0
        self.audio.stop_drone()
        self.audio.play("jumpscare", 1.0)
        self.shake_amount = 7  # Significantly reduced screen shake

    def update(self, dt):
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
            self.handle_input(dt)
            self.update_instability(dt)
            self.update_creature(dt)

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
            self.shake_amount = random.randint(4, 8)  # Gentle shake
            if self.state_timer >= 2.2:
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

        nw, nh = 470, 270
        nx = SCREEN_WIDTH // 2 - nw // 2
        ny = SCREEN_HEIGHT // 2 - nh // 2
        pygame.draw.rect(surface, (235, 230, 215), (nx, ny, nw, nh))
        pygame.draw.rect(surface, (160, 150, 130), (nx, ny, nw, nh), 2)

        lines = [
            "You told us again last night that someone was in the room.",
            "Nobody was there. We put the furniture back where you like it.",
            "Please take your evening tablets.",
            "Please stop writing on the walls.",
            "",
            "- Night Staff"
        ]
        start_y = ny + 25
        for line in lines:
            if line:
                tsurf = self.font_hand.render(line, True, (40, 30, 30))
                surface.blit(tsurf, (nx + 25, start_y))
            start_y += 32

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

            if self.creature.is_active and self.creature.is_illuminated:
                cx = self.creature.pos[0] - self.cam_x
                cy = self.creature.pos[1] - self.cam_y
                pygame.draw.circle(canvas, (255, 255, 255), (int(cx - 4), int(cy - 14)), 2)
                pygame.draw.circle(canvas, (255, 255, 255), (int(cx + 4), int(cy - 14)), 2)
                pygame.draw.circle(canvas, (255, 60, 40), (int(cx - 4), int(cy - 14)), 1)
                pygame.draw.circle(canvas, (255, 60, 40), (int(cx + 4), int(cy - 14)), 1)

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

            # Contextual Interaction Prompts (Searching Furniture)
            px, py = self.player_x, self.player_y
            prompt = ""

            if math.hypot(px - self.room.nightstand_rect.centerx, py - self.room.nightstand_rect.centery) < 55:
                if not self.room.note_read:
                    prompt = "[E] Read Note"
                elif not self.room.nightstand_searched:
                    prompt = "[E] Search Nightstand Drawer"
            elif math.hypot(px - self.room.wardrobe_rect.centerx, py - self.room.wardrobe_rect.centery) < 65:
                prompt = "[E] Check Wardrobe"
            elif math.hypot(px - self.room.bookshelf_1.centerx, py - self.room.bookshelf_1.centery) < 60:
                if not self.room.bookshelf_searched:
                    prompt = "[E] Search Bookshelf"
                elif self.room.key_revealed and not self.room.key_collected:
                    prompt = "[E] Take Key"
            elif math.hypot(px - self.room.study_desk_rect.centerx, py - self.room.study_desk_rect.centery) < 65:
                prompt = "[E] Search Desk Drawers"
            elif math.hypot(px - self.room.storage_shelf.centerx, py - self.room.storage_shelf.centery) < 60:
                if not self.room.storage_shelf_searched:
                    prompt = "[E] Search Storage Shelf"
                elif self.room.id_revealed and not self.room.id_collected:
                    prompt = "[E] Pick up ID Card"
            elif math.hypot(px - self.room.storage_crate_1.centerx, py - self.room.storage_crate_1.centery) < 55:
                if not self.room.storage_crate_1_searched:
                    prompt = "[E] Search Wooden Crate"
            elif self.room.false_key_visible and not self.room.false_key_used and math.hypot(px - self.room.false_key_rect.centerx, py - self.room.false_key_rect.centery) < 50:
                prompt = "[E] Pick up Key"
            elif self.room.fake_door_visible and math.hypot(px - self.room.fake_door_rect.centerx, py - self.room.fake_door_rect.centery) < 65:
                prompt = "[E] Open Door"
            else:
                for b in self.room.batteries:
                    if b["revealed"] and not b["collected"] and math.hypot(px - b["rect"].centerx, py - b["rect"].centery) < 50:
                        prompt = "[E] Pick up Battery"
                        break
                if not prompt:
                    for d in self.room.doors:
                        if math.hypot(px - d.closed_rect.centerx, py - d.closed_rect.centery) < 65:
                            if d.is_exit:
                                prompt = "[E] Unlock Exit Door" if (self.room.has_key and self.room.id_collected) else "[E] Examine Locked Exit Door"
                            else:
                                prompt = "[E] Close Door" if d.is_open else f"[E] Open {d.name}"
                            break

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

        # ----------------- JUMPSCARE (Blackout Only) -----------------
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

        # ----------------- AMBIGUOUS ENDING (Blackout Death) -----------------
        elif self.state == STATE_AMBIGUOUS_ENDING:
            canvas.fill((4, 4, 6))

            t_end = self.font_msg.render("There was never anyone else in the room.", True, (220, 215, 210))
            canvas.blit(t_end, (SCREEN_WIDTH // 2 - t_end.get_width() // 2, SCREEN_HEIGHT // 2 - 30))

            if self.state_timer >= 2.5:
                t_sub = self.font_hud.render("Press [R] to Play Again   |   [ESC] to Quit", True, (160, 160, 160))
                canvas.blit(t_sub, (SCREEN_WIDTH // 2 - t_sub.get_width() // 2, SCREEN_HEIGHT // 2 + 35))

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
