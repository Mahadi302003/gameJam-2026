# DON'T LOOK AWAY — GameJam: "UNSTABLE"

> A complete 2D top-down psychological horror game built in Python 3 with Pygame.  
> **Theme:** *UNSTABLE* — The protagonist's perception and mental state are unreliable.

---

## 🎮 Objective & How to Play

### Objective
**SEARCH THE FURNITURE to find the KEY and your RESIDENT ID, then escape through the Heavy Exit Door.**

* **Top-Left HUD:**
  ```text
  KEY: [ ]   ID: [ ]
  FLASHLIGHT [████████░░] 82%
  Status: ON [Click to Toggle]
  ```
* **Exit Door Logic:**
  * Without items: `"THE DOOR IS LOCKED."`
  * With Key but no ID: `"I CAN'T LEAVE WITHOUT MY ID."`
  * With both Key + ID: The door opens, allowing you to escape and uncover the **final plot twist**!

---

## 🔍 Searchable Furniture (Items are no longer in plain sight!)
Items are now tucked into the environment, requiring exploration:
1. **The Study Bookshelf:** Press <kbd>E</kbd> to search the shelves. You discover a hollow book hiding the **Brass Key**!
2. **The Storage Shelf:** Press <kbd>E</kbd> to search the metal shelf. You uncover the **Resident ID Card** tucked behind medical binders!
3. **The Bedroom Nightstand:**
   * On top: The **Night Staff Note** (`[E] Read Note`).
   * Drawer: Search the drawer to find **Battery 1**!
4. **The Wooden Storage Crate:** Press <kbd>E</kbd> to search the crate and uncover **Battery 2**!
5. **The Study Desk & Wardrobe:** Interactive searchable furniture revealing discarded patient papers and scratched wood.

---

## 🔦 Flashlight & Lighting
* **Narrow Focused Beam:** The flashlight beam has been tightened to a claustrophobic **54° cone** (350px reach).
* **Ambient Halo:** Even when the flashlight is clicked **OFF**, a very small, soft halo (~22px) remains around your feet so you can still faintly see where you are stepping, while the rest of the room is enveloped in pitch darkness.

---

## 🎭 The Plot Twist Ending (No Cheap Jumpscare on Escape)
When you gather both the **Key** and **ID Card** and open the exit door:
1. The door unlatches and swings open with warm white light.
2. You step through the doorway into what looks like freedom.
3. The dark house fades away into a quiet, softly-lit hospital / care residence corridor.
4. You look back at the room you just escaped from: the door is labeled **ROOM 4**, and it swings gently without any lock.
5. Beside the door hangs the **Night Staff Observation Whiteboard**:
   ```text
   ST. ALDRIC RESIDENCE - NIGHT OBSERVATION LOG
   RESIDENT #0412 (ROOM 4)
   
   "Resident reported being stalked by an entity in darkness.
    Emptied bookshelves looking for a 'key' to escape.
    Rearranged room chair multiple times during episode.
    
    DIRECTIVE: Room door must remain unlocked per hospital rules.
    Night staff have placed a flashlight beside his bed."
   ```
6. The reality hits you:
   > *"There was no creature.*  
   > *You were running from your own shadow.*  
   > *There was never anyone else in the room."*

*(Jumpscare only occurs if you run out of battery in the dark during active gameplay!)*

---

## 🕹️ Controls
* **W, A, S, D** — Move protagonist
* **Mouse Cursor** — Aim flashlight beam
* **Left-Click / Right-Click / F** — **Toggle Flashlight ON / OFF**
* **E** — **Interact:** Search bookshelves/crates/drawers, pick up items, read notes, open doors
* **R** — Full restart of all game state
* **ESC** — Quit

### 🛠️ Debug Testing Keys
* **F1** — Toggle **Debug HUD** (shows live Instability %, Creature stage, and event log)
* **F2** — **Force Next Instability Event** immediately
* **F3** — **Instant Key + ID** (walk straight to the exit door to experience the plot twist ending!)

---

## 🚀 How to Run
Double-click **[`run_game.bat`](file:///c:/Users/gabit/Desktop/gamejam/run_game.bat)** or run in PyCharm (<kbd>Shift</kbd> + <kbd>F10</kbd>).
