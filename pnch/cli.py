"""pnch: the command line."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time as _time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Group
from rich.live import Live
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.syntax import Syntax
from rich.text import Text

from . import config as config_mod
from . import pdf, report, termimg, ui
from .paths import cache_dir, config_file, data_file
from .store import Session, Store
from .timeutil import (
    DAY_ABBR, ParseError, add_business_days, fmt_hm, fmt_hours_num, fmt_hrmin, fmt_long, fmt_md, fmt_money, fmt_range,
    fmt_time, now, parse_date, parse_hours, parse_time, parse_week, parse_when, week_start,
)

app = typer.Typer(
    name="pnch",
    help="⏱  [bold]pnch[/]: clock in/out, log what you did, and ship a weekly log + invoice PDF.\n\nRun [b]pnch[/] on its own for the full-screen app.",
    rich_markup_mode="rich",
    no_args_is_help=False,
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

WEEK_HELP = "Which week: [b]this[/], [b]last[/], [b]-2[/], or any date in it (10/14, 2026-10-14)."


# ── helpers ──────────────────────────────────────────────────────────────────

def _load() -> tuple[Store, dict]:
    cfg = config_mod.load()
    ui.set_theme(cfg["ui"].get("theme", "catppuccin"))
    return Store.load(), cfg


def _fail(msg: str, code: int = 1):
    ui.err(msg)
    raise typer.Exit(code)


def _ensure_unlocked(store: Store, monday: date) -> None:
    if store.is_approved(monday):
        _fail(
            f"The week of {fmt_md(monday)} is approved and locked. "
            f"Run [b]pnch unapprove -w {monday.isoformat()}[/] to change it."
        )


def _check_overlap(store: Store, start: datetime, end: datetime | None, exclude: int | None = None) -> None:
    o = store.overlap(start, end, exclude)
    if o:
        _fail(f"That overlaps session #{o.id} ({fmt_md(o.day)} {fmt_range(o.start, o.end)}).")


def _pick_week(store: Store, week: str | None) -> date:
    """Explicit week wins. Otherwise this week, or last week if this one is still empty."""
    if week is not None:
        return parse_week(week)
    cur = week_start(date.today())
    if not store.in_week(cur) and store.in_week(cur - timedelta(weeks=1)):
        return cur - timedelta(weeks=1)
    return cur


def _ask_notes(prompt: str = "What did you work on?") -> list[str]:
    if not sys.stdin.isatty():
        return []
    ui.console.print(Text(f"  {prompt}", style=f"bold {ui.T.accent}"),
                     Text("(one per line, empty line to finish)", style=ui.T.dim))
    notes = []
    while True:
        try:
            line = ui.console.input(Text("  › ", style=ui.T.accent)).strip()
        except EOFError:
            break
        if not line:
            break
        notes.append(line)
    return notes


def _export_path(cfg: dict, r: report.Report) -> Path:
    return report.export_path(cfg, r)


# ── clocking ─────────────────────────────────────────────────────────────────

@app.command("in")
def clock_in(
    note: Optional[list[str]] = typer.Argument(None, help="What you're starting on (optional)."),
    at: Optional[str] = typer.Option(None, "--at", help="Start time if you forgot: 9:30am, 'yesterday 9pm'."),
):
    """Clock in. [dim]e.g. pnch in fixing the scraper[/]"""
    store, _ = _load()
    run = store.running()
    if run:
        _fail(f"Already on the clock since {fmt_time(run.start)} (#{run.id}). [b]pnch out[/] first.")
    start = parse_when(at) if at else now()
    if start > now() + timedelta(minutes=1):
        _fail("Can't clock in in the future.")
    _ensure_unlocked(store, week_start(start.date()))
    _check_overlap(store, start, None)
    s = store.add(start, None, [" ".join(note)] if note else [])
    store.save()
    ui.console.print(ui.session_card(s, "clocked in", border=ui.T.ok))


@app.command("out")
def clock_out(
    note: Optional[list[str]] = typer.Argument(None, help="What you did (otherwise you'll be asked)."),
    at: Optional[str] = typer.Option(None, "--at", help="End time if you forgot: 5:15pm, 'today 5pm'."),
):
    """Clock out and describe what you did."""
    store, cfg = _load()
    run = store.running()
    if not run:
        _fail("You're not clocked in.")
    end = parse_when(at, default_date=run.start.date()) if at else now()
    if at and end <= run.start and len(at.split()) == 1:
        end += timedelta(days=1)  # worked past midnight
    if end <= run.start:
        _fail(f"End time has to be after the start ({fmt_time(run.start)}).")
    if end > now() + timedelta(minutes=1):
        _fail("Can't clock out in the future.")
    if note:
        run.notes.append(" ".join(note))
    run.end = end
    if not note and sys.stdin.isatty():
        # show the block, ask for anything missing, then confirm it
        ui.console.print(ui.session_card(run, "punch out", border=ui.T.accent2))
        run.notes += _ask_notes("Did you do anything else not listed?" if run.notes else "What did you work on?")
        day = f"{DAY_ABBR[run.day.weekday()]} {fmt_md(run.day)}"
        if not Confirm.ask(Text(f"  Save {day} {fmt_range(run.start, run.end)} ({fmt_hm(run.minutes())})?",
                                style=f"bold {ui.T.text}"), default=True):
            ui.info("Not saved. You're still clocked in.")
            raise typer.Exit()
    store.save()
    ui.console.print(ui.session_card(run, "clocked out", border=ui.T.accent))
    r = report.build(store, cfg, run.week)
    ui.console.print(Text("  ") + ui.totals_line(r))


@app.command()
def note(
    text: list[str] = typer.Argument(..., help="The note."),
    id: Optional[int] = typer.Option(None, "--id", help="Session to add to (default: current or last)."),
):
    """Add a line of description to the current (or last) session."""
    store, _ = _load()
    s = store.get(id) if id else (store.running() or store.last())
    if not s:
        _fail("No session to attach a note to.")
    _ensure_unlocked(store, s.week)
    s.notes.append(" ".join(text))
    store.save()
    ui.ok(f"Note added to #{s.id} ({fmt_md(s.day)} {fmt_range(s.start, s.end)})")


@app.command()
def add(
    day: str = typer.Argument(..., help="Date: today, yesterday, tue, 10/14, 2026-10-14"),
    start: str = typer.Argument(..., help="Start time: 11pm, 9:30am, 21:30"),
    end: str = typer.Argument(..., help="End time (past midnight is fine: 12:12am)"),
    note: Optional[list[str]] = typer.Argument(None, help="What you did."),
):
    """Add a session after the fact. [dim]e.g. pnch add 10/14 11pm 12:12am getting leads together[/]"""
    store, _ = _load()
    d = parse_date(day)
    s_dt = datetime.combine(d, parse_time(start))
    e_dt = datetime.combine(d, parse_time(end))
    if e_dt <= s_dt:
        e_dt += timedelta(days=1)
    if e_dt > now() + timedelta(minutes=1):
        _fail(f"That block ends in the future ({fmt_range(s_dt, e_dt)}). Check the day or am/pm.")
    _ensure_unlocked(store, week_start(d))
    _check_overlap(store, s_dt, e_dt)
    notes = [" ".join(note)] if note else _ask_notes()
    s = store.add(s_dt, e_dt, notes)
    store.save()
    ui.console.print(ui.session_card(s, "added", border=ui.T.ok))


@app.command()
def edit(
    id: int = typer.Argument(..., help="Session # (see pnch log)."),
    day: Optional[str] = typer.Option(None, "--date", "-d", help="Move to another date."),
    start: Optional[str] = typer.Option(None, "--start", "-s", help="New start time."),
    end: Optional[str] = typer.Option(None, "--end", "-e", help="New end time."),
    notes: Optional[list[str]] = typer.Option(None, "--note", "-n", help="Replace notes (repeat for several lines)."),
    add_note: Optional[list[str]] = typer.Option(None, "--add-note", "-a", help="Append a note line."),
):
    """Fix a session's date, times or notes. With no options, asks you interactively."""
    store, _ = _load()
    s = store.get(id)
    if not s:
        _fail(f"No session #{id}.")
    _ensure_unlocked(store, s.week)

    interactive = not any([day, start, end, notes, add_note]) and sys.stdin.isatty()
    if interactive:
        ui.console.print(ui.session_card(s, f"editing #{s.id}"))
        ui.info("Press enter to keep a value. Separate note lines with ' | '.")
        day = Prompt.ask("  date", default=s.day.isoformat())
        start = Prompt.ask("  start", default=fmt_time(s.start))
        if not s.running:
            end = Prompt.ask("  end", default=fmt_time(s.end))
        joined = Prompt.ask("  notes", default=" | ".join(s.notes))
        notes = [n.strip() for n in joined.split("|") if n.strip()]

    d = parse_date(day) if day else s.day
    new_start = datetime.combine(d, parse_time(start) if start else s.start.time())
    new_end = s.end
    if s.end is not None:
        new_end = datetime.combine(d, parse_time(end) if end else s.end.time())
        if new_end <= new_start:
            new_end += timedelta(days=1)
    elif end:
        _fail("That session is still running. Use [b]pnch out --at[/] to end it.")
    _ensure_unlocked(store, week_start(d))
    _check_overlap(store, new_start, new_end, exclude=s.id)
    s.start, s.end = new_start, new_end
    if notes is not None:
        s.notes = list(notes)
    if add_note:
        s.notes += list(add_note)
    store.save()
    ui.console.print(ui.session_card(s, "updated", border=ui.T.ok))


