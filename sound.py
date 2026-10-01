"""
================================================================================
sound.py  —  DON'T LOOK AWAY  |  Procedural Horror Audio Engine
================================================================================
ALL audio work lives in this file.
Teammates editing main.py will never conflict with changes made here.

External sound files (optional override):
    Place .wav / .ogg / .mp3 files inside   assets/sounds/<name>.<ext>
    Available names:
        click, footstep, pickup_battery, pickup_key, drawer_open,
        creature_move, door_open, heartbeat, jumpscare,
        whisper, ambient_hum, drone, tension, stinger

    If a file is missing, procedural synthesis is used automatically.
    The game NEVER crashes on missing audio.

IMPORTANT for main.py:
    Call  audio.update()  once per frame inside the game loop.
    (It is needed for the non-blocking jumpscare silence.)

Quick-tune constants (easy to adjust during GameJam):
    MASTER_VOL              — overall output gain  (0.0 – 1.0)
    FOOTSTEP_INTERVAL       — seconds between player step sounds
    HEARTBEAT_INTERVAL      — seconds between heartbeat pulses
    JUMPSCARE_DUCK_MS       — milliseconds of total silence before the jumpscare
    JUMPSCARE_HIT_DELAY_MS  — how far into the jumpscare sound the impact lands
                              (use it to sync the screen flash)
    TENSION_MAX_VOL         — maximum volume of the tension drone
================================================================================
"""

import io
import math
import os
import random
import sys
import wave
from array import array

import pygame

# ==============================================================================
# QUICK-TUNE CONSTANTS
# ==============================================================================
MASTER_VOL             = 1.0   # Global volume multiplier (0.0 – 1.0)
FOOTSTEP_INTERVAL      = 0.42  # Seconds between player step sounds
HEARTBEAT_INTERVAL     = 0.70  # Seconds between heartbeat pulses
AMBIENT_LOOP_DELAY     = 18.0  # Legacy constant, kept so old code doesn't break
JUMPSCARE_DUCK_MS      = 300   # Silence before the jumpscare starts
JUMPSCARE_HIT_DELAY_MS = 350   # Impact lands this long after the jumpscare sound starts
TENSION_MAX_VOL        = 0.45  # Volume cap for the tension drone

SAMPLE_RATE  = 22050           # Lower rate = much faster generation at startup
NUM_CHANNELS = 16              # Default is 8, too few for layered horror audio
JUMPSCARE_CHANNEL_ID = 0       # Reserved channel so the jumpscare is never dropped

SR     = SAMPLE_RATE
TWO_PI = 2.0 * math.pi

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
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=SR, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(NUM_CHANNELS)
        pygame.mixer.set_reserved(1)   # channel 0 is kept free for the jumpscare
        AUDIO_INITIALIZED = True
    except Exception:
        AUDIO_INITIALIZED = False


_init_mixer()


# ==============================================================================
# LOW-LEVEL HELPERS
# ==============================================================================
def _noise() -> float:
    """White noise sample between -1 and 1."""
    return random.random() * 2.0 - 1.0


def _soft_clip(sample: float, drive: float = 1.2) -> float:
    """Soft saturation (tanh). Makes things sound loud and aggressive without harsh clipping."""
    return math.tanh((sample / 22000.0) * drive) * 26000.0


def _lowpass(samples: list, alpha: float = 0.20) -> list:
    """1-pole low-pass filter. Smaller alpha = more muffled."""
    out = [0.0] * len(samples)
    val = 0.0
    for i, s in enumerate(samples):
        val += alpha * (s - val)
        out[i] = val
    return out


def _highpass(samples: list, alpha: float = 0.20) -> list:
    """Simple high-pass: the signal minus its low-passed version (hissy, airy)."""
    low = _lowpass(samples, alpha)
    return [s - l for s, l in zip(samples, low)]


def _loop_crossfade(samples: list, fade_seconds: float) -> list:
    """Blends the end of a sound into its start so it loops without a click."""
    fade = int(SR * fade_seconds)
    n = len(samples)
    for i in range(fade):
        a = i / fade
        samples[i] = samples[i] * a + samples[n - fade + i] * (1.0 - a)
    return samples[:n - fade]


