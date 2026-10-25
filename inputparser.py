"""Terminal input decoding for termfluid.

The terminal is put into SGR mouse reporting mode (xterm 1003 + 1006), so a
mouse position arrives as:

    ESC [ < Cb ; Cx ; Cy M      (press / motion)
    ESC [ < Cb ; Cx ; Cy m      (release)

Legacy X10 reports (ESC [ M + 3 bytes) are accepted too.  The parser is a
stream parser: sequences may be split across reads at any point.
"""

from __future__ import annotations

import time

ESC = 0x1B


class InputParser:
    def __init__(self):
        self.buf = b""
        self._esc_since = None

    def feed(self, data, now=None):
        """Consume raw bytes and return a list of input events.

        Events:
            ("key", name)              arrows, space, q, r, ...
            ("mouse", col, row)        pointer moved / was reported
            ("click", col, row, button)
            ("wheel", col, row, delta)
        """
        if now is None:
            now = time.monotonic()
        self.buf += data
        events = []
        while self.buf:
            buf = self.buf

            if buf[0] != ESC:
                self.buf = buf[1:]
                self._esc_since = None
                event = self._plain_byte(buf[0])
                if event:
                    events.append(event)
                continue

            # ESC ...
            if len(buf) == 1:
                if self._esc_since is None:
                    self._esc_since = now
                break
            nxt = buf[1]

            if nxt == ord("["):
                self._esc_since = None
                # ---- SGR mouse
                if buf.startswith(b"\x1b[<"):
                    end = -1
                    for i in range(3, len(buf)):
                        if buf[i] == ord("M") or buf[i] == ord("m"):
                            end = i
                            break
                    if end < 0:
                        if len(buf) > 64:       # garbage guard
                            self.buf = buf[1:]
                            continue
                        break
                    seq = buf[: end + 1]
                    self.buf = buf[end + 1 :]
                    event = self._parse_sgr(seq)
                    if event:
                        events.append(event)
                    continue
                # ---- legacy X10 mouse
                if buf.startswith(b"\x1b[M"):
                    if len(buf) < 6:
                        break
                    seq = buf[:6]
                    self.buf = buf[6:]
                    event = self._parse_x10(seq)
                    if event:
                        events.append(event)
                    continue
                # ---- generic CSI (arrow keys, focus events, ...)
                end = None
                for i in range(2, len(buf)):
                    if 0x40 <= buf[i] <= 0x7E:
                        end = i
                        break
                if end is None:
                    if len(buf) > 64:
                        self.buf = buf[1:]
                        continue
                    break
                seq = buf[: end + 1]
                self.buf = buf[end + 1 :]
                event = self._parse_csi(seq)
                if event:
                    events.append(event)
                continue

            if nxt == ord("O"):
                self._esc_since = None
                if len(buf) < 3:
                    break
                seq = buf[:3]
                self.buf = buf[3:]
                event = self._parse_ss3(seq)
                if event:
                    events.append(event)
                continue

            # A lone ESC followed by something that is not a sequence.
            self._esc_since = None
            self.buf = buf[1:]
            events.append(("key", "esc"))

        return events

    def flush_escape(self, now=None):
        """Emit ESC once it is clear that no sequence is following it."""
        if self.buf != b"\x1b":
            return []
        if now is None:
            now = time.monotonic()
        if self._esc_since is None:
            self._esc_since = now
        if now - self._esc_since >= 0.04:
            self.buf = b""
            self._esc_since = None
            return [("key", "esc")]
        return []

    # ------------------------------------------------------------- internals
    @staticmethod
    def _plain_byte(byte):
        if byte == 0x03:
            return ("key", "ctrl-c")
        if byte == 0x0C:
            return ("key", "ctrl-l")
        if byte in (0x0D, 0x0A):
            return None
        if 0x20 <= byte < 0x7F:
            char = chr(byte).lower()
            if char == " ":
                return ("key", "space")
            return ("key", char)
        return None

    @staticmethod
    def _parse_sgr(seq):
        final = seq[-1:]
        try:
            body = seq[3:-1].decode("ascii")
            cb_s, cx_s, cy_s = body.split(";")
            cb, cx, cy = int(cb_s), int(cx_s), int(cy_s)
        except (ValueError, UnicodeDecodeError):
            return None
        if cx < 1 or cy < 1:
            return None
        col, row = cx - 1, cy - 1
        button = cb & 3
        wheel = bool(cb & 64)
        motion = bool(cb & 32)
        pressed = final == b"M"
        if wheel:
            return ("wheel", col, row, 1 if button == 0 else -1)
        if pressed and not motion and button < 3:
            return ("click", col, row, button)
        return ("mouse", col, row)

    @staticmethod
    def _parse_x10(seq):
        if len(seq) != 6:
            return None
        cb = seq[3] - 32
        cx = seq[4] - 32
        cy = seq[5] - 32
        if cx < 1 or cy < 1:
            return None
        col, row = cx - 1, cy - 1
        button = cb & 3
        wheel = bool(cb & 64)
        if wheel:
            return ("wheel", col, row, 1 if button == 0 else -1)
        # X10 only reports presses; button 3 is the release marker.
        if button < 3:
            return ("click", col, row, button)
        return ("mouse", col, row)

    @staticmethod
    def _parse_csi(seq):
        final = seq[-1:]
        if final == b"A":
            return ("key", "up")
        if final == b"B":
            return ("key", "down")
        if final == b"C":
            return ("key", "right")
        if final == b"D":
            return ("key", "left")
        if final == b"H":
            return ("key", "home")
        if final == b"F":
            return ("key", "end")
        return None

    @staticmethod
    def _parse_ss3(seq):
        final = seq[-1:]
        return {
            b"A": ("key", "up"),
            b"B": ("key", "down"),
            b"C": ("key", "right"),
            b"D": ("key", "left"),
        }.get(final)