@app.command("rm")
def remove(
    id: int = typer.Argument(..., help="Session # to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask."),
):
    """Delete a session."""
    store, _ = _load()
    s = store.get(id)
    if not s:
        _fail(f"No session #{id}.")
    _ensure_unlocked(store, s.week)
    ui.console.print(ui.session_card(s, f"delete #{s.id}?", border=ui.T.err))
    if not yes and not Confirm.ask("  Delete it?", default=False):
        raise typer.Exit()
    store.remove(id)
    store.save()
    ui.ok(f"Deleted #{id}.")


# ── viewing ──────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context):
    """No command: open the full-screen app (or just print the dashboard when not in a terminal)."""
    if ctx.invoked_subcommand is not None:
        return
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        _show_dashboard()
        return
    from .tui import run_tui
    run_tui()




def _show_dashboard(banner: bool = True, week: str | None = None) -> None:
    store, cfg = _load()
    if banner and cfg["ui"].get("banner", True):
        ui.console.print(Text(""), ui.banner(), Text(""))
    ui.console.print(ui.dashboard(store, report.build(store, cfg, parse_week(week)), cfg))
    run = store.running()
    if run and run.minutes() > 12 * 60:
        ui.warn(f"You've been clocked in for {fmt_hm(run.minutes())}. Forgot to clock out? "
                "[b]pnch out --at 5pm[/]")