def _build_sound(samples: list, sample_rate: int = SR) -> "pygame.mixer.Sound | None":
    """Converts float samples into a mono pygame.Sound using an in-memory WAV file."""
    if not AUDIO_INITIALIZED:
        return None
    try:
        pcm = array("h", (max(-32767, min(32767, int(s))) for s in samples))
        if sys.byteorder == "big":
            pcm.byteswap()   # WAV data must be little-endian
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm.tobytes())
        buf.seek(0)
        return pygame.mixer.Sound(buf)
    except Exception:
        return None


# ==============================================================================
# PROCEDURAL SOUNDS — SMALL UI / WORLD SOUNDS
# ==============================================================================
def _synth_click():
    """Tactile flashlight click."""
    dur = int(SR * 0.04)
    samples = [
        math.sin(TWO_PI * 2400 * i / SR) * math.exp(-i / (SR * 0.006)) * 24000
        + _noise() * math.exp(-i / (SR * 0.004)) * 9000
        for i in range(dur)
    ]
    return _build_sound(samples)


def _synth_footstep():
    """Muffled, quiet player footstep, so the creature sounds stand out."""
    dur = int(SR * 0.09)
    samples = []
    for i in range(dur):
        t = i / SR
        thump = math.sin(TWO_PI * 58.0 * t) * math.exp(-t / 0.025) * 9000
        creak = _noise() * math.exp(-t / 0.015) * 2200
        samples.append(thump + creak)
    return _build_sound(_lowpass(samples, alpha=0.18))


def _synth_pickup_battery():
    """Two-tone pickup chime."""
    half = int(SR * 0.11)
    s1 = [math.sin(TWO_PI * 587 * i / SR) * math.exp(-i / (SR * 0.07)) * 16000 for i in range(half)]
    s2 = [math.sin(TWO_PI * 880 * i / SR) * math.exp(-i / (SR * 0.09)) * 19000 for i in range(half)]
    return _build_sound(s1 + s2)


def _synth_pickup_key():
    """Key pickup: a metallic chime with a slightly detuned, uneasy shimmer."""
    dur = int(SR * 0.5)
    samples = []
    for i in range(dur):
        t = i / SR
        v = (math.sin(TWO_PI * 784 * t) * 0.5
             + math.sin(TWO_PI * 1174 * t) * 0.3
             + math.sin(TWO_PI * 1661 * t) * 0.22)   # slightly "wrong" top note
        samples.append(v * math.exp(-t / 0.16) * 22000)
    return _build_sound(samples)


def _synth_door_open():
    """Heavy door: a long, uneven creak followed by a dull settle thud."""
    dur = int(SR * 1.1)
    samples = [0.0] * dur
    phase = 0.0
    creak_len = int(SR * 0.85)
    for i in range(creak_len):
        t = i / SR
        # Stick-slip creak: the pitch jitters, like old hinges
        f = 150 + 60 * math.sin(TWO_PI * 1.3 * t) + 25 * _noise()
        phase += TWO_PI * f / SR
        stick = 0.6 + 0.4 * math.sin(TWO_PI * 31 * t + 2 * math.sin(TWO_PI * 4 * t))
        env = math.sin(math.pi * i / creak_len)
        samples[i] += (math.tanh(2.5 * math.sin(phase)) * 0.7 + _noise() * 0.3) * stick * env * 15000
    settle = int(SR * 0.85)
    for i in range(dur - settle):
        t = i / SR
        samples[settle + i] += math.sin(TWO_PI * 70 * t) * math.exp(-t / 0.06) * 14000
    return _build_sound([_soft_clip(s, 1.1) for s in samples])


def _synth_drawer_open():
    """Wooden drawer / crate: juddering friction slide, then a dull stop."""
    dur = int(SR * 0.45)
    slide = int(SR * 0.33)
    rough = _lowpass([_noise() for _ in range(dur)], 0.35)
    samples = [0.0] * dur
    for i in range(slide):
        t = i / SR
        judder = 0.55 + 0.45 * math.sin(TWO_PI * (38 + 14 * t) * t + 1.5 * math.sin(TWO_PI * 5 * t))
        env = math.sin(math.pi * i / slide) ** 0.6
        samples[i] += rough[i] * judder * env * 30000
    for i in range(dur - slide):
        t = i / SR
        samples[slide + i] += (math.sin(TWO_PI * 85 * t) + 0.3 * _noise()) * math.exp(-t / 0.03) * 15000
    return _build_sound([_soft_clip(s, 1.1) for s in samples])


