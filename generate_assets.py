"""
================================================================================
generate_assets.py  —  DON'T LOOK AWAY  |  Audio Asset Generator
================================================================================
INSPIRATION: Silent Hill + Amnesia: The Dark Descent
- Silent Hill: industrial drones, distant scraping metal, radio static,
               Akira Yamaoka's signature "silence before the hit" tension
- Amnesia:     cave-depth reverb, organic breathing, slow-building unease,
               sounds that feel PHYSICAL and wrong

Design philosophy for every sound:
  1. Silence is a weapon — short sounds hit harder with silence after
  2. Sub-bass you feel, not just hear (40-60 Hz)
  3. Nothing is clean or digital — everything is slightly detuned or noisy
  4. Reverb creates the "old building" space

Run once before playing the game:
    python3 generate_assets.py

Writes .wav files to assets/sounds/ — main.py auto-loads them.
No changes to main.py needed.
================================================================================
"""

import math
import os
import random
import struct
import wave

OUT_DIR = os.path.join("assets", "sounds")
RATE    = 44100

os.makedirs(OUT_DIR, exist_ok=True)

# ==============================================================================
# CORE UTILITY LIBRARY
# ==============================================================================

def clamp(v):
    return max(-32767, min(32767, int(v)))

def write_wav(filename, samples):
    path = os.path.join(OUT_DIR, filename)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", clamp(s)) for s in samples))
    print(f"  ✓  {filename:<28}  ({len(samples)/RATE:.2f}s)")

def n(length):
    """White noise."""
    return [random.random() * 2 - 1 for _ in range(length)]

def sine(freq, dur_s, amp=1.0):
    length = int(RATE * dur_s)
    return [amp * math.sin(2 * math.pi * freq * i / RATE) for i in range(length)]

def fade(samples, fi=0.01, fo=0.05):
    """Fade in/out to prevent clicks."""
    s = list(samples)
    fis = int(RATE * fi)
    fos = int(RATE * fo)
    for i in range(min(fis, len(s))):
        s[i] *= i / fis
    for i in range(min(fos, len(s))):
        s[-(i+1)] *= i / fos
    return s

def exp_env(samples, decay_s):
    """Exponential decay envelope."""
    return [s * math.exp(-i / (RATE * decay_s)) for i, s in enumerate(samples)]

def bell_env(samples):
    """Rise and fall (bell shape)."""
    N = len(samples)
    return [s * math.sin(math.pi * i / N) for i, s in enumerate(samples)]

def reverb(samples, room_size=0.08, decay=0.40, taps=5):
    """
    Multi-tap comb-filter reverb — simulates a cold stone room (Amnesia-style).
    room_size: delay in seconds per tap
    decay: how much each echo fades
    """
    delay = int(RATE * room_size)
    out = list(samples) + [0.0] * (delay * taps)
    for tap in range(1, taps + 1):
        g = decay ** tap
        start = delay * tap
        for i, s in enumerate(samples):
            out[start + i] += s * g
    return out

def mix(a, b, gain_a=1.0, gain_b=1.0):
    """Mix two lists of samples together (different lengths OK)."""
    length = max(len(a), len(b))
    out = [0.0] * length
    for i, s in enumerate(a):
        out[i] += s * gain_a
    for i, s in enumerate(b):
        out[i] += s * gain_b
    return out

def fm_sine(carrier, mod_freq, mod_depth, dur_s):
    """
    FM synthesis — the backbone of Silent Hill's industrial textures.
    Produces complex, inharmonic tones that feel 'wrong'.
    carrier: base frequency (Hz)
    mod_freq: modulator frequency (Hz)
    mod_depth: how much the modulator shifts the carrier (in Hz)
    """
    length = int(RATE * dur_s)
    return [
        math.sin(
            2 * math.pi * (carrier + mod_depth * math.sin(2 * math.pi * mod_freq * i / RATE)) * i / RATE
        )
        for i in range(length)
    ]

def bandpass_noise(length, center_hz, bandwidth_hz):
    """
    Approximate band-limited noise by multiplying white noise with a sine.
    Used for breath textures and radio static (Amnesia style).
    """
    raw = n(length)
    return [
        raw[i] * math.sin(2 * math.pi * center_hz * i / RATE)
        * (0.85 + 0.15 * math.sin(2 * math.pi * (bandwidth_hz * 0.1) * i / RATE))
        for i in range(length)
    ]