@app.command()
def status(
    watch: bool = typer.Option(False, "--watch", "-W", help="Live-updating dashboard (ctrl-c to quit)."),
    week: Optional[str] = typer.Option(None, "--week", "-w", help=WEEK_HELP),
):
    """Dashboard: current shift + this week at a glance."""
    store, cfg = _load()
    monday = parse_week(week)
    show_banner = cfg["ui"].get("banner", True)
    if not watch:
        _show_dashboard(week=week)
        return
    try:
        with Live(console=ui.console, screen=True, auto_refresh=False) as live:
            while True:
                store = Store.load()
                live.update(Group(*([Text(""), ui.banner(), Text("")] if show_banner else []), ui.dashboard(store, report.build(store, cfg, monday), cfg, live=True),
                                  Text("  ctrl-c to quit", style=ui.T.faint)), refresh=True)
                _time.sleep(1)
    except KeyboardInterrupt:
        pass


@app.command("log")
def log_cmd(week: Optional[str] = typer.Option(None, "--week", "-w", help=WEEK_HELP)):
    """List a week's sessions with their #s (for edit / rm)."""
    store, cfg = _load()
    monday = parse_week(week)
    r = report.build(store, cfg, monday)
    if not r.days:
        ui.console.print(ui.panel(Text("nothing logged", style=ui.T.dim), f"week {fmt_md(r.monday)} – {fmt_md(r.sunday)}",
                                  subtitle=ui.status_chip(store, monday)))
        return
    ui.console.print(ui.panel(Group(ui.sessions_table(store, monday), Text(""), ui.totals_line(r)),
                              f"week {fmt_md(r.monday)} – {fmt_md(r.sunday)}",
                              subtitle=ui.status_chip(store, monday)))