# ==============================================================================
# PROCEDURAL SOUNDS — THE CREATURE
# ==============================================================================
def _creature_move_samples() -> list:
    """
    Organic, wrong-sounding movement. Every call is randomised, so each
    generated variant is different:
      - a wet, gurgling growl/breath underneath
      - irregular dragging scrapes (like something being pulled across wood)
      - clusters of bone cracks / joint pops
    """
    dur_s = random.uniform(0.65, 1.0)
    dur = int(SR * dur_s)
    s = [0.0] * dur

    # 1. Wet growl: a distorted low tone with a gurgling amplitude wobble
    base = random.uniform(48.0, 68.0)
    gurgle_rate = random.uniform(14.0, 26.0)
    phase = 0.0
    breath = _lowpass([_noise() for _ in range(dur)], 0.22)
    for i in range(dur):
        t = i / SR
        f = base * (1.0 - 0.25 * t / dur_s) * (1.0 + 0.05 * _noise())
        phase += TWO_PI * f / SR
        growl = math.tanh(3.0 * math.sin(phase))   # square-ish: audible on laptop speakers
        env = math.sin(math.pi * i / dur)
        gurgle = 0.5 + 0.5 * math.sin(TWO_PI * gurgle_rate * t + 3.0 * math.sin(TWO_PI * 2.3 * t))
        s[i] += growl * gurgle * env * 6500
        s[i] += breath[i] * (0.4 + 0.6 * gurgle) * env * 26000

    # 2. Dragging scrapes at random moments
    for _ in range(random.randint(2, 4)):
        start = int(SR * random.uniform(0.0, dur_s - 0.2))
        length = int(SR * random.uniform(0.08, 0.2))
        hiss = _highpass([_noise() for _ in range(length)], 0.35)
        squeak_f = random.uniform(380.0, 900.0)
        sq_phase = 0.0
        for j in range(length):
            if start + j >= dur:
                break
            t = j / SR
            env = math.sin(math.pi * j / length) ** 0.7
            sq_phase += TWO_PI * (squeak_f + 120.0 * math.sin(TWO_PI * 17.0 * t)) / SR
            s[start + j] += (hiss[j] * 0.75 + math.sin(sq_phase) * 0.25) * env * 13000

    # 3. Bone cracks: small clusters of sharp clicks
    for _ in range(random.randint(3, 6)):
        cluster_t = random.uniform(0.02, dur_s - 0.06)
        for k in range(random.randint(1, 3)):
            ci = int(SR * (cluster_t + k * random.uniform(0.004, 0.014)))
            clen = int(SR * 0.004)
            amp = random.uniform(14000.0, 24000.0)
            for j in range(clen):
                if ci + j < dur:
                    s[ci + j] += _noise() * (1.0 - j / clen) * amp

    return [_soft_clip(x, drive=1.4) for x in s]


def _synth_stinger():
    """
    OPTIONAL: a short violin-like shriek for the moment the flashlight
    first catches the creature. Call audio.play("stinger") from main.py.
    """
    dur = int(SR * 1.0)
    voices = [1318.5, 1396.9, 1975.5]          # E6, F6, B6: harsh cluster
    phases = [0.0] * len(voices)
    samples = []
    for i in range(dur):
        t = i / SR
        bend = 1.0 + 0.03 * math.sin(TWO_PI * 7.0 * t) - 0.06 * t
        v = 0.0
        for k, f in enumerate(voices):
            phases[k] += TWO_PI * f * bend / SR
            p = phases[k]
            # Sawtooth-like tone from a few harmonics = bowed string feel
            v += math.sin(p) + 0.5 * math.sin(2 * p) + 0.33 * math.sin(3 * p)
        bow = _noise() * 0.6
        env = (t / 0.01) if t < 0.01 else math.exp(-(t - 0.01) / 0.35)
        samples.append(_soft_clip((v * 0.33 + bow) * env * 16000, drive=1.8))
    return _build_sound(samples)


