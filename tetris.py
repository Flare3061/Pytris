import pygame
import random
import sys
import copy
import math

# --- 定数 ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 800
GRID_SIZE = 30
FIELD_WIDTH, FIELD_HEIGHT = 10, 20
FIELD_OFFSET_X = (SCREEN_WIDTH // 2) - (FIELD_WIDTH * GRID_SIZE // 2)
FIELD_OFFSET_Y = (SCREEN_HEIGHT // 2) - (FIELD_HEIGHT * GRID_SIZE // 2)
BLACK, WHITE, GRAY, DARK_GRAY = (0, 0, 0), (255, 255, 255), (20, 20, 20), (80, 80, 80)
CYAN, BLUE, ORANGE, YELLOW = (0, 255, 255), (0, 0, 255), (255, 165, 0), (255, 255, 0)
GREEN, PURPLE, RED = (0, 255, 0), (128, 0, 128), (255, 0, 0)
GARBAGE_COLOR = (100, 100, 100)
GARBAGE_TIMER_COLOR = (150, 0, 0)
GARBAGE_TIMER_GHOST_COLOR = (180, 180, 180)
SHAPES = {
    'I': [(-1, 0), (0, 0), (1, 0), (2, 0)], 'J': [(-1, -1), (-1, 0), (0, 0), (1, 0)],
    'L': [(1, -1), (-1, 0), (0, 0), (1, 0)], 'O': [(0, 0), (1, 0), (0, 1), (1, 1)],
    'S': [(0, -1), (1, -1), (-1, 0), (0, 0)], 'T': [(0, -1), (-1, 0), (0, 0), (1, 0)],
    'Z': [(-1, -1), (0, -1), (0, 0), (1, 0)]
}
SHAPE_COLORS = {
    'I': CYAN, 'J': BLUE, 'L': ORANGE, 'O': YELLOW, 'S': GREEN, 'T': PURPLE, 'Z': RED
}
KICK_TABLES_JLSTZ = {
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0, +2), (-1, +2)], (1, 0): [(0, 0), (+1, 0), (+1, +1), (0, -2), (+1, -2)],
    (1, 2): [(0, 0), (+1, 0), (+1, +1), (0, -2), (+1, -2)], (2, 1): [(0, 0), (-1, 0), (-1, -1), (0, +2), (-1, +2)],
    (2, 3): [(0, 0), (+1, 0), (+1, -1), (0, +2), (+1, +2)], (3, 2): [(0, 0), (-1, 0), (-1, +1), (0, -2), (-1, -2)],
    (3, 0): [(0, 0), (-1, 0), (-1, +1), (0, -2), (-1, -2)], (0, 3): [(0, 0), (+1, 0), (+1, -1), (0, +2), (+1, +2)],
}
KICK_TABLES_I = {
    (0, 1): [(0, 0), (-2, 0), (+1, 0), (-2, +1), (+1, -2)], (1, 0): [(0, 0), (+2, 0), (-1, 0), (+2, -1), (-1, +2)],
    (1, 2): [(0, 0), (-1, 0), (+2, 0), (-1, -2), (+2, +1)], (2, 1): [(0, 0), (+1, 0), (-2, 0), (+1, +2), (-2, -1)],
    (2, 3): [(0, 0), (+2, 0), (-1, 0), (+2, -1), (-1, +2)], (3, 2): [(0, 0), (-2, 0), (+1, 0), (-2, +1), (+1, -2)],
    (3, 0): [(0, 0), (+1, 0), (-2, 0), (+1, +2), (-2, -1)], (0, 3): [(0, 0), (-1, 0), (+2, 0), (-1, -2), (+2, +1)],
}

# --- クラス定義 ---
class Tetromino:
    # (変更なし)
    def __init__(self, shape_name):
        self.shape_name = shape_name; self.shape = [list(pos) for pos in SHAPES[shape_name]]
        self.color = SHAPE_COLORS[shape_name]; self.x = FIELD_WIDTH // 2 - 1
        self.y = 19 if any(p[1] < 0 for p in self.shape) else 18; self.rotation = 0
    def get_blocks_positions(self): return [(self.x + x, self.y + y) for x, y in self.shape]
    def move(self, dx, dy, board):
        self.x += dx; self.y += dy
        if not board.is_valid_position(self): self.x -= dx; self.y -= dy; return False
        return True
    def rotate(self, board, clockwise=True):
        if self.shape_name == 'O': return True, (0, 0)
        original_shape = [list(pos) for pos in self.shape]; original_x, original_y, original_rotation = self.x, self.y, self.rotation
        new_rotation = (self.rotation + (1 if clockwise else -1) + 4) % 4
        for i in range(len(self.shape)): self.shape[i] = [-self.shape[i][1], self.shape[i][0]] if clockwise else [self.shape[i][1], -self.shape[i][0]]
        rotation_key = (original_rotation, new_rotation)
        kicks = KICK_TABLES_I.get(rotation_key, [(0, 0)]) if self.shape_name == 'I' else KICK_TABLES_JLSTZ.get(rotation_key, [(0, 0)])
        for dx, dy in kicks:
            if board.is_valid_position(self, offset_x=dx, offset_y=dy):
                self.x += dx; self.y += dy; self.rotation = new_rotation
                return True, (dx, dy)
        self.shape, self.x, self.y, self.rotation = original_shape, original_x, original_y, original_rotation
        return False, (0, 0)

class Board:
    def add_garbage(self, lines, hole_col):
        """ [改修] お邪魔ラインをせり上げる (グリッド操作版) """
        # ゲームオーバーチェック用 (シフト前にコピー)
        original_grid = [row[:] for row in self.grid]

        # 既存ブロックを上にlines分シフト
        for y in range(self.buffer_height, self.visible_height + self.buffer_height - lines):
            self.grid[y] = self.grid[y + lines]
        # 新しい空行を上に追加（シフトした分）
        for y in range(self.visible_height + self.buffer_height - lines, self.visible_height + self.buffer_height):
             self.grid[y] = [0] * FIELD_WIDTH # 空行で埋める (ここがお邪魔ラインになる)

        # お邪魔ライン生成 (8はお邪魔ブロックを示す値)
        garbage_line_data = [8] * FIELD_WIDTH
        garbage_line_data[hole_col] = 0 # 穴をあける

        # 下からlines分をお邪魔ラインで埋める
        for y in range(self.visible_height + self.buffer_height - lines, self.visible_height + self.buffer_height):
            self.grid[y] = list(garbage_line_data)

        # せり上げによってブロックが画面外（バッファ領域より上）にはみ出したかチェック
        for y in range(self.buffer_height): # yは 0 から 19 まで
            if any(original_grid[y]): # シフト前にバッファ領域 (0-19) にブロックがあった場合
                
                # [修正点] y-lines < 0 かどうかで判定する
                if y - lines < 0: 
                    # 元々 y (0<=y<20) の位置にあったブロックが、
                    # lines分シフトした結果、0未満の位置に押し出された
                    print(f"Game over due to topping out with garbage! Shift amount: {lines}")
                    return True # ゲームオーバー

        return False # ゲームオーバーではない

    def clear_all(self):
        self.grid = [[0 for _ in range(FIELD_WIDTH)] for _ in range(self.visible_height + self.buffer_height)]
    def draw(self, screen, is_visible=True):
        pygame.draw.rect(screen, DARK_GRAY, (FIELD_OFFSET_X - 5, FIELD_OFFSET_Y - 5, FIELD_WIDTH * GRID_SIZE + 10, self.visible_height * GRID_SIZE + 10), 5)
        pygame.draw.rect(screen, BLACK, (FIELD_OFFSET_X, FIELD_OFFSET_Y, FIELD_WIDTH * GRID_SIZE, self.visible_height * GRID_SIZE))
        if is_visible:
            for y in range(self.buffer_height, self.visible_height + self.buffer_height):
                for x in range(FIELD_WIDTH):
                    color_index = self.grid[y][x]
                    if color_index > 0:
                        color = GARBAGE_COLOR if color_index == 8 else self.colors[color_index - 1]
                        self.draw_block(screen, x, y - self.buffer_height, color)
    def __init__(self):
        self.buffer_height = 20; self.visible_height = 20
        self.grid = [[0 for _ in range(FIELD_WIDTH)] for _ in range(self.visible_height + self.buffer_height)]
        self.colors = list(SHAPE_COLORS.values())
    def draw_block(self, screen, x, y, color, alpha=255):
        if y < 0: return
        px, py = FIELD_OFFSET_X + x * GRID_SIZE, FIELD_OFFSET_Y + y * GRID_SIZE
        if alpha < 255: s = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA); s.fill((*color, alpha)); screen.blit(s, (px, py))
        else: pygame.draw.rect(screen, color, (px, py, GRID_SIZE, GRID_SIZE)); pygame.draw.rect(screen, DARK_GRAY, (px, py, GRID_SIZE, GRID_SIZE), 1)
    def is_valid_position(self, tetromino, offset_x=0, offset_y=0):
        for x, y in tetromino.get_blocks_positions():
            x_check, y_check = x + offset_x, y + offset_y
            if not (0 <= x_check < FIELD_WIDTH and y_check < self.visible_height + self.buffer_height): return False
            if y_check >= 0 and self.grid[y_check][x_check] > 0: return False
        return True
    def lock_tetromino(self, tetromino):
        game_over = True
        for x, y in tetromino.get_blocks_positions():
            if y >= self.buffer_height: game_over = False
            if y >= 0: self.grid[y][x] = list(SHAPE_COLORS.keys()).index(tetromino.shape_name) + 1
        return game_over
    def clear_lines(self):
        new_grid = []; lines_cleared = 0
        new_grid.extend(self.grid[:self.buffer_height])
        for y in range(self.buffer_height, self.visible_height + self.buffer_height):
            if not all(cell > 0 for cell in self.grid[y]): new_grid.append(self.grid[y])
            else: lines_cleared += 1
        for _ in range(lines_cleared): new_grid.insert(self.buffer_height, [0 for _ in range(FIELD_WIDTH)])
        self.grid = new_grid
        return lines_cleared
    def get_ghost_y(self, tetromino):
        ghost = copy.deepcopy(tetromino);
        while self.is_valid_position(ghost, offset_y=1): ghost.y += 1
        return ghost.y
    def check_t_spin(self, tetromino, last_kick_offset):
        if tetromino.shape_name != 'T': return "NONE"
        cx, cy = tetromino.x, tetromino.y
        corners = {'A': (cx - 1, cy - 1), 'B': (cx + 1, cy - 1), 'C': (cx - 1, cy + 1), 'D': (cx + 1, cy + 1)}
        filled_corners = sum(1 for pos in corners.values() if not (0 <= pos[0] < FIELD_WIDTH and pos[1] < self.visible_height + self.buffer_height) or (pos[1] >= 0 and self.grid[pos[1]][pos[0]] > 0))
        if filled_corners < 3: return "NONE"
        r = tetromino.rotation
        front_keys = ['A', 'B'] if r == 0 else ['B', 'D'] if r == 1 else ['C', 'D'] if r == 2 else ['A', 'C']
        back_keys = ['C', 'D'] if r == 0 else ['A', 'C'] if r == 1 else ['A', 'B'] if r == 2 else ['B', 'D']
        filled_front = sum(1 for key in front_keys if not (0 <= corners[key][0] < FIELD_WIDTH and corners[key][1] < self.visible_height + self.buffer_height) or (corners[key][1] >= 0 and self.grid[corners[key][1]][corners[key][0]] > 0))
        filled_back = sum(1 for key in back_keys if not (0 <= corners[key][0] < FIELD_WIDTH and corners[key][1] < self.visible_height + self.buffer_height) or (corners[key][1] >= 0 and self.grid[corners[key][1]][corners[key][0]] > 0))
        if filled_front == 2 and filled_back >= 1: return "FULL"
        elif filled_front == 1 and filled_back == 2: return "FULL" if abs(last_kick_offset[1]) == 2 else "MINI"
        return "NONE"
    def is_empty(self): return all(all(cell == 0 for cell in row) for row in self.grid)

