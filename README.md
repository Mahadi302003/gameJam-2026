# DON'T LOOK AWAY — GameJam: "UNSTABLE"

> A complete 2D top-down psychological horror game built in Python 3 with Pygame.  
> **Theme:** *UNSTABLE* — The protagonist's perception and mental state are unreliable.

---

## 🎮 Flow & How to Play

### Game Flow
1. **Title Menu** — Press <kbd>SPACE</kbd> or <kbd>Left-Click</kbd> to begin.
2. **Prologue Story Screen** — Atmospheric narrative fade-in describing the protagonist's slipping mental state, establishing the psychological horror. Press <kbd>SPACE</kbd> to wake up into the game.
3. **Gameplay** — Wake up in the **Central Hallway** with doors open, ready to roam and search the interconnected rooms.

### Controls
* **W, A, S, D** — Move protagonist
* **Mouse Cursor** — Aim flashlight beam
* **Left-Click / Right-Click / F** — **Toggle Flashlight ON / OFF** (Conserve battery, but beware of what moves in the dark!)
* **E** — **Interact:** Pick up Key & Batteries, Open/Close Doors, Unlock Main Exit Door
* **R** — Restart game at any time
* **ESC** — Quit

### Objective
1. Start in the **Central Hallway** outside the rooms.
2. The room doors are **open and unlocked**, allowing you to immediately enter and explore:
   * **The Study & Gallery (Top-Right):** Look for the glowing golden **Key** resting on the large study desk. Don't miss the changing portrait on the wall.
   * **The Bedroom (Top-Left):** Contains **Battery 1** on the nightstand, wardrobe, and the shifting chair.
   * **The Storage Room (Bottom-Left):** Contains **Battery 2** on a supply crate and the carved wall clue: `"DON'T LET IT GO DARK."`
   * **The Exit Foyer (Bottom-Right):** Contains **Battery 3** and the **Heavy Locked Exit Door**.
3. Pick up the **Key** from the Study.
4. **DON'T LOOK AWAY:** The creature freezes when caught in your flashlight beam, but moves closer whenever you turn away, turn your flashlight off, or let the darkness take over.
5. Reach the **Heavy Main Exit Door** in the Foyer with your key and press <kbd>E</kbd> to escape... or discover what is actually happening.

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
FLASHLIGHT_ANGLE = 80        # Beam cone angle in degrees (70-90)
FLASHLIGHT_RANGE = 400       # Beam reach in pixels
FLASHLIGHT_BATTERY = 100.0   # Starting battery percentage
BATTERY_DRAIN = 0.65         # Battery % drained per second while flashlight is ON (~155s of continuous light)
BATTERY_REFILL = 50.0        # Battery % restored per battery pickup
CREATURE_MOVE_DELAY = 1.8    # Seconds outside flashlight beam before relocating
CREATURE_AGGRO_DELAY = 1.0   # Faster relocation once key is obtained
CREATURE_ATTACK_DIST = 46    # Proximity threshold for game over in darkness
BLACKOUT_KILL_TIME = 4.5     # Seconds of total darkness before forced jumpscare
```
