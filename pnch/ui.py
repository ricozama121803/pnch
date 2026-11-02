"""Terminal look & feel: themes, gradients, big clock digits, bars, tables."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .report import Report
from .store import Session, Store
from .timeutil import DAY_ABBR, fmt_hm, fmt_md, fmt_money, fmt_range, fmt_time, week_days

console = Console(highlight=False)

THEMES = {
    "catppuccin": dict(
        base="#1e1e2e", text="#cdd6f4", muted="#a6adc8", dim="#585b70", faint="#313244",
        accent="#cba6f7", accent2="#89b4fa", ok="#a6e3a1", warn="#f9e2af", err="#f38ba8",
        grad=["#f5c2e7", "#cba6f7", "#b4befe", "#89b4fa", "#89dceb", "#94e2d5"],
    ),
    "nord": dict(
        base="#2e3440", text="#eceff4", muted="#d8dee9", dim="#4c566a", faint="#3b4252",
        accent="#88c0d0", accent2="#81a1c1", ok="#a3be8c", warn="#ebcb8b", err="#bf616a",
        grad=["#8fbcbb", "#88c0d0", "#81a1c1", "#5e81ac", "#b48ead"],
    ),
    "gruvbox": dict(
        base="#282828", text="#ebdbb2", muted="#bdae93", dim="#665c54", faint="#3c3836",
        accent="#fe8019", accent2="#fabd2f", ok="#b8bb26", warn="#fabd2f", err="#fb4934",
        grad=["#fb4934", "#fe8019", "#fabd2f", "#b8bb26", "#8ec07c"],
    ),
    "tokyonight": dict(
        base="#1a1b26", text="#c0caf5", muted="#a9b1d6", dim="#565f89", faint="#292e42",
        accent="#bb9af7", accent2="#7aa2f7", ok="#9ece6a", warn="#e0af68", err="#f7768e",
        grad=["#f7768e", "#bb9af7", "#7aa2f7", "#7dcfff", "#73daca"],
    ),
    "rosepine": dict(
        base="#191724", text="#e0def4", muted="#908caa", dim="#524f67", faint="#26233a",
        accent="#c4a7e7", accent2="#9ccfd8", ok="#9ccfd8", warn="#f6c177", err="#eb6f92",
        grad=["#eb6f92", "#ebbcba", "#f6c177", "#c4a7e7", "#9ccfd8"],
    ),
}

T = SimpleNamespace(**THEMES["catppuccin"])


def set_theme(name: str) -> None:
    T.__dict__.update(THEMES.get(name, THEMES["catppuccin"]))


# ── color helpers ────────────────────────────────────────────────────────────

def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb))


def ramp(n: int, stops: list[str] | None = None) -> list[str]:
    stops = stops or T.grad
    if n <= 1:
        return [stops[0]]
    out = []
    for i in range(n):
        pos = i / (n - 1) * (len(stops) - 1)
        k = min(int(pos), len(stops) - 2)
        out.append(_lerp(stops[k], stops[k + 1], pos - k))
    return out


def gradient(s: str, bold: bool = True, stops: list[str] | None = None) -> Text:
    t = Text()
    for ch, col in zip(s, ramp(len(s), stops)):
        t.append(ch, style=f"{'bold ' if bold else ''}{col}")
    return t


# ── big digits ───────────────────────────────────────────────────────────────

GLYPHS = {
    "0": ["█▀█", "█ █", "▀▀▀"],
    "1": ["▀█ ", " █ ", "▀▀▀"],
    "2": ["▀▀█", "█▀▀", "▀▀▀"],
    "3": ["▀▀█", " ▀█", "▀▀▀"],
    "4": ["█ █", "▀▀█", "  ▀"],
    "5": ["█▀▀", "▀▀█", "▀▀▀"],
    "6": ["█▀▀", "█▀█", "▀▀▀"],
    "7": ["▀▀█", "  █", "  ▀"],
    "8": ["█▀█", "█▀█", "▀▀▀"],
    "9": ["█▀█", "▀▀█", "▀▀▀"],
    ":": [" ", "▀", "▀"],
    " ": [" ", " ", " "],
}


def big(s: str, stops: list[str] | None = None) -> Text:
    rows = ["", "", ""]
    for ch in s:
        g = GLYPHS.get(ch, GLYPHS[" "])
        for i in range(3):
            rows[i] += g[i] + " "
    width = len(rows[0])
    cols = ramp(width, stops)
    out = Text()
    for i, row in enumerate(rows):
        for ch, col in zip(row, cols):
            out.append(ch, style=f"bold {col}")
        if i < 2:
            out.append("\n")
    return out


def clock_str(seconds: int, with_seconds: bool = True) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if with_seconds else f"{h:02d}:{m:02d}"


# ── small pieces ─────────────────────────────────────────────────────────────

def chip(label: str, color: str) -> Text:
    return Text.assemble((f" {label} ", f"bold {T.base} on {color}"))


def status_chip(store: Store, monday: date) -> Text:
    rec = store.approval(monday)
    if rec and rec.get("exports"):
        return chip("✓ exported", T.ok)
    if rec:
        return chip("✓ approved", T.accent2)
    return chip("◌ pending", T.warn)


def bar(minutes: int, scale: int, width: int = 26, color: str | None = None) -> Text:
    parts = " ▏▎▍▌▋▊▉█"
    color = color or T.accent
    if minutes <= 0:
        return Text("·" + " " * (width - 1), style=T.faint)
    cells = min(width, minutes / max(scale, 1) * width)
    full = int(cells)
    frac = parts[int((cells - full) * 8)] if full < width else ""
    t = Text("█" * full + (frac.strip() and frac), style=color)
    t.append("─" * (width - len(t)), style=T.faint)
    return t


def ok(msg: str) -> None:
    console.print(Text("  ✓ ", style=f"bold {T.ok}") + Text.from_markup(msg, style=T.text))


def info(msg: str) -> None:
    console.print(Text("  › ", style=f"bold {T.accent}") + Text.from_markup(msg, style=T.muted))


def warn(msg: str) -> None:
    console.print(Text("  ! ", style=f"bold {T.warn}") + Text.from_markup(msg, style=T.text))


def err(msg: str) -> None:
    console.print(Text("  ✗ ", style=f"bold {T.err}") + Text.from_markup(msg, style=T.text))


def panel(body, title: str, subtitle=None, border: str | None = None, padding=(1, 2)) -> Panel:
    return Panel(
        body,
        box=box.ROUNDED,
        border_style=border or T.dim,
        title=Text.assemble(" ", gradient(title), " "),
        title_align="left",
        subtitle=subtitle,
        subtitle_align="right",
        padding=padding,
    )


def kv(*pairs: tuple[str, str | Text]) -> Table:
    g = Table.grid(padding=(0, 2))
    g.add_column(style=T.dim, justify="right")
    g.add_column(style=T.text)
    for k, v in pairs:
        g.add_row(k, v)
    return g


def notes_text(notes: list[str], indent: str = "") -> Text:
    t = Text()
    for i, n in enumerate(notes):
        if i:
            t.append("\n")
        t.append(f"{indent}› ", style=T.accent)
        t.append(n, style=T.text)
    return t


# ── composite views ──────────────────────────────────────────────────────────

def week_bars(store: Store, monday: date, at: datetime | None = None, width: int = 26) -> Table:
    days = week_days(monday)
    mins = [sum(s.minutes(at) for s in store.on_day(d)) for d in days]
    scale = max(8 * 60, max(mins))
    g = Table.grid(padding=(0, 1))
    g.add_column(width=2)
    g.add_column(width=6)
    g.add_column(width=6)
    g.add_column()
    g.add_column(justify="right", width=8)
    g.add_column()
    today = date.today()
    colors = ramp(7)
    for d, m, col in zip(days, mins, colors):
        is_today = d == today
        running = any(s.running for s in store.on_day(d))
        g.add_row(
            Text("›", style=f"bold {T.accent}") if is_today else Text(""),
            Text(DAY_ABBR[d.weekday()], style=f"bold {T.text}" if is_today else T.muted),
            Text(fmt_md(d), style=T.dim),
            bar(m, scale, width=width, color=col),
            Text(fmt_hm(m) if m else "", style=T.text),
            Text(" ●", style=f"bold {T.ok}") if running else Text(""),
        )
    return g


def totals_line(r: Report) -> Text:
    t = Text()
    t.append("total ", style=T.dim)
    t.append(fmt_hm(r.total_minutes), style=f"bold {T.text}")
    t.append("   billed ", style=T.dim)
    t.append(("" if r.approved else "≈ ") + fmt_hm(r.billed_minutes), style=f"bold {T.text}")
    t.append("   ", style=T.dim)
    t.append(fmt_money(r.amount), style=f"bold {T.ok}")
    if r.approved:
        t.append(f"   invoice #{r.invoice_number}", style=T.dim)
    return t


def dashboard(store: Store, r: Report, cfg: dict, live: bool = False) -> Group:
    now = datetime.now()
    run = store.running()
    stamp = Text(f"{now:%a %b} {now.day} · {fmt_time(now)}", style=T.dim)

    if run:
        head = Table.grid(expand=True)
        head.add_column()
        head.add_column(justify="right")
        head.add_row(Text.assemble(chip("● ON THE CLOCK", T.ok)), stamp)
        clock = big(clock_str(run.seconds(now), with_seconds=live))
        meta = Text.assemble(
            ("since ", T.dim), (fmt_time(run.start), f"bold {T.text}"),
            ("  ·  ", T.dim), (f"#{run.id}", T.dim),
        )
        parts = [head, Text(""), clock, Text(""), meta]
        if run.notes:
            parts += [Text(""), notes_text(run.notes)]
        else:
            parts += [Text(""), Text("› no notes yet, add one with  pnch note \"…\"", style=T.dim)]
        top = panel(Group(*parts), "pnch", border=T.accent)
    else:
        today_min = sum(s.minutes() for s in store.on_day(date.today()))
        head = Table.grid(expand=True)
        head.add_column()
        head.add_column(justify="right")
        head.add_row(chip("○ OFF THE CLOCK", T.dim), stamp)
        clock = big(clock_str(today_min * 60, with_seconds=False), stops=[T.dim, T.muted])
        hint = Text.assemble(("today", T.dim), ("  ·  pnch in \"what you're starting\"", T.faint))
        top = panel(Group(head, Text(""), clock, Text(""), hint), "pnch")

    week = panel(
        Group(week_bars(store, r.monday, now), Text(""), totals_line(r)),
        f"week {fmt_md(r.monday)} – {fmt_md(r.sunday)}",
        subtitle=status_chip(store, r.monday),
    )
    return Group(top, week)


def sessions_table(store: Store, monday: date) -> Table:
    t = Table(
        box=box.SIMPLE_HEAD, header_style=f"bold {T.accent}", border_style=T.dim,
        show_edge=False, pad_edge=False, expand=False,
    )
    t.add_column("day", style=T.muted, no_wrap=True)
    t.add_column("#", style=T.dim, justify="right")
    t.add_column("time", style=T.text, no_wrap=True)
    t.add_column("dur", style=T.accent2, justify="right", no_wrap=True)
    t.add_column("what", style=T.text, max_width=70)
    last_day = None
    for s in store.in_week(monday):
        if last_day and s.day != last_day:
            t.add_section()
        day = f"{DAY_ABBR[s.day.weekday()]} {fmt_md(s.day)}" if s.day != last_day else ""
        last_day = s.day
        rng = Text(fmt_range(s.start, s.end))
        if s.running:
            rng.stylize(f"bold {T.ok}")
        t.add_row(day, str(s.id), rng, fmt_hm(s.minutes()), notes_text(s.notes) if s.notes else Text("—", style=T.faint))
    return t


def session_card(s: Session, title: str, border: str | None = None) -> Panel:
    body = kv(
        ("#", str(s.id)),
        ("day", f"{DAY_ABBR[s.day.weekday()]} {fmt_md(s.day)}"),
        ("time", fmt_range(s.start, s.end)),
        ("duration", fmt_hm(s.minutes())),
    )
    parts = [body]
    if s.notes:
        parts += [Text(""), notes_text(s.notes)]
    return panel(Group(*parts), title, border=border, padding=(0, 2))


# ── banner ───────────────────────────────────────────────────────────────────

# Figlet "ANSI Shadow"-style letters. The first "!" is flipped upside down into a "¡".
BANNER_GLYPHS = {
    "¡": ["██╗", "╚═╝", "██╗", "██║", "██║", "╚═╝"],
    "P": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔═══╝ ", "██║     ", "╚═╝     "],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    "C": [" ██████╗", "██╔════╝", "██║     ", "██║     ", "╚██████╗", " ╚═════╝"],
    "H": ["██╗  ██╗", "██║  ██║", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "!": ["██╗", "██║", "██║", "╚═╝", "██╗", "╚═╝"],
}


def _fit(a: list[str], b: list[str], gap: int = 1) -> list[str]:
    """Slide glyph b left against a (figlet-style kerning), keeping at least `gap` spaces."""
    w = max(len(x) for x in a)
    a = [x.ljust(w) for x in a]
    free = min(w - len(x.rstrip()) + len(y) - len(y.lstrip()) for x, y in zip(a, b))
    if free < gap:
        b = [" " * (gap - free) + y for y in b]
        free = gap
    k = free - gap
    out = []
    for x, y in zip(a, b):
        tail, overlap = x[: w - k], x[w - k:]
        merged = "".join(c2 if c1 == " " else c1 for c1, c2 in zip(overlap, y[:k].ljust(k)))
        out.append(tail + merged + y[k:])
    return out


def banner(word: str = "¡PNCH!") -> Text:
    rows = BANNER_GLYPHS[word[0]]
    for ch in word[1:]:
        rows = _fit(rows, BANNER_GLYPHS[ch])
    rows = [r.rstrip() for r in rows]
    cols = ramp(max(len(r) for r in rows))
    out = Text(no_wrap=True, overflow="crop")
    for i, row in enumerate(rows):
        out.append("  ")
        for ch, col in zip(row, cols):
            out.append(ch, style=f"bold {col}")
        if i < len(rows) - 1:
            out.append("\n")
    return out