@app.command()
def weeks(n: int = typer.Option(8, "--last", "-n", help="How many weeks back.")):
    """Overview of recent weeks and whether they're approved/exported."""
    from rich import box
    from rich.table import Table

    store, cfg = _load()
    t = Table(box=box.SIMPLE_HEAD, header_style=f"bold {ui.T.accent}", show_edge=False, pad_edge=False)
    for col, j in [("week", "left"), ("hours", "right"), ("billed", "right"), ("amount", "right"),
                   ("invoice", "right"), ("status", "left")]:
        t.add_column(col, justify=j)
    cur = week_start(date.today())
    keys = {cur - timedelta(weeks=i) for i in range(n)} | {s.week for s in store.sessions if s.week >= cur - timedelta(weeks=n)}
    for monday in sorted(keys, reverse=True)[:max(n, 1)]:
        r = report.build(store, cfg, monday)
        empty = not r.days
        style = ui.T.faint if empty else ui.T.text
        t.add_row(
            Text(f"{fmt_md(monday)} – {fmt_md(r.sunday)}", style=style),
            Text(fmt_hm(r.total_minutes) if not empty else "·", style=style),
            Text(fmt_hm(r.billed_minutes) if not empty else "", style=style),
            Text(fmt_money(r.amount) if not empty else "", style=ui.T.ok if not empty else style),
            Text(f"#{r.invoice_number}" if r.approved else "", style=ui.T.dim),
            ui.status_chip(store, monday) if not empty or r.approved else Text(""),
        )
    ui.console.print(ui.panel(t, "weeks"))


# ── preview / approve / export ───────────────────────────────────────────────

@app.command()
def preview(
    week: Optional[str] = typer.Option(None, "--week", "-w", help=WEEK_HELP),
    page: Optional[int] = typer.Option(None, "--page", "-p", help="Show just page N (bigger)."),
    open_: bool = typer.Option(False, "--open", "-o", help="Open in your PDF viewer instead of the terminal."),
):
    """See what the PDF will look like (watermarked until the week is approved)."""
    store, cfg = _load()
    monday = _pick_week(store, week)
    r = report.build(store, cfg, monday)
    if not r.days:
        _fail(f"Nothing logged for the week of {fmt_md(monday)}.")
    path = pdf.render(r, cfg, cache_dir() / f"preview-{monday.isoformat()}.pdf", preview=not r.approved)
    if not open_ and termimg.supports_inline_images():
        termimg.show_inline(path, [page] if page else None)
    elif sys.stdout.isatty() and not termimg.open_external(path):
        ui.warn("Couldn't find a PDF viewer.")
    ui.info(f"week {fmt_md(r.monday)} – {fmt_md(r.sunday)} · {fmt_hrmin(r.total_minutes)} · "
            f"billed {fmt_hrmin(r.billed_minutes)} · {fmt_money(r.amount)}"
            + ("" if r.approved else " · [i]not approved yet[/]"))
    ui.info(f"[dim]{path}[/]")


