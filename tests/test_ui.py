import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import termfluid
from fluid import Fluid


class UiHelperTests(unittest.TestCase):
    def setUp(self):
        self.fluid = Fluid(80, 24, seed=1)

    def test_status_fits_and_keeps_quit_visible(self):
        text = termfluid.make_status(80, self.fluid, 60, False, False, None, False, "")
        self.assertEqual(len(text), 80)
        self.assertIn("q:quit", text)
        self.assertTrue(text.startswith(" termfluid"))

    def test_status_optional_fields_only_when_they_fit(self):
        wide = termfluid.make_status(
            160, self.fluid, 42, True, True, (10, 20), True, "move the mouse to push the liquid"
        )
        self.assertIn("PAUSED", wide)
        self.assertIn("DEMO", wide)
        self.assertIn("RING", wide)
        self.assertIn("mouse 10,20", wide)
        self.assertIn("move the mouse", wide)
        narrow = termfluid.make_status(
            80, self.fluid, 42, True, True, (10, 20), True, "move the mouse to push the liquid"
        )
        self.assertEqual(len(narrow), 80)
        self.assertIn("q:quit", narrow)
        self.assertNotIn("move the mouse", narrow)

    def test_draw_ring_stays_in_bounds(self):
        lines = ["." * 40 for _ in range(20)]
        out = termfluid.draw_ring(lines, (20.0, 20.0), 40, 20)
        self.assertEqual(len(out), 20)
        self.assertTrue(all(len(line) == 40 for line in out))
        self.assertTrue(any("o" in line for line in out))
        self.assertEqual(out, termfluid.draw_ring(out, (20.0, 20.0), 40, 20))

    def test_demo_target_stays_on_screen(self):
        for step in range(200):
            x, y = termfluid.demo_target(100, 30, step * 0.05)
            self.assertGreaterEqual(x, 0.0)
            self.assertLessEqual(x, 100.0)
            self.assertGreaterEqual(y, 0.0)
            self.assertLessEqual(y, 30.0)


if __name__ == "__main__":
    unittest.main()
