"""
level.py - Map, Level layout, Collision, and Art Integration for 2D Horror GameJam.

Believable Apartment Layout:
- Player Spawn: In the Bedroom (narrative beginning)
- Central Corridor: Narrow, tense 96px residential hallway with subtle environmental details
- Bedroom (Top-Left): Cozy bedroom with furniture along walls, dark wardrobe corner
- Bathroom (Top-Center): Compact, authentic bathroom with tub, sink, toilet
- Kitchen (Top-Right): Wide kitchen with perimeter counters, pantry alcove & dining
- Storage / Utility (Bottom-Left): Tucked-away compact utility room with sheeted crates & clues
- Entry Hall / Foyer (Bottom-Center): Dedicated vestibule with shoe cabinet, doormat, wall frame, leading to Exit
- Living Room & Study (Bottom-Right): Balanced main room with sofa suite, bookshelves, blind spots, corner key desk

Provides public properties for teammate systems:
- level.walls
- level.furniture_colliders
- level.player_spawn
- level.exit_position
- level.exit_rect
- level.key_position
- level.battery_positions
- level.creature_positions
- level.event_objects
"""

import math
import pygame
from assets import AssetManager, SCALE


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

    def draw(self, surface, cam_x, cam_y, assets=None):
        if assets is None:
            assets = AssetManager.get_instance()

        sx = self.closed_rect.x - cam_x
        sy = self.closed_rect.y - cam_y
        w, h = self.closed_rect.width, self.closed_rect.height

        # Visual Doorframe Jambs (Enhances visual readability)
        pygame.draw.rect(surface, (40, 28, 20), (sx - 3, sy, 4, h))
        pygame.draw.rect(surface, (40, 28, 20), (sx + w - 1, sy, 4, h))

        if self.is_exit:
            # Heavy Exit Door
            exit_sprite = assets.sprites.get('exit_door')
            if exit_sprite:
                ew, eh = exit_sprite.get_size()
                surface.blit(exit_sprite, (sx + (w - ew) // 2, sy + (h - eh) // 2))
            else:
                color = (65, 85, 65) if self.is_open else (90, 45, 45)
                pygame.draw.rect(surface, color, (sx, sy, w, h))
                pygame.draw.rect(surface, (25, 25, 25), (sx, sy, w, h), 2)

            # Red exit sign above exit door
            sign = assets.sprites.get('exit_sign_red')
            if sign:
                surface.blit(sign, (sx + (w - sign.get_width()) // 2, sy - 22))
        else:
            if not self.is_open:
                # Closed door sprite
                door_sprite = assets.sprites.get('door_wood')
                if door_sprite:
                    scaled = pygame.transform.scale(door_sprite, (w, h))
                    surface.blit(scaled, (sx, sy))
                else:
                    pygame.draw.rect(surface, (110, 80, 55), (sx, sy, w, h))
                    pygame.draw.rect(surface, (55, 38, 25), (sx, sy, w, h), 2)
            else:
                # Open door swung against the wall, opening is clear
                door_sprite = assets.sprites.get('door_wood')
                swung_w = 8
                swung_rect = (sx - swung_w, sy - 4, swung_w, h + 8)
                if door_sprite:
                    scaled = pygame.transform.scale(door_sprite, (swung_w, h + 8))
                    surface.blit(scaled, (sx - swung_w, sy - 4))
                else:
                    pygame.draw.rect(surface, (95, 68, 44), swung_rect)
                    pygame.draw.rect(surface, (45, 30, 20), swung_rect, 1)


class Level:
    """
    Level manager handling apartment layout, collisions,
    furniture positioning, horror sightlines, and team variables.
    """
    def __init__(self):
        self.assets = AssetManager.get_instance()

        # Overall house bounding box (encloses all rooms & entry vestibule)
        self.house_rect = pygame.Rect(160, 96, 1184, 808)

        # ----------------------------------------------------------------------
        # 1. PUBLIC TEAM INTEGRATION POSITIONS & RECTS
        # ----------------------------------------------------------------------
        # Player spawns in the Bedroom beside the bed
        self.player_spawn = (310, 240)

        # Main Exit Door at bottom of the Entry Hall
        self.exit_position = (640, 880)
        self.exit_rect = pygame.Rect(600, 880, 80, 24)

        # Key located deep in the house on the Living Room study desk
        self.key_position = (1200, 740)

        # 2 battery pickup locations across different rooms
        self.battery_positions = [
            (200, 700),   # 1. Storage room crates
            (585, 580)    # 2. Entry foyer shoe cabinet
        ]

        # Creature predefined event positions (no pathfinding needed)
        self.creature_positions = {
            "far": (190, 432),          # 1. West dead-end of corridor
            "mid": (1280, 140),         # 2. Kitchen dark corner / pantry
            "close": (200, 740),        # 3. Storage utility room deep shadow
            "very_close": (1245, 560),  # 4. Living room shadowy corner behind cabinet
            "final": (640, 800)         # 5. Entry hall looming in front of exit door
        }

        # ----------------------------------------------------------------------
        # 2. WALLS (Rectangular colliders with narrow corridor & varied rooms)
        # ----------------------------------------------------------------------
        self.walls = [
            # --- EXTERIOR BOUNDARY WALLS ---
            pygame.Rect(160, 96, 1184, 24),     # North Outer Wall
            pygame.Rect(160, 96, 24, 684),      # West Outer Wall (Bedroom & Storage)
            pygame.Rect(1320, 96, 24, 768),     # East Outer Wall (Kitchen & Living Room)
            pygame.Rect(160, 756, 414, 24),     # South Wall of Storage Room
            pygame.Rect(730, 840, 614, 24),     # South Wall of Living Room

            # --- NORTH ROOM PARTITIONS (Y=96 to Y=384) ---
            pygame.Rect(480, 96, 24, 288),      # Wall: Bedroom vs Bathroom
            pygame.Rect(744, 96, 24, 288),      # Wall: Bathroom vs Kitchen

            # --- CORRIDOR NORTH WALL (Y=384, with 64px doorways) ---
            pygame.Rect(160, 384, 160, 24),     # Bedroom west section
            pygame.Rect(384, 384, 206, 24),     # Between Bedroom & Bathroom doors
            pygame.Rect(654, 384, 186, 24),     # Between Bathroom & Kitchen doors
            pygame.Rect(904, 384, 440, 24),     # Kitchen east section

            # --- CORRIDOR SOUTH WALL (Y=480, narrow 96px corridor!) ---
            pygame.Rect(160, 480, 160, 24),     # Storage west section
            pygame.Rect(384, 480, 166, 24),     # Storage east section
            pygame.Rect(854, 480, 490, 24),     # Living Room east section

            # --- ENTRY HALL / FOYER WALLS (Vestibule X: 550 to 730, Y: 480 to 880) ---
            pygame.Rect(550, 480, 24, 400),     # West Wall of Entry Hall
            pygame.Rect(730, 480, 24, 400),     # East Wall of Entry Hall (shared with Living)
            pygame.Rect(550, 880, 50, 24),      # South Wall west of Exit Door
            pygame.Rect(680, 880, 74, 24),      # South Wall east of Exit Door
        ]

        # For backwards compatibility with main.py
        self.static_walls = self.walls

        # ----------------------------------------------------------------------
        # 3. INTERACTIVE DOORS
        # ----------------------------------------------------------------------
        self.doors = [
            InteractiveDoor(320, 384, 64, 24, is_exit=False, is_open=True, name="Bedroom Door"),
            InteractiveDoor(590, 384, 64, 24, is_exit=False, is_open=True, name="Bathroom Door"),
            InteractiveDoor(840, 384, 64, 24, is_exit=False, is_open=True, name="Kitchen Door"),
            InteractiveDoor(320, 480, 64, 24, is_exit=False, is_open=True, name="Storage Door"),
            InteractiveDoor(790, 480, 64, 24, is_exit=False, is_open=True, name="Living Room Door"),
            InteractiveDoor(600, 880, 80, 24, is_exit=True, is_open=False, name="Main Exit Door"),
        ]

        # ----------------------------------------------------------------------
        # 4. FURNITURE & COLLIDERS (Arranged along perimeter walls for open paths)
        # ----------------------------------------------------------------------
        # 1. Bedroom (Top-Left: X: 160..480, Y: 96..384)
        self.bed_rect = pygame.Rect(190, 120, 96, 128)          # Against North wall
        self.nightstand_rect = pygame.Rect(295, 120, 48, 48)     # Next to bed with clock
        self.wardrobe_rect = pygame.Rect(410, 125, 64, 96)       # Against East wall (dark shadow behind)
        self.dresser_rect = pygame.Rect(185, 270, 48, 80)        # Against West wall

        # Moving Chair in Bedroom
        self.chair_initial_pos = (260, 290)
        self.chair_altered_pos = (340, 220)
        self.chair_pos = list(self.chair_initial_pos)
        self.chair_rect = pygame.Rect(self.chair_pos[0], self.chair_pos[1], 32, 32)
        self.chair_has_moved = False

        # 2. Bathroom (Top-Center, compact: X: 504..744, Y: 96..384)
        self.bathtub_rect = pygame.Rect(520, 125, 160, 54)       # Against North wall
        self.sink_rect = pygame.Rect(520, 210, 48, 48)          # Against West wall
        self.toilet_rect = pygame.Rect(690, 210, 48, 48)        # Against East wall
        self.laundry_rect = pygame.Rect(690, 295, 48, 48)       # Laundry basket against East wall

        # 3. Kitchen (Top-Right: X: 768..1320, Y: 96..384)
        self.fridge_rect = pygame.Rect(775, 125, 64, 96)        # In corner alcove
        self.stove_rect = pygame.Rect(890, 125, 60, 64)         # Along North wall
        self.counter_rect = pygame.Rect(960, 125, 128, 64)      # Along North wall
        self.dining_table_rect = pygame.Rect(1120, 230, 120, 70)# Dining table with plenty of clearance
        self.dining_chair_1 = pygame.Rect(1080, 240, 32, 50)
        self.dining_chair_2 = pygame.Rect(1245, 240, 32, 50)

        # 4. Storage Room (Bottom-Left, utility: X: 160..550, Y: 480..756)
        self.sheet_chair_rect = pygame.Rect(185, 520, 80, 80)   # Against West wall
        self.sheet_crates_rect = pygame.Rect(185, 660, 96, 80)  # In SW corner
        self.storage_shelf_rect = pygame.Rect(470, 640, 70, 80) # Against East wall

        # 5. Entry Hall / Foyer (Bottom-Center: X: 550..730, Y: 480..880)
        self.foyer_table = pygame.Rect(575, 560, 40, 70)        # Shoe cabinet against West wall
        self.foyer_shelf = pygame.Rect(685, 660, 40, 70)        # Coat rack against East wall

        # 6. Living Room & Study (Bottom-Right: X: 730..1320, Y: 480..840)
        self.bookshelf_1 = pygame.Rect(870, 508, 96, 80)        # Against North wall
        self.living_sidetable = pygame.Rect(1140, 510, 48, 50)   # Side table near display cabinet
        self.display_cabinet = pygame.Rect(1245, 510, 70, 110)  # Against East wall
        self.sofa_rect = pygame.Rect(950, 630, 96, 50)          # Sofa facing South TV
        self.armchair_rect = pygame.Rect(865, 630, 50, 50)      # Armchair 1 beside sofa
        self.armchair_2_rect = pygame.Rect(1070, 630, 50, 50)   # Armchair 2 (frames conversation area)
        self.coffee_table_rect = pygame.Rect(970, 700, 60, 40)  # Coffee table
        self.tv_console_rect = pygame.Rect(950, 780, 96, 60)    # TV against South wall
        self.study_desk_rect = pygame.Rect(1200, 740, 110, 80)  # Corner study desk with key
        self.floor_lamp = pygame.Rect(1290, 660, 24, 50)

        # UNSTABLE: Portrait in Living Room
        self.painting_rect = pygame.Rect(1030, 485, 64, 48)
        self.painting_seen_once = False
        self.painting_altered = False

        # Environmental Clue in Storage Room
        self.clue_text = "DON'T LET IT GO DARK."
        self.clue_pos = (210, 506)

        # Full collision list
        self.furniture_colliders = [
            self.bed_rect, self.nightstand_rect, self.wardrobe_rect, self.dresser_rect, self.chair_rect,
            self.bathtub_rect, self.sink_rect, self.toilet_rect, self.laundry_rect,
            self.fridge_rect, self.stove_rect, self.counter_rect, self.dining_table_rect,
            self.dining_chair_1, self.dining_chair_2,
            self.sheet_chair_rect, self.sheet_crates_rect, self.storage_shelf_rect,
            self.foyer_table, self.foyer_shelf,
            self.bookshelf_1, self.living_sidetable, self.display_cabinet,
            self.sofa_rect, self.armchair_rect, self.armchair_2_rect,
            self.coffee_table_rect, self.tv_console_rect, self.study_desk_rect, self.floor_lamp
        ]

        # ----------------------------------------------------------------------
        # 5. COLLECTIBLES: KEY & BATTERIES
        # ----------------------------------------------------------------------
        self.has_key = False
        self.key_collected = False
        self.key_rect = pygame.Rect(self.key_position[0], self.key_position[1], 24, 24)

        # Compatibility list for main.py
        self.batteries = [
            {"rect": pygame.Rect(pos[0], pos[1], 20, 20), "collected": False, "room": "Storage" if i == 0 else "Foyer"}
            for i, pos in enumerate(self.battery_positions)
        ]

        # ----------------------------------------------------------------------
        # 6. ENVIRONMENTAL HORROR EVENT TARGETS
        # ----------------------------------------------------------------------
        self.event_objects = {
            "bedroom_chair": {
                "type": "chair",
                "room": "bedroom",
                "initial_pos": self.chair_initial_pos,
                "altered_pos": self.chair_altered_pos,
                "rect": self.chair_rect,
                "has_altered": False
            },
            "living_painting": {
                "type": "painting",
                "room": "living",
                "pos": (self.painting_rect.x, self.painting_rect.y),
                "rect": self.painting_rect,
                "seen_once": False,
                "has_altered": False
            },
            "wardrobe_eyes": {
                "type": "wardrobe",
                "room": "bedroom",
                "pos": (self.wardrobe_rect.x, self.wardrobe_rect.y),
                "rect": self.wardrobe_rect,
                "has_altered": False
            },
            "bathroom_mirror": {
                "type": "mirror",
                "room": "bathroom",
                "pos": (520, 180),
                "rect": pygame.Rect(520, 180, 48, 48),
                "has_altered": False
            },
            "storage_clue": {
                "type": "graffiti",
                "room": "storage",
                "pos": self.clue_pos,
                "text": self.clue_text
            }
        }

        self.floor_cache = None
        self._build_floor_cache()

    def _build_floor_cache(self):
        """Pre-renders tiled floors for the apartment onto a cached surface."""
        w, h = self.house_rect.width, self.house_rect.height
        self.floor_cache = pygame.Surface((w, h))
        self.floor_cache.fill((16, 14, 12))

        def tile_rect(surf, texture, rect):
            if not texture:
                return
            tw, th = texture.get_size()
            rx = rect.x - self.house_rect.x
            ry = rect.y - self.house_rect.y
            for y in range(ry, ry + rect.height, th):
                for x in range(rx, rx + rect.width, tw):
                    sub_w = min(tw, rx + rect.width - x)
                    sub_h = min(th, ry + rect.height - y)
                    if sub_w > 0 and sub_h > 0:
                        surf.blit(texture, (x, y), (0, 0, sub_w, sub_h))

        # 1. Bedroom Floor: Burgundy Carpet
        tile_rect(self.floor_cache, self.assets.floors.get('bedroom'), pygame.Rect(184, 120, 296, 264))

        # 2. Bathroom Floor: White Ceramic Tile
        tile_rect(self.floor_cache, self.assets.floors.get('bathroom'), pygame.Rect(504, 120, 240, 264))

        # 3. Kitchen Floor: Terracotta Checker Tile
        tile_rect(self.floor_cache, self.assets.floors.get('kitchen'), pygame.Rect(768, 120, 552, 264))

        # 4. Central Corridor: Narrow Crimson Runner (Y: 408 to 480)
        tile_rect(self.floor_cache, self.assets.floors.get('corridor'), pygame.Rect(184, 408, 1136, 72))

        # 5. Entry Hall / Foyer: Grey Stone Floor (Y: 480 to 880)
        tile_rect(self.floor_cache, self.assets.floors.get('corridor_neutral'), pygame.Rect(574, 480, 156, 400))

        # 6. Storage Room Floor: Weathered Wood Planks (fills up to wall X=550)
        tile_rect(self.floor_cache, self.assets.floors.get('storage'), pygame.Rect(184, 504, 366, 252))

        # 7. Living Room Floor: Herringbone Parquet
        tile_rect(self.floor_cache, self.assets.floors.get('living'), pygame.Rect(754, 504, 566, 336))

    def get_solid_colliders(self):
        """Returns all solid bounding boxes player cannot pass through."""
        colliders = list(self.walls)
        for d in self.doors:
            c = d.get_solid_collider()
            if c:
                colliders.append(c)

        self.chair_rect.topleft = self.chair_pos
        colliders.extend(self.furniture_colliders)
        return colliders

    def draw_environment(self, surface, cam_x, cam_y, font_sm):
        """Renders floorboards, walls, furniture, clutter, horror details and items."""
        # 1. Floor
        fx = self.house_rect.x - cam_x
        fy = self.house_rect.y - cam_y
        surface.blit(self.floor_cache, (fx, fy))

        # 2. Floor Blood / Scratches / Clutter
        blood_scratch = self.assets.sprites.get('blood_scratches')
        if blood_scratch:
            surface.blit(blood_scratch, (280 - cam_x, 620 - cam_y))
            surface.blit(blood_scratch, (630 - cam_x, 780 - cam_y))

        blood_hand = self.assets.sprites.get('blood_handprint')
        if blood_hand:
            surface.blit(blood_hand, (230 - cam_x, 520 - cam_y))
            surface.blit(blood_hand, (530 - cam_x, 260 - cam_y))

        # Corridor subtle environmental details (1-2 subtle touches)
        blood_drop = self.assets.sprites.get('blood_drips')
        if blood_drop:
            surface.blit(blood_drop, (720 - cam_x, 435 - cam_y))

        # Entry Hall Doormat in front of Exit Door
        doormat = self.assets.sprites.get('entry_doormat')
        if doormat:
            surface.blit(doormat, (620 - cam_x, 845 - cam_y))

        # 3. Walls
        brick_tile = self.assets.walls.get('brick')
        tw, th = brick_tile.get_size() if brick_tile else (32, 32)

        for w in self.walls:
            sx = w.x - cam_x
            sy = w.y - cam_y
            if brick_tile:
                for y in range(0, w.height, th):
                    for x in range(0, w.width, tw):
                        sub_w = min(tw, w.width - x)
                        sub_h = min(th, w.height - y)
                        surface.blit(brick_tile, (sx + x, sy + y), (0, 0, sub_w, sub_h))
            else:
                pygame.draw.rect(surface, (55, 48, 44), (sx, sy, w.width, w.height))
            pygame.draw.rect(surface, (30, 22, 18), (sx, sy, w.width, w.height), 2)

        # 4. Interactive Doors
        for d in self.doors:
            d.draw(surface, cam_x, cam_y, self.assets)

        # 5. Wall Decors (Posters, Signs, Notes, Graffiti)
        extinguisher = self.assets.sprites.get('fire_extinguisher')
        if extinguisher:
            surface.blit(extinguisher, (220 - cam_x, 388 - cam_y))

        corridor_note = self.assets.sprites.get('note_paper')
        if corridor_note:
            surface.blit(corridor_note, (520 - cam_x, 392 - cam_y))

        poster = self.assets.sprites.get('poster_normal')
        if poster:
            surface.blit(poster, (240 - cam_x, 100 - cam_y))

        mirror = self.assets.sprites.get('mirror_ghost' if self.has_key else 'mirror_clean')
        if mirror:
            surface.blit(mirror, (520 - cam_x, 180 - cam_y))

        foyer_frame = self.assets.sprites.get('wall_frame_small')
        if foyer_frame:
            surface.blit(foyer_frame, (685 - cam_x, 500 - cam_y))

        clue_sx = self.clue_pos[0] - cam_x
        clue_sy = self.clue_pos[1] - cam_y
        clue_surf = font_sm.render(self.clue_text, True, (180, 70, 60))
        surface.blit(clue_surf, (clue_sx, clue_sy))

        spiderweb = self.assets.sprites.get('spiderweb')
        if spiderweb:
            surface.blit(spiderweb, (185 - cam_x, 504 - cam_y))

        # 6. Furniture Drawing
        # --- BEDROOM ---
        bed = self.assets.sprites.get('bed_brown')
        if bed:
            surface.blit(bed, (self.bed_rect.x - cam_x, self.bed_rect.y - cam_y))

        clock = self.assets.sprites.get('alarm_clock')
        if clock:
            surface.blit(clock, (self.nightstand_rect.x - cam_x, self.nightstand_rect.y - cam_y))

        wardrobe_key = 'wardrobe_eyes' if self.has_key else 'wardrobe_closed'
        wardrobe = self.assets.sprites.get(wardrobe_key)
        if wardrobe:
            surface.blit(wardrobe, (self.wardrobe_rect.x - cam_x, self.wardrobe_rect.y - cam_y))

        dresser = self.assets.sprites.get('bedroom_dresser')
        if dresser:
            surface.blit(dresser, (self.dresser_rect.x - cam_x, self.dresser_rect.y - cam_y))

        chair = self.assets.sprites.get('dining_chair' if not self.chair_has_moved else 'dining_chair_fallen')
        if chair:
            surface.blit(chair, (self.chair_pos[0] - cam_x, self.chair_pos[1] - cam_y))

        # --- BATHROOM ---
        tub_key = 'bathtub_bloody' if self.has_key else 'bathtub_clean'
        tub = self.assets.sprites.get(tub_key)
        if tub:
            surface.blit(tub, (self.bathtub_rect.x - cam_x, self.bathtub_rect.y - cam_y))

        sink = self.assets.sprites.get('sink_bloody' if self.has_key else 'sink_clean')
        if sink:
            surface.blit(sink, (self.sink_rect.x - cam_x, self.sink_rect.y - cam_y))

        toilet = self.assets.sprites.get('toilet')
        if toilet:
            surface.blit(toilet, (self.toilet_rect.x - cam_x, self.toilet_rect.y - cam_y))

        laundry = self.assets.sprites.get('washing_machine')
        if laundry:
            surface.blit(laundry, (self.laundry_rect.x - cam_x, self.laundry_rect.y - cam_y))

        # --- KITCHEN ---
        fridge = self.assets.sprites.get('fridge_closed')
        if fridge:
            surface.blit(fridge, (self.fridge_rect.x - cam_x, self.fridge_rect.y - cam_y))

        stove = self.assets.sprites.get('kitchen_stove')
        if stove:
            surface.blit(stove, (self.stove_rect.x - cam_x, self.stove_rect.y - cam_y))

        counter = self.assets.sprites.get('kitchen_counter')
        if counter:
            surface.blit(counter, (self.counter_rect.x - cam_x, self.counter_rect.y - cam_y))

        dtable = self.assets.sprites.get('dining_table')
        if dtable:
            surface.blit(dtable, (self.dining_table_rect.x - cam_x, self.dining_table_rect.y - cam_y))

        k_chair = self.assets.sprites.get('dining_chair')
        if k_chair:
            surface.blit(k_chair, (self.dining_chair_1.x - cam_x, self.dining_chair_1.y - cam_y))
            surface.blit(k_chair, (self.dining_chair_2.x - cam_x, self.dining_chair_2.y - cam_y))

        knife = self.assets.sprites.get('knife_bloody')
        if knife:
            surface.blit(knife, (1030 - cam_x, 130 - cam_y))

        # --- STORAGE ROOM ---
        sheet_chair = self.assets.sprites.get('sheet_chair')
        if sheet_chair:
            surface.blit(sheet_chair, (self.sheet_chair_rect.x - cam_x, self.sheet_chair_rect.y - cam_y))

        sheet_crates = self.assets.sprites.get('sheet_table')
        if sheet_crates:
            surface.blit(sheet_crates, (self.sheet_crates_rect.x - cam_x, self.sheet_crates_rect.y - cam_y))

        shelf = self.assets.sprites.get('bookshelf')
        if shelf:
            surface.blit(shelf, (self.storage_shelf_rect.x - cam_x, self.storage_shelf_rect.y - cam_y))

        # --- ENTRY HALL / FOYER ---
        shoe_cab = self.assets.sprites.get('shoe_cabinet')
        if shoe_cab:
            surface.blit(shoe_cab, (self.foyer_table.x - cam_x, self.foyer_table.y - cam_y))

        if shelf:
            surface.blit(shelf, (self.foyer_shelf.x - cam_x, self.foyer_shelf.y - cam_y))

        # --- LIVING ROOM ---
        b_shelf = self.assets.sprites.get('bookshelf')
        if b_shelf:
            surface.blit(b_shelf, (self.bookshelf_1.x - cam_x, self.bookshelf_1.y - cam_y))

        side_table = self.assets.sprites.get('coffee_table')
        if side_table:
            surface.blit(side_table, (self.living_sidetable.x - cam_x, self.living_sidetable.y - cam_y))

        painting_key = 'portrait_corrupt' if self.painting_altered else 'portrait_normal'
        painting = self.assets.sprites.get(painting_key)
        if painting:
            surface.blit(painting, (self.painting_rect.x - cam_x, self.painting_rect.y - cam_y))

        cabinet = self.assets.sprites.get('cabinet_broken' if self.has_key else 'display_cabinet')
        if cabinet:
            surface.blit(cabinet, (self.display_cabinet.x - cam_x, self.display_cabinet.y - cam_y))

        sofa = self.assets.sprites.get('sofa_torn' if self.has_key else 'sofa_clean')
        if sofa:
            surface.blit(sofa, (self.sofa_rect.x - cam_x, self.sofa_rect.y - cam_y))

        armchair = self.assets.sprites.get('armchair_clean')
        if armchair:
            surface.blit(armchair, (self.armchair_rect.x - cam_x, self.armchair_rect.y - cam_y))
            surface.blit(armchair, (self.armchair_2_rect.x - cam_x, self.armchair_2_rect.y - cam_y))

        coffee_t = self.assets.sprites.get('coffee_table')
        if coffee_t:
            surface.blit(coffee_t, (self.coffee_table_rect.x - cam_x, self.coffee_table_rect.y - cam_y))

        tv_key = 'tv_broken' if self.has_key else 'tv_console'
        tv = self.assets.sprites.get(tv_key)
        if tv:
            surface.blit(tv, (self.tv_console_rect.x - cam_x, self.tv_console_rect.y - cam_y))

        desk = self.assets.sprites.get('sheet_table')
        if desk:
            surface.blit(desk, (self.study_desk_rect.x - cam_x, self.study_desk_rect.y - cam_y))

        lamp = self.assets.sprites.get('floor_lamp')
        if lamp:
            surface.blit(lamp, (self.floor_lamp.x - cam_x, self.floor_lamp.y - cam_y))

        # ----------------------------------------------------------------------
        # 7. ITEMS: KEY & BATTERIES
        # ----------------------------------------------------------------------
        if not self.key_collected:
            key_sprite = self.assets.sprites.get('key_item')
            kx = self.key_rect.centerx - cam_x
            ky = self.key_rect.centery - cam_y
            pulse = math.sin(pygame.time.get_ticks() / 250.0) * 3
            pygame.draw.circle(surface, (255, 230, 80), (int(kx), int(ky)), int(8 + pulse), 1)
            if key_sprite:
                surface.blit(key_sprite, (kx - key_sprite.get_width() // 2, ky - key_sprite.get_height() // 2))
            else:
                pygame.draw.circle(surface, (255, 215, 60), (int(kx), int(ky)), 5)

        bat_sprite = self.assets.sprites.get('battery_item')
        for bat in self.batteries:
            if not bat["collected"]:
                r = bat["rect"]
                bx, by = r.x - cam_x, r.y - cam_y
                if bat_sprite:
                    surface.blit(bat_sprite, (bx, by))
                else:
                    pygame.draw.rect(surface, (50, 185, 100), (bx, by, r.width, r.height))


# Compatibility alias for main.py
GameRoom = Level