@app.command()
def approve(week: Optional[str] = typer.Option(None, "--week", "-w", help=WEEK_HELP)):
    """Review a week, confirm billed hours + invoice details, and lock it in."""
    store, cfg = _load()
    monday = _pick_week(store, week)
    if store.is_approved(monday):
        r = report.build(store, cfg, monday)
        ui.ok(f"The week of {fmt_md(monday)} is already approved (invoice #{r.invoice_number}). "
              "[b]pnch export[/] makes the PDF.")
        return
    run = store.running()
    if run and run.week == monday:
        _fail("You're still clocked in this week. [b]pnch out[/] first.")
    r = report.build(store, cfg, monday)
    if not r.days:
        _fail(f"Nothing logged for the week of {fmt_md(monday)}.")

    ui.console.print(ui.panel(Group(ui.sessions_table(store, monday), Text(""), ui.totals_line(r)),
                              f"review · week {fmt_md(r.monday)} – {fmt_md(r.sunday)}", subtitle=ui.status_chip(store, monday)))
    ui.info(f"Worked [b]{fmt_hrmin(r.total_minutes)}[/]. Billing rule '{cfg['invoice']['billing']}' "
            f"gives [b]{fmt_hrmin(r.billed_minutes)}[/].")

    billed = parse_hours(Prompt.ask("  Billed hours", default=fmt_hours_num(r.billed_minutes)))
    role = cfg["invoice"]["role"]
    summary = Prompt.ask(f"  Invoice line [dim](after '{role} -')[/]", default=r.summary or None) or ""
    number = IntPrompt.ask("  Invoice #", default=r.invoice_number)
    issued = parse_date(Prompt.ask("  Issued", default="today"))
    due = add_business_days(issued, int(cfg["invoice"]["due_business_days"]))
    rate = float(cfg["invoice"]["rate"])
    amount = round(rate * billed / 60, 2)

    ui.console.print(ui.panel(ui.kv(
        ("billed", fmt_hrmin(billed)),
        ("rate", f"{fmt_money(rate, cents=False)}/hr"),
        ("amount", Text(fmt_money(amount), style=f"bold {ui.T.ok}")),
        ("invoice", f"#{number}"),
        ("item", f"{role} -\n{summary}" if summary else role),
        ("issued", fmt_long(issued)),
        ("due", fmt_long(due)),
    ), "about to approve", border=ui.T.accent2, padding=(0, 2)))
    if Confirm.ask("  Look at the PDF first?", default=False):
        tmp = report.Report(**{**r.__dict__, "billed_minutes": billed, "summary": summary,
                               "invoice_number": number, "issued": issued, "due": due, "rate": rate})
        path = pdf.render(tmp, cfg, cache_dir() / f"preview-{monday.isoformat()}.pdf", preview=True)
        if termimg.supports_inline_images():
            termimg.show_inline(path)
        else:
            termimg.open_external(path)
    if not Confirm.ask(Text(f"  Approve and lock the week of {fmt_md(monday)}?", style=f"bold {ui.T.text}"), default=True):
        ui.info("Not approved. Nothing changed.")
        raise typer.Exit()

    store.weeks[monday.isoformat()] = {
        "approved_at": datetime.now().isoformat(timespec="seconds"),
        "total_minutes": r.total_minutes,
        "billed_minutes": billed,
        "rate": rate,
        "invoice_number": number,
        "summary": summary,
        "issued": issued.isoformat(),
        "due": due.isoformat(),
        "exports": [],
    }
    store.save()
    ui.ok(f"Approved and locked. Invoice #{number} · {fmt_money(amount)}")
    if Confirm.ask("  Export the PDF now?", default=True):
        export(week=monday.isoformat(), out=None, open_=False)


@app.command()
def unapprove(week: Optional[str] = typer.Option(None, "--week", "-w", help=WEEK_HELP)):
    """Unlock an approved week so you can edit it again."""
    store, _ = _load()
    monday = _pick_week(store, week)
    if not store.is_approved(monday):
        _fail(f"The week of {fmt_md(monday)} isn't approved.")
    if not Confirm.ask(f"  Unlock the week of {fmt_md(monday)}? (you'll need to approve it again)", default=False):
        raise typer.Exit()
    del store.weeks[monday.isoformat()]
    store.save()
    ui.ok("Unlocked.")


@app.command()
def export(
    week: Optional[str] = typer.Option(None, "--week", "-w", help=WEEK_HELP),
    out: Optional[Path] = typer.Option(None, "--out", help="Write the PDF here instead of the export dir."),
    open_: bool = typer.Option(False, "--open", "-o", help="Open it afterwards."),
):
    """Write the final PDF for an approved week."""
    store, cfg = _load()
    monday = _pick_week(store, week)
    if not store.is_approved(monday):
        _fail(f"The week of {fmt_md(monday)} isn't approved yet. "
              "Check it with [b]pnch preview[/], then run [b]pnch approve[/].")
    r = report.build(store, cfg, monday)
    path = (out.expanduser() if out else _export_path(cfg, r)).resolve()
    pdf.render(r, cfg, path, preview=False)
    store.weeks[monday.isoformat()].setdefault("exports", []).append(
        {"path": str(path), "at": datetime.now().isoformat(timespec="seconds")})
    store.save()
    ui.ok(f"Saved [b]{path}[/]")
    if open_:
        termimg.open_external(path)


# ── misc ─────────────────────────────────────────────────────────────────────

@app.command()
def undo(steps: int = typer.Argument(1, help="How many changes to undo.")):
    """Undo your last change (punch in/out, items, edits, approvals…)."""
    _load()
    from . import history
    for _ in range(max(1, steps)):
        label = history.undo()
        if label is None:
            ui.info("Nothing left to undo.")
            break
        ui.ok(f"Undid: {label}")


@app.command()
def redo(steps: int = typer.Argument(1, help="How many changes to redo.")):
    """Redo a change you just undid."""
    _load()
    from . import history
    for _ in range(max(1, steps)):
        label = history.redo()
        if label is None:
            ui.info("Nothing to redo.")
            break
        ui.ok(f"Redid: {label}")


@app.command()
def config(
    edit_: bool = typer.Option(False, "--edit", "-e", help="Open the config in $EDITOR."),
    path: bool = typer.Option(False, "--path", help="Just print where the files live."),
):
    """Show or edit your details (name, client, rate, theme…)."""
    _load()  # creates the file on first run
    f = config_file()
    if path:
        ui.console.print(f"config  {f}\ndata    {data_file()}\ncache   {cache_dir()}")
        return
    if edit_:
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or ("nano" if shutil.which("nano") else "vi")
        subprocess.call([editor, str(f)])
        try:
            config_mod.load()
            ui.ok("Config saved.")
        except Exception as e:  # noqa: BLE001
            ui.err(f"Config has a problem: {e}")
        return
    ui.console.print(ui.panel(Syntax(f.read_text(), "toml", theme="ansi_dark", background_color="default"),
                              "config", subtitle=Text(str(f), style=ui.T.dim), padding=(0, 1)))


@app.command()
def bar(json_: bool = typer.Option(False, "--json", help="Waybar-style JSON.")):
    """One-line status for your bar / prompt (waybar, polybar, tmux…)."""
    store = Store.load()
    run = store.running()
    week_min = sum(s.minutes() for s in store.in_week(week_start(date.today())))
    if run:
        h, m = divmod(run.minutes(), 60)
        text, cls = f"● {h}:{m:02d}", "running"
        tip = f"since {fmt_time(run.start)}" + (f" · {run.notes[-1]}" if run.notes else "")
    else:
        text, cls, tip = f"○ {fmt_hm(week_min)}", "idle", "off the clock"
    tip += f"\nthis week: {fmt_hm(week_min)}"
    if json_:
        print(json.dumps({"text": text, "tooltip": tip, "class": cls, "alt": cls}))
    else:
        print(text)


def run():
    try:
        app()
    except ParseError as e:
        ui.err(str(e))
        sys.exit(2)
