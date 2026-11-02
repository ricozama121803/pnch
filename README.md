# ¡PNCH!

A terminal time clock. Punch in and out, jot down what you worked on, and at the end of the
week approve it and export a log + invoice PDF.

![pnch on the clock](docs/screenshots/main.svg)

Meet **Bucky**, the boxing beaver next to the banner. He naps while you're off the clock; punch
in and the fight bell wakes him up to punch down trees until you punch out.

![off the clock, Bucky asleep](docs/screenshots/off-the-clock.svg)

## Install

Needs Python 3.11+.

```sh
git clone https://github.com/ricozama121803/pnch.git
pipx install -e ./pnch          # gives you the `pnch` command
pnch config --edit              # your name, address, client, rate
```

Optional: `man pnch` after linking the man page:

```sh
mkdir -p ~/.local/share/man/man1 && ln -s "$PWD/pnch/man/pnch.1" ~/.local/share/man/man1/
```

## Using the app

Run `pnch` on its own. Commands go in the **prompt bar** at the bottom; what you're working on
goes in the **working on** box.

| type | does |
| --- | --- |
| `in` / `in fixing the scraper` | punch in: a timer, your punch-in time and your item list appear |
| `out` | punch out: shows what you did, asks "Did you do anything else not listed?", confirm the times |
| `undo` / `redo` | take back your last change, or put it back (also `ctrl+z` / `ctrl+y`) |
| `/vday [day]` | view a day: blocks, total and a timeline (`/vday yesterday`) |
| `/vweek [week]` | view a week's times with a timeline per day (`/vweek last`) |
| `/weeks` | calendar of all your weeks: preview, export or approve any of them |
| `/previewLogs [week]` | preview the log + invoice PDF |
| `/exportLogs [week]` | save the PDF to your export folder (approves the week first if needed) |
| `/config` | hourly rate, color theme, export folder, file-name style |
| `/help` | everything |

Typing `/` opens a menu: `↑` `↓` to pick, `tab` to complete, `enter` to run.

![the slash menu](docs/screenshots/slash-menu.svg)

### Punching out

`out` (or `ctrl+s`) shows the block, what you listed, and asks if you did anything else.
Each line you add is saved as soon as you press `enter`; an empty `enter` punches out.
`esc` keeps you on the clock. Punch in and out as many times a day as you like.

![punching out](docs/screenshots/punch-out.svg)

### Days and weeks

`tab` cycles prompt bar → working on → **today** → **week**; `enter` on a panel opens it.
In a day, `enter` on a block edits it (times and descriptions, every `enter` saves), and the
last row, **+ add a block**, adds one. `[` `]` flip between days or weeks.

![a day](docs/screenshots/day.svg)
![a week](docs/screenshots/week.svg)

### Picking a week

`/weeks` shows every week as a calendar row with its hours and status. `↑` `↓` to pick,
`p` preview, `e` export, `a` approve, `enter` to open it.

![the week picker](docs/screenshots/weeks.svg)

### Overlapping blocks

If a block's times overlap another one, pnch shows both and offers the fixes that make sense:
merge them, fit the new one into the free gap, shorten the other one, or replace it.

![fixing an overlap](docs/screenshots/overlap.svg)

### Settings

`/config` sets your hourly rate, theme (live preview: catppuccin, nord, gruvbox, tokyonight,
rosepine), export folder and file-name style. Everything else (name, address, client, billing
rule) lives in the config file: `ctrl+o` there, or `pnch config --edit`.

![config](docs/screenshots/config.svg)

### Keys

| key | does |
| --- | --- |
| `tab` | switch between prompt bar, working on, today, week |
| `ctrl+s` | punch in / punch out |
| `ctrl+n` | jump to the working-on box |
| `ctrl+z` / `ctrl+y` | undo / redo |
| `ctrl+p` | command palette: approve, export, past blocks, … |
| `ctrl+q` | quit: always asks; on the clock you can punch out or keep the clock running |
| `f1` | every shortcut |

### Saving and crashes

Everything is written to disk the moment you press `enter`. The status line says
**● on the clock** while a block is running, **● unsaved** only when you've typed an item but
not pressed `enter` yet, and **✓ saved** otherwise. If pnch closes unexpectedly while you're
clocked in, the next launch tells you when it last saw you and lets you keep the clock running
or end the block then. Half-typed items come back too, and a damaged data file is restored from
its backup.

## The PDF

Approving a week locks it and fixes the billed hours (by default worked time rounded down to
whole hours: 9h 20m → 9h; you can change it while approving). The export is two pages:

| log | invoice |
| --- | --- |
| ![log page](docs/screenshots/pdf-log.png) | ![invoice page](docs/screenshots/pdf-invoice.png) |

Until a week is approved, previews are watermarked **PREVIEW**.

## From the shell

Every action also works as `pnch <command>`, which is handy for scripts and status bars.

```sh
pnch in fixing the scraper          # clock in (the item is optional)
pnch note "checked VPN prefix list"
pnch out --at 5:15pm                # forgot to clock out
pnch add 10/14 11pm 12:12am pulled the leads list together
pnch log                            # this week's blocks with their #s
pnch edit 3                         # or --start / --end / --note
pnch rm 3
pnch undo                           # pnch redo puts it back

pnch preview -w last                # PDF inline (kitty/Ghostty/WezTerm) or in your viewer
pnch approve -w last                # confirm billed hours + invoice line, lock the week
pnch export -w last                 # write the PDF to your export folder
pnch unapprove -w last              # unlock a week to edit it

pnch weeks                          # hours, invoice # and status per week
pnch status -W                      # live dashboard
pnch bar --json                     # one-liner for waybar / polybar / tmux
```

Weeks: `-w this | last | -2 | 10/14`. Days: `today`, `yesterday`, `tue`, `10/14`, `2026-10-14`.
Times: `9`, `9am`, `9:30pm`, `930pm`, `21:30`. Weeks run Monday–Sunday, and a block that runs
past midnight counts on the day it started. See `man pnch` for everything.

## Files

| | |
| --- | --- |
| `~/.config/pnch/config.toml` | your details, rate, theme, export settings |
| `~/.local/share/pnch/data.json` | the log (plus a `.bak` and undo history) |
| `~/Documents/pnch/` | exported PDFs (change it in `/config`) |

`pnch config --path` prints them. Set `PNCH_HOME=/some/folder` to keep everything in one place.

## Development

```sh
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q             # 121 tests, each in its own temp folder
.venv/bin/python scripts/screenshots.py   # regenerate the screenshots above
```

The tests cover odd times and dates, overlapping blocks, locked weeks, undo/redo, damaged data
files, export file names, multi-page PDFs, and the app itself driven with real key presses.
