"""Bucky, the pnch mascot: a side-view beaver in boxing gloves who punches down a tree,
walks on, and punches the next one. Drawn in shading characters like the Ghostty ghost."""
from __future__ import annotations

from rich.text import Text

from . import ui

W, H = 46, 10          # canvas size; row 9 is the ground
GROUND = H - 1
BX = 1                 # Bucky's x position (he walks in place; the world scrolls)

# ── Bucky (facing right) ─────────────────────────────────────────────────────
# o outline  b fur  l belly  e eye  n nose  t teeth  g glove  w arm  k tail  f foot
_BODY_TOP = [
    "      oo          ",
    "    obbbbo        ",
    "   obbbbbeoo      ",
    "   obbbbbbbbbn    ",
]
GUARD = _BODY_TOP + [
    " kk obbbbbbbtt ggg ",
    "kkkkobbllbbbbwwggg ",
    " kk  obllllbo  ggg ",
    "      ff  ff       ",
]
WINDUP = _BODY_TOP + [
    " kk obbbbbbbtt     ",
    "kkkkobbllbbbggg    ",
    " kk  obllllbggg    ",
    "      ff  ff ggg   ",
]
WINDUP[-1] = "      ff  ff       "
WINDUP[-2] = " kk  obllllbggg    "
PUNCH = _BODY_TOP + [
    " kk obbbbbbbtt         ",
    "kkkkobbllbbbbwwwwwwggg ",
    " kk  obllllbo      ggg ",
    "      ff  ff       ggg ",
]
PUNCH[-1] = "      ff  ff        "
PUNCH[-2] = " kk  obllllbo     ggg "
PUNCH[-3] = "kkkkobbllbbbbwwwwwggg "
PUNCH[-4] = " kk obbbbbbbtt    ggg "
CHEER = [
    "               ggg",
    "      oo       ggg",
    "    obbbbo    w   ",
    "   obbbbbeoo w    ",
    "   obbbbbbbbbn    ",
    " kk obbbbbbbttw   ",
    "kkkkobbllbbbbw    ",
    " kk  obllllbo     ",
    "      ff  ff      ",
]
WALK_A = GUARD[:-1] + ["     ff    ff      "]
WALK_B = GUARD[:-1] + ["       ff ff       "]

# ── the tree ─────────────────────────────────────────────────────────────────
# c leaves  r trunk  h log (fallen trunk)  s stump top
TREE = [
    "   cccc     ",
    " cccccccc   ",
    "cccccccccc  ",
    "ccccccccccc ",
    " ccccccccc  ",
    "    rrr     ",
    "    rrr     ",
    "    rrr     ",
    "   rrrrr    ",
]
SHAKE = [" " + r[:-1] for r in TREE[:5]] + TREE[5:]
LEAN1 = ["  " + r[:-2] for r in TREE[:5]] + [" " + TREE[5][:-1], " " + TREE[6][:-1]] + TREE[7:]
LEAN2 = [
    "                ",
    "          cccc  ",
    "        cccccccc",
    "       ccccccccc",
    "      cccccccc  ",
    "      rrcccc    ",
    "     rrr        ",
    "    rrr         ",
    "   rrrrr        ",
]
FALLEN = [
    "                        ",
    "                        ",
    "                        ",
    "                        ",
    "                        ",
    "                  cccc  ",
    "                ccccccc ",
    "    sss     cccccccccccc",
    "   rrrrrhhhhhhhhhcccccc ",
]
TREE_HIT_X = 4  # trunk's left column inside the tree drawing

# ── timeline (one tick ≈ 0.12s) ──────────────────────────────────────────────
REACH = BX + len(PUNCH[5].rstrip())         # where the punching glove ends
TX = REACH - TREE_HIT_X                      # tree x while being punched
APPROACH = W + 12 - TX                       # walking ticks (tree enters from off-screen)

_PUNCH = [("windup", 2), ("punch", 2), ("guard", 2)]
_FALL = [("lean1", 2), ("lean2", 2), ("dust", 2), ("fallen", 3), ("cheer", 5)]
FIGHT = [step for _ in range(3) for step in _PUNCH] + _FALL
FIGHT_LEN = sum(n for _, n in FIGHT)
CYCLE = FIGHT_LEN + APPROACH


