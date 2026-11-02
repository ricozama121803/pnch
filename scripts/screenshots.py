"""Regenerate the README screenshots from the real app, using made-up demo data.

    .venv/bin/pip install -e '.[dev]'
    .venv/bin/python scripts/screenshots.py

Everything happens in a throwaway folder with the clock frozen on a Thursday afternoon,
so your own log and config are never touched.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
NOW = datetime(2026, 10, 29, 15, 12, 30)   # a Thursday afternoon

os.environ["PNCH_HOME"] = tempfile.mkdtemp(prefix="pnch-shots-")

import freezegun  # noqa: E402

freezegun.configure(extend_ignore_list=["textual", "asyncio", "rich"])


def seed() -> None:
    from pnch import config
    from pnch.store import Store

    config.load()
    for key, value in [("name", "Alex Rivera"), ("email", "alex@example.com"), ("paypal", "@alexrivera")]:
        config.set_value("you", key, value)
    config.set_value("client", "name", "Acme Robotics")
    config.set_value("invoice", "doc_title", "Acme Robotics Logs + Invoice")
    config.set_value("invoice", "role", "Acme Frontend Contractor")

    st = Store.load()
    d = lambda s: datetime.fromisoformat(s)  # noqa: E731
    blocks = [
        # two weeks ago (approved + exported)
        ("2026-10-13 16:00", "2026-10-13 17:03", ["Kickoff meeting"]),
        ("2026-10-14 23:00", "2026-10-15 00:12", ["Pulled together the manual leads list"]),
        ("2026-10-15 11:00", "2026-10-15 13:26", ["Meeting", "Scraper tools + AWS; checked VPN prefix list"]),
        ("2026-10-15 15:00", "2026-10-15 16:30", ["Lambda/Terraform changes into Git"]),
        ("2026-10-18 20:00", "2026-10-18 23:09", ["Automated scraper changes after meeting", "Updated READMEs"]),
        # last week (approved)
        ("2026-10-19 10:00", "2026-10-19 12:15", ["Sprint planning", "Ticket grooming"]),
        ("2026-10-21 13:30", "2026-10-21 17:45", ["Built the export API endpoint"]),
        ("2026-10-23 09:15", "2026-10-23 11:00", ["Code review", "Fixed flaky tests"]),
        # this week
        ("2026-10-26 09:00", "2026-10-26 11:30", ["Standup", "Reviewed PRs"]),
        ("2026-10-26 13:00", "2026-10-26 17:15", ["Scraper retries + backoff"]),
        ("2026-10-27 10:00", "2026-10-27 12:00", ["AWS cost report"]),
        ("2026-10-27 19:00", "2026-10-27 21:40", ["Leads cleanup for sales"]),
        ("2026-10-28 09:30", "2026-10-28 12:45", ["Dashboard charts"]),
        ("2026-10-28 14:00", "2026-10-28 18:00", ["Dashboard filters", "Wrote tests"]),
        ("2026-10-29 09:00", "2026-10-29 12:10", ["Client call", "Spec for invoices v2"]),
    ]
    for start, end, notes in blocks:
        st.add(d(start), d(end), notes)
    st.add(d("2026-10-29 13:48"), None, ["Fixing the scraper timeout", "Checked AWS logs"])
    for monday, number, billed, summary, exported in [
        ("2026-10-12", 1007, 540, "Scraper, leads, AWS and meeting work", True),
        ("2026-10-19", 1008, 480, "Planning, export API and code review", False),
    ]:
        st.weeks[monday] = {
            "approved_at": "2026-10-20T09:00:00", "total_minutes": billed, "billed_minutes": billed, "rate": 25.0,
            "invoice_number": number, "summary": summary, "issued": "2026-10-21", "due": "2026-11-10",
            "exports": [{"path": "~/Documents/pnch/x.pdf", "at": "2026-10-21T09:00:00"}] if exported else [],
        }
    st.save()


async def shoot() -> None:
    from pnch import mascot
    from pnch.tui import BlockEditor, ConflictScreen, DayScreen, LogScreen, PnchApp, WeekPicker

    OUT.mkdir(parents=True, exist_ok=True)
    app = PnchApp()
    async with app.run_test(size=(132, 44)) as pilot:
        main = app.main

        async def snap(name: str, mode: str | None = None, frame: int | None = None) -> None:
            await pilot.pause(0.3)
            if mode is not None:
                main._mode, main._frame = mode, frame - 1
                main._mascot_tick()
                await pilot.pause(0.05)
            app.save_screenshot(f"{name}.svg", path=str(OUT))
            print("  saved", name)

        await pilot.pause(0.5)
        main.query_one("#new").focus()
        await snap("main", "fight", 4)                      # mid-punch

        main.query_one("#cmd").focus()
        await pilot.press("/", "down", "down")
        await snap("slash-menu", "fight", 26)
        await pilot.press("escape")
        main.query_one("#cmd").value = ""

        await pilot.press(*"out", "enter")
        await pilot.press(*"Bumped the retry limit")
        await snap("punch-out")
        main.query_one("#new").value = ""
        app.screen.query_one("#extra").value = ""
        await pilot.press("escape")

        app.push_screen(DayScreen(date(2026, 10, 28)))
        await snap("day")
        await pilot.press("escape")

        app.push_screen(LogScreen(date(2026, 10, 26)))
        await snap("week")
        await pilot.press("escape")

        app.push_screen(WeekPicker())
        await pilot.pause(0.2)
        await pilot.press("up")
        await snap("weeks")
        await pilot.press("escape")

        app.push_screen(DayScreen(date(2026, 10, 27)))
        await pilot.pause(0.2)
        await pilot.press("down", "down", "enter")
        await pilot.press(*"9:30am", "enter", *"10:30am", "enter", *"Quick sync", "enter")
        await snap("overlap")
        await pilot.press("escape", "escape", "escape")

        await pilot.press(*"/config", "enter")
        await snap("config")
        await pilot.press("escape")

    # off the clock: Bucky asleep
    from pnch.store import Store
    st = Store.load()
    st.running().end = datetime(2026, 10, 29, 15, 10)
    st.save(record=False)
    app = PnchApp()
    async with app.run_test(size=(132, 44)) as pilot:
        await pilot.pause(0.5)
        app.main._mode, app.main._frame = "sleep", 3
        app.main._mascot_tick()
        await pilot.pause(0.1)
        app.save_screenshot("off-the-clock.svg", path=str(OUT))
        print("  saved off-the-clock")


def pdf_pages() -> None:
    import pypdfium2 as pdfium

    from pnch import config, pdf, report
    from pnch.store import Store

    r = report.build(Store.load(), config.load(), date(2026, 10, 12))
    path = pdf.render(r, config.load(), Path(os.environ["PNCH_HOME"]) / "demo.pdf")
    doc = pdfium.PdfDocument(str(path))
    for i, name in enumerate(["pdf-log", "pdf-invoice"]):
        doc[i].render(scale=1.4).to_pil().save(OUT / f"{name}.png")
        print("  saved", name)


if __name__ == "__main__":
    with freezegun.freeze_time(NOW, tick=True):
        seed()
        asyncio.run(shoot())
        pdf_pages()
    print(f"screenshots in {OUT}")
    sys.exit(0)