# ==============================================================================
# PROCEDURAL SOUNDS — JUMPSCARE
# ==============================================================================
def _synth_jumpscare():
    """
    The climax. Built as a sequence:
      0.00–0.35 s  suck-in: airy noise swell + rising tone (the "breath before")
      0.35 s       IMPACT: sub-bass drop + mid thud (audible on laptops) + noise burst
      0.35 s →     SCREAM: high, unstable, inhuman cluster with ring modulation,
                   rasp, and a stuttering "glitch" gate (fits the UNSTABLE theme)
      tail         tinnitus ring, like your ears are ringing from the shock
    """
    dur = int(SR * 2.6)
    out = [0.0] * dur

    # --- 1. Suck-in ----------------------------------------------------------
    suck = int(SR * JUMPSCARE_HIT_DELAY_MS / 1000.0)
    air = _highpass([_noise() for _ in range(suck)], 0.3)
    phase = 0.0
    for i in range(suck):
        x = i / suck
        f = 120.0 + 520.0 * x * x
        phase += TWO_PI * f / SR
        out[i] += _soft_clip(air[i] * (x ** 3) * 24000 + math.sin(phase) * (x ** 2.5) * 7000, drive=1.3)

    # --- 2. Impact + scream + tinnitus ---------------------------------------
    ratios = [1.0, 1.059, 1.414, 0.5, 2.03]    # unison, minor 2nd, tritone, growl octave, sour top
    amps   = [0.38, 0.30, 0.26, 0.32, 0.14]
    phases = [0.0] * len(ratios)
    ph_sub = ph_thud = ph_ring = 0.0
    wander = 0.0

    for i in range(dur - suck):
        t = i / SR

        # Sub-bass drop 60 → 28 Hz (felt on headphones)
        ph_sub += TWO_PI * (28.0 + 32.0 * math.exp(-t / 0.10)) / SR
        sub = math.sin(ph_sub) * math.exp(-t / 0.45) * 24000

        # Mid "thud" 140 → 60 Hz (heard on laptop speakers)
        ph_thud += TWO_PI * (60.0 + 80.0 * math.exp(-t / 0.05)) / SR
        thud = math.sin(ph_thud) * math.exp(-t / 0.12) * 22000

        # Noise burst
        burst = _noise() * math.exp(-t / 0.07) * 24000

        # Scream pitch: leaps up in 0.12 s, wanders erratically, sags at the end
        if i % 64 == 0:
            wander = (wander + random.uniform(-1.0, 1.0) * 0.07) * 0.9
        rise = min(1.0, t / 0.12)
        sag = 1.0 - 0.35 * max(0.0, min(1.0, (t - 0.9) / 1.3))
        f0 = (650.0 + 650.0 * rise) * (1.0 + wander + 0.05 * math.sin(TWO_PI * 13.0 * t)) * sag

        voice = 0.0
        for k in range(len(ratios)):
            phases[k] += TWO_PI * f0 * ratios[k] / SR
            voice += math.sin(phases[k]) * amps[k]
        ph_ring += TWO_PI * 137.0 / SR
        voice *= 0.55 + 0.45 * math.sin(ph_ring)    # ring mod = inhuman, metallic
        voice += _noise() * 0.35                    # throat rasp

        # Stutter gate in the first half-second: the sound "glitches"
        gate = 1.0 if (t > 0.55 or math.sin(TWO_PI * 22.0 * t) > -0.3) else 0.25
        scream_env = (t / 0.015) if t < 0.015 else math.exp(-(t - 0.015) / 1.0)
        scream = voice * gate * scream_env * 20000

        tinnitus = math.sin(TWO_PI * 6800.0 * t) * math.exp(-t / 0.9) * (1.0 - math.exp(-t / 0.08)) * 3500

        out[suck + i] += _soft_clip(sub + thud + burst + scream, drive=2.2) + tinnitus

    return _build_sound(out)


