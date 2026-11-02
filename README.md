# ⏱ pnch

Clock in/out from the terminal, jot down what you did, and at the end of the week
approve it and export a log + invoice PDF.

Meet **Bucky**, the boxing beaver next to the ¡PNCH! banner. He naps while you're off the clock;
punch in and the fight bell wakes him up to punch down trees until you punch out
(turn him off with `mascot = false` under `[ui]`).

## Install

```sh
pipx install -e ~/projects/PunchDesk    # gives you the `pnch` command
pnch config --edit                      # set your name, address, client, rate, theme
```

## The app

Run `pnch` on its own for the full-screen app. Type commands in the **prompt bar** at the bottom:

| type | does |
| --- | --- |
| `in` / `in fixing the scraper` | punch in (timer, punch-in time and your item list appear) |
| `out` | punch out: shows what you did, asks "Did you do anything else not listed?", confirm times, save |
| `undo` / `redo` | take back your last change, or put it back (also `ctrl+z` / `ctrl+y`) |
| `/vday [day]` | view a day, with its total next to the date (`/vday yesterday`) |
| `/vweek [week]` | view the week's times (`/vweek last`) |
| `/previewLogs [week]` | preview the week's log + invoice PDF |
| `/exportLogs [week]` | save the PDF into your export folder (approves the week first if needed) |
| `/weeks` | calendar of all your weeks: ↑↓ to pick one, `p` preview · `e` export · `a` approve · `enter` open |
| `/config` | hourly rate, color theme (live preview), export folder, file-name style |
| `/help` | everything |

What you're working on goes in the separate **working on** box. `tab` switches between the
prompt bar → working on → today → week; `enter` on today or week opens it. In the working-on
box, `↑` jumps into the item list (`f2` rename, `delete` remove, `esc` back).

The status line under the prompt shows **● unsaved** while a block is in progress or you've typed
an item without adding it, and **✓ saved** otherwise. Everything is written to disk immediately; if
pnch closes unexpectedly while you're clocked in, the next launch tells you when it last saw you
and lets you keep the clock running or end the block at that time. Half-typed items come back too.

Shortcuts: `ctrl+s` punch in/out · `ctrl+n` working-on box · `ctrl+p` command palette (approve,
export, past blocks…) · `ctrl+q` quit · `f1` all the rest.

The day and week views end with a timeline bar showing when each block happened.
In the day view (`tab` to **today**, `enter`) pick a block and press `enter` to edit its descriptions.
Every `enter` saves right away: adding, renaming (`f2`) or removing (`delete`) a line, and changing a
finished block's times. `esc` just closes.

If a block's times overlap another block, pnch shows both and lets you **merge** them, **fit** the new
one into the free gap, **shorten** the other one, or **replace** it (or go back and change the times).

Quitting always asks first. Off the clock: "Are you sure? Everything will be saved." On the clock:
punch out (review and save the block, then quit) or stay clocked in (the clock keeps running while
pnch is closed). Anything typed in the working-on box is saved either way.

The layout adapts to the window: in narrow windows the side panels tuck away (today and week totals
move under the timer, `ctrl+b` brings them back) and the big timer switches to a compact one.

Every command below also works straight from your shell as `pnch <command>`.

## Day to day

```sh
pnch in fixing the scraper     # clock in (note is optional)
pnch note "checked VPN prefix list"
pnch out                       # asks what you did if there are no notes yet
pnch status                    # dashboard
pnch status -W                 # live dashboard with a ticking clock
```

Forgot to clock in or out?

```sh
pnch in --at 9:30am
pnch out --at 5:15pm
pnch add 10/14 11pm 12:12am getting manual leads together
pnch log                       # shows session #s
pnch edit 3                    # interactive edit (or --start/--end/--note)
pnch rm 3
pnch undo                      # take back the last change (pnch redo puts it back)
```

## End of the week

```sh
pnch preview                   # PDF preview inline (kitty/ghostty/wezterm) or in your viewer
pnch approve                   # review, confirm billed hours + invoice line, lock the week
pnch export                    # writes ~/Documents/pnch/logsweekM_D-M_D.pdf
```

`export` only works on approved weeks. Approved weeks are locked; `pnch unapprove` unlocks one.
Every week command takes `-w this | last | -2 | 10/14`.

## Extras

- `pnch weeks`: history with hours, amount, invoice # and status
- `pnch bar` / `pnch bar --json`: one-liner for waybar, polybar, tmux or your prompt
- Themes in config: `catppuccin`, `nord`, `gruvbox`, `tokyonight`, `rosepine`
- Files: `pnch config --path`. Set `PNCH_HOME=/some/dir` to sandbox everything.

Weeks run Monday–Sunday. A session that crosses midnight counts on the day it started.
Billed hours come from `invoice.billing` (`down` by default: 9h 20m → 9h), and you can override them at approval.
