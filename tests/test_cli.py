"""The `pnch <command>` CLI when people use it in the wrong order or with bad input."""
import os
import subprocess
import sys

from typer.testing import CliRunner

from pnch.cli import app
from pnch.store import Store
from tests.conftest import MON

runner = CliRunner()


def pnch(*args, input=None):
    return runner.invoke(app, list(args), input=input)


def test_clock_in_twice_is_refused():
    assert pnch("in", "--at", "10/14/26 9am", "first").exit_code == 0
    r = pnch("in", "--at", "10/14/26 10am")
    assert r.exit_code == 1 and "Already on the clock" in r.output
    assert len(Store.load().sessions) == 1


def test_clock_out_without_clocking_in():
    r = pnch("out")
    assert r.exit_code == 1 and "not clocked in" in r.output


def test_clock_out_before_the_start_is_refused():
    pnch("in", "--at", "10/14/26 9am")
    r = pnch("out", "--at", "10/14/26 8am")
    assert r.exit_code == 1 and Store.load().running() is not None


def test_clock_out_past_midnight_rolls_to_the_next_day():
    pnch("in", "--at", "10/14/26 11pm")
    assert pnch("out", "--at", "12:30am", "late fix").exit_code == 0
    s = Store.load().sessions[0]
    assert s.end.day == 15 and s.minutes() == 90 and s.notes == ["late fix"]


def test_add_rejects_future_and_overlapping_blocks():
    r = pnch("add", "today", "11:58pm", "11:59pm", "x")
    assert r.exit_code == 1 or "future" in r.output   # (fine either way if the test runs at 11:59pm)
    assert pnch("add", "10/14/26", "9am", "10am", "a").exit_code == 0
    r = pnch("add", "10/14/26", "9:30am", "11am", "b")
    assert r.exit_code == 1 and "overlaps" in r.output


def test_add_crossing_midnight():
    assert pnch("add", "10/14/26", "11pm", "12:12am", "leads").exit_code == 0
    assert Store.load().sessions[0].minutes() == 72


def test_note_with_nothing_logged():
    r = pnch("note", "hello")
    assert r.exit_code == 1 and "No session" in r.output


def test_locked_week_cannot_be_edited_or_deleted():
    pnch("add", "10/14/26", "9am", "10am", "a")
    st = Store.load()
    st.weeks[MON.isoformat()] = {"billed_minutes": 60, "rate": 25.0, "invoice_number": 1, "summary": "",
                                 "issued": "2026-10-20", "due": "2026-11-07", "exports": []}
    st.save()
    for args in (["edit", "1", "--end", "11am"], ["rm", "1", "-y"], ["add", "10/15/26", "9am", "10am", "b"],
                 ["note", "--id", "1", "more"]):
        r = pnch(*args)
        assert r.exit_code == 1 and "locked" in r.output, args
    assert Store.load().sessions[0].notes == ["a"]


def test_export_needs_approval_first():
    pnch("add", "10/14/26", "9am", "10am", "a")
    r = pnch("export", "-w", "10/14/26")
    assert r.exit_code == 1 and "isn't approved" in r.output


def test_cannot_approve_while_clocked_in_that_week():
    pnch("in", "--at", "10/14/26 9am")
    r = pnch("approve", "-w", "10/14/26")
    assert r.exit_code == 1 and "still clocked in" in r.output


def test_undo_redo_from_the_cli():
    assert "Nothing left to undo" in pnch("undo").output
    pnch("add", "10/14/26", "9am", "10am", "a")
    assert "Undid: add block" in pnch("undo").output
    assert Store.load().sessions == []
    assert "Redid" in pnch("redo").output
    assert len(Store.load().sessions) == 1


def test_bad_time_gives_a_friendly_message_not_a_traceback(home):
    env = {**os.environ, "PNCH_HOME": str(home)}
    r = subprocess.run([sys.executable, "-m", "pnch", "add", "today", "25pm", "1pm"], env=env,
                       capture_output=True, text=True)
    assert r.returncode == 2 and "bad hour" in r.stdout + r.stderr and "Traceback" not in r.stderr


def test_plain_pnch_without_a_terminal_prints_the_dashboard():
    r = pnch()
    assert r.exit_code == 0 and "OFF THE CLOCK" in r.output
