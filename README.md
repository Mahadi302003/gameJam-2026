# DON'T LOOK AWAY — GameJam: "UNSTABLE"

> A complete 2D top-down psychological horror game built in Python 3 with Pygame.  
> **Theme:** *UNSTABLE* — The protagonist's perception and mental state are unreliable.

---

## 🎮 How to Play

### Controls
* **W, A, S, D** — Move protagonist
* **Mouse Cursor** — Aim flashlight beam
* **Left-Click / Right-Click / F** — **Toggle Flashlight ON / OFF** (Conserve battery, but beware of what moves in the dark!)
* **E** — **Interact:** Open/Close Doors, Pick up Key & Batteries, Unlock Main Exit Door
* **R** — Restart game at any time
* **ESC** — Quit

### Objective
1. Start in the dark **Bedroom**.
2. Press **[E]** to unlatch the door and step out into the **Central Hallway**.
3. Explore the interconnected rooms (**Bedroom, Study/Gallery, Storage Room, and Exit Foyer**).
4. Find the **Key** hidden on the writing desk in the **Study**.
5. Pick up spare **Batteries** to keep your flashlight charged.
6. **DON'T LOOK AWAY:** The creature freezes when caught in your flashlight beam, but moves closer whenever you turn away, turn your flashlight off, or let the darkness take over.
7. Reach the **Heavy Main Exit Door** in the Foyer and escape... or discover what is actually happening.

---

## 🚀 Running the Game

### Option 1: Double-Click the Launcher (Easiest)
Double-click **`run_game.bat`** in `C:\Users\gabit\Desktop\gamejam\run_game.bat`.

### Option 2: Run in PyCharm
Right-click on **`main.py`** and select **Run 'main'** (or press `Shift + F10`).

### Option 3: Terminal / Command Prompt
```bash
cd C:\Users\gabit\Desktop\gamejam
python main.py
```

---

## ⚙️ Difficulty & Balancing Settings

All core gameplay and balance parameters are located right at the top of [main.py](file:///c:/Users/gabit/Desktop/gamejam/main.py#L26-L50) for easy tuning:

```python
PLAYER_SPEED = 3.3           # WASD speed in pixels per frame
FLASHLIGHT_ANGLE = 78        # Beam cone angle in degrees (70-90)
FLASHLIGHT_RANGE = 390       # Beam reach in pixels
FLASHLIGHT_BATTERY = 100.0   # Starting battery percentage
BATTERY_DRAIN = 1.8          # Battery % drained per second while flashlight is ON
BATTERY_REFILL = 45.0        # Battery % restored per battery pickup
CREATURE_MOVE_DELAY = 1.6    # Seconds outside flashlight beam before relocating
CREATURE_AGGRO_DELAY = 0.9   # Faster relocation once key is obtained
CREATURE_ATTACK_DIST = 46    # Proximity threshold for game over in darkness
BLACKOUT_KILL_TIME = 4.2     # Seconds of total darkness before forced jumpscare
```

---

## 📁 Optional External Assets

The game contains procedural pixel-art sprites and built-in procedural audio synthesis, so it runs completely self-contained.

You can drop your custom art or sound files directly into `assets/` at any time:

```text
gamejam/
│
├── main.py
├── README.md
├── run_game.bat
└── assets/
    ├── images/
    │   └── (Optional: player.png, creature.png, jumpscare.png)
    └── sounds/
        ├── click.wav           # Flashlight toggle click
        ├── footstep.wav        # Walking footsteps
        ├── pickup_battery.wav  # Battery pickup
        ├── pickup_key.wav      # Key pickup
        ├── creature_move.wav   # Rustle / scuttle sound
        ├── door_open.wav       # Creaking door unlatching
        ├── heartbeat.wav       # Heartbeat in darkness
        └── jumpscare.wav       # Climax jumpscare sound
```

If an asset is missing or fails to load, the game automatically uses the procedural fallback and will **never crash**.