class Game:
    def __init__(self, screen):
        self.lock_delay_duration = 500; self.lock_delay_reset_limit = 15
        self.DAS_DELAY = 160; self.ARR_SPEED = 20
        self.ARE_DELAY = 100; self.ARE_DELAY_LINE_CLEAR = 400
        self.NOTIFICATION_DURATION = 700
        self.screen = screen
        # [新規] Tetr.io準拠 (LEGACYモード用) パラメータ
        self.DAS_DELAY_LEGACY = 133
        self.ARR_SPEED_LEGACY = 0
        self.ARE_DELAY_LEGACY = 0
        self.ARE_DELAY_LINE_CLEAR_LEGACY = 0
        self.LOCK_DELAY_DURATION_LEGACY = 500 # (参考値: Tetr.ioデフォルトと同じ)
        
        # [新規] Tetr.io準拠 B2B (Surge) ボーナステーブル
        self.b2b_surge_bonuses = {0: 0, 2: 1, 4: 2, 9: 3, 25: 4, 68: 5, 186: 6, 505: 7, 1371: 8}

        self.state = 'MENU'
        # [改修] メニューオプションと状態
        self.game_mode = None
        # [改修] SPRINTを削除し、SCORE ATTACKを追加
        self.menu_options = ['MARATHON', 'SCORE ATTACK', 'APEX', 'GAUNTLET'] 
        self.selected_option = 0
        
        self.marathon_type = None # [新規] '150 LINES' or 'ENDLESS'
        self.marathon_options = ['150 LINES', 'ENDLESS'] # [新規]
        self.selected_marathon_type = 0 # [新規]

        # [新規] SCORE ATTACK サブメニュー
        self.score_attack_options = ['SPRINT', 'ULTRA']
        self.selected_score_attack_type = 0

        self.countdown_timer = 0; self.countdown_text = ""
        self.game_over = False; self.game_won = False
        
        self.gauntlet_difficulty = None; self.difficulty_options = ['EASY', 'NORMAL', 'HARD', 'EXTREME', 'THE SUN']
        self.selected_difficulty = 0; self.garbage_stock = 0; self.attack_timer = 0
        self.current_attack_interval = 0; self.current_attack_amount = 0
        self.progress_counter = 0; self.gauntlet_level = 1; self.gauntlet_max_level = 0
        self.gauntlet_legacy_mode = False # [新規] 裏モードフラグ

        # [新規] ULTRAモード用
        self.ultra_legacy_mode = False
        self.total_attack = 0

        # [改修] 既存のテーブルを legacy (裏モード用) にリネーム
        # [改修] EASYのテーブルを調整
        self.gauntlet_attack_tables_legacy = {
            'EASY': {1: (2, 24000), 2: (2, 21000), 3: (2, 18000), 4: (2, 15000), 5: (2, 13000), 6: (3, 17000), 7: (3, 14000), 8: (3, 12000), 9: (3, 10500), 10: (3, 9000)},
            'NORMAL': {1: (3, 12000), 2: (3, 11000), 3: (3, 10500), 4: (3, 9700), 5: (3, 9000), 6: (3, 8500), 7: (3, 8000), 8: (3, 7500), 9: (3, 7000), 10: (4, 8500),
                       11: (4, 8000), 12: (4, 7500), 13: (4, 7000), 14: (4, 6500), 15: (4, 6000)},
            'HARD': {1: (4, 6800), 2: (4, 6600), 3: (4, 6200), 4: (4, 6000), 5: (4, 5700), 6: (4, 5500), 7: (4, 5300), 8: (4, 5000), 9: (4, 4800), 10: (4, 4600), 
                     11: (4, 4400), 12: (5, 5300), 13: (5, 5000), 14: (5, 4800), 15: (5, 4600)},
            'EXTREME': {1: (5, 6500), 2: (5, 6400), 3: (5, 6200), 4: (5, 6000), 5: (5, 5800), 6: (5, 5500), 7: (5, 5350), 8: (5, 5200), 9: (5, 5000), 10: (5, 4800), 
                        11: (5, 4600), 12: (5, 4450), 13: (5, 4300), 14: (5, 4150), 15: (5, 4000), 16: (5, 3850), 17: (5, 3700), 18: (5, 3600), 19: (5, 3450), 20: (5, 3300)},
            'THE SUN': {1: (5, 4000), 2: (5, 3940), 3: (5, 3870), 4: (5, 3810), 5: (5, 3750), 6: (5, 3690), 7: (5, 3630), 8: (5, 3570), 9: (5, 3510), 10: (5, 3460), 
                        11: (5, 3400), 12: (5, 3350), 13: (5, 3290), 14: (5, 3240), 15: (5, 3190), 16: (5, 3140), 17: (5, 3090), 18: (5, 3040), 19: (5, 3000), 20: (5, 2940),
                        21: (5, 2890), 22: (5, 2850), 23: (5, 2800), 24: (5, 2760), 25: (5, 2710), 26: (5, 2670), 27: (5, 2620), 28: (5, 2580), 29: (5, 2540), 30: (5, 2500)}
        }
        
        # [新規] 新しいテーブル
        self.gauntlet_attack_tables = {
            'EASY': {1: (2, 24000), 2: (2, 21000), 3: (2, 19000), 4: (2, 17000), 5: (2, 15000), 6: (3, 20000), 7: (3, 17000), 8: (3, 15000), 9: (3, 13500), 10: (3, 12000)},
            'NORMAL': {1: (3, 18000), 2: (3, 16500), 3: (3, 15000), 4: (3, 14000), 5: (3, 13000), 6: (3, 12000), 7: (3, 11000), 8: (3, 10000), 9: (3, 9500), 10: (3, 9000),
                       11: (4, 11000), 12: (4, 10000), 13: (4, 9000), 14: (4, 8500), 15: (4, 8000)},
            'HARD': {1: (3, 7200), 2: (3, 7000), 3: (3, 6700), 4: (3, 6500), 5: (3, 6300), 6: (4, 8000), 7: (4, 7800), 8: (4, 7600), 9: (4, 7300), 10: (4, 7100), 
                     11: (4, 6900), 12: (5, 6600), 13: (5, 6400), 14: (5, 6200), 15: (5, 6000)},
            'EXTREME': {1: (4, 8000), 2: (4, 7700), 3: (4, 7400), 4: (4, 7200), 5: (4, 6900), 6: (4, 6700), 7: (4, 6400), 8: (4, 6200), 9: (4, 6000), 10: (4, 5750), 
                        11: (4, 5550), 12: (4, 5350), 13: (4, 5150), 14: (4, 5000), 15: (4, 4800), 16: (5, 5800), 17: (5, 5500), 18: (5, 5400), 19: (5, 5200), 20: (5, 5000)},
            'THE SUN': {1: (5, 6600), 2: (5, 6500), 3: (5, 6450), 4: (5, 6350), 5: (5, 6270), 6: (5, 6180), 7: (5, 6080), 8: (5, 6000), 9: (5, 5900), 10: (5, 5810), 
                        11: (5, 5720), 12: (5, 5640), 13: (5, 5550), 14: (5, 5470), 15: (5, 5390), 16: (5, 5300), 17: (5, 5220), 18: (5, 5150), 19: (5, 5070), 20: (5, 5000),
                        21: (5, 4920), 22: (5, 4840), 23: (5, 4770), 24: (5, 4700), 25: (5, 4620), 26: (5, 4560), 27: (5, 4500), 28: (5, 4420), 29: (5, 4350), 30: (5, 4300)}
        }
        
        self.garbage_gauge_height = FIELD_HEIGHT * GRID_SIZE

        self.board = Board(); self.current_tetromino = None
        self.next_tetrominos = []; self.hold_tetromino = None; self.notifications = []
        self.key_pressed = {"left": False, "right": False}; self.was_soft_dropping = False
        self.das_timer = {"left": 0, "right": 0}; self.arr_timer = {"left": 0, "right": 0}
        self.master_timer = 0; self.end_roll_timer = 65000; self.roll_prep_timer = 0
        self.last_kick_offset = (0, 0)
        self.master_fall_speed_table = [ (0, 1066.667), (30, 711.1111), (35, 533.3333), (40, 426.6667), (50, 355.5556), (60, 266.6667), (70, 133.3333), (80, 88.88889), (90, 66.66667), (100, 53.33333), (120, 44.44444), (140, 38.09524), (160, 33.33333), (170, 29.62963), (200, 1066.667), (220, 133.3333), (230, 66.66667), (233, 44.44444), (236, 33.33333), (239, 26.66667), (243, 22.22222), (247, 19.04762), (251, 16.66667), (300, 8.333333), (330, 5.555556), (360, 4.166667), (400, 3.333333), (420, 4.166667), (450, 5.555556), (500, 0.793651) ]
        self.master_timing_table = [ (0, 500, 1200, 500, 150), (500, 500, 850, 500, 150), (600, 500, 550, 500, 150), (700, 300, 500, 500, 150), (800, 235, 235, 500, 150), (900, 235, 235, 300, 150) ]
        self.font = pygame.font.SysFont("Meiryo", 24); self.font_large = pygame.font.SysFont("Meiryo", 36)
        self.font_action = pygame.font.SysFont("Meiryo", 32, bold=True); self.font_game_over = pygame.font.SysFont("Meiryo", 60)
        self.font_menu = pygame.font.SysFont("Meiryo", 48, bold=True)

    def reset_game_variables(self):
        self.board = Board()
        self.can_hold = True; self.game_over = False; self.game_won = False
        self.score = 0; self.level = 0 if self.game_mode == 'APEX' else 1
        self.lines_cleared_total = 0; self.fall_speed = 1000; self.fall_time = 0
        self.b2b_active = False; self.ren_counter = -1
        self.b2b_streak = 0 # [新規] Legacyモード (Tetr.io) のB2Bカウント
        self.notifications = []; self.hold_tetromino = None; self.current_tetromino = None
        self.initial_action = None; self.master_timer = 0; self.end_roll_timer = 65000; self.roll_prep_timer = 0
        self.garbage_stock = 0; self.attack_timer = 0; self.progress_counter = 0; self.gauntlet_level = 1
        self.gauntlet_alternate_mode = False # [新規] リスタート時にフラグをリセット
        self.total_attack = 0 # [新規] ULTRAモード用にリセット

        self.bag = []
        first_mino = random.choice(['I', 'J', 'L', 'T']); self.bag.append(first_mino)
        remaining = list(SHAPES.keys()); remaining.remove(first_mino)
        random.shuffle(remaining); self.bag.extend(remaining)
        self.fill_bag(); self.update_next_queue_before_spawn()
        
        # [改修] モード別初期化
        if self.game_mode == 'APEX': # [改修] MASTER -> APEX
            self.update_master_speeds()
        elif self.game_mode == 'GAUNTLET':
            # [改修] LEGACYモードかどうかでパラメータを切り替える
            if self.gauntlet_legacy_mode:
                # Tetr.io準拠 (LEGACY) 設定
                self.fall_speed = 1000
                self.ARE_DELAY = self.ARE_DELAY_LEGACY
                self.ARE_DELAY_LINE_CLEAR = self.ARE_DELAY_LINE_CLEAR_LEGACY
                self.lock_delay_duration = self.LOCK_DELAY_DURATION_LEGACY
                self.DAS_DELAY = self.DAS_DELAY_LEGACY
                self.ARR_SPEED = self.ARR_SPEED_LEGACY
            else:
                # 標準 (デフォルト) 設定
                self.fall_speed = 1000
                self.ARE_DELAY = 100
                self.ARE_DELAY_LINE_CLEAR = 400
                self.lock_delay_duration = 500
                self.DAS_DELAY = 160
                self.ARR_SPEED = 20
            self.level = 1 
            self.set_gauntlet_attack_params()
            if self.gauntlet_difficulty == 'EASY': self.gauntlet_max_level = 10
            elif self.gauntlet_difficulty == 'NORMAL': self.gauntlet_max_level = 15
            elif self.gauntlet_difficulty == 'HARD': self.gauntlet_max_level = 15
            elif self.gauntlet_difficulty == 'EXTREME' : self.gauntlet_max_level = 20
            else: self.gauntlet_max_level = 30
        
        # [新規] ULTRAモード初期化
        elif self.game_mode == 'ULTRA':
            if self.ultra_legacy_mode:
                # Tetr.io準拠 (LEGACY) 設定
                self.fall_speed = 1000
                self.ARE_DELAY = self.ARE_DELAY_LEGACY
                self.ARE_DELAY_LINE_CLEAR = self.ARE_DELAY_LINE_CLEAR_LEGACY
                self.lock_delay_duration = self.LOCK_DELAY_DURATION_LEGACY
                self.DAS_DELAY = self.DAS_DELAY_LEGACY
                self.ARR_SPEED = self.ARR_SPEED_LEGACY
            else:
                 # 標準 (デフォルト) 設定
                self.fall_speed = 1000
                self.ARE_DELAY = 100
                self.ARE_DELAY_LINE_CLEAR = 400
                self.lock_delay_duration = 500
                self.DAS_DELAY = 160
                self.ARR_SPEED = 20
            self.master_timer = 180000 # 3分 (ms)
            self.level = 1 # UI表示用 (固定)

        elif self.game_mode == 'SPRINT': # [新規] SPRINT初期化
            self.fall_speed = 1000
            self.ARE_DELAY = 100; self.ARE_DELAY_LINE_CLEAR = 400
            self.lock_delay_duration = 500; self.DAS_DELAY = 160; self.ARR_SPEED = 20
            self.level = 1 # UI表示用 (固定)
        elif self.game_mode == 'MARATHON': # [新規] MARATHON初期化 (タイプ別)
            if self.marathon_type == '150 LINES':
                self.marathon_level_goal = 15
            else: # ENDLESS
                self.marathon_level_goal = float('inf')
            self.fall_speed = 1000
            self.level = 1

    def set_gauntlet_attack_params(self):
        if self.game_mode != 'GAUNTLET' or self.gauntlet_difficulty is None: return
        
        # [改修] 裏モードフラグに応じて使用するテーブルセットを決定
        active_table_set = self.gauntlet_attack_tables
        if self.gauntlet_legacy_mode:
            print("Using LEGACY tables for Alternate Mode.") # デバッグ用
            active_table_set = self.gauntlet_attack_tables_legacy
        
        table = active_table_set[self.gauntlet_difficulty]
        level_key = min(self.level, max(table.keys()))
        self.current_attack_amount, self.current_attack_interval = table[level_key]
        self.attack_timer = self.current_attack_interval # タイマーリセット
    def add_notification(self, text, color):
        self.notifications.append({'text': text, 'timer': self.NOTIFICATION_DURATION, 'color': color})
    def update_next_queue_before_spawn(self):
        self.next_tetrominos = [Tetromino(self.bag[i]) for i in range(min(5, len(self.bag)))]
    def update_next_queue_after_spawn(self):
        self.next_tetrominos = [Tetromino(self.bag[i]) for i in range(min(5, len(self.bag)))]
    def fill_bag(self):
        new_bag = list(SHAPES.keys()); random.shuffle(new_bag); self.bag.extend(new_bag)
    def spawn_tetromino(self):
        while len(self.bag) < 7: self.fill_bag()
        shape_to_spawn = self.bag[0]
        if self.initial_action == "HOLD":
            if self.hold_tetromino is None:
                self.hold_tetromino = Tetromino(shape_to_spawn); self.bag.pop(0); shape_to_spawn = self.bag[0]
            else:
                held_shape, self.hold_tetromino = self.hold_tetromino.shape_name, Tetromino(shape_to_spawn); shape_to_spawn = held_shape
            self.can_hold = False
        self.bag.pop(0) # Holdしなかった場合もpop
        self.current_tetromino = Tetromino(shape_to_spawn); self.update_next_queue_after_spawn()
        if self.initial_action == "ROTATE_CW": self.current_tetromino.rotate(self.board, True)
        elif self.initial_action == "ROTATE_CCW": self.current_tetromino.rotate(self.board, False)
        elif self.initial_action == "ROTATE_180": self.current_tetromino.rotate(self.board, True); self.current_tetromino.rotate(self.board, True)
        if not self.board.is_valid_position(self.current_tetromino): self.game_over = True
        self.last_move_was_rotate = False; self.is_grounded = False; self.lock_delay_timer = 0; self.lock_delay_resets = 0
        if self.initial_action != "HOLD": self.can_hold = True
        self.initial_action = None
    def handle_das_arr(self, delta_time):
        for direction in ["left", "right"]:
            if self.key_pressed[direction]:
                self.das_timer[direction] += delta_time
                if self.das_timer[direction] > self.DAS_DELAY:
                    
                    dx = -1 if direction == "left" else 1
                    
                    if self.ARR_SPEED == 0:
                        # [新規] ARR=0 (即時移動) の処理
                        self.arr_timer[direction] = 0 # タイマーリセット
                        
                        # DAS完了フレームで壁まで移動
                        while self.state in ("PLAYING", "END_ROLL") and self.current_tetromino and self.current_tetromino.move(dx, 0, self.board):
                            self.last_move_was_rotate = False
                            self.reset_lock_delay_if_grounded()
                            
                    else:
                        # [既存] ARR > 0 (通常リピート) の処理
                        self.arr_timer[direction] += delta_time
                        while self.arr_timer[direction] > self.ARR_SPEED:
                            if self.state in ("PLAYING", "END_ROLL") and self.current_tetromino and self.current_tetromino.move(dx, 0, self.board):
                                self.last_move_was_rotate = False
                                self.reset_lock_delay_if_grounded()
                            self.arr_timer[direction] -= self.ARR_SPEED
            else:
                self.das_timer[direction] = 0
                self.arr_timer[direction] = 0
    def update_countdown(self, delta_time):
        self.countdown_timer -= delta_time
        if self.countdown_timer > 1000: self.countdown_text = "Ready?"
        elif self.countdown_timer > 0: self.countdown_text = "Go!"
        else:
            self.state = 'PLAYING'
            if self.game_mode == 'APEX': self.master_timer = 0
            self.spawn_tetromino()

    def update(self, delta_time, keys):
        if self.game_over or self.game_won: return
        self.handle_das_arr(delta_time)
        self.notifications = [n for n in self.notifications if n['timer'] > 0]
        for n in self.notifications: n['timer'] -= delta_time
        
        # [改修] MARATHON_SELECT, DIFFICULTY_SELECT, SCORE_ATTACK_SELECT を追加
        if self.state in ('MENU', 'MARATHON_SELECT', 'SCORE_ATTACK_SELECT', 'DIFFICULTY_SELECT'): return

        # [改修] タイマーを動かすモードを追加 (SPRINT, APEX, ULTRA)
        if self.game_mode in ['MARATHON', 'APEX', 'SPRINT', 'ULTRA'] and self.state not in ['MENU', 'COUNTDOWN']:
            if self.game_mode == 'APEX' and self.state in ['END_ROLL', 'ARE_END_ROLL']: # [改修] APEXのみ
                self.end_roll_timer -= delta_time
                if self.end_roll_timer <= 0: self.game_won = True; return
            elif self.state not in ['MENU', 'COUNTDOWN', 'ROLL_PREP']: 
                # [改修] ULTRAモードはタイマー減少
                if self.game_mode == 'ULTRA':
                    self.master_timer -= delta_time
                    if self.master_timer <= 0:
                        self.master_timer = 0
                        self.game_won = True; return
                else:
                    self.master_timer += delta_time # 共通タイマー (MARATHON, APEX, SPRINT)
        
        elif self.game_mode == 'GAUNTLET' and self.state not in ['MENU', 'COUNTDOWN']:
            # (GAUNTLETのタイマー処理 - 変更なし)
            self.attack_timer -= delta_time
            if self.attack_timer <= 0:
                self.garbage_stock += self.current_attack_amount
                
                # [改修] LEGACYモード対応
                active_table_set = self.gauntlet_attack_tables
                if self.gauntlet_legacy_mode:
                    active_table_set = self.gauntlet_attack_tables_legacy
                
                table = active_table_set[self.gauntlet_difficulty]
                level_key = min(self.level, max(table.keys()))
                self.current_attack_amount, self.current_attack_interval = table[level_key]
                self.attack_timer += self.current_attack_interval
        
        if self.state == 'COUNTDOWN': self.update_countdown(delta_time); return
        if self.state == 'ROLL_PREP':
            # (変更なし)
            self.roll_prep_timer -= delta_time
            if self.roll_prep_timer <= 0:
                self.state = 'END_ROLL'; self.ARE_DELAY = 235; self.ARE_DELAY_LINE_CLEAR = 235
                self.spawn_tetromino()
            return
        if self.state == "ARE":
            # (変更なし)
            self.are_timer -= delta_time
            if self.are_timer <= 0: self.state = "PLAYING"; self.spawn_tetromino()
            return
        if self.state == "ARE_END_ROLL":
            # (変更なし)
            self.are_timer -= delta_time
            if self.are_timer <= 0: self.state = "END_ROLL"; self.spawn_tetromino()
            return

        if self.current_tetromino is None: return
        is_soft_dropping_now = keys[pygame.K_DOWN] and self.state in ("PLAYING", "END_ROLL")
        if is_soft_dropping_now and not self.was_soft_dropping: self.fall_time = 0
        self.was_soft_dropping = is_soft_dropping_now
        
        self.fall_time += delta_time
        
        # [改修] LEGACYモードのソフトドロップ分岐 (GAUNTLET または ULTRA)
        legacy_soft_drop = (self.gauntlet_legacy_mode and self.game_mode == 'GAUNTLET') or \
                           (self.ultra_legacy_mode and self.game_mode == 'ULTRA')
        
        if legacy_soft_drop and is_soft_dropping_now:
            # [新規] LEGACYモードのソフトドロップ (即接地)
            ghost_y = self.board.get_ghost_y(self.current_tetromino)
            if self.current_tetromino.y < ghost_y:
                self.current_tetromino.y = ghost_y
                self.last_move_was_rotate = False
                # 接地したのでロックディレイタイマーを開始/リセット
                if not self.is_grounded: 
                    self.is_grounded = True
                    self.lock_delay_timer = 0
                self.reset_lock_delay_if_grounded()
            # この場合、通常の重力落下/SD落下はスキップ
            
        else:
            # [既存] 通常の落下処理 (重力または標準ソフトドロップ)
            current_speed = (self.fall_speed / 20) if is_soft_dropping_now else self.fall_speed
            if current_speed <= 0: current_speed = 0.001 
            drop_count = 0
            while self.fall_time >= current_speed: 
                drop_count += 1
                self.fall_time -= current_speed
            
            if drop_count > 0:
                for _ in range(drop_count):
                    if not self.board.is_valid_position(self.current_tetromino, offset_y=1): break
                    self.current_tetromino.move(0, 1, self.board)
                    # [改修] ULTRAモードでもSDスコアは加算しない
                    if is_soft_dropping_now and self.game_mode in ['GAUNTLET', 'SPRINT', 'ULTRA']: pass 
                    elif is_soft_dropping_now and self.game_mode != 'APEX': self.score += 1
                if self.board.is_valid_position(self.current_tetromino, offset_y=1): 
                    self.is_grounded = False
                    self.lock_delay_timer = 0
        
        is_currently_grounded = not self.board.is_valid_position(self.current_tetromino, offset_y=1)
        if is_currently_grounded:
            if not self.is_grounded: self.is_grounded = True; self.lock_delay_timer = 0
            self.lock_delay_timer += delta_time
            if self.lock_delay_timer >= self.lock_delay_duration: self.lock_down()
        else: self.is_grounded = False

    def reset_lock_delay_if_grounded(self):
        if self.is_grounded and self.lock_delay_resets < self.lock_delay_reset_limit:
            self.lock_delay_timer = 0; self.lock_delay_resets += 1
    
    def calculate_guideline_attack_power(self, lines, t_spin_type, is_b2b, ren_counter, is_pc):
        """ [改修] ガイドライン準拠の攻撃力計算 (is_difficultを返す) """
        if is_pc: return 10, True

        base_attack = 0
        is_difficult = False

        if t_spin_type == "FULL":
            if lines == 1: base_attack = 2; is_difficult = True
            elif lines == 2: base_attack = 4; is_difficult = True
            elif lines == 3: base_attack = 6; is_difficult = True
        elif t_spin_type == "MINI":
             if lines == 1: base_attack = 1; is_difficult = True
        elif lines == 1: base_attack = 0
        elif lines == 2: base_attack = 1
        elif lines == 3: base_attack = 2
        elif lines == 4: base_attack = 4; is_difficult = True
        
        b2b_bonus = 1 if (is_difficult and is_b2b) else 0

        ren_bonuses = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 5]
        ren_bonus = ren_bonuses[min(ren_counter, len(ren_bonuses)-1)] if ren_counter >= 0 else 0
        
        total_attack = base_attack + b2b_bonus + ren_bonus
        
        return total_attack, is_difficult
    
    def calculate_tetrio_attack_power(self, lines, t_spin_type, b2b_streak, ren_counter, is_pc):
        """ [新規] Tetr.io準拠の攻撃力計算 (Multiplier, Surge) """
        if is_pc: return 10, True # PCは 10固定, B2Bカウント対象

        base_attack = 0
        is_difficult = False

        if t_spin_type == "FULL":
            if lines == 1: base_attack = 2
            elif lines == 2: base_attack = 4
            elif lines == 3: base_attack = 6
            is_difficult = True # T-SpinはB2B対象
        elif t_spin_type == "MINI":
            if lines == 1: base_attack = 1 # Mini Single は 1 (Tetr.io)
            is_difficult = True
            # Mini Double は 0
        elif lines == 1: base_attack = 0 # Single
        elif lines == 2: base_attack = 1 # Double
        elif lines == 3: base_attack = 2 # Triple
        elif lines == 4: base_attack = 4; is_difficult = True # Tetris
        
        # B2B (Surge) ボーナス
        b2b_bonus = 0
        if is_difficult and b2b_streak > 0:
            b2b_bonus = self.calculate_b2b_surge_bonus(b2b_streak)
            # print(f"Surge active: Streak {b2b_streak}, Bonus {b2b_bonus}")

        total_base_attack = base_attack + b2b_bonus

        total_attack = 0
        
        # コンボ計算 (Multiplier)
        if total_base_attack > 0:
            # Base > 0 の場合: Base * (1 + 0.25 * REN)
            multiplier = 1.0 + (0.25 * ren_counter) if ren_counter >= 0 else 1.0
            total_attack = total_base_attack * multiplier
        elif ren_counter >= 1:
            # Base = 0 (Singleなど) かつ 2-REN (ren_counter=1) 以上の場合: ln(1 + 1.25 * REN)
            total_attack = math.log(1.0 + 1.25 * ren_counter)
        
        # Tetr.ioはデフォルトで切り捨て (Rounding Mode: DOWN)
        return math.floor(total_attack), is_difficult
    
    def calculate_b2b_surge_bonus(self, b2b_streak):
        """ [新規] Tetr.io準拠のB2Bサージボーナス計算 """
        bonus = 0
        for index, val in enumerate(self.b2b_surge_bonuses):
            if b2b_streak >= index:
                bonus = val
            else:
                break
        return bonus
    
    def lock_down(self):
        if self.current_tetromino is None or not (not self.board.is_valid_position(self.current_tetromino, offset_y=1)): return
        
        t_spin_type = self.board.check_t_spin(self.current_tetromino, self.last_kick_offset) if self.last_move_was_rotate else "NONE"
        if self.board.lock_tetromino(self.current_tetromino): self.game_over = True; return
        lines = self.board.clear_lines()
        is_pc = self.board.is_empty() if lines > 0 else False
        if lines > 0: self.ren_counter += 1
        else: self.ren_counter = -1
        
        # [改修] 攻撃力計算の分岐
        is_legacy = (self.gauntlet_legacy_mode and self.game_mode == 'GAUNTLET') or \
                    (self.ultra_legacy_mode and self.game_mode == 'ULTRA')
        
        attack_power = 0
        is_difficult_action = False
        
        if is_legacy:
            attack_power, is_difficult_action = self.calculate_tetrio_attack_power(
                lines, t_spin_type, self.b2b_streak, self.ren_counter, is_pc
            )
        else:
            attack_power, is_difficult_action = self.calculate_guideline_attack_power(
                lines, t_spin_type, self.b2b_active, self.ren_counter, is_pc
            )
        if attack_power > 0:
            self.add_notification(f"{attack_power}", GREEN)
        # [改修] Gauntletモードの処理を分離
        if self.game_mode == 'GAUNTLET':
            
            # 2. 相殺処理
            offset_amount = 0
            if attack_power > 0 and self.garbage_stock > 0:
                offset_amount = min(attack_power, self.garbage_stock)
                self.garbage_stock -= offset_amount
                attack_power -= offset_amount # 相殺後の余剰攻撃力

            # 3. 進捗を加算 (計算した攻撃力で加算)
            self.progress_counter += attack_power

            # 4. お邪魔のせり上げ (相殺しきれなかった場合、またはライン消去なしの場合)
            garbage_to_add = 0
            if attack_power == 0 and self.garbage_stock > 0 and offset_amount == 0: # 攻撃なし＆ストックあり
                garbage_to_add = self.garbage_stock
            # (攻撃力 > 0 で相殺しきれなかった場合 (attack_power > 0)、その攻撃力は進捗に回る)

            if garbage_to_add > 0:
                while garbage_to_add > 0:
                    hole = random.randint(0, FIELD_WIDTH - 1)
                    add_amount = random.randint(1, min(4, garbage_to_add)) # 1～4行ずつ、バラバラにせり上げる
                    if self.board.add_garbage(add_amount, hole):
                        self.game_over = True
                    garbage_to_add -= add_amount
                if self.game_over: return
                self.garbage_stock = 0

            # 5. レベル更新
            self.update_gauntlet_level()


        should_enter_roll_prep = self.add_score_and_update_level(lines, t_spin_type, is_pc, attack_power, is_difficult_action)

        if should_enter_roll_prep:
            self.state = 'ROLL_PREP'; self.board.clear_all(); self.roll_prep_timer = 5000
        elif self.state == 'END_ROLL':
            self.state = "ARE_END_ROLL"
        else:
            self.state = "ARE"
        
        self.are_timer = self.ARE_DELAY_LINE_CLEAR if lines > 0 else self.ARE_DELAY
        self.current_tetromino = None; self.initial_action = None; self.last_move_was_rotate = False

    def update_standard_level_and_speed(self):
        # [改修] MARATHONのタイプ別に勝利判定
        if self.game_mode == 'MARATHON' and self.marathon_type == '150 LINES' and self.lines_cleared_total >= 150:
             self.game_won = True; return
        
        # ENDLESS または 150 LINES 途中
        new_level = (self.lines_cleared_total // 10) + 1
        if new_level != self.level:
            self.level = new_level
            calc_speed = math.pow(0.8 - ((self.level - 1) * 0.007), self.level - 1) * 1000
            self.fall_speed = max(1, calc_speed)
            
    def update_master_speeds(self):
        current_fall_speed = self.master_fall_speed_table[0][1]
        for level_thresh, speed in self.master_fall_speed_table:
            if self.level >= level_thresh: current_fall_speed = speed
            else: break
        self.fall_speed = max(1, current_fall_speed)
        for level_thresh, are, line_are, lock_delay, das in self.master_timing_table:
            if self.level >= level_thresh:
                self.ARE_DELAY = are; self.ARE_DELAY_LINE_CLEAR = line_are
                self.lock_delay_duration = lock_delay; self.DAS_DELAY = das
            else: break
    def update_master_level(self, lines_cleared, t_spin_type):
        if self.state in ['END_ROLL', 'ARE_END_ROLL']: return False
        level_before_update = self.level
        spin_key = "FULL" if t_spin_type == "FULL" else "NONE"
        level_gains = {(0, "NONE"): 1, (1, "NONE"): 2, (2, "NONE"): 3, (3, "NONE"): 5, (4, "NONE"): 7, (1, "FULL"): 2, (2, "FULL"): 3, (3, "FULL"): 5}
        level_increase = level_gains.get((lines_cleared, spin_key), lines_cleared + 1)
        is_at_section_wall = ((self.level % 100) == 99 and self.level < 900) or self.level == 998
        if not (is_at_section_wall and lines_cleared == 0): self.level += level_increase
        self.level = min(999, self.level)
        if self.level != level_before_update: self.update_master_speeds()
        return self.level >= 999 and level_before_update < 999
    
    def update_gauntlet_level(self):
        if self.game_mode != 'GAUNTLET': return
        while self.progress_counter >= 10:
            self.progress_counter -= 10
            self.level += 1
            if self.level > self.gauntlet_max_level:
                self.game_won = True; return
            self.set_gauntlet_attack_params()

    def add_score_and_update_level(self, lines, t_spin_type, is_pc, attack_power, is_difficult):
        """ [改修] 攻撃力とB2B判定を引数で受け取る """
        
        should_enter_roll_prep = False
        
        # [改修] モード別処理
        if self.game_mode == 'APEX': # [改修] MASTER -> APEX
            should_enter_roll_prep = self.update_master_level(lines, t_spin_type)
        elif self.game_mode == 'GAUNTLET':
            pass
        elif self.game_mode == 'SPRINT': # [新規]
            self.lines_cleared_total += lines
            if self.lines_cleared_total >= 40:
                self.game_won = True
        
        # [新規] ULTRA (attack_powerはlock_downで計算済み)
        elif self.game_mode == 'ULTRA':
            self.total_attack += attack_power
            self.lines_cleared_total += lines

        # (通知関連)
        action_map = {
            ("FULL", 1): "T-Spin Single", ("FULL", 2): "T-Spin Double", ("FULL", 3): "T-Spin Triple",
            ("MINI", 1): "T-Spin Mini", ("MINI", 2): "T-Spin Mini Double",
            ("NONE", 4): "Tetris"
        }
        text_to_show = action_map.get((t_spin_type, lines))
        
        is_legacy = (self.gauntlet_legacy_mode and self.game_mode == 'GAUNTLET') or \
                    (self.ultra_legacy_mode and self.game_mode == 'ULTRA')
        
        is_b2b = False
        if is_legacy:
            is_b2b = is_difficult and self.b2b_streak > 0
            if is_b2b: self.add_notification(f"B2B x{self.b2b_streak}", ORANGE)
        else:
            is_b2b = is_difficult and self.b2b_active
            if is_b2b: self.add_notification("Back-to-Back", ORANGE)
            
        if text_to_show: self.add_notification(text_to_show, YELLOW)
        if self.ren_counter >= 1: self.add_notification(f"{self.ren_counter} REN", CYAN)
        if is_pc: self.add_notification("Perfect Clear", WHITE)
        
        # B2B / Streak 更新
        if is_difficult:
            self.b2b_active = True
            self.b2b_streak += 1
        elif lines > 0:
            self.b2b_active = False
            if is_legacy:
                self.b2b_streak = 0 # Legacy (Tetr.io) モードではライン消去でB2Bが切れる
        
        self.draw_notifications

        # [改修] MARATHON (ENDLESS含む) のみスコア計算
        if self.game_mode == 'MARATHON':
            # MARATHONモードではスコア計算のためにガイドライン攻撃力を再計算 (B2Bボーナスはスコア用)
            base_score_map = {
                ("FULL", 1): 800, ("FULL", 2): 1200, ("FULL", 3): 1600,
                ("MINI", 1): 200, ("MINI", 2): 400,
                ("NONE", 4): 800,
                ("NONE", 1): 100, ("NONE", 2): 300, ("NONE", 3): 500
            }
            base_score = base_score_map.get((t_spin_type, lines), 0)
            
            b2b_bonus = 1.5 if is_b2b else 1.0 # スコア計算時のB2Bボーナス
            ren_bonus = [0, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
            ren_score = ren_bonus[min(self.ren_counter, len(ren_bonus)-1)] * self.level if self.ren_counter > 0 else 0
            self.score += int(base_score * self.level * b2b_bonus) + ren_score
            if is_pc: self.score += {1: 800, 2: 1200, 3: 1800, 4: 3200}.get(lines, 0) * self.level
            
            self.lines_cleared_total += lines
            self.update_standard_level_and_speed()
            
        return should_enter_roll_prep
    
    def handle_input(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r: self.__init__(self.screen); return
        if self.game_over or self.game_won: return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT: self.key_pressed["left"] = True
            elif event.key == pygame.K_RIGHT: self.key_pressed["right"] = True
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT: self.key_pressed["left"] = False
            elif event.key == pygame.K_RIGHT: self.key_pressed["right"] = False
        if event.type == pygame.KEYDOWN:
            if self.state == 'MENU':
                if event.key == pygame.K_UP: self.selected_option = (self.selected_option - 1) % len(self.menu_options)
                elif event.key == pygame.K_DOWN: self.selected_option = (self.selected_option + 1) % len(self.menu_options)
                elif event.key == pygame.K_RETURN:
                    # [改修] モード選択分岐
                    self.game_mode = self.menu_options[self.selected_option]
                    if self.game_mode == 'GAUNTLET': 
                        self.state = 'DIFFICULTY_SELECT'
                    elif self.game_mode == 'MARATHON':
                        self.state = 'MARATHON_SELECT' # [新規]
                    # [新規] SCORE ATTACK サブメニューへ
                    elif self.game_mode == 'SCORE ATTACK':
                        self.state = 'SCORE_ATTACK_SELECT'
                    else: # APEX
                        self.reset_game_variables()
                        self.state = 'COUNTDOWN'
                        self.countdown_timer = 2000
            
            elif self.state == 'MARATHON_SELECT': # [新規] MARATHONサブメニュー
                 if event.key == pygame.K_UP: 
                     self.selected_marathon_type = (self.selected_marathon_type - 1) % len(self.marathon_options)
                 elif event.key == pygame.K_DOWN: 
                     self.selected_marathon_type = (self.selected_marathon_type + 1) % len(self.marathon_options)
                 elif event.key == pygame.K_RETURN:
                     self.marathon_type = self.marathon_options[self.selected_marathon_type]
                     self.reset_game_variables()
                     self.state = 'COUNTDOWN'
                     self.countdown_timer = 2000
                 elif event.key == pygame.K_ESCAPE: 
                     self.state = 'MENU'

            # [新規] SCORE ATTACK サブメニュー
            elif self.state == 'SCORE_ATTACK_SELECT':
                 if event.key == pygame.K_UP: 
                     self.selected_score_attack_type = (self.selected_score_attack_type - 1) % len(self.score_attack_options)
                 elif event.key == pygame.K_DOWN: 
                     self.selected_score_attack_type = (self.selected_score_attack_type + 1) % len(self.score_attack_options)
                 elif event.key == pygame.K_RETURN:
                     # 選択されたモード (SPRINT or ULTRA) を game_mode に設定
                     self.game_mode = self.score_attack_options[self.selected_score_attack_type]
                     
                     # [新規] 裏モード判定 (ULTRAのみ)
                     mods = pygame.key.get_mods()
                     is_alternate = (mods & pygame.KMOD_SHIFT) or (mods & pygame.KMOD_CTRL)
                     
                     if self.game_mode == 'ULTRA':
                         self.ultra_legacy_mode = is_alternate
                     else:
                         self.ultra_legacy_mode = False # SPRINTでは未使用

                     self.reset_game_variables()
                     self.state = 'COUNTDOWN'
                     self.countdown_timer = 2000
                 elif event.key == pygame.K_ESCAPE: 
                     self.state = 'MENU'

            elif self.state == 'DIFFICULTY_SELECT':
                if event.key == pygame.K_UP: self.selected_difficulty = (self.selected_difficulty - 1) % len(self.difficulty_options)
                elif event.key == pygame.K_DOWN: self.selected_difficulty = (self.selected_difficulty + 1) % len(self.difficulty_options)
                elif event.key == pygame.K_RETURN:
                    # [改修] 裏モード判定 (Shift or Ctrl + Enter)
                    selected_difficulty_name = self.difficulty_options[self.selected_difficulty]
                    mods = pygame.key.get_mods()
                    is_alternate = (mods & pygame.KMOD_SHIFT) or (mods & pygame.KMOD_CTRL)
                    
                    if is_alternate:
                        self.gauntlet_legacy_mode = True
                    else:
                        self.gauntlet_legacy_mode = False
                        
                    self.gauntlet_difficulty = selected_difficulty_name
                    self.reset_game_variables(); self.state = 'COUNTDOWN'; self.countdown_timer = 2000
                elif event.key == pygame.K_ESCAPE: self.state = 'MENU'
            elif self.state in ("ARE", "ARE_END_ROLL", "COUNTDOWN", "END_ROLL"):
                if event.key in (pygame.K_UP, pygame.K_x):
                    if self.initial_action == "ROTATE_CW": self.initial_action = "ROTATE_180"
                    else: self.initial_action = "ROTATE_CW"
                elif event.key in (pygame.K_z, pygame.K_LCTRL):
                    if self.initial_action == "ROTATE_CCW": self.initial_action = "ROTATE_180"
                    else: self.initial_action = "ROTATE_CCW"
                elif event.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT): self.initial_action = "HOLD"
            elif self.state == "PLAYING" and self.current_tetromino:
                if event.key == pygame.K_LEFT: self.handle_single_move(-1)
                elif event.key == pygame.K_RIGHT: self.handle_single_move(1)
                elif event.key in (pygame.K_UP, pygame.K_x): self.handle_rotation(True)
                elif event.key in (pygame.K_z, pygame.K_LCTRL): self.handle_rotation(False)
                elif event.key == pygame.K_SPACE: self.hard_drop()
                elif event.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT): self.hold()
    
    def handle_single_move(self, dx):
        if self.current_tetromino.move(dx, 0, self.board): self.last_move_was_rotate = False; self.reset_lock_delay_if_grounded()
    def handle_rotation(self, clockwise):
        success, kick_offset = self.current_tetromino.rotate(self.board, clockwise)
        if success: self.last_move_was_rotate = True; self.last_kick_offset = kick_offset; self.reset_lock_delay_if_grounded()
    def hard_drop(self):
        if not self.current_tetromino: return
        drop_dist = self.board.get_ghost_y(self.current_tetromino) - self.current_tetromino.y
        # [改修] ULTRAモードでもHDスコアは加算しない
        if self.game_mode != 'APEX' and self.game_mode != 'GAUNTLET' and self.game_mode != 'ULTRA': 
            self.score += drop_dist * 2
        self.current_tetromino.y += drop_dist; self.lock_down()
    def hold(self):
        if not self.can_hold: return
        self.can_hold = False
        if self.hold_tetromino is None:
            self.hold_tetromino = Tetromino(self.current_tetromino.shape_name)
            self.spawn_tetromino()
        else:
            held_shape, self.hold_tetromino = self.hold_tetromino.shape_name, Tetromino(self.current_tetromino.shape_name)
            self.current_tetromino = Tetromino(held_shape);
            if not self.board.is_valid_position(self.current_tetromino): self.game_over = True
        self.last_move_was_rotate = False

    def draw(self):
        self.screen.fill(GRAY)
        # [改修] 描画ステート追加
        if self.state == 'MENU': self.draw_menu()
        elif self.state == 'MARATHON_SELECT': self.draw_marathon_menu() # [新規]
        # [新規] SCORE ATTACK サブメニュー描画
        elif self.state == 'SCORE_ATTACK_SELECT': self.draw_score_attack_menu()
        elif self.state == 'DIFFICULTY_SELECT': self.draw_difficulty_menu()
        else:
            is_board_visible = self.state not in ['END_ROLL', 'ARE_END_ROLL']
            self.board.draw(self.screen, is_board_visible)
            if self.game_won: self.draw_game_won()
            elif self.game_over: self.draw_game_over()
            elif self.state in ("PLAYING", "END_ROLL") and self.current_tetromino:
                ghost_y = self.board.get_ghost_y(self.current_tetromino)
                current_blocks = self.current_tetromino.get_blocks_positions()
                for x, y in current_blocks:
                    y_ghost = y - self.current_tetromino.y + ghost_y
                    self.board.draw_block(self.screen, x, y_ghost - self.board.buffer_height, self.current_tetromino.color, alpha=100)
                for x, y in current_blocks:
                    self.board.draw_block(self.screen, x, y - self.board.buffer_height, self.current_tetromino.color)
            self.draw_ui()
            if self.state == 'COUNTDOWN': self.draw_countdown()
        pygame.display.flip()

    def draw_ui(self):
        ui_left_x = FIELD_OFFSET_X - 220; ui_y_start = FIELD_OFFSET_Y
        hold_text = self.font_large.render('HOLD', True, WHITE); self.screen.blit(hold_text, (ui_left_x, ui_y_start))
        if self.hold_tetromino: self.draw_preview_mino(self.hold_tetromino, ui_left_x + 30, ui_y_start + 70, self.can_hold)
        
        if self.game_mode == 'GAUNTLET':
            self.draw_gauntlet_gauge(FIELD_OFFSET_X - 25, FIELD_OFFSET_Y)
            self.draw_notifications(ui_left_x, ui_y_start + 150)
        else:
            self.draw_notifications(ui_left_x, ui_y_start + 150)
        
        ui_right_x = FIELD_OFFSET_X + FIELD_WIDTH * GRID_SIZE + 40
        next_text = self.font_large.render('NEXT', True, WHITE); self.screen.blit(next_text, (ui_right_x, ui_y_start))
        for i, mino in enumerate(self.next_tetrominos):
            self.draw_preview_mino(mino, ui_right_x + 30, ui_y_start + 70 + i * 80)

        # [改修] UI描画分岐
        if self.game_mode == 'APEX': # [改修] MASTER -> APEX
             self.draw_master_ui(ui_left_x, ui_right_x)
        elif self.game_mode == 'GAUNTLET': 
            self.draw_gauntlet_ui(ui_left_x, ui_right_x)
        elif self.game_mode == 'SPRINT': # [新規]
            self.draw_sprint_ui(ui_left_x, ui_right_x)
        # [新規] ULTRA
        elif self.game_mode == 'ULTRA':
            self.draw_ultra_ui(ui_left_x, ui_right_x)
        elif self.game_mode == 'MARATHON': # [改修]
            self.draw_standard_ui(ui_left_x, ui_right_x)
    
    def draw_standard_ui(self, ui_left_x, ui_right_x):
        stats_y_base = FIELD_OFFSET_Y + 70 + 5 * 80 + 20
        score_text = self.font_large.render('SCORE', True, WHITE); self.screen.blit(score_text, (ui_left_x, stats_y_base))
        score_val = self.font.render(f'{self.score}', True, WHITE); self.screen.blit(score_val, (ui_left_x, stats_y_base + 40))
        
        # [改修] MARATHONタイプ別にゴール表示
        lines_goal = (self.level -1) * 10 + 10
        level_text = self.font_large.render(f"LEVEL {self.level}", True, WHITE); self.screen.blit(level_text, (ui_right_x, stats_y_base + 80))
        lines_progress = self.font.render(f"LINES: {self.lines_cleared_total} / {lines_goal}", True, WHITE)
        self.screen.blit(lines_progress, (ui_right_x, stats_y_base + 120))

        seconds = self.master_timer / 1000; minutes = int(seconds // 60); seconds %= 60
        timer_text = f"{minutes:02}:{seconds:05.2f}"; timer_color = WHITE
        time_label = self.font_large.render('TIME', True, WHITE); self.screen.blit(time_label, (ui_right_x, stats_y_base))
        time_val = self.font_large.render(timer_text, True, timer_color); self.screen.blit(time_val, (ui_right_x, stats_y_base + 40))
    
    def draw_master_ui(self, ui_left_x, ui_right_x):
        if self.state in ['END_ROLL', 'ARE_END_ROLL']:
            seconds = max(0, self.end_roll_timer / 1000); timer_text = f"{seconds:.2f}"; timer_color = RED
        else:
            seconds = self.master_timer / 1000; minutes = int(seconds // 60); seconds %= 60
            timer_text = f"{minutes:02}:{seconds:05.2f}"; timer_color = WHITE
        time_label = self.font_large.render('TIME', True, WHITE); self.screen.blit(time_label, (ui_right_x, 550))
        time_val = self.font_large.render(timer_text, True, timer_color); self.screen.blit(time_val, (ui_right_x, 590))
        section_map = {0: 100, 100: 200, 200: 300, 300: 400, 400: 500, 500: 600, 600: 700, 700: 800, 800: 900, 900: 999}
        current_section_start = (self.level // 100) * 100 if self.level < 900 else 900
        level_goal = section_map.get(current_section_start, 999)
        level_text = self.font_large.render(f"LEVEL", True, WHITE); self.screen.blit(level_text, (ui_left_x, 550))
        level_progress = self.font.render(f"{self.level} / {level_goal}", True, WHITE); self.screen.blit(level_progress, (ui_left_x, 590))
    
    def draw_gauntlet_ui(self, ui_left_x, ui_right_x):
        # 進捗表示 (右下)
        progress_text = self.font_large.render(f"PROGRESS", True, WHITE)
        self.screen.blit(progress_text, (ui_right_x, 550))
        progress_val = self.font.render(f"{self.progress_counter} / 10", True, WHITE)
        self.screen.blit(progress_val, (ui_right_x, 590))
        level_text = self.font_large.render(f"LEVEL {self.level}", True, WHITE)
        self.screen.blit(level_text, (ui_right_x, 630))

    def draw_sprint_ui(self, ui_left_x, ui_right_x):
        """ [新規] SPRINTモードのUIを描画 """
        stats_y_base = FIELD_OFFSET_Y + 70 + 5 * 80 + 20

        # TIME (右側)
        seconds = self.master_timer / 1000
        minutes = int(seconds // 60)
        seconds %= 60
        timer_text = f"{minutes:02}:{seconds:05.2f}"
        time_label = self.font_large.render('TIME', True, WHITE)
        self.screen.blit(time_label, (ui_right_x, stats_y_base))
        time_val = self.font_large.render(timer_text, True, WHITE)
        self.screen.blit(time_val, (ui_right_x, stats_y_base + 40))

        # LINES (左側)
        lines_text = self.font_large.render(f"LINES", True, WHITE)
        self.screen.blit(lines_text, (ui_left_x, stats_y_base))
        lines_progress = self.font.render(f"{self.lines_cleared_total} / 40", True, WHITE)
        self.screen.blit(lines_progress, (ui_left_x, stats_y_base + 40))
    
    def draw_ultra_ui(self, ui_left_x, ui_right_x):
        """ [新規] ULTRAモードのUIを描画 """
        stats_y_base = FIELD_OFFSET_Y + 70 + 5 * 80 + 20

        # TIME (右側)
        seconds = max(0, self.master_timer / 1000)
        minutes = int(seconds // 60)
        seconds %= 60
        timer_text = f"{minutes:02}:{seconds:05.2f}"
        # ラスト10秒でタイマーを赤くする
        timer_color = RED if self.master_timer < 10000 else WHITE
        
        time_label = self.font_large.render('TIME', True, WHITE)
        self.screen.blit(time_label, (ui_right_x, stats_y_base))
        time_val = self.font_large.render(timer_text, True, timer_color)
        self.screen.blit(time_val, (ui_right_x, stats_y_base + 40))

        # LINES (左側)
        lines_text = self.font_large.render(f"LINES", True, WHITE)
        self.screen.blit(lines_text, (ui_left_x, stats_y_base))
        lines_val = self.font.render(f"{self.lines_cleared_total}", True, WHITE)
        self.screen.blit(lines_val, (ui_left_x, stats_y_base + 40))

        # ATTACK (左側、LINESの下)
        attack_text = self.font_large.render(f"ATTACK", True, WHITE)
        self.screen.blit(attack_text, (ui_left_x, stats_y_base + 80))
        attack_val = self.font.render(f"{self.total_attack}", True, WHITE)
        self.screen.blit(attack_val, (ui_left_x, stats_y_base + 120))


    def draw_gauntlet_gauge(self, gauge_x, gauge_y):
        """ [新規] Gauntletのお邪魔ゲージとタイマーを描画 """
        gauge_width = 20
        max_gauge_height = FIELD_HEIGHT * GRID_SIZE # ゲージの最大高 (ピクセル)
        line_height_px = GRID_SIZE # ゲージ1段分の高さ

        # 背景
        pygame.draw.rect(self.screen, DARK_GRAY, (gauge_x, gauge_y, gauge_width, max_gauge_height))
        
        # ストックゲージ (濃い色)
        stock_height = min(self.garbage_stock * line_height_px, max_gauge_height)
        stock_rect = pygame.Rect(gauge_x, gauge_y + max_gauge_height - stock_height, gauge_width, stock_height)
        pygame.draw.rect(self.screen, RED, stock_rect)

        # 充填タイマーゲージ (薄い色)
        if self.current_attack_interval > 0 and self.attack_timer > 0:
            # タイマーの進行度 (0.0 -> 1.0)
            timer_ratio = 1.0 - (self.attack_timer / self.current_attack_interval)
            # 次の攻撃量に応じたタイマーゲージの高さ
            attack_amount_height = self.current_attack_amount * line_height_px
            # タイマー進行度に応じた現在のタイマーゲージの高さ
            timer_height = attack_amount_height * timer_ratio
            # タイマーゲージがストックゲージと重ならないように、かつ最大高さを超えないように調整
            timer_height = min(timer_height, max_gauge_height - stock_height)
            
            
            timer_rect = pygame.Rect(gauge_x, gauge_y + max_gauge_height - stock_height - attack_amount_height, gauge_width, attack_amount_height)
            pygame.draw.rect(self.screen, GARBAGE_TIMER_GHOST_COLOR, timer_rect)
            
            timer_rect = pygame.Rect(gauge_x, gauge_y + max_gauge_height - stock_height - timer_height, gauge_width, timer_height)
            pygame.draw.rect(self.screen, GARBAGE_TIMER_COLOR, timer_rect)
            

        # ゲージ枠線
        pygame.draw.rect(self.screen, WHITE, (gauge_x, gauge_y, gauge_width, max_gauge_height), 1)

    def draw_preview_mino(self, tetromino, px, py, is_enabled=True):
        size = GRID_SIZE * 0.8; shape = SHAPES[tetromino.shape_name]
        color = tetromino.color if is_enabled else DARK_GRAY
        ox = size / 2 if tetromino.shape_name == 'O' else -size / 2 if tetromino.shape_name == 'I' else 0
        oy = -size / 2 if tetromino.shape_name == 'I' else 0
        for x, y in shape: pygame.draw.rect(self.screen, color, (px + (x * size) + ox, py + (y * size) + oy, size - 1, size - 1))
    def draw_notifications(self, x_base, y_base):
        y_offset = y_base
        for n in self.notifications:
            alpha = max(0, min(255, int(255 * (n['timer'] / (self.NOTIFICATION_DURATION / 2)))))
            text_surface = self.font_action.render(n['text'], True, n['color']); text_surface.set_alpha(alpha)
            text_rect = text_surface.get_rect(midtop=(x_base + 100, y_offset)); self.screen.blit(text_surface, text_rect)
            y_offset += text_rect.height
    def draw_menu(self):
        title = self.font_game_over.render("TETRIS", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 150)))
        for i, option in enumerate(self.menu_options):
            color = YELLOW if i == self.selected_option else WHITE
            text = self.font_menu.render(option, True, color)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50 + i * 70)))
        info = self.font.render("UP/DOWN to select, ENTER to start", True, WHITE)
        self.screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 240)))
    
    def draw_marathon_menu(self):
        """ [新規] MARATHONタイプ選択画面 """
        title = self.font_menu.render("Select Type", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 150)))
        for i, option in enumerate(self.marathon_options):
            color = YELLOW if i == self.selected_marathon_type else WHITE
            text = self.font_large.render(option, True, color)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50 + i * 60)))
        info = self.font.render("UP/DOWN to select, ENTER to start, ESC to back", True, WHITE)
        self.screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 300)))
    
    def draw_score_attack_menu(self):
        """ [新規] SCORE ATTACKタイプ選択画面 """
        title = self.font_menu.render("Score Attack", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 150)))
        for i, option in enumerate(self.score_attack_options):
            color = YELLOW if i == self.selected_score_attack_type else WHITE
            text = self.font_large.render(option, True, color)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50 + i * 60)))
        info = self.font.render("UP/DOWN to select, ENTER to start, ESC to back", True, WHITE)
        self.screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 300)))

    def draw_difficulty_menu(self):
        title = self.font_menu.render("Select Difficulty", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 150)))
        for i, option in enumerate(self.difficulty_options):
            color = YELLOW if i == self.selected_difficulty else WHITE
            text = self.font_large.render(option, True, color)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50 + i * 60)))
        info = self.font.render("UP/DOWN to select, ENTER to start, ESC to back", True, WHITE)
        self.screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 300)))

    def draw_countdown(self):
        s = pygame.Surface((FIELD_WIDTH*GRID_SIZE, 100), pygame.SRCALPHA); s.fill((0, 0, 0, 128))
        self.screen.blit(s, (FIELD_OFFSET_X, SCREEN_HEIGHT//2 - 50))
        text = self.font_game_over.render(self.countdown_text, True, WHITE)
        self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
    def draw_game_over(self):
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA); s.fill((0, 0, 0, 180)); self.screen.blit(s, (0, 0))
        text = self.font_game_over.render('GAME OVER', True, RED); self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)))
        text_r = self.font.render('Press R to return to the menu', True, WHITE); self.screen.blit(text_r, text_r.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)))
    def draw_game_won(self):
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA); s.fill((0, 0, 0, 180)); self.screen.blit(s, (0, 0))
        # [改修] SPRINTとULTRAの勝利メッセージを変更
        if self.game_mode == 'SPRINT':
            text = self.font_game_over.render('FINISH!', True, CYAN)
        elif self.game_mode == 'ULTRA':
            text = self.font_game_over.render('TIME UP!', True, CYAN)
        else:
            text = self.font_game_over.render('YOU WIN!', True, YELLOW)
        self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)))
        text_r = self.font.render('Press R to return to the menu', True, WHITE); self.screen.blit(text_r, text_r.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)))

# --- メイン関数 ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption('Modern Tetris')
    clock = pygame.time.Clock()
    game = Game(screen)
    running = True
    while running:
        delta_time = clock.tick(60)
        keys = pygame.key.get_pressed()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            game.handle_input(event)
        game.update(delta_time, keys)
        game.draw()
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()