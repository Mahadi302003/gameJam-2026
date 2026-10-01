"""
assets.py - Centralized asset loader and sprite cache for 2D GameJam horror game.
Loads sprite sheets once and slices them cleanly into pixel-perfect surfaces.
"""

import os
import pygame

SCALE = 2  # 16px tile -> 32px tile for crisp pixel-art and smooth 24px player movement

class AssetManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AssetManager()
        return cls._instance

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.house2_dir = os.path.join(base_dir, "assets", "house_2.0", "Modern House with a Horror Twist 2.0")
        if not os.path.exists(self.house2_dir):
            self.house2_dir = os.path.join(base_dir, "assets")

        self.sheets = {}
        self.sprites = {}
        self.floors = {}
        self.walls = {}
        self._load_sheets()
        self._extract_all()

    def _load_img(self, filename):
        path = os.path.join(self.house2_dir, filename)
        if not os.path.exists(path):
            for root, _, files in os.walk(os.path.dirname(self.house2_dir)):
                if filename in files:
                    path = os.path.join(root, filename)
                    break
        try:
            img = pygame.image.load(path)
            if pygame.display.get_surface() is not None:
                img = img.convert_alpha()
            return img
        except Exception as e:
            print(f"[AssetManager] Error loading {path}: {e}")
            surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            surf.fill((100, 100, 100, 255))
            return surf

    def _load_sheets(self):
        self.sheets['bedroom'] = self._load_img('Modern House Bedroom 2.0.png')
        self.sheets['bathroom'] = self._load_img('Modern House Bathroom 2.0.png')
        self.sheets['kitchen'] = self._load_img('Modern House Kitchen 2.0.png')
        self.sheets['living'] = self._load_img('Modern House Living Room 2.0.png')
        self.sheets['corridor'] = self._load_img('Corridor.png')
        self.sheets['doors'] = self._load_img('DoorsandWindows 2.0.png')
        self.sheets['attic'] = self._load_img('ModernHouse Attic 2.0.png')
        self.sheets['fridge'] = self._load_img('Fridge.png')
        self.sheets['clutter'] = self._load_img('Clutter.png')
        self.sheets['blood'] = self._load_img('Blood spatter.png')

    def _cut(self, sheet_key, rect, scale=SCALE):
        """Cuts a subsurface from a loaded sheet and scales it cleanly."""
        sheet = self.sheets[sheet_key]
        sw, sh = sheet.get_size()
        r = pygame.Rect(rect)
        r.x = max(0, min(r.x, sw - 1))
        r.y = max(0, min(r.y, sh - 1))
        r.w = max(1, min(r.w, sw - r.x))
        r.h = max(1, min(r.h, sh - r.y))
        sub = sheet.subsurface(r).copy()
        if scale != 1:
            sub = pygame.transform.scale(sub, (r.w * scale, r.h * scale))
        return sub

    def _extract_all(self):
        # --- FLOOR PATTERNS (Seamless 48x48 blocks) ---
        self.floors['living'] = self._cut('living', (0, 48, 48, 48))
        self.floors['living_dark'] = self._cut('living', (0, 0, 48, 48))
        self.floors['rug_red'] = self._cut('living', (48, 0, 48, 48))
        self.floors['bedroom'] = self._cut('bedroom', (192, 48, 48, 48))
        self.floors['bedroom_slate'] = self._cut('bedroom', (144, 192, 48, 48))
        self.floors['bathroom'] = self._cut('bathroom', (0, 0, 48, 48))
        self.floors['bathroom_green'] = self._cut('bathroom', (0, 240, 48, 48))
        self.floors['kitchen'] = self._cut('kitchen', (0, 96, 48, 48))
        self.floors['kitchen_grey'] = self._cut('kitchen', (48, 96, 48, 48))
        self.floors['storage'] = self._cut('attic', (0, 32, 48, 32))
        self.floors['corridor'] = self._cut('corridor', (112, 80, 48, 48))
        self.floors['corridor_neutral'] = self._cut('corridor', (64, 80, 48, 48))

        # --- WALL PATTERNS ---
        self.walls['brick'] = self._cut('corridor', (128, 0, 64, 48))
        self.walls['attic_wood'] = self._cut('attic', (0, 48, 48, 32))
        self.walls['plain_light'] = self._cut('corridor', (0, 80, 64, 32))

        # --- DOORS & SIGNS ---
        self.sprites['door_wood'] = self._cut('doors', (0, 32, 32, 32))
        self.sprites['door_white'] = self._cut('doors', (0, 0, 32, 32))
        self.sprites['door_dark_open'] = self._cut('doors', (32, 32, 32, 32))
        self.sprites['door_dark_eyes'] = self._cut('doors', (64, 32, 32, 32))
        self.sprites['exit_door'] = self._cut('corridor', (12, 188, 24, 36))
        self.sprites['exit_sign_green'] = self._cut('corridor', (0, 72, 16, 8))
        self.sprites['exit_sign_red'] = self._cut('corridor', (64, 72, 16, 8))
        self.sprites['fire_extinguisher'] = self._cut('corridor', (52, 65, 12, 15))
        self.sprites['entry_doormat'] = self._cut('corridor', (97, 33, 14, 7), scale=3)

        # --- BEDROOM FURNITURE ---
        self.sprites['bed_brown'] = self._cut('bedroom', (48, 0, 48, 64))
        self.sprites['bed_unmade'] = self._cut('bedroom', (96, 0, 48, 64))
        self.sprites['bed_blue'] = self._cut('bedroom', (0, 192, 48, 64))
        self.sprites['wardrobe_closed'] = self._cut('bedroom', (0, 96, 48, 48))
        self.sprites['wardrobe_open'] = self._cut('bedroom', (48, 96, 48, 48))
        self.sprites['wardrobe_eyes'] = self._cut('bedroom', (96, 96, 48, 48))
        self.sprites['alarm_clock'] = self._cut('bedroom', (0, 48, 32, 16))
        self.sprites['bedroom_dresser'] = self._cut('bedroom', (348, 0, 24, 48))
        self.sprites['poster_normal'] = self._cut('bedroom', (255, 103, 20, 28))
        self.sprites['poster_bloody'] = self._cut('bedroom', (303, 103, 20, 28))

        # --- BATHROOM FURNITURE ---
        self.sprites['toilet'] = self._cut('bathroom', (0, 48, 32, 32))
        self.sprites['toilet_side'] = self._cut('bathroom', (0, 80, 32, 32))
        self.sprites['sink_clean'] = self._cut('bathroom', (32, 48, 32, 32))
        self.sprites['sink_bloody'] = self._cut('bathroom', (64, 48, 32, 32))
        self.sprites['mirror_clean'] = self._cut('bathroom', (144, 48, 32, 32))
        self.sprites['mirror_ghost'] = self._cut('bathroom', (192, 48, 32, 32))
        self.sprites['bathtub_clean'] = self._cut('bathroom', (144, 144, 96, 32))
        self.sprites['bathtub_bloody'] = self._cut('bathroom', (144, 224, 96, 32))
        self.sprites['shower_booth'] = self._cut('bathroom', (0, 160, 48, 64))
        self.sprites['washing_machine'] = self._cut('bathroom', (112, 0, 32, 32))

        # --- KITCHEN FURNITURE ---
        self.sprites['fridge_closed'] = self._cut('fridge', (16, 96, 32, 48))
        self.sprites['fridge_open'] = self._cut('fridge', (112, 96, 32, 48))
        self.sprites['kitchen_stove'] = self._cut('kitchen', (32, 0, 32, 48))
        self.sprites['kitchen_counter'] = self._cut('kitchen', (64, 0, 64, 48))
        self.sprites['dining_table'] = self._cut('kitchen', (128, 0, 96, 48))
        self.sprites['dining_chair'] = self._cut('kitchen', (224, 0, 16, 32))
        self.sprites['dining_chair_fallen'] = self._cut('kitchen', (240, 32, 16, 32))
        self.sprites['kitchen_shelf'] = self._cut('kitchen', (96, 96, 48, 32))

        # --- LIVING ROOM & FOYER FURNITURE ---
        self.sprites['sofa_clean'] = self._cut('living', (0, 96, 48, 32))
        self.sprites['sofa_torn'] = self._cut('living', (48, 96, 48, 32))
        self.sprites['armchair_clean'] = self._cut('living', (0, 128, 32, 32))
        self.sprites['armchair_torn'] = self._cut('living', (32, 128, 32, 32))
        self.sprites['coffee_table'] = self._cut('living', (192, 240, 48, 40))
        self.sprites['shoe_cabinet'] = self._cut('living', (240, 256, 16, 26))
        self.sprites['tv_console'] = self._cut('living', (96, 240, 48, 40))
        self.sprites['tv_broken'] = self._cut('living', (144, 240, 48, 40))
        self.sprites['bookshelf'] = self._cut('living', (288, 48, 48, 48))
        self.sprites['display_cabinet'] = self._cut('living', (0, 232, 48, 56))
        self.sprites['cabinet_broken'] = self._cut('living', (48, 232, 48, 56))
        self.sprites['portrait_normal'] = self._cut('living', (144, 96, 32, 32))
        self.sprites['portrait_corrupt'] = self._cut('living', (176, 96, 32, 32))
        self.sprites['floor_lamp'] = self._cut('living', (144, 48, 16, 32))
        self.sprites['house_plant'] = self._cut('living', (288, 0, 32, 32))
        self.sprites['wall_frame_small'] = self._cut('living', (128, 0, 32, 32))

        # --- STORAGE ROOM / ATTIC FURNITURE ---
        self.sprites['sheet_chair'] = self._cut('attic', (0, 0, 48, 48))
        self.sprites['sheet_table'] = self._cut('attic', (48, 0, 48, 48))
        self.sprites['spiderweb'] = self._cut('attic', (64, 0, 32, 32))

        # --- CLUTTER & BLOOD ---
        self.sprites['blood_handprint'] = self._cut('blood', (32, 16, 16, 16))
        self.sprites['blood_scratches'] = self._cut('blood', (16, 16, 16, 16))
        self.sprites['blood_pool'] = self._cut('blood', (0, 0, 16, 16))
        self.sprites['blood_drips'] = self._cut('blood', (0, 32, 16, 16))
        self.sprites['knife_clean'] = self._cut('clutter', (0, 16, 16, 16))
        self.sprites['knife_bloody'] = self._cut('clutter', (16, 16, 16, 16))
        self.sprites['note_paper'] = self._cut('clutter', (32, 0, 16, 16))
        self.sprites['mug_blue'] = self._cut('clutter', (20, 44, 16, 16))
        self.sprites['books_stack'] = self._cut('clutter', (36, 40, 16, 16))

        # --- COLLECTIBLE ITEMS ---
        key_surf = pygame.Surface((24 * SCALE, 24 * SCALE), pygame.SRCALPHA)
        kx, ky = 12 * SCALE, 12 * SCALE
        pygame.draw.circle(key_surf, (255, 230, 80), (kx, ky - 4 * SCALE), 6 * SCALE, 2 * SCALE)
        pygame.draw.rect(key_surf, (255, 215, 60), (kx - 2 * SCALE, ky - 2 * SCALE, 4 * SCALE, 12 * SCALE))
        pygame.draw.rect(key_surf, (255, 215, 60), (kx + 2 * SCALE, ky + 2 * SCALE, 4 * SCALE, 3 * SCALE))
        pygame.draw.rect(key_surf, (255, 215, 60), (kx + 2 * SCALE, ky + 7 * SCALE, 3 * SCALE, 2 * SCALE))
        self.sprites['key_item'] = key_surf

        bat_surf = pygame.Surface((18 * SCALE, 18 * SCALE), pygame.SRCALPHA)
        bw, bh = 14 * SCALE, 16 * SCALE
        pygame.draw.rect(bat_surf, (50, 190, 100), (2 * SCALE, 2 * SCALE, bw, bh))
        pygame.draw.rect(bat_surf, (230, 230, 230), (bw, 6 * SCALE, 3 * SCALE, 5 * SCALE))
        pygame.draw.rect(bat_surf, (20, 50, 25), (2 * SCALE, 2 * SCALE, bw, bh), 1 * SCALE)
        self.sprites['battery_item'] = bat_surf

        # --- COCKROACH ANIMATION FRAMES (192x32 sheet = 6 frames of 32x32) ---
        self.cockroach_frames = []
        try:
            roach_path = os.path.join(self.house2_dir, 'cockroach animation.png')
            if os.path.exists(roach_path):
                roach_img = pygame.image.load(roach_path)
                if pygame.display.get_surface() is not None:
                    roach_img = roach_img.convert_alpha()
                rw, rh = roach_img.get_size()
                frame_w = rh  # square frames (32x32)
                n_frames = max(1, rw // frame_w)
                for i in range(n_frames):
                    frame = roach_img.subsurface((i * frame_w, 0, frame_w, rh)).copy()
                    frame = pygame.transform.scale(frame, (frame_w * SCALE, rh * SCALE))
                    self.cockroach_frames.append(frame)
        except Exception as e:
            print(f"[AssetManager] Cockroach animation: {e}")
            self.cockroach_frames = []
