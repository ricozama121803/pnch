"""Bucky, the pnch mascot: a boxing beaver drawn in shading characters,
animated the same way as the Ghostty ghost (a shimmering outline + a little motion loop)."""
from __future__ import annotations

from rich.text import Text

from . import ui

# mask legend
#   o outline     b fur        l light fur (muzzle)   e eye   c closed eye
#   n nose        t teeth      g glove                w glove cuff / arm
#   k tail        * spark
_HEAD = [
    "            oo        oo              ",
    "           obbooooooooobbo            ",
    "          obbbbbbbbbbbbbbbo           ",
]
_FEET = "             ooo      ooo             "

GUARD = _HEAD + [
    "       ggg bbb ebbbbbbe bbb ggg       ",
    "      ggggg bbbbbllllbbbbb ggggg      ",
    "      ggggg bbbbllnnllbbbb ggggg      ",
    "       gggw obbbblttlbbbbo wggg       ",
    "           wobbbbbbbbbbbbow  kkkkk    ",
    "            obbbbbbbbbbbbo kkkkkkk    ",
    "             ooo      ooo   kkkkk     ",
]

BOB = _HEAD + [
    "           bbb ebbbbbbe bbb           ",
    "       ggg  bbbbbllllbbbbb  ggg       ",
    "      ggggg bbbbllnnllbbbb ggggg      ",
    "      gggggwobbbblttlbbbbowggggg      ",
    "       ggg  obbbbbbbbbbbbo  ggg kkkkk ",
    "            obbbbbbbbbbbbo  kkkkkkk   ",
    "             ooo      ooo  kkkkk      ",
]

JAB_R = _HEAD + [
    "       ggg bbb ebbbbbbe bbb       ggg   ",
    "      ggggg bbbbbllllbbbbbwwwwwwggggg * ",
    "      ggggg bbbbllnnllbbbb     ggggg  * ",
    "       gggw obbbblttlbbbbo      ggg  *  ",
    "           wobbbbbbbbbbbbo   kkkkk      ",
    "            obbbbbbbbbbbbo kkkkkkk      ",
    _FEET + "  kkkkk",
]
JAB_R[-1] = "             ooo      ooo   kkkkk     "

JAB_L = _HEAD + [
    "  ggg      bbb ebbbbbbe bbb ggg       ",
    "*gggggwwwwwwbbbbbllllbbbbb ggggg      ",
    "*ggggg      bbbbllnnllbbbb ggggg      ",
    " *ggg      obbbblttlbbbbo wggg        ",
    "            obbbbbbbbbbbbow  kkkkk    ",
    "            obbbbbbbbbbbbo kkkkkkk    ",
    "             ooo      ooo   kkkkk     ",
]

BLINK = [row.replace("e", "c") for row in GUARD]

FLICK = GUARD[:7] + [
    "           wobbbbbbbbbbbbow    kkkk   ",
    "            obbbbbbbbbbbbo   kkkkkk   ",
    "             ooo      ooo  kkkkkk     ",
]

# (pose, ticks) — one tick is ~0.12s
SEQUENCE = [
    (GUARD, 6), (BOB, 2), (GUARD, 3), (BOB, 2), (GUARD, 3),
    (JAB_R, 2), (GUARD, 1), (JAB_L, 2), (GUARD, 1), (JAB_R, 3), (GUARD, 5),
    (BLINK, 1), (GUARD, 6), (FLICK, 2), (GUARD, 1), (FLICK, 2), (GUARD, 6),
]
FRAMES = [pose for pose, n in SEQUENCE for _ in range(n)]
HEIGHT = len(GUARD)
WIDTH = max(len(r) for pose, _ in SEQUENCE for r in pose)

_OUTLINE = "+=xo*·o=+"
_FUR = "$$$$$@$$$$%$$$@$"
_COLORS = {
    "fur_hi": "#d9a066", "fur_lo": "#8f5a33", "muzzle": "#e8c49a", "nose": "#6b4128",
    "teeth": "#fafafa", "glove": "#ef4e5c", "glove_hi": "#ff8a94", "cuff": "#e8e8e8",
    "tail": "#6b4428", "tail_hi": "#8f5f3a", "spark": "#f9e2af", "lid": "#5c3a22",
}


def _shade(a: str, b: str, t: float) -> str:
    return ui._lerp(a, b, max(0.0, min(1.0, t)))


def frame(i: int) -> Text:
    """Render animation frame i as rich Text."""
    pose = FRAMES[i % len(FRAMES)]
    outline_cols = ui.ramp(WIDTH)  # follows the theme gradient, like the banner
    out = Text(no_wrap=True, overflow="crop")
    for y, row in enumerate(pose):
        row = row.ljust(WIDTH)
        fur = _shade(_COLORS["fur_hi"], _COLORS["fur_lo"], y / (HEIGHT - 1))
        for x, m in enumerate(row):
            if m == " ":
                out.append(" ")
            elif m == "o":  # the shimmer sweeps diagonally around the outline
                out.append(_OUTLINE[(x - y + i) % len(_OUTLINE)], style=outline_cols[x])
            elif m == "b":
                out.append(_FUR[(x * 7 + y * 3 + i // 4) % len(_FUR)], style=fur)
            elif m == "l":
                out.append("%", style=_COLORS["muzzle"])
            elif m == "e":
                out.append(" ")
            elif m == "c":
                out.append("-", style=_COLORS["lid"])
            elif m == "n":
                out.append("@", style=f"bold {_COLORS['nose']}")
            elif m == "t":
                out.append("█", style=_COLORS["teeth"])
            elif m == "g":
                hi = (x + y + i // 2) % 5 == 0
                out.append("@" if not hi else "%", style=f"bold {_COLORS['glove_hi'] if hi else _COLORS['glove']}")
            elif m == "w":
                out.append("=", style=_COLORS["cuff"])
            elif m == "k":
                out.append("#" if (x + y) % 2 else "x", style=_COLORS["tail_hi"] if (x + y + i // 3) % 3 == 0 else _COLORS["tail"])
            elif m == "*":
                out.append("*" if (x + y + i) % 2 else "+", style=f"bold {_COLORS['spark']}")
        if y < HEIGHT - 1:
            out.append("\n")
    return out


def frame_count() -> int:
    return len(FRAMES)
