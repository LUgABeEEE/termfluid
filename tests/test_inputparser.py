import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inputparser import InputParser


class InputParserTests(unittest.TestCase):
    def test_sgr_mouse_motion(self):
        parser = InputParser()
        events = parser.feed(b"\x1b[<35;50;15M", now=0.0)
        self.assertEqual(events, [("mouse", 49, 14)])

    def test_sgr_left_click_and_release(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b[<0;10;5M"), [("click", 9, 4, 0)])
        self.assertEqual(parser.feed(b"\x1b[<0;10;5m"), [("mouse", 9, 4)])

    def test_sgr_right_and_middle_click(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b[<2;3;4M"), [("click", 2, 3, 2)])
        self.assertEqual(parser.feed(b"\x1b[<1;3;4M"), [("click", 2, 3, 1)])

    def test_sgr_wheel(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b[<64;3;4M"), [("wheel", 2, 3, 1)])
        self.assertEqual(parser.feed(b"\x1b[<65;3;4M"), [("wheel", 2, 3, -1)])

    def test_drag_is_still_a_position(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b[<32;7;8M"), [("mouse", 6, 7)])

    def test_split_mouse_sequence(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b[<3"), [])
        self.assertEqual(parser.feed(b"5;50;15Mabc"), [("mouse", 49, 14), ("key", "a"), ("key", "b"), ("key", "c")])

    def test_legacy_x10_mouse(self):
        parser = InputParser()
        events = parser.feed(b"\x1b[M" + bytes([32 + 0, 32 + 10, 32 + 5]))
        self.assertEqual(events, [("click", 9, 4, 0)])

    def test_arrow_keys(self):
        parser = InputParser()
        self.assertEqual(
            parser.feed(b"\x1b[A\x1b[B\x1b[C\x1b[D"),
            [("key", "up"), ("key", "down"), ("key", "right"), ("key", "left")],
        )

    def test_application_arrows(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1bOA\x1bOD"), [("key", "up"), ("key", "left")])

    def test_plain_keys(self):
        parser = InputParser()
        self.assertEqual(
            parser.feed(b"qQ+- \x03"),
            [("key", "q"), ("key", "q"), ("key", "+"), ("key", "-"), ("key", "space"), ("key", "ctrl-c")],
        )

    def test_lone_escape_needs_a_grace_period(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b", now=0.0), [])
        self.assertEqual(parser.flush_escape(now=0.01), [])
        self.assertEqual(parser.flush_escape(now=0.1), [("key", "esc")])

    def test_escape_followed_by_key_is_not_a_sequence(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1bx"), [("key", "esc"), ("key", "x")])

    def test_unknown_csi_is_ignored(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b[?1;2c"), [])
        self.assertEqual(parser.feed(b"\x1b[I"), [])

    def test_invalid_mouse_numbers_are_ignored(self):
        parser = InputParser()
        self.assertEqual(parser.feed(b"\x1b[<0;abc;4M"), [])
        self.assertEqual(parser.feed(b"\x1b[<0;0;4M"), [])

    def test_garbage_guard_does_not_hang(self):
        parser = InputParser()
        parser.feed(b"\x1b[<" + b"9" * 100)
        self.assertLessEqual(len(parser.buf), 100)


if __name__ == "__main__":
    unittest.main()