# ==============================================================================
# 1. FOOTSTEP  (Priority 1)
# ─ Inspiration: Amnesia's heavy stone corridor footsteps
# ─ Three variations: each has a different low-frequency thud and floor character
# ─ Key: you FEEL the weight of each step (50-80 Hz bass)
# ==============================================================================
def gen_footstep():
    configs = [
        # (bass_hz, creak_hz, dur_s, creak_mod, room_size)
        (62,  290, 0.14, 18, 0.06),   # wooden plank — deep hollow thud
        (70,  340, 0.11, 22, 0.05),   # slightly lighter, faster
        (55,  260, 0.16, 14, 0.07),   # slowest, heaviest — like approaching dread
    ]
    for idx, (bass_hz, creak_hz, dur_s, creak_mod, room) in enumerate(configs):
        dur = int(RATE * dur_s)

        # Heavy bass impact — the "weight" of the protagonist
        bass = exp_env(sine(bass_hz, dur_s), 0.030)

        # Floor creak — FM modulated so it sounds organic, not synthetic
        creak = [
            fm_sine(creak_hz, 7, creak_mod, dur_s)[i]
            * math.exp(-i / (RATE * 0.022))
            for i in range(dur)
        ]

        # Floor texture — shaped noise burst at impact moment
        noise_burst = n(dur)
        texture = [noise_burst[i] * math.exp(-i / (RATE * 0.010)) for i in range(dur)]

        # Distant room reflection (very short reverb)
        layer = [
            bass[i]    * 22000
            + creak[i] * 8500
            + texture[i] * 4500
            for i in range(dur)
        ]
        name = f"footstep{'_' + str(idx) if idx > 0 else ''}.wav"
        write_wav(name, fade(reverb(layer, room, 0.22, 3), 0.001, 0.018))


# ==============================================================================
# 2. AMBIENT_HUM  (Priority 2)
# ─ Inspiration: Silent Hill's "hotel room" ambience — Akira Yamaoka
# ─ Four detuned oscillators beating against each other create natural wobble
# ─ Barely audible industrial hiss sits underneath (radio static texture)
# ─ A very faint distant "metal pipe" harmonic floats in and out
# ==============================================================================
def gen_ambient_hum():
    dur_s = 10.0    # 10 seconds — seamless background loop
    dur   = int(RATE * dur_s)

    # Low cinematic horror drone oscillators (38Hz sub-bass, 55Hz base, detuned 56.2Hz wobble)
    drone_freqs = [38.0, 55.0, 56.2, 88.0, 110.5]
    drone_amps  = [0.45, 0.40, 0.30, 0.20, 0.12]

    body = [0.0] * dur
    for freq, amp in zip(drone_freqs, drone_amps):
        for i in range(dur):
            body[i] += math.sin(2 * math.pi * freq * i / RATE) * amp

    # Slow ominous tremolo swell (movie score tension feel)
    for i in range(dur):
        t       = i / RATE
        tremolo = 0.70 + 0.30 * math.sin(2 * math.pi * 0.15 * t)
        body[i] *= tremolo * 5200

    # Distant industrial hiss layer
    hiss = n(dur)
    for i in range(dur):
        body[i] += hiss[i] * 380

    # Faint metallic resonant harmonic (Sinister / Silent Hill movie tension)
    for i in range(dur):
        t = i / RATE
        pipe_amp = 0.035 * abs(math.sin(math.pi * t / 4.0))  # 4s swell
        body[i] += math.sin(2 * math.pi * 174.61 * t) * pipe_amp * 5000

    # Seamless loop fade
    out_audio = fade(body, fi=0.40, fo=0.40)
    write_wav("ambient_hum.wav", out_audio)
    write_wav("drone.wav", out_audio)