# ==============================================================================
# PROCEDURAL SOUNDS — BODY & MIND
# ==============================================================================
def _synth_heartbeat_speed(bpm: float):
    """One heartbeat cycle at the given BPM (loops seamlessly)."""
    cycle = 60.0 / max(40.0, min(180.0, bpm))
    dur = int(SR * cycle)
    samples = [0.0] * dur

    def thump(start_s, length_s, freq, amp):
        start = int(SR * start_s)
        for i in range(int(SR * length_s)):
            if start + i < dur:
                t = i / SR
                body = math.sin(TWO_PI * freq * t)
                knock = math.sin(TWO_PI * freq * 2.2 * t) * 0.35   # overtone: audible on laptops
                samples[start + i] += (body + knock) * math.exp(-t / 0.035) * amp

    thump(0.0, 0.14, 42.0, 27000)    # lub
    thump(0.18, 0.12, 50.0, 21000)   # dub
    muffled = _lowpass(samples, alpha=0.16)
    return _build_sound([_soft_clip(s, 1.2) for s in muffled])


def _synth_whisper():
    """
    Unintelligible whispered syllables. Timing, pitch and "s"/"sh" sounds are
    random every launch, so it almost sounds like words, but never quite.
    """
    dur_s = 1.9
    dur = int(SR * dur_s)
    samples = [0.0] * dur
    t_cursor = random.uniform(0.02, 0.12)

    while t_cursor < dur_s - 0.25:
        length = random.uniform(0.14, 0.34)
        start = int(SR * t_cursor)
        n = int(SR * length)
        f_start = random.uniform(350.0, 900.0)
        f_end = random.uniform(350.0, 1000.0)
        breath = _lowpass([_noise() for _ in range(n)], 0.35)
        fric = _highpass([_noise() for _ in range(n)], 0.5)
        has_s = random.random() < 0.5
        phase = 0.0
        for j in range(n):
            if start + j >= dur:
                break
            frac = j / n
            env = math.sin(math.pi * frac)
            phase += TWO_PI * (f_start + (f_end - f_start) * frac) / SR
            # Breath shaped by a moving "formant" = vowel-like
            voiced = breath[j] * (0.6 + 0.4 * math.sin(phase)) * 2.2
            # "s"/"sh" at the end of some syllables
            s_env = max(0.0, (frac - 0.7) / 0.3) if has_s else 0.0
            samples[start + j] += (voiced * env + fric[j] * s_env * 0.6) * 11000
        t_cursor += length + random.uniform(0.04, 0.2)

    return _build_sound([_soft_clip(s, 1.0) for s in samples])


# ==============================================================================
# PROCEDURAL SOUNDS — LOOPS
# ==============================================================================
def _synth_ambient_hum():
    """
    Evolving room tone (8 s loop):
      - low beating drone (felt) with harmonics (heard on laptops)
      - filtered air in an empty room
      - faint events at RANDOM times every launch: a double knock, a creak,
        a distant breath, a far-off scrape. Quiet enough that the player
        wonders whether they heard anything at all.
    """
    dur_s = 8.0
    dur = int(SR * dur_s)
    s = [0.0] * dur

    # 1. Drone
    p1 = p2 = p3 = p4 = 0.0
    for i in range(dur):
        t = i / SR
        p1 += TWO_PI * 41.0 / SR
        p2 += TWO_PI * 41.7 / SR
        p3 += TWO_PI * 82.3 / SR
        p4 += TWO_PI * 123.9 / SR
        swell = 0.8 + 0.2 * math.sin(TWO_PI * 0.125 * t)
        s[i] = (math.sin(p1) * 0.42 + math.sin(p2) * 0.34
                + math.sin(p3) * 0.16 + math.sin(p4) * 0.08) * swell * 11000

    # 2. Room air
    air = _lowpass([_noise() * 3000 for _ in range(dur)], 0.08)
    for i in range(dur):
        s[i] += air[i] * (0.75 + 0.25 * math.sin(TWO_PI * 0.25 * i / SR))

    def event_time(length_s):
        return int(SR * random.uniform(0.5, dur_s - 1.0 - length_s))

    # 3a. Double knock (like someone on the other side of a wall)
    k = event_time(0.4)
    for hit in (0.0, random.uniform(0.18, 0.3)):
        start = k + int(SR * hit)
        for i in range(int(SR * 0.09)):
            t = i / SR
            s[start + i] += (math.sin(TWO_PI * 95 * t) + 0.4 * _noise()) * math.exp(-t / 0.02) * 3800

    # 3b. Floor creak
    c = event_time(0.4)
    c_len = int(SR * 0.35)
    ph = 0.0
    for i in range(c_len):
        t = i / SR
        ph += TWO_PI * (170 - 50 * t + 15 * _noise()) / SR
        s[c + i] += math.tanh(2 * math.sin(ph)) * math.sin(math.pi * i / c_len) * 1800

    # 3c. Distant breath
    b = event_time(0.9)
    b_len = int(SR * 0.9)
    breath = _lowpass([_noise() for _ in range(b_len)], 0.3)
    for i in range(b_len):
        s[b + i] += breath[i] * math.sin(math.pi * i / b_len) * 4500

    # 3d. Far-off scrape
    d = event_time(0.6)
    d_len = int(SR * 0.6)
    scrape = _lowpass(_highpass([_noise() for _ in range(d_len)], 0.3), 0.4)
    for i in range(d_len):
        s[d + i] += scrape[i] * math.sin(math.pi * i / d_len) * 2600

    s = _loop_crossfade(s, 0.5)
    return _build_sound([_soft_clip(x, 1.0) for x in s])


