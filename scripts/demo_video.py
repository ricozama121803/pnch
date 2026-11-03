"""Record the demo video from the real app, using made-up data.

    .venv/bin/pip install -e '.[dev]'
    pip install playwright            # any Python works for the render step; it uses your Chrome
    .venv/bin/python scripts/demo_video.py record /tmp/pnch-demo
    python scripts/demo_video.py render /tmp/pnch-demo         # -> docs/demo.mp4 + docs/demo.gif

`record` drives pnch with scripted key presses in a throwaway PNCH_HOME (your own log and
config are never touched) and saves an SVG per frame plus how long each one stays on screen.
`render` turns those into PNGs with headless Chrome and stitches them with ffmpeg.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 29, 15, 12, 0)   # a Thursday afternoon
SIZE = (120, 40)
W, H = 1920, 1080
TYPE = 0.06                                # seconds per typed character


# ── record ───────────────────────────────────────────────────────────────────

class Tape:
    """Collects frames: an SVG of the screen (or a title card) and how long it shows."""

    def __init__(self, out: Path):
        self.out = out
        self.frames: list[dict] = []
        self.app = self.pilot = None

    def card(self, title: str, sub: str = "", secs: float = 2.2) -> None:
        self.frames.append({"card": [title, sub], "secs": secs})

    async def snap(self, secs: float) -> None:
        await self.pilot.pause()
        svg = self.app.export_screenshot(title="pnch")
        name = hashlib.sha1(svg.encode()).hexdigest()[:16] + ".svg"
        (self.out / name).write_text(svg)
        if self.frames and self.frames[-1].get("svg") == name:
            self.frames[-1]["secs"] += secs
        else:
            self.frames.append({"svg": name, "secs": secs})

    async def wait(self, secs: float, step: float = 0.5) -> None:
        """Hold on screen while the app keeps living (clock ticks, Bucky moves)."""
        left = secs
        while left > 0:
            await self.pilot.pause(min(step, left))
            await self.snap(min(step, left))
            left -= step

    async def keys(self, *keys: str, secs: float = 0.6) -> None:
        for k in keys:
            await self.pilot.press(k)
            await self.snap(secs)

    async def type(self, text: str, enter: bool = True, hold: float = 0.5) -> None:
        for ch in text:
            await self.pilot.press(ch)
            await self.snap(TYPE)
        await self.snap(hold)
        if enter:
            await self.keys("enter", secs=0.7)

    def save(self) -> None:
        (self.out / "frames.json").write_text(json.dumps(self.frames, indent=1))


async def first_run(tape: Tape) -> None:
    from pnch.tui import PnchApp

    app = PnchApp()
    async with app.run_test(size=SIZE, notifications=True) as pilot:
        tape.app, tape.pilot = app, pilot
        await pilot.pause(0.4)
        await tape.wait(2.5)                                   # welcome
        await tape.keys("enter", secs=0.8)
        await tape.type("Alex Rivera")
        await tape.type("Frontend Contractor")
        await tape.type("alex@example.com")
        await tape.type("@alexrivera")
        await tape.type("Acme Robotics")
        await tape.type("ap@acme.example")
        await tape.type("Acme Frontend Contractor")
        app.screen.query_one("#ob-invoice-rate").value = ""
        await tape.type("45")
        await tape.keys("down", "down", "down", "down", secs=0.8)   # theme previews
        await tape.keys("down", secs=1.6)                      # leonida
        await tape.keys("enter", secs=0.4)
        await tape.wait(4)                                     # the tour
        await tape.keys("enter", secs=0.3)
        await tape.wait(2.5)


async def a_few_days_in(tape: Tape, clock) -> None:
    from pnch.tui import PnchApp

    app = PnchApp()
    # PDF previews leave the app for your PDF viewer; here we render the same PDF and show its pages.
    app.run_cli = lambda *args, wait=True: show_pdf(tape, args)
    async with app.run_test(size=SIZE, notifications=True) as pilot:
        tape.app, tape.pilot = app, pilot
        await pilot.pause(0.4)
        await tape.wait(1.5)
        await tape.type("in")                                  # punch in
        await tape.wait(1.2)
        await tape.type("Date picker fix for mobile Safari")
        await tape.type("Checked the iOS layout")
        await tape.wait(1.2)

        # tab flips between the bottom bar and the top; arrows move around up there
        await tape.keys("tab", secs=1.0)
        await tape.keys("tab", secs=1.0)
        await tape.keys("up", "up", secs=0.8)                  # into the items
        await tape.keys("right", secs=1.0)                     # today
        await tape.keys("enter", secs=0.5)                     # open today
        await tape.wait(1)
        await tape.keys("down", "down", secs=0.8)
        await tape.keys("escape", secs=0.8)
        await tape.keys("down", secs=1.0)                      # week
        await tape.keys("enter", secs=0.5)                     # open the week
        await tape.wait(1)
        await tape.keys("down", "down", "down", "down", secs=0.6)
        await tape.keys("left_square_bracket", secs=2.0)       # last week
        await tape.keys("right_square_bracket", secs=1.0)
        await tape.keys("escape", secs=0.8)
        await tape.keys("left", secs=0.8)
        await tape.keys("tab", secs=0.8)

        # forgot to log yesterday's overtime: it overlaps a block, so merge them
        await tape.type("/", enter=False, hold=0.8)            # the slash menu
        await tape.keys("down", "down", secs=0.5)
        await tape.keys("up", "up", secs=0.5)
        await tape.keys("tab", secs=0.6)                       # complete /vday
        await tape.type("yesterday", hold=0.3)
        await tape.wait(1)
        await tape.keys("down", "down", secs=0.6)              # "+ add a block"
        await tape.keys("enter", secs=0.8)
        await tape.type("12pm")
        await tape.type("1:30pm")
        await tape.type("Chart tooltips", enter=False)
        await tape.keys("enter", secs=0.5)
        await tape.wait(3.5)                                   # times overlap: options
        await tape.keys("m", secs=0.5)                         # merge them
        await tape.wait(2.5)
        await tape.keys("escape", secs=2.5)                    # the day, merged
        await tape.keys("escape", secs=0.8)

        tape.card("two hours later", secs=1.6)
        clock.move_to(NOW + timedelta(hours=2, minutes=4))
        await pilot.pause(1.2)                                 # let the clock catch up
        await tape.wait(1.5)
        await tape.type("out")                                 # punch out
        await tape.wait(1)
        await tape.type("Fixed the sticky header on iOS")
        await tape.keys("enter", secs=0.4)                     # empty enter saves
        await tape.wait(2.5)

        tape.card("the PDF", "last week is approved: preview it, then export", secs=2)
        await tape.type("/previewLogs last", enter=False, hold=0.6)
        await tape.keys("enter", secs=1.0)
        await tape.type("/exportLogs last")
        await tape.wait(3.5)


def show_pdf(tape: Tape, args: tuple) -> None:
    """Stand-in for `pnch preview`: build the same PDF and put its pages on screen."""
    if not args or args[0] != "preview":
        return
    import pypdfium2 as pdfium

    from pnch import config, pdf, report
    from pnch.paths import cache_dir
    from pnch.store import Store
    from pnch.timeutil import parse_week

    week = args[args.index("-w") + 1] if "-w" in args else None
    cfg = config.load()
    r = report.build(Store.load(), cfg, parse_week(week))
    path = pdf.render(r, cfg, cache_dir() / "preview.pdf", preview=not r.approved)
    pages = []
    for i, page in enumerate(pdfium.PdfDocument(str(path))):
        png = tape.out / f"pdf-{r.monday}-{i}.png"
        page.render(scale=2.2).to_pil().save(png)
        pages.append(png.name)
    tape.frames.append({"pdf": pages, "name": report.export_filename(cfg, r), "secs": 6.5})


def record(out: Path) -> None:
    os.environ["PNCH_HOME"] = tempfile.mkdtemp(prefix="pnch-demo-")
    os.environ["HOME"] = os.environ["PNCH_HOME"]   # exports land in the throwaway folder too
    sys.path.insert(0, str(ROOT / "scripts"))
    import freezegun

    freezegun.configure(extend_ignore_list=["textual", "asyncio", "rich"])
    from demo_data import seed_log

    out.mkdir(parents=True, exist_ok=True)
    tape = Tape(out)
    with freezegun.freeze_time(NOW, tick=True) as clock:
        tape.card("pnch", "a time clock for your terminal")
        tape.card("first run", "a minute of setup")
        asyncio.run(first_run(tape))
        seed_log(running=False)
        from pnch.tui import write_heartbeat
        write_heartbeat(clean=True)                            # as if you'd quit with ctrl+q
        tape.card("a few days in", "punch in, log what you do, punch out")
        asyncio.run(a_few_days_in(tape, clock))
        tape.card("pnch", "every week becomes a work log + invoice PDF", secs=2.5)
    tape.save()
    print(f"{len(tape.frames)} frames, {sum(f['secs'] for f in tape.frames):.0f}s → {out}")


# ── render ───────────────────────────────────────────────────────────────────

PAGE = """<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden}}
body{{background:radial-gradient(ellipse at 70% 110%,#ff4fa355,transparent 55%),
radial-gradient(ellipse at 15% -10%,#2ee6d633,transparent 50%),#140a24;display:grid;place-items:center;
font-family:'Fira Code',ui-monospace,monospace}}
.term svg{{height:{th}px;width:auto;display:block;filter:drop-shadow(0 18px 40px #0009)}}
h1{{margin:0;font-size:120px;letter-spacing:4px;text-align:center;
background:linear-gradient(90deg,#ff9a3c,#ff4fa3,#c04dff,#3fc8f2,#2ee6d6);
-webkit-background-clip:text;background-clip:text;color:transparent}}
p{{margin:16px 0 0;font-size:40px;color:#e8d4f5;text-align:center}}
.pdf{{display:flex;flex-direction:column;align-items:center;gap:18px}}
.bar{{font-size:24px;color:#fdeaff;display:flex;gap:28px}}.bar span{{color:#9d82b8}}
.pages{{display:flex;gap:40px}}.pages img{{height:{ph}px;box-shadow:0 18px 40px #000a;border-radius:4px}}
</style>{body}"""


def render(src: Path) -> None:
    from playwright.sync_api import sync_playwright

    frames = json.loads((src / "frames.json").read_text())
    pngs = src / "png"
    pngs.mkdir(exist_ok=True)
    (src / "blank.html").write_text("<!doctype html>")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": W, "height": H})
        for i, f in enumerate(frames):
            png = pngs / f"{i:04d}.png"
            f["png"] = str(png)
            if png.exists():
                continue
            if "pdf" in f:
                pages = "".join(f'<img src="file://{src / p}">' for p in f["pdf"])
                body = (f'<div class="pdf"><div class="bar">{f["name"]}<span>preview · f5 or /previewLogs'
                        f'</span></div><div class="pages">{pages}</div></div>')
            elif "card" in f:
                title, sub = f["card"]
                body = f"<div><h1>{title}</h1><p>{sub}</p></div>"
            else:
                body = f'<div class="term">{(src / f["svg"]).read_text()}</div>'
            page.goto(f"file://{src}/blank.html")    # file:// page so PDF page images can load
            page.set_content(PAGE.format(w=W, h=H, th=H - 80, ph=H - 140, body=body), wait_until="networkidle")
            page.screenshot(path=str(png))
            if i % 25 == 0:
                print(f"  {i}/{len(frames)}")
        browser.close()

    concat = src / "concat.txt"
    lines = []
    for f in frames:
        lines += [f"file '{f['png']}'", f"duration {f['secs']:.3f}"]
    lines.append(f"file '{frames[-1]['png']}'")   # ffmpeg needs the last frame repeated
    concat.write_text("\n".join(lines) + "\n")

    docs = ROOT / "docs"
    mp4, gif = docs / "demo.mp4", docs / "demo.gif"
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat)]
    encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    # Fedora's stock ffmpeg ships OpenH264 instead of x264.
    codec = (["-c:v", "libx264", "-crf", "20", "-preset", "slow"] if " libx264 " in encoders
             else ["-c:v", "libopenh264", "-b:v", "3M"])
    subprocess.run([*ff, "-vf", "fps=30,format=yuv420p", *codec, "-movflags", "+faststart", str(mp4)], check=True)
    subprocess.run([*ff, "-vf", "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=4", str(gif)], check=True)
    for p in (mp4, gif):
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("record", "render"):
        sys.exit(__doc__)
    (record if sys.argv[1] == "record" else render)(Path(sys.argv[2]))