# ==============================================================================
# 3. CREATURE_MOVE  (Priority 3)
# ─ Inspiration: Amnesia's "grunt" movement + Silent Hill's "pyramid head drag"
# ─ Three-part sound: distant thud → wet organic scrape → sub-bass displacement
# ─ Should make the player's stomach drop when they hear it off-screen
# ==============================================================================
def gen_creature_move():
    dur_s = 0.80
    dur   = int(RATE * dur_s)

    # --- Part 1: Heavy displacement thud (0.0 – 0.10s) ---
    # The creature's mass hitting the floor. Very low, very short.
    thud_s  = 0.10
    thud_n  = int(RATE * thud_s)
    thud    = [
        (
            math.sin(2 * math.pi * 38 * i / RATE) * 0.7   # sub-bass body
            + math.sin(2 * math.pi * 78 * i / RATE) * 0.3  # mid presence
        )
        * math.exp(-i / (RATE * 0.035))
        * 28000
        for i in range(thud_n)
    ]

    # --- Part 2: Wet organic scrape (0.08 – 0.55s) ---
    # FM modulated noise — like something dragging across a wet stone floor
    scrape_s = 0.50
    scrape_n = int(RATE * scrape_s)
    scrape   = [
        fm_sine(95, 13, 60, scrape_s)[i]
        * (random.random() * 0.6 + 0.4)                    # irregular texture
        * math.exp(-i / (RATE * 0.28))
        * 14000
        for i in range(scrape_n)
    ]

    # --- Part 3: A single distant creak at the end ---
    # Makes the player think: "is it BEHIND the wall?"
    creak_s  = 0.20
    creak_n  = int(RATE * creak_s)
    creak    = [
        math.sin(2 * math.pi * (130 + 40 * math.sin(2 * math.pi * 5 * i / RATE)) * i / RATE)
        * math.exp(-i / (RATE * 0.12))
        * 9000
        for i in range(creak_n)
    ]

    # Assemble
    out = [0.0] * dur
    for i, s in enumerate(thud):
        if i < dur:
            out[i] += s
    for i, s in enumerate(scrape):
        idx = int(RATE * 0.06) + i
        if idx < dur:
            out[idx] += s
    for i, s in enumerate(creak):
        idx = int(RATE * 0.55) + i
        if idx < dur:
            out[idx] += s

    # Heavy stone-room reverb — makes it sound like it's in the next room
    write_wav("creature_move.wav", fade(reverb(out, 0.09, 0.45, 5), 0.002, 0.12))


# ==============================================================================
# 4. HEARTBEAT  (Priority 4)
# ─ Inspiration: Silent Hill 2 — the sound that plays in James's room
# ─ Panic heartbeat: irregular rhythm, each beat slightly different
# ─ A barely-audible breath sits between beats (the protagonist's terror)
# ─ Low room resonance — like hearing your own pulse in a silent building
# ==============================================================================
def gen_heartbeat():
    # One complete lub-dub cycle = 0.8 seconds (75 BPM — slightly fast/scared)
    dur_s = 0.80
    dur   = int(RATE * dur_s)
    out   = [0.0] * dur

    def thump(offset_s, freq, amp, decay_s, harmonic=1.5):
        """Single heartbeat impact."""
        start = int(RATE * offset_s)
        length = int(RATE * 0.24)
        for i in range(length):
            idx = start + i
            if idx < dur:
                # Primary beat
                primary   = math.sin(2 * math.pi * freq * i / RATE)
                # Fleshy harmonic overtone (makes it sound biological)
                over      = math.sin(2 * math.pi * freq * harmonic * i / RATE) * 0.28
                env       = math.exp(-i / (RATE * decay_s))
                out[idx] += (primary + over) * env * amp

    # Lub — deeper, stronger (48 Hz)
    thump(0.00,  48, 30000, 0.048, 1.4)
    # Dub — slightly higher, softer (60 Hz), comes a beat later
    thump(0.28,  60, 22000, 0.042, 1.6)

    # Breath between beats — shaped noise, barely there
    raw = n(dur)
    for i in range(dur):
        t = i / RATE
        # Breath rises after dub, falls before lub
        breath_env = abs(math.sin(math.pi * ((t - 0.35) / 0.40))) if 0.35 < t < 0.75 else 0.0
        out[i] += raw[i] * breath_env * 1200

    write_wav("heartbeat.wav", fade(reverb(out, 0.11, 0.20, 3), 0.002, 0.05))