def _synth_tension():
    """
    Dissonant string-like drone that slowly drifts out of tune, like reality
    slipping. Raise/lower it with audio.set_tension(0.0 – 1.0).
    """
    dur_s = 6.0
    dur = int(SR * dur_s)
    freqs = [440.0, 466.16, 622.25, 1318.5]
    amps  = [0.32, 0.30, 0.24, 0.12]
    phases = [0.0] * len(freqs)
    samples = []
    for i in range(dur):
        t = i / SR
        drift = 1.0 + 0.012 * math.sin(TWO_PI * t / dur_s)    # slow detune, one cycle per loop
        trem = 0.7 + 0.3 * math.sin(TWO_PI * 0.5 * t)
        v = 0.0
        for k in range(len(freqs)):
            vib = 1.0 + 0.006 * math.sin(TWO_PI * (4.5 + k * 0.7) * t)
            phases[k] += TWO_PI * freqs[k] * vib * (drift if k % 2 else 1.0) / SR
            p = phases[k]
            v += (math.sin(p) + 0.45 * math.sin(2 * p) + 0.25 * math.sin(3 * p)) * amps[k]
        v += _noise() * 0.08    # bow noise
        samples.append(v * trem * 11000)
    samples = _loop_crossfade(samples, 0.4)
    return _build_sound([_soft_clip(x, 1.2) for x in samples])


# ==============================================================================
# SYNTHESIS DISPATCH TABLE
# ==============================================================================
_SYNTH_REGISTRY = {
    "click":          _synth_click,
    "footstep":       _synth_footstep,
    "pickup_battery": _synth_pickup_battery,
    "pickup_key":     _synth_pickup_key,
    "door_open":      _synth_door_open,
    "drawer_open":    _synth_drawer_open,
    "jumpscare":      _synth_jumpscare,
    "stinger":        _synth_stinger,
    "whisper":        _synth_whisper,
    "ambient_hum":    _synth_ambient_hum,
    "tension":        _synth_tension,
    "heartbeat_slow": lambda: _synth_heartbeat_speed(60.0),
    "heartbeat_med":  lambda: _synth_heartbeat_speed(88.0),
    "heartbeat_fast": lambda: _synth_heartbeat_speed(130.0),
}


def _make_creature_pair():
    """One random creature variant plus a genuinely muffled (far away) copy."""
    samples = _creature_move_samples()
    return _build_sound(samples), _build_sound(_lowpass(samples, alpha=0.10))


# Names that just point to another sound (no extra generation time)
_ALIASES = {
    "heartbeat": "heartbeat_med",
    "drone":     "ambient_hum",
}

CREATURE_VARIANTS = 4
HEARTBEAT_LOOPS = ["heartbeat", "heartbeat_slow", "heartbeat_med", "heartbeat_fast"]