def _state(t: int):
    """-> (bucky pose, tree pose, tree x, stump x or None, walked distance, effect, effect tick)"""
    t %= CYCLE
    if t < FIGHT_LEN:
        acc, punches = 0, 0
        for name, n in FIGHT:
            if t < acc + n:
                k = t - acc
                break
            acc += n
            punches += name == "punch"
        bucky = {"windup": WINDUP, "punch": PUNCH, "guard": GUARD, "cheer": CHEER}.get(name, GUARD)
        tree = {"lean1": LEAN1, "lean2": LEAN2, "dust": FALLEN, "fallen": FALLEN, "cheer": FALLEN}.get(name, TREE)
        if name == "punch":
            tree = SHAKE if k % 2 == 0 else TREE
        effect = name if name in ("punch", "dust") else None
        return bucky, tree, TX, None, 0, effect, k
    a = t - FIGHT_LEN                       # walking: the world slides left
    bucky = WALK_A if (a // 2) % 2 == 0 else WALK_B
    return bucky, TREE, TX + APPROACH - a, TX - a, a, None, 0


# ── drawing ──────────────────────────────────────────────────────────────────
_OUTLINE = "+=xo*·o=+"
_FUR = "$$$@$$%$$$@$$"
C = {
    "fur_hi": "#d9a066", "fur_lo": "#8f5a33", "belly": "#e8c49a", "nose": "#4a2c1a", "eye": "#fafafa",
    "teeth": "#fafafa", "glove": "#ef4e5c", "glove_hi": "#ff8a94", "arm": "#b97a45", "tail": "#6b4428",
    "foot": "#5a3a22", "leaf": ["#a6e3a1", "#7fc77f", "#5ea566", "#4e8f52"], "trunk": "#8b5a2b",
    "trunk_hi": "#a87444", "spark": "#f9e2af", "dust": "#9a8c7a", "ground": "#585b70",
}
_GROUND = "_.,_  _.  ,_ ._ _,  ._  _ ,_.  _"


def _blit(canvas, art, x0, y0, painter, t):
    for dy, row in enumerate(art):
        y = y0 + dy
        if not 0 <= y < H:
            continue
        for dx, m in enumerate(row):
            x = x0 + dx
            if m != " " and 0 <= x < W:
                canvas[y][x] = painter(m, x, y, t)


def _paint_bucky(m, x, y, t):
    fur = ui._lerp(C["fur_hi"], C["fur_lo"], y / (H - 1))
    if m == "o":
        return _OUTLINE[(x - y + t) % len(_OUTLINE)], ui.ramp(W)[x]
    if m == "b":
        return _FUR[(x * 5 + y * 3 + t // 4) % len(_FUR)], fur
    return {
        "l": ("%", C["belly"]), "e": ("●", C["eye"]), "c": ("-", C["foot"]), "n": ("@", C["nose"]), "t": ("▌", C["teeth"]),
        "w": ("=", C["arm"]), "k": ("#" if (x + y) % 2 else "x", C["tail"]), "f": ("▀", C["foot"]),
        "g": ("@" if (x + y + t // 2) % 5 else "%", C["glove"] if (x + y + t // 2) % 5 else C["glove_hi"]),
    }.get(m, ("?", fur))


def _paint_tree(m, x, y, t):
    if m == "c":
        ch = "%@&$%#@%"[(x * 3 + y + t // 3) % 8]
        return ch, C["leaf"][(x + y * 2 + t // 3) % 4]
    if m == "r":
        return ("|" if x % 2 else "#"), (C["trunk_hi"] if (y + t // 4) % 3 == 0 else C["trunk"])
    if m == "h":
        return "=", C["trunk"]
    if m == "s":
        return "_", C["trunk_hi"]
    return "?", C["trunk"]


def _fight(i: int) -> Text:
    bucky, tree, tx, stump_x, walked, effect, k = _state(i)
    canvas = [[(" ", "") for _ in range(W)] for _ in range(H)]

    # ground scrolls while Bucky walks
    for x in range(W):
        canvas[GROUND][x] = (_GROUND[(x + walked) % len(_GROUND)], C["ground"])
    # last tree's stump + log slide away behind him
    if stump_x is not None:
        _blit(canvas, FALLEN, stump_x, GROUND - len(FALLEN), _paint_tree, i)
    _blit(canvas, tree, tx, GROUND - len(tree), _paint_tree, i)
    _blit(canvas, bucky, BX, GROUND - len(bucky), _paint_bucky, i)

    if effect == "punch":                                    # impact sparks + falling leaves
        cx = tx + TREE_HIT_X - 1
        for dx, dy, ch in [(0, -4, "*"), (1, -5, "+"), (1, -3, "x"), (-1, -5, "·")][: 2 + k]:
            if 0 <= cx + dx < W:
                canvas[GROUND + dy][cx + dx] = (ch, C["spark"])
        for n in range(3):
            lx, ly = tx + 2 + (n * 4 + i) % 8, 5 + (k + n) % 3
            if 0 <= lx < W and canvas[ly][lx][0] == " ":
                canvas[ly][lx] = (",." [n % 2], C["leaf"][n])
    elif effect == "dust":
        for n, dx in enumerate(range(8, 24, 3)):
            x = tx + dx
            if 0 <= x < W:
                canvas[GROUND - 1 - (n + k) % 2][x] = ("~.°"[n % 3], C["dust"])

    out = Text(no_wrap=True, overflow="crop")
    for y, row in enumerate(canvas):
        for ch, style in row:
            out.append(ch, style=style or None)
        if y < H - 1:
            out.append("\n")
    return out


# ── asleep / the bell ────────────────────────────────────────────────────────
# Bucky naps sitting down, gloves on the ground. c = closed eye, e = open eye, ! = startled
SLEEP = [
    "                   ",
    "      oo           ",
    "    obbbbo         ",
    "   obbbbbcoo       ",
    " kkobbbbbbbbbn     ",
    "kkkkobbllbbbtt     ",
    " kk obbllllbwggg   ",
    "     ff  ff  ggg   ",
]
SLEEP_B = [  # breathing out: a little lower and rounder
    "                   ",
    "                   ",
    "      oo           ",
    "    obbbbocoo      ",
    " kkobbbbbbbbbbn    ",
    "kkkkobbllbbbbtt    ",
    " kk obbllllllbwggg ",
    "     ff  ff   ggg  ",
]
SLEEP_B[3] = "    obbbbbcoo      "
AWAKE = [row.replace("c", "e") for row in SLEEP]

# the fight bell, hanging on a post at the right; a = bell, p = post, d = clapper
BELL = [
    "  qqqqq ",
    "    p   ",
    "  aaaaa ",
    " aaaaaaa",
    " aaaaaaa",
    "aaaaaaaaa",
    "    d   ",
]
BELL_X = 34
BELL_LEN = 22          # ticks: ding ding (shaking), Bucky jolts awake, then stands up


def _paint_bell(m, x, y, t):
    if m == "q":
        return "=", C["trunk"]
    if m == "p":
        return "|", C["trunk"]
    if m == "d":
        return "o", C["spark"]
    return "@%#@%"[(x + y + t) % 5], ("#f9e2af" if (x + y + t) % 3 else "#e5c07b")


def _scene(i: int, bucky, extras) -> Text:
    canvas = [[(" ", "") for _ in range(W)] for _ in range(H)]
    for x in range(W):
        canvas[GROUND][x] = (_GROUND[x % len(_GROUND)], C["ground"])
    _blit(canvas, bucky, BX, GROUND - len(bucky), _paint_bucky, i)
    for x, y, ch, color in extras:
        if 0 <= x < W and 0 <= y < H:
            canvas[y][x] = (ch, color)
    out = Text(no_wrap=True, overflow="crop")
    for y, row in enumerate(canvas):
        for ch, style in row:
            out.append(ch, style=style or None)
        if y < H - 1:
            out.append("\n")
    return out


def sleep_frame(i: int) -> Text:
    pose = SLEEP if (i // 10) % 2 == 0 else SLEEP_B
    extras = []
    for n in range(3):                      # three z's drifting up and to the right
        k = (i + n * 9) % 27
        x, y = BX + 12 + k // 3, 4 - k // 6
        ch = "z" if k < 9 else ("z" if k < 18 else "Z")
        if y >= 0:
            extras.append((x, y, ch, ui.ramp(3, [ui.T.muted, ui.T.accent2])[min(2, k // 9)]))
    return _scene(i, pose, extras)


def bell_frame(i: int) -> Text:
    """i runs 0..BELL_LEN-1: the bell rings, Bucky wakes with a start, then gets up."""
    shake = (-1, 1)[i % 2] if i < 12 else 0
    if i < 6:
        bucky = SLEEP
    elif i < 14:
        bucky = AWAKE
    else:
        bucky = GUARD
    canvas = [[(" ", "") for _ in range(W)] for _ in range(H)]
    for x in range(W):
        canvas[GROUND][x] = (_GROUND[x % len(_GROUND)], C["ground"])
    _blit(canvas, bucky, BX, GROUND - len(bucky), _paint_bucky, i)
    _blit(canvas, BELL, BELL_X + shake, 1, _paint_bell, i)
    for y in range(8, GROUND):
        canvas[y][BELL_X + 4] = ("|", C["trunk"])
    if i < 12:                               # DING! and sound waves
        word = "DING!" if (i // 3) % 2 == 0 else "DING!!"
        for n, ch in enumerate(word):
            x = BELL_X - 7 + n
            if 0 <= x < W:
                canvas[1 + (i % 2)][x] = (ch, f"bold {C['spark']}")
        for n, (dx, dy) in enumerate([(-2, 4), (-3, 5), (10, 4), (11, 5)]):
            x, y = BELL_X + dx, dy
            if 0 <= x < W and (i + n) % 2 == 0:
                canvas[y][x] = (")" if dx > 0 else "(", C["spark"])
    if 6 <= i < 14:                          # "!" over his head
        canvas[2][BX + 9] = ("!", f"bold {C['spark']}")
    out = Text(no_wrap=True, overflow="crop")
    for y, row in enumerate(canvas):
        for ch, style in row:
            out.append(ch, style=style or None)
        if y < H - 1:
            out.append("\n")
    return out


def frame(i: int, mode: str = "fight") -> Text:
    """mode: sleep (off the clock) · bell (just punched in) · fight (on the clock)"""
    if mode == "sleep":
        return sleep_frame(i)
    if mode == "bell":
        return bell_frame(min(i, BELL_LEN - 1))
    return _fight(i)


def frame_count() -> int:
    return CYCLE
