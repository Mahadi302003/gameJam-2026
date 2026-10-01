"""
================================================================================
sound.py  —  DON'T LOOK AWAY  |  Audio Engine
================================================================================
ALL audio work lives in this file.
Teammates editing main.py will never conflict with changes made here.

External sound files (optional override):
    Place .wav / .ogg / .mp3 files inside   assets/sounds/<name>.<ext>
    Available names:
        click, footstep, pickup_battery, pickup_key,
        creature_move, door_open, heartbeat, jumpscare,
        whisper, ambient_hum

    If a file is missing, the procedural fallback is used automatically.
    The game NEVER crashes on missing audio.

Quick-tune constants (easy to adjust during GameJam):
    MASTER_VOL          — overall output gain  (0.0 – 1.0)
    FOOTSTEP_INTERVAL   — seconds between step sounds
    HEARTBEAT_INTERVAL  — seconds between heartbeat pulses
    AMBIENT_LOOP_DELAY  — seconds between ambient hum loops
================================================================================
"""

import io
import math
import os
import random
import struct
import wave

import pygame

# ==============================================================================
# QUICK-TUNE CONSTANTS
# ==============================================================================
MASTER_VOL        = 1.0   # Global volume multiplier (0.0 – 1.0)
FOOTSTEP_INTERVAL = 0.38  # Seconds between footstep sounds while moving
HEARTBEAT_INTERVAL = 0.70 # Seconds between heartbeat pulses in darkness
AMBIENT_LOOP_DELAY = 18.0 # Seconds between ambient hum loops while playing

# ==============================================================================
# MIXER BOOTSTRAP
# ==============================================================================
AUDIO_INITIALIZED = False

def _init_mixer():
    """Tries to initialise pygame.mixer. Safe to call multiple times."""
    global AUDIO_INITIALIZED
    if AUDIO_INITIALIZED:
        return
    try:
        # stereo (channels=2) gives us panning room for future expansion
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        AUDIO_INITIALIZED = True
    except Exception:
        AUDIO_INITIALIZED = False

_init_mixer()


# ==============================================================================
# LOW-LEVEL WAV BUILDER  (BytesIO → pygame.Sound, no temp files)
# ==============================================================================
def _build_sound(samples: list, sample_rate: int = 44100) -> "pygame.mixer.Sound | None":
    """
    Convert a list of float samples (–32767 … 32767 range expected) into a
    mono pygame.Sound via an in-memory WAV buffer.
    Returns None if audio is not initialised or on any error.
    """
    if not AUDIO_INITIALIZED:
        return None
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            clamped = (max(-32767, min(32767, int(s))) for s in samples)
            w.writeframes(b"".join(struct.pack("<h", v) for v in clamped))
        buf.seek(0)
        return pygame.mixer.Sound(buf)
    except Exception:
        return None


# ==============================================================================
# PROCEDURAL SOUND SYNTHESIS
# Each function returns a pygame.Sound (or None) without any external files.
# ==============================================================================

def _synth_click() -> "pygame.mixer.Sound | None":
    """Sharp, tactile flashlight toggle click."""
    rate = 44100
    dur  = int(rate * 0.045)
    samples = [
        math.sin(2 * math.pi * 2600 * i / rate) * math.exp(-i / (rate * 0.006)) * 28000
        + (random.random() * 2 - 1) * math.exp(-i / (rate * 0.004)) * 10000
        for i in range(dur)
    ]
    return _build_sound(samples, rate)


def _synth_footstep() -> "pygame.mixer.Sound | None":
    """Muffled wooden floorboard creak on each step."""
    rate = 44100
    dur  = int(rate * 0.08)
    # Low thump layer
    thump  = [math.sin(2 * math.pi * 72 * i / rate) * math.exp(-i / (rate * 0.022)) for i in range(dur)]
    # Creak noise layer
    creak  = [(random.random() * 2 - 1) * math.exp(-i / (rate * 0.018)) for i in range(dur)]
    samples = [(thump[i] * 16000 + creak[i] * 5000) for i in range(dur)]
    return _build_sound(samples, rate)


def _synth_pickup_battery() -> "pygame.mixer.Sound | None":
    """Rising two-tone tech pickup chime."""
    rate = 44100
    half = int(rate * 0.12)
    s1 = [math.sin(2 * math.pi * 587 * i / rate) * math.exp(-i / (rate * 0.08)) * 20000 for i in range(half)]
    s2 = [math.sin(2 * math.pi * 880 * i / rate) * math.exp(-i / (rate * 0.10)) * 24000 for i in range(half)]
    return _build_sound(s1 + s2, rate)


def _synth_pickup_key() -> "pygame.mixer.Sound | None":
    """Bright mystical three-harmonic chime."""
    rate = 44100
    dur  = int(rate * 0.40)
    samples = [
        (
            math.sin(2 * math.pi * 784  * i / rate) * 0.50
            + math.sin(2 * math.pi * 1174 * i / rate) * 0.35
            + math.sin(2 * math.pi * 1568 * i / rate) * 0.25
        ) * math.exp(-i / (rate * 0.14)) * 28000
        for i in range(dur)
    ]
    return _build_sound(samples, rate)


def _synth_creature_move() -> "pygame.mixer.Sound | None":
    """Low eerie wood-scratch — signals the creature repositioning."""
    rate = 44100
    dur  = int(rate * 0.35)
    samples = [
        (
            math.sin(2 * math.pi * (108 + 44 * math.sin(2 * math.pi * 9 * i / rate)) * i / rate) * 0.55
            + (random.random() * 2 - 1) * 0.45
        ) * math.exp(-i / (rate * 0.16)) * 16000
        for i in range(dur)
    ]
    return _build_sound(samples, rate)


def _synth_door_open() -> "pygame.mixer.Sound | None":
    """Heavy wooden door creaking open."""
    rate = 44100
    dur  = int(rate * 0.60)
    samples = [
        (
            math.sin(2 * math.pi * (145 + 80 * math.sin(2 * math.pi * 13 * i / rate)) * i / rate) * 0.65
            + (random.random() * 2 - 1) * 0.35
        ) * math.sin(math.pi * i / dur) * 20000
        for i in range(dur)
    ]
    return _build_sound(samples, rate)


def _synth_heartbeat() -> "pygame.mixer.Sound | None":
    """Deep bass double-thump (lub-dub) — plays during battery blackout."""
    rate   = 44100
    dur    = int(rate * 0.55)
    samples = [0.0] * dur
    # First thump  (lub)
    for i in range(int(rate * 0.18)):
        samples[i] += math.sin(2 * math.pi * 52 * i / rate) * math.exp(-i / (rate * 0.045)) * 28000
    # Second thump (dub) — slightly softer
    offset = int(rate * 0.22)
    for i in range(int(rate * 0.18)):
        if offset + i < dur:
            samples[offset + i] += math.sin(2 * math.pi * 62 * i / rate) * math.exp(-i / (rate * 0.045)) * 24000
    return _build_sound(samples, rate)


def _synth_jumpscare() -> "pygame.mixer.Sound | None":
    """
    Terrifying dissonant screech + bass impact + harsh noise.
    This is the climax — make it memorable.
    """
    rate = 44100
    dur  = int(rate * 2.0)
    samples = []
    for i in range(dur):
        t     = i / rate
        freq  = max(175, 1700 - t * 750)           # descending screech
        screech = (
            math.sin(2 * math.pi * freq * t)
            + 0.65 * math.sin(2 * math.pi * (freq * 1.414) * t)   # √2 dissonance
            + 0.50 * math.sin(2 * math.pi * (freq * 0.71 ) * t)   # sub-harmonic
        )
        bass  = math.sin(2 * math.pi * 42 * t) * math.exp(-t / 0.45) * 2.2
        noise = (random.random() * 2 - 1) * (0.9 if t < 0.65 else 0.28)
        env   = (t / 0.08) if t < 0.08 else math.exp(-(t - 0.08) / 1.2)
        val   = (screech * 0.50 + bass * 0.32 + noise * 0.38) * env * 30000
        samples.append(val)
    return _build_sound(samples, rate)


def _synth_whisper() -> "pygame.mixer.Sound | None":
    """
    Unsettling breathed whisper texture — optional atmospheric layer.
    A band of shaped noise that rises and falls like exhaled breath.
    """
    rate = 44100
    dur  = int(rate * 1.4)
    samples = []
    for i in range(dur):
        t      = i / rate
        # Slow breath envelope (two breaths)
        env    = abs(math.sin(math.pi * t / 0.70))
        noise  = (random.random() * 2 - 1)
        # Very soft band-pass approximation: multiply noise by a modulated sine
        band   = math.sin(2 * math.pi * 800 * t) * 0.15 + noise * 0.85
        val    = band * env * 6000
        samples.append(val)
    return _build_sound(samples, rate)


def _synth_ambient_hum() -> "pygame.mixer.Sound | None":
    """
    Low, barely-audible drone — room ambience during gameplay.
    Layered overtones that create unease without being noticeable consciously.
    """
    rate = 44100
    dur  = int(rate * 4.0)
    samples = []
    for i in range(dur):
        t   = i / rate
        # Three detuned sine layers
        s   = (
            math.sin(2 * math.pi * 55.0 * t) * 0.50
            + math.sin(2 * math.pi * 56.3 * t) * 0.30   # slight beating
            + math.sin(2 * math.pi * 110.8 * t) * 0.20  # first harmonic
        )
        # Slow tremolo
        tremolo = 0.85 + 0.15 * math.sin(2 * math.pi * 0.25 * t)
        val = s * tremolo * 5500
        samples.append(val)
    # Fade in / out to avoid clicks on loop
    fade = int(rate * 0.25)
    for i in range(fade):
        factor = i / fade
        samples[i]        *= factor
        samples[-(i + 1)] *= factor
    return _build_sound(samples, rate)


# ==============================================================================
# SYNTHESIS DISPATCH TABLE
# Add new sounds here without touching main.py
# ==============================================================================
_SYNTH_REGISTRY = {
    "click":           _synth_click,
    "footstep":        _synth_footstep,
    "pickup_battery":  _synth_pickup_battery,
    "pickup_key":      _synth_pickup_key,
    "creature_move":   _synth_creature_move,
    "door_open":       _synth_door_open,
    "heartbeat":       _synth_heartbeat,
    "jumpscare":       _synth_jumpscare,
    "whisper":         _synth_whisper,
    "ambient_hum":     _synth_ambient_hum,
}


# ==============================================================================
# PUBLIC AUDIO MANAGER
# ==============================================================================
class AudioManager:
    """
    Loads sounds from   assets/sounds/<name>.(wav|ogg|mp3)   when available.
    Falls back silently to procedural synthesis when files are missing.
    Never crashes. Never blocks the game.

    Usage (from main.py):
        from sound import AudioManager
        audio = AudioManager()
        audio.play("footstep", volume=0.5)
        audio.loop("ambient_hum", volume=0.15)
        audio.stop_loop("ambient_hum")
    """

    def __init__(self):
        self._sounds: dict = {}         # name → pygame.Sound | None
        self._loops:  dict = {}         # name → channel currently looping

        # Attempt to preload / synthesise every registered sound
        _sound_dir = os.path.join("assets", "sounds")
        for name in _SYNTH_REGISTRY:
            self._sounds[name] = self._load_or_synth(name, _sound_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_or_synth(self, name: str, sound_dir: str):
        """Try external file first; fall back to procedural synthesis."""
        if AUDIO_INITIALIZED:
            for ext in (".wav", ".ogg", ".mp3"):
                path = os.path.join(sound_dir, f"{name}{ext}")
                if os.path.exists(path):
                    try:
                        return pygame.mixer.Sound(path)
                    except Exception:
                        pass  # corrupt file — fall through to synthesis

        # Procedural fallback
        synth_fn = _SYNTH_REGISTRY.get(name)
        if synth_fn and AUDIO_INITIALIZED:
            try:
                return synth_fn()
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def play(self, name: str, volume: float = 1.0) -> None:
        """
        Play a one-shot sound at the given volume.
        volume is multiplied by MASTER_VOL.
        """
        if not AUDIO_INITIALIZED:
            return
        snd = self._sounds.get(name)
        if snd:
            try:
                snd.set_volume(max(0.0, min(1.0, volume * MASTER_VOL)))
                snd.play()
            except Exception:
                pass

    def loop(self, name: str, volume: float = 1.0) -> None:
        """
        Play a sound on repeat until stop_loop() is called.
        Safe to call multiple times — will not stack duplicate loops.
        """
        if not AUDIO_INITIALIZED:
            return
        if name in self._loops:
            return                          # already looping
        snd = self._sounds.get(name)
        if snd:
            try:
                snd.set_volume(max(0.0, min(1.0, volume * MASTER_VOL)))
                channel = snd.play(loops=-1) # -1 = loop forever
                if channel:
                    self._loops[name] = channel
            except Exception:
                pass

    def stop_loop(self, name: str) -> None:
        """Stop a previously started loop."""
        channel = self._loops.pop(name, None)
        if channel:
            try:
                channel.stop()
            except Exception:
                pass

    def stop_all(self) -> None:
        """Stop every active sound (loops and one-shots)."""
        if not AUDIO_INITIALIZED:
            return
        try:
            pygame.mixer.stop()
        except Exception:
            pass
        self._loops.clear()

    def set_master_volume(self, vol: float) -> None:
        """Change MASTER_VOL at runtime (e.g. from a settings menu)."""
        global MASTER_VOL
        MASTER_VOL = max(0.0, min(1.0, vol))

    def is_playing(self, name: str) -> bool:
        """Returns True if a named loop is currently active."""
        return name in self._loops