# ==============================================================================
# 5. JUMPSCARE  (Priority 5)
# ─ Inspiration: Akira Yamaoka "You're Not Here" → abrupt reverse
#               + Amnesia's monster scream
# ─ Structure: 0.00s — total silence (3-frame black)
#              0.00s — INSTANT full-volume bass slam (no attack)
#              0.03s — tritone screech begins and ascends (opposite of SH norm)
#              0.60s — noise wall peaks
#              0.80s — screech breaks into dissonant noise
#              2.50s — slow fade
# ─ Key: the silence BEFORE makes the hit feel violent
# ==============================================================================
def gen_jumpscare():
    dur_s   = 2.5
    dur     = int(RATE * dur_s)
    noise_s = n(dur)
    out     = [0.0] * dur

    for i in range(dur):
        t = i / RATE

        # === BASS SLAM — instant, no attack, pure physical impact ===
        # Inspired by SH2's "save room ambush" sub hit
        bass = (
            math.sin(2 * math.pi * 38 * t) * 0.60
            + math.sin(2 * math.pi * 55 * t) * 0.30
            + math.sin(2 * math.pi * 28 * t) * 0.20
        ) * math.exp(-t / 0.30) * 2.5

        # === ASCENDING SCREECH — tritone + minor 7th (most dissonant intervals) ===
        # Yamaoka uses ascending rather than descending for visceral shock
        base = min(2400, 180 + t * 880)                 # sweeps UP fast
        screech = (
            math.sin(2 * math.pi * base * t)
            + 0.75 * math.sin(2 * math.pi * base * 1.4142 * t)   # tritone
            + 0.55 * math.sin(2 * math.pi * base * 1.6818 * t)   # minor 7th
            + 0.35 * math.sin(2 * math.pi * base * 0.5    * t)   # sub-octave
        ) * (min(1.0, t / 0.015))                        # instant attack
        screech_env = math.exp(-max(0, t - 0.02) / 1.5)

        # === NOISE WALL — Amnesia's signature "monster nearby" static ===
        noise_env = min(1.0, t / 0.008) * max(0.0, 1.0 - (t - 0.5) * 0.9)
        noise_env = max(0.0, noise_env)

        # === MIX ===
        val = (
            bass    * 0.38 * 30000
            + screech * screech_env * 0.40 * 30000
            + noise_s[i] * noise_env * 0.28 * 30000
        )
        out[i] = val

    write_wav("jumpscare.wav", fade(out, fi=0.0005, fo=0.25))


# ==============================================================================
# 6. WHISPER  (Priority 6)
# ─ Inspiration: Amnesia's "Daniel... run..." and Silent Hill's radio whispers
# ─ Sounds like a voice saying something you can ALMOST understand
# ─ Three layers: breath, formant ghost, room reflection
# ─ Deliberately kept ambiguous — could be the creature, could be the player's mind
# ==============================================================================
def gen_whisper():
    dur_s = 2.8
    dur   = int(RATE * dur_s)

    # === Layer 1: Breath — shaped noise, two exhales ===
    raw = n(dur)
    breath = []
    for i in range(dur):
        t = i / RATE
        # Two breath pulses, 1.4s apart
        b1 = abs(math.sin(math.pi * t / 1.0)) if t < 1.0 else 0.0
        b2 = abs(math.sin(math.pi * (t - 1.4) / 1.0)) if 1.4 < t < 2.4 else 0.0
        env = max(b1, b2)
        breath.append(raw[i] * env * 7500)

    # === Layer 2: Formant ghost — "vowel" frequencies of speech ===
    # Human vowels live around 300-800 Hz (first formant) and 800-2500 Hz (second)
    # We use 420 Hz and 1100 Hz — sounds like a muffled "o" or "ah"
    formant = [0.0] * dur
    for i in range(dur):
        t   = i / RATE
        # Slow amplitude modulation — the "voice" fades in and out
        vmod = 0.5 + 0.5 * math.sin(2 * math.pi * 0.35 * t)
        f1  = math.sin(2 * math.pi * 420  * t) * 0.55
        f2  = math.sin(2 * math.pi * 1100 * t) * 0.30
        f3  = math.sin(2 * math.pi * 2200 * t) * 0.12   # airy overtone
        formant[i] = (f1 + f2 + f3) * vmod * 2200 * abs(math.sin(math.pi * t / dur_s))

    # === Layer 3: Sub presence — barely felt, not heard ===
    sub = [
        math.sin(2 * math.pi * 45 * i / RATE)
        * abs(math.sin(math.pi * i / dur))
        * 1800
        for i in range(dur)
    ]

    layer = [breath[i] + formant[i] + sub[i] for i in range(dur)]

    # Large room reverb — sounds like it's coming from another room / inside the walls
    write_wav("whisper.wav", fade(reverb(layer, 0.14, 0.38, 5), fi=0.10, fo=0.20))


# ==============================================================================
# SUPPORTING SOUNDS  (used by main.py but not the user's 6 priorities)
# ==============================================================================

def gen_click():
    """Vintage flashlight click — mechanical, slightly broken."""
    dur_s = 0.055
    dur   = int(RATE * dur_s)
    raw   = n(dur)
    # Metal-on-metal transient
    metal = [
        math.sin(2 * math.pi * 3200 * i / RATE) * math.exp(-i / (RATE * 0.005))
        for i in range(dur)
    ]
    layer = [
        raw[i]   * math.exp(-i / (RATE * 0.004)) * 16000
        + metal[i] * 12000
        + math.sin(2 * math.pi * 160 * i / RATE) * math.exp(-i / (RATE * 0.008)) * 7000
        for i in range(dur)
    ]
    write_wav("click.wav", fade(layer, 0.001, 0.008))


def gen_pickup_battery():
    """Relief sound — the only 'positive' sound in the game."""
    # Deliberate contrast: clean rising tone vs everything else being dirty
    # (This contrast makes it feel MORE relieving)
    notes = [523.25, 659.25, 783.99]   # C5, E5, G5 — major chord = safety
    all_s = []
    for freq in notes:
        dur = int(RATE * 0.13)
        body = [
            math.sin(2 * math.pi * freq * i / RATE) * math.exp(-i / (RATE * 0.10))
            + math.sin(2 * math.pi * freq * 2 * i / RATE) * math.exp(-i / (RATE * 0.05)) * 0.25
            for i in range(dur)
        ]
        all_s.extend([s * 22000 for s in body])
    write_wav("pickup_battery.wav", fade(all_s, 0.003, 0.04))


def gen_pickup_key():
    """Key discovery — eerie shimmer, not celebratory."""
    # Minor key shimmer — the key is found but that doesn't mean you're safe
    dur_s = 0.65
    dur   = int(RATE * dur_s)
    freqs = [440.0, 523.25, 659.25, 783.99, 932.33]   # A minor arpeggiated
    body  = [0.0] * dur
    for j, freq in enumerate(freqs):
        delay = int(RATE * j * 0.04)   # staggered entry — like wind chimes
        for i in range(dur):
            if i >= delay:
                t   = i - delay
                body[i] += (
                    math.sin(2 * math.pi * freq * t / RATE)
                    * math.exp(-t / (RATE * 0.22))
                    * (0.50 - j * 0.07)
                )
    raw = n(dur)
    shimmer = [raw[i] * math.exp(-i / (RATE * 0.009)) * 0.10 for i in range(dur)]
    layer = [(body[i] + shimmer[i]) * 28000 for i in range(dur)]
    write_wav("pickup_key.wav", fade(reverb(layer, 0.05, 0.30, 3), 0.002, 0.10))