# ==============================================================================
# PUBLIC AUDIO MANAGER
# ==============================================================================
class AudioManager:
    """
    Loads sounds from assets/sounds/<name>.(wav|ogg|mp3) when available.
    Falls back to procedural synthesis when files are missing.
    Never crashes. Never blocks the game.

    Usage (from main.py):
        audio = AudioManager()
        audio.update()                         # every frame!
        audio.play("footstep", volume=0.5)
        audio.loop("ambient_hum", volume=0.6)
        audio.set_tension(0.0 – 1.0)
        audio.play_at_distance("creature_move", dist, max_dist)
        audio.duck_for_jumpscare()
    """

    def __init__(self):
        self._sounds: dict = {}       # name → pygame.Sound | None
        self._loops: dict = {}        # name → channel currently looping
        self._loop_vols: dict = {}    # name → volume requested (before MASTER_VOL)
        self._tension_level = 0.0
        self._heartbeat_bpm = 88.0
        self._jumpscare_at = None     # pygame tick when a pending jumpscare fires

        sound_dir = os.path.join("assets", "sounds")

        for name in _SYNTH_REGISTRY:
            self._sounds[name] = self._load_file(name, sound_dir) or self._synth(name)

        for alias, target in _ALIASES.items():
            self._sounds[alias] = self._load_file(alias, sound_dir) or self._sounds.get(target)

        # A real creature_move file overrides the procedural variants
        self._sounds["creature_move"] = self._load_file("creature_move", sound_dir)
        if AUDIO_INITIALIZED:
            for i in range(CREATURE_VARIANTS):
                try:
                    near, far = _make_creature_pair()
                except Exception:
                    near = far = None
                self._sounds[f"creature_move_{i}"] = near
                self._sounds[f"creature_move_muffled_{i}"] = far

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _load_file(name: str, sound_dir: str):
        if not AUDIO_INITIALIZED:
            return None
        for ext in (".wav", ".ogg", ".mp3"):
            path = os.path.join(sound_dir, f"{name}{ext}")
            if os.path.exists(path):
                try:
                    return pygame.mixer.Sound(path)
                except Exception:
                    pass   # corrupt file, fall back to synthesis
        return None

    @staticmethod
    def _synth(name: str):
        fn = _SYNTH_REGISTRY.get(name)
        if fn and AUDIO_INITIALIZED:
            try:
                return fn()
            except Exception:
                return None
        return None

    def _resolve_creature(self, muffled: bool = False) -> str:
        """Picks a random creature variant unless a creature_move file was provided."""
        if self._sounds.get("creature_move") is not None:
            return "creature_move"
        prefix = "creature_move_muffled_" if muffled else "creature_move_"
        return f"{prefix}{random.randint(0, CREATURE_VARIANTS - 1)}"

    @staticmethod
    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    # ------------------------------------------------------------------
    # Public API (backwards compatible)
    # ------------------------------------------------------------------
    def play(self, name: str, volume: float = 1.0) -> None:
        """Play a one-shot sound. volume is multiplied by MASTER_VOL."""
        if not AUDIO_INITIALIZED:
            return
        if name == "creature_move":
            name = self._resolve_creature()
        snd = self._sounds.get(name)
        if not snd:
            return
        try:
            if name == "jumpscare":
                channel = pygame.mixer.Channel(JUMPSCARE_CHANNEL_ID)
                channel.play(snd)
            else:
                channel = snd.play()
            # Volume goes on the CHANNEL, so overlapping copies don't affect each other
            if channel:
                channel.set_volume(self._clamp(volume * MASTER_VOL))
        except Exception:
            pass

    def loop(self, name: str, volume: float = 1.0) -> None:
        """Play a sound on repeat until stop_loop(). Will not stack duplicates."""
        if not AUDIO_INITIALIZED or name in self._loops:
            return
        snd = self._sounds.get(name)
        if not snd:
            return
        try:
            channel = snd.play(loops=-1)
            if channel:
                channel.set_volume(self._clamp(volume * MASTER_VOL))
                self._loops[name] = channel
                self._loop_vols[name] = volume
        except Exception:
            pass

    def stop_loop(self, name: str) -> None:
        """Stop a previously started loop."""
        channel = self._loops.pop(name, None)
        self._loop_vols.pop(name, None)
        if channel:
            try:
                channel.stop()
            except Exception:
                pass

    def stop_all(self) -> None:
        """Stop every sound, and cancel a pending jumpscare."""
        self._jumpscare_at = None
        self._loops.clear()
        self._loop_vols.clear()
        if not AUDIO_INITIALIZED:
            return
        try:
            pygame.mixer.stop()
        except Exception:
            pass

    def set_master_volume(self, vol: float) -> None:
        """Change MASTER_VOL at runtime. Running loops update immediately."""
        global MASTER_VOL
        MASTER_VOL = self._clamp(vol)
        for name, channel in self._loops.items():
            try:
                channel.set_volume(self._clamp(self._loop_vols.get(name, 1.0) * MASTER_VOL))
            except Exception:
                pass

    def is_playing(self, name: str) -> bool:
        """True if a named loop is currently active."""
        return name in self._loops

    # ------------------------------------------------------------------
    # Horror helpers
    # ------------------------------------------------------------------
    def update(self) -> None:
        """Call once per frame. Fires the jumpscare after the silence."""
        if self._jumpscare_at is not None and pygame.time.get_ticks() >= self._jumpscare_at:
            self._jumpscare_at = None
            self.play("jumpscare", volume=1.0)

    def duck_for_jumpscare(self) -> None:
        """
        Cuts ALL sound, waits JUMPSCARE_DUCK_MS in silence (without freezing
        the game), then plays the jumpscare. The impact lands
        JUMPSCARE_DUCK_MS + JUMPSCARE_HIT_DELAY_MS after this call:
        trigger the screen flash at that moment.
        """
        self.stop_all()
        self._jumpscare_at = pygame.time.get_ticks() + JUMPSCARE_DUCK_MS

    def jumpscare_pending(self) -> bool:
        """True while waiting in the silence before the jumpscare."""
        return self._jumpscare_at is not None

    def set_tension(self, level: float) -> None:
        """0.0 = calm, 1.0 = maximum dread. Safe to call every frame."""
        self._tension_level = self._clamp(level)
        if self._tension_level <= 0.02:
            self.stop_loop("tension")
            return
        vol = self._tension_level * TENSION_MAX_VOL
        if not self.is_playing("tension"):
            self.loop("tension", volume=vol)
        else:
            self._loop_vols["tension"] = vol
            try:
                self._loops["tension"].set_volume(self._clamp(vol * MASTER_VOL))
            except Exception:
                pass

    def play_at_distance(self, name: str, distance: float, max_distance: float, volume: float = 1.0) -> None:
        """Quieter AND more muffled the further away the sound is."""
        if max_distance <= 0 or distance >= max_distance:
            return
        factor = max(0.0, 1.0 - (distance / max_distance) ** 1.2)
        eff = volume * factor
        if eff <= 0.01:
            return
        far = distance > max_distance * 0.45
        if name == "creature_move":
            target = self._resolve_creature(muffled=far)
        elif far and f"{name}_muffled" in self._sounds:
            target = f"{name}_muffled"
        else:
            target = name
        self.play(target, volume=eff)

    def set_heartbeat_rate(self, bpm: float) -> None:
        """
        Switches the active heartbeat loop to slow / medium / fast.
        Only has an effect while a heartbeat loop is playing.
        """
        self._heartbeat_bpm = max(40.0, min(180.0, bpm))
        if self._heartbeat_bpm < 75.0:
            target = "heartbeat_slow"
        elif self._heartbeat_bpm <= 105.0:
            target = "heartbeat_med"
        else:
            target = "heartbeat_fast"

        if not any(self.is_playing(k) for k in HEARTBEAT_LOOPS) or self.is_playing(target):
            return
        for k in HEARTBEAT_LOOPS:
            self.stop_loop(k)
        self.loop(target, volume=0.7)

    # ------------------------------------------------------------------
    # Compatibility with the drone methods main.py already uses
    # ------------------------------------------------------------------
    def start_drone(self, volume: float = 0.25) -> None:
        """Starts the background ambience loop."""
        self.loop("ambient_hum", volume=volume)

    def set_drone_volume(self, vol: float) -> None:
        """Changes the ambience volume (safe to call every frame)."""
        channel = self._loops.get("ambient_hum")
        if channel:
            self._loop_vols["ambient_hum"] = vol
            try:
                channel.set_volume(self._clamp(vol * MASTER_VOL))
            except Exception:
                pass

    def stop_drone(self) -> None:
        """Stops the background ambience loop."""
        self.stop_loop("ambient_hum")