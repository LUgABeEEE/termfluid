#!/usr/bin/env python3
"""termfluid -- an interactive ASCII liquid you can push around with the mouse.

A pure-standard-library terminal program.  Particles are pulled down by
gravity and pushed away from the pointer; their local density is drawn with
ASCII characters (- + = % # @ ...).  The liquid starts as a slab at the top
of the screen and falls / splashes / pools at the bottom.

Run:
    python3 termfluid.py            # interactive
    python3 termfluid.py --demo     # automatic pointer, good for recording
    python3 termfluid.py --headless 180 --width 100 --height 30

Keys:
    mouse                 push the liquid  (terminal must report mouse motion)
    arrows / WASD         move the force centre without a mouse
    click                 splash
    wheel                 stronger / weaker force
    space                 pause
    g                     toggle gravity
    r                     reset the liquid to the top
    c                     show / hide the force-centre ring
    q / Esc / Ctrl-C      quit
"""

from __future__ import annotations

import argparse
import collections
import math
import os
import select
import signal
import sys
import time

try:
    import termios
    import tty
except ImportError:  # native Windows: no POSIX terminal layer
    termios = None
    tty = None

from fluid import Fluid
from inputparser import InputParser

VERSION = "1.0"
MIN_WIDTH = 20
MIN_ROWS = 8
SIM_DT = 1.0 / 60.0

ESC = "\x1b"
ALT_ON = ESC + "[?1049h"
ALT_OFF = ESC + "[?1049l"
CURSOR_HIDE = ESC + "[?25l"
CURSOR_SHOW = ESC + "[?25h"
CLEAR = ESC + "[2J" + ESC + "[H"
MOUSE_ON = ESC + "[?1000h" + ESC + "[?1002h" + ESC + "[?1003h" + ESC + "[?1006h"
MOUSE_OFF = ESC + "[?1003l" + ESC + "[?1002l" + ESC + "[?1000l" + ESC + "[?1006l"


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def terminal_size():
    try:
        size = os.get_terminal_size(1)
        return max(1, size.columns), max(1, size.lines)
    except OSError:
        try:
            size = os.get_terminal_size(0)
            return max(1, size.columns), max(1, size.lines)
        except OSError:
            return 80, 24


class Terminal:
    """Raw-mode alternate-screen terminal with SGR mouse reporting."""

    def __init__(self, mouse=True, raw=True):
        self.mouse = mouse
        self.raw = raw
        self.prev = None
        self.old_attrs = None
        self.active = False

    def __enter__(self):
        try:
            if self.raw:
                self.old_attrs = termios.tcgetattr(0)
                tty.setraw(0)
            self.active = True
            seq = ALT_ON + CURSOR_HIDE + CLEAR
            if self.mouse:
                seq += MOUSE_ON
            _write_all(1, seq.encode("ascii", "ignore"))
            return self
        except BaseException:
            if self.old_attrs is not None:
                termios.tcsetattr(0, termios.TCSADRAIN, self.old_attrs)
                self.old_attrs = None
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            seq = (MOUSE_OFF if self.mouse else "") + CURSOR_SHOW + ALT_OFF
            _write_all(1, seq.encode("ascii", "ignore"))
        finally:
            if self.old_attrs is not None:
                termios.tcsetattr(0, termios.TCSADRAIN, self.old_attrs)
            self.active = False

    def invalidate(self):
        self.prev = None
        _write_all(1, ("\x1b[2J\x1b[H").encode())

    def draw(self, lines):
        w = len(lines[0]) if lines else 0
        out = []
        if self.prev is None:
            out.append("\x1b[H\x1b[2J")
            prev = [None] * len(lines)
        else:
            prev = self.prev
            if len(prev) != len(lines):
                out.append("\x1b[2J\x1b[H")
                prev = [None] * len(lines)
        for i, line in enumerate(lines):
            if i < len(prev) and prev[i] == line:
                continue
            out.append("\x1b[{};1H".format(i + 1))
            out.append(line)
            out.append("\x1b[K")
        if out:
            _write_all(1, "".join(out).encode("utf-8", "ignore"))
        self.prev = list(lines)
        return w


def make_status(width, fluid, fps, paused, demo, mouse_coords, cursor_on, message):
    """Build the one-line status bar.  The quit key is kept early so that it
    survives truncation in narrow terminals; optional hints are only appended
    when they fit completely."""
    flags = []
    if paused:
        flags.append("PAUSED")
    if not fluid.gravity_on:
        flags.append("NO GRAVITY")
    if demo:
        flags.append("DEMO")
    if cursor_on:
        flags.append("RING")
    left = " termfluid"
    if flags:
        left += " [" + "][".join(flags) + "]"
    controls = "  q:quit  space:pause  r:reset  g:gravity"
    extra = "  c:ring  wheel:force"
    right = "  {:3.0f}fps {:4d}p".format(fps, len(fluid.px))
    if mouse_coords and width >= 92:
        right += "  mouse {},{}".format(mouse_coords[0], mouse_coords[1])
    text = left + controls + extra + right
    if message and len(text) + 2 + len(message) <= width:
        text += "  " + message
    return text[:width].ljust(width)


def draw_ring(lines, mouse, width, height):
    if not mouse:
        return lines
    mx = int(mouse[0])
    my = int(mouse[1] / 2.0)
    radius = 3
    marks = set()
    for angle in range(0, 360, 30):
        x = int(round(mx + radius * math.cos(math.radians(angle))))
        y = int(round(my + (radius / 2.0) * math.sin(math.radians(angle))))
        if 0 <= x < width and 0 <= y < height:
            marks.add((x, y))
    rows = [list(line) for line in lines]
    for x, y in marks:
        rows[y][x] = "o"
    return ["".join(row) for row in rows]


def demo_target(width, height, t):
    cx = width * (0.5 + 0.32 * math.sin(t * 0.9))
    cy = height * (0.62 + 0.20 * math.sin(t * 1.37 + 0.7))
    return cx, cy


def run_headless(args):
    width = 100 if args.width is None else args.width
    height = 30 if args.height is None else args.height
    fluid = Fluid(
        width,
        height,
        particles=args.particles,
        seed=args.seed,
        gravity=args.gravity,
        mouse_strength=args.force,
        mouse_radius=args.radius,
    )
    steps = max(0, args.headless)
    for i in range(steps):
        if args.demo:
            t = i * SIM_DT
            cx, cy = demo_target(width, height, t)
            fluid.set_mouse(cx, cy)
            if i and i % 180 == 0:
                fluid.click()
        fluid.step(SIM_DT)
    print("\n".join(fluid.render()))
    stats = fluid.stats()
    print(
        "# particles={n} mean_y={mean_y_frac:.3f} max_speed={max_speed:.1f} "
        "nan={nan} outside={outside}".format(**stats),
        file=sys.stderr,
    )
    return 0


def run_interactive(args):
    if termios is None or tty is None:
        print(
            "termfluid: native Windows is not supported; run it inside WSL or over SSH. "
            "stdout/stdin must be a terminal.",
            file=sys.stderr,
        )
        return 2
    tty_input = sys.stdin.isatty()
    if not (tty_input or args.pipe_input) or not sys.stdout.isatty():
        print(
            "termfluid: stdout must be a terminal (and stdin a terminal unless --pipe-input).\n"
            "Try it from a real terminal, or use --headless for a static frame.",
            file=sys.stderr,
        )
        return 2

    snapshot_lines = None
    with Terminal(mouse=(not args.no_mouse) and tty_input, raw=tty_input) as term:
        cols, rows = terminal_size()
        fluid = Fluid(
            cols,
            max(MIN_ROWS - 1, rows - 1),
            particles=args.particles,
            seed=args.seed,
            gravity=args.gravity,
            mouse_strength=args.force,
            mouse_radius=args.radius,
        )
        parser = InputParser()
        paused = False
        running = True
        demo = bool(args.demo)
        demo_t = 0.0
        cursor_on = False
        message = ""
        message_until = 0.0
        hint_until = time.monotonic() + 6.0
        mouse_coords = None
        acc = 0.0
        last_frame = time.monotonic()
        next_frame = last_frame
        fps = float(args.fps)
        fps_smooth = fps
        frame_times = collections.deque(maxlen=30)
        prev_size = (cols, rows)
        started = time.monotonic()

        old_handlers = {}

        def stop_on_signal(signum, frame):
            nonlocal running
            running = False

        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            try:
                old_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, stop_on_signal)
            except (OSError, ValueError):
                pass

        def flash(text, seconds=1.8):
            nonlocal message, message_until
            message = text
            message_until = time.monotonic() + seconds

        def handle(event):
            nonlocal paused, running, demo, cursor_on, mouse_coords
            kind = event[0]
            if kind == "mouse":
                col, row = event[1], event[2]
                col = max(0, min(cols - 1, col))
                row = max(0, min(rows - 1, row))
                mouse_coords = (col, row)
                demo = False
                fluid.set_mouse(col, row)
            elif kind == "click":
                col, row, button = event[1], event[2], event[3]
                col = max(0, min(cols - 1, col))
                row = max(0, min(rows - 1, row))
                mouse_coords = (col, row)
                demo = False
                fluid.set_mouse(col, row)
                if button == 0:
                    fluid.click()
            elif kind == "wheel":
                col, row, delta = event[1], event[2], event[3]
                col = max(0, min(cols - 1, col))
                row = max(0, min(rows - 1, row))
                mouse_coords = (col, row)
                fluid.mouse_strength = max(60.0, min(1200.0, fluid.mouse_strength + delta * 40.0))
                flash("force {:d}".format(int(fluid.mouse_strength)))
            elif kind == "key":
                key = event[1]
                if key in ("q", "esc", "ctrl-c"):
                    running = False
                elif key == "space":
                    paused = not paused
                    flash("paused" if paused else "resumed")
                elif key == "r":
                    fluid.reset()
                    mouse_coords = None
                    term.invalidate()
                    flash("reset - liquid back at the top")
                elif key == "g":
                    fluid.toggle_gravity()
                    flash("gravity off" if not fluid.gravity_on else "gravity on")
                elif key == "c":
                    cursor_on = not cursor_on
                    flash("force ring on" if cursor_on else "force ring off")
                elif key in ("+", "="):
                    fluid.mouse_strength = min(1200.0, fluid.mouse_strength + 40.0)
                    flash("force {:d}".format(int(fluid.mouse_strength)))
                elif key in ("-", "_"):
                    fluid.mouse_strength = max(60.0, fluid.mouse_strength - 40.0)
                    flash("force {:d}".format(int(fluid.mouse_strength)))
                elif key in ("up", "down", "left", "right", "w", "a", "s", "d"):
                    if key in ("up", "w"):
                        fluid.move_force_center(0, -1)
                    elif key in ("down", "s"):
                        fluid.move_force_center(0, 1)
                    elif key in ("left", "a"):
                        fluid.move_force_center(-1, 0)
                    elif key in ("right", "d"):
                        fluid.move_force_center(1, 0)
                    demo = False
                    if fluid.mouse is not None:
                        mouse_coords = (
                            max(0, min(cols - 1, int(fluid.mouse[0]))),
                            max(0, min(rows - 1, int(fluid.mouse[1] / 2.0))),
                        )
                elif key == "ctrl-l":
                    term.invalidate()

        while running:
            now = time.monotonic()
            if args.duration is not None and now - started >= args.duration:
                running = False
                break
            timeout = max(0.0, next_frame - now)
            try:
                readable, _, _ = select.select([0], [], [], timeout)
            except InterruptedError:
                readable = []
            if readable:
                try:
                    data = os.read(0, 8192)
                except OSError:
                    data = b""
                if not data:
                    running = False
                else:
                    for event in parser.feed(data):
                        handle(event)
            for event in parser.flush_escape():
                handle(event)

            now = time.monotonic()
            frame_dt = min(0.25, now - last_frame)
            last_frame = now
            frame_times.append(now)
            if len(frame_times) >= 2:
                span = frame_times[-1] - frame_times[0]
                if span >= 0.05:
                    fps_smooth = (len(frame_times) - 1) / span

            size = terminal_size()
            cols, rows = size
            if size != prev_size:
                prev_size = size
                if cols < MIN_WIDTH or rows < MIN_ROWS:
                    pass
                else:
                    term.invalidate()
                    fluid.resize(cols, rows - 1)
                    flash("resized - liquid reset")

            if rows >= MIN_ROWS and cols >= MIN_WIDTH:
                if demo:
                    demo_t += frame_dt
                    cx, cy = demo_target(cols, rows - 1, demo_t)
                    fluid.set_mouse(cx, cy)
                    if int(demo_t / 3.0) != int((demo_t - frame_dt) / 3.0):
                        fluid.click()
                    mouse_coords = (int(cx), int(cy))
                if not paused:
                    acc += frame_dt
                    steps = 0
                    while acc >= SIM_DT and steps < 3:
                        fluid.step(SIM_DT)
                        acc -= SIM_DT
                        steps += 1
                    if steps == 3:
                        acc = min(acc, SIM_DT)
                else:
                    acc = 0.0

                lines = fluid.render()
                if cursor_on and fluid.mouse is not None:
                    lines = draw_ring(lines, fluid.mouse, cols, rows - 1)
                hint = ""
                if time.monotonic() < hint_until:
                    hint = "move the mouse to push the liquid"
                current_message = message if time.monotonic() < message_until else hint
                status_text = make_status(
                    cols,
                    fluid,
                    fps_smooth,
                    paused,
                    demo,
                    mouse_coords,
                    cursor_on,
                    current_message,
                )
                term.draw(lines + ["\x1b[7m" + status_text + "\x1b[0m"])
                snapshot_lines = lines + [status_text]
            else:
                msg = "terminal too small (need {}x{})".format(MIN_WIDTH, MIN_ROWS)
                line = msg[:cols].ljust(cols)
                term.draw([line])
                snapshot_lines = [line]

            next_frame += 1.0 / max(10.0, fps)
            if next_frame < now - 0.05:
                next_frame = now + 1.0 / max(10.0, fps)

    for sig, handler in old_handlers.items():
        try:
            signal.signal(sig, handler)
        except (OSError, ValueError):
            pass

    if args.snapshot and snapshot_lines is not None:
        try:
            with open(args.snapshot, "w", encoding="utf-8") as handle:
                handle.write("\n".join(snapshot_lines) + "\n")
        except OSError as exc:
            print("termfluid: could not write snapshot: {}".format(exc), file=sys.stderr)
    return 0


def _positive_int(text):
    """argparse type: a whole number >= 1 (rejects 0, negatives and junk)."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected an integer, got {!r}".format(text))
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1, got {}".format(value))
    return value


def build_parser():
    p = argparse.ArgumentParser(
        prog="termfluid",
        description="Interactive ASCII liquid: gravity pulls it down, your mouse pushes it away.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--fps", type=float, default=60.0, help="target frame rate")
    p.add_argument("--particles", type=int, default=None, help="number of particles (auto by terminal area)")
    p.add_argument("--seed", type=int, default=1234, help="random seed")
    p.add_argument("--gravity", type=float, default=25.0, help="gravity strength in cells/s^2")
    p.add_argument("--force", type=float, default=240.0, help="mouse repulsion strength")
    p.add_argument("--radius", type=float, default=14.0, help="mouse force radius (simulation units; 2 units = 1 row)")
    p.add_argument("--demo", action="store_true", help="automatic moving force centre (no mouse needed)")
    p.add_argument("--duration", type=float, metavar="SECONDS", help="quit automatically after SECONDS (for recordings/tests)")
    p.add_argument("--snapshot", metavar="FILE", help="write the final ASCII frame and status line to FILE on exit")
    p.add_argument("--pipe-input", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--no-mouse", action="store_true", help="do not enable terminal mouse reporting")
    p.add_argument("--headless", type=int, metavar="STEPS", help="simulate STEPS then print one ASCII frame")
    p.add_argument("--width", type=_positive_int, metavar="COLS", help="width for --headless")
    p.add_argument("--height", type=_positive_int, metavar="ROWS", help="height for --headless")
    p.add_argument("--version", action="version", version="termfluid " + VERSION)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.fps <= 0:
        args.fps = 60.0
    if args.headless is not None:
        return run_headless(args)
    return run_interactive(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