def gen_door_open():
    """Heavy door — old hospital/asylum weight."""
    total_s = 1.20
    total   = int(RATE * total_s)
    out     = [0.0] * total

    # Latch (0.0 – 0.06s): metal click
    for i in range(int(RATE * 0.06)):
        raw_n = random.random() * 2 - 1
        out[i] = (
            raw_n * math.exp(-i / (RATE * 0.007)) * 20000
            + math.sin(2 * math.pi * 2100 * i / RATE) * math.exp(-i / (RATE * 0.009)) * 9000
        )

    # Swing moan (0.06 – 0.90s): descending FM creak
    moan_start = int(RATE * 0.06)
    moan_s     = 0.84
    moan_n     = int(RATE * moan_s)
    for i in range(moan_n):
        progress = i / moan_n
        freq     = 170 - 80 * progress   # drops from 170 Hz to 90 Hz
        raw_n    = random.random() * 2 - 1
        s        = (
            math.sin(2 * math.pi * (freq + 25 * math.sin(2 * math.pi * 9 * i / RATE)) * i / RATE) * 0.60
            + raw_n * 0.40
        ) * math.sin(math.pi * i / moan_n) * 17000
        idx = moan_start + i
        if idx < total:
            out[idx] += s

    # Settle thud (0.95 – 1.10s)
    settle_start = int(RATE * 0.95)
    for i in range(int(RATE * 0.14)):
        idx = settle_start + i
        if idx < total:
            out[idx] += (
                math.sin(2 * math.pi * 72 * i / RATE) * math.exp(-i / (RATE * 0.045)) * 22000
                + (random.random() * 2 - 1) * math.exp(-i / (RATE * 0.025)) * 5000
            )

    write_wav("door_open.wav", fade(reverb(out, 0.10, 0.32, 4), 0.001, 0.08))


def gen_static_burst():
    """Radio static burst — SH-style creature proximity warning."""
    dur_s = 0.22
    dur   = int(RATE * dur_s)
    raw   = n(dur)
    # Band-limited static (500-4000 Hz range)
    layer = []
    for i in range(dur):
        t = i / RATE
        band = (
            raw[i]
            * (0.7 + 0.3 * math.sin(2 * math.pi * 2200 * t))
            * math.sin(math.pi * i / dur) ** 1.5
        )
        layer.append(band * 20000)
    write_wav("static_burst.wav", fade(layer, 0.002, 0.025))


def gen_low_drone_sting():
    """Tension swell — creature's first appearance. No melody, pure dread."""
    dur_s = 2.0
    dur   = int(RATE * dur_s)
    raw   = n(dur)
    body  = []
    for i in range(dur):
        t    = i / RATE
        # Cluster of detuned low tones — creates maximum tension
        freq = 52.0
        s = (
            math.sin(2 * math.pi * freq       * t) * 0.45
            + math.sin(2 * math.pi * freq * 1.03 * t) * 0.30   # minor 2nd dissonance
            + math.sin(2 * math.pi * freq * 2.0  * t) * 0.18
            + math.sin(2 * math.pi * freq * 2.96 * t) * 0.12   # tritone
        )
        # Bell envelope: swells up then fades
        env  = math.sin(math.pi * t / dur_s) ** 0.55
        nb   = raw[i] * 0.06
        body.append((s + nb) * env * 20000)
    write_wav("low_drone_sting.wav", fade(reverb(body, 0.14, 0.40, 4), fi=0.08, fo=0.25))


# ==============================================================================
# RUN ALL
# ==============================================================================
if __name__ == "__main__":
    print("\n🎵  DON'T LOOK AWAY — Audio Asset Generator")
    print("    Style: Silent Hill / Amnesia  (organic, industrial, wrong)")
    print(f"    Writing to: {os.path.abspath(OUT_DIR)}\n")

    generators = [
        # Your 6 priority sounds (redesigned)
        ("footstep",        gen_footstep),
        ("ambient_hum",     gen_ambient_hum),
        ("creature_move",   gen_creature_move),
        ("heartbeat",       gen_heartbeat),
        ("jumpscare",       gen_jumpscare),
        ("whisper",         gen_whisper),
        # Supporting sounds
        ("click",           gen_click),
        ("pickup_battery",  gen_pickup_battery),
        ("pickup_key",      gen_pickup_key),
        ("door_open",       gen_door_open),
        ("static_burst",    gen_static_burst),
        ("low_drone_sting", gen_low_drone_sting),
    ]

    ok = 0
    for name, fn in generators:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f"  ✗  {name:<26}  ERROR: {e}")

    print(f"\n✅  {ok}/{len(generators)} sounds written to assets/sounds/")
    print("    Test them:    python3 test_sounds.py")
    print("    Play game:    python3 main.py\n")
