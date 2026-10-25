import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fluid import RAMP, Fluid

ALLOWED = set(RAMP)


def settle(fluid, steps=150):
    for _ in range(steps):
        fluid.step(1.0 / 60.0)
    return fluid


def ink(lines):
    return sum(1 for row in lines for char in row if char != " ")


def count_near(fluid, mx, my, radius):
    return sum(
        1
        for i in range(len(fluid.px))
        if math.hypot(fluid.px[i] - mx, fluid.py[i] - my) < radius
    )


class FluidTests(unittest.TestCase):
    def make(self, width=80, height=24, seed=42, particles=None):
        return Fluid(width, height, seed=seed, particles=particles)

    def test_initial_liquid_is_at_the_top(self):
        fluid = self.make()
        stats = fluid.stats()
        self.assertEqual(stats["n"], len(fluid.px))
        self.assertEqual(stats["nan"], 0)
        self.assertEqual(stats["outside"], 0)
        self.assertLess(stats["mean_y_frac"], 0.30)
        lines = fluid.render()
        self.assertEqual(len(lines), 24)
        for line in lines:
            self.assertEqual(len(line), 80)
            self.assertTrue(set(line) <= ALLOWED)
        top = ink(lines[:4])
        bottom = ink(lines[-4:])
        self.assertGreater(top, 0.85 * 4 * 80)
        self.assertEqual(bottom, 0)

    def test_gravity_pulls_liquid_to_the_bottom(self):
        fluid = self.make()
        settle(fluid, 150)
        stats = fluid.stats()
        self.assertGreater(stats["mean_y_frac"], 0.65)
        self.assertEqual(stats["nan"], 0)
        self.assertEqual(stats["outside"], 0)
        lines = fluid.render()
        bottom = ink(lines[-5:])
        top = ink(lines[:4])
        self.assertGreater(bottom, 0.85 * 5 * 80)
        self.assertLess(top, 0.05 * 4 * 80)
        self.assertEqual(len(fluid.px), stats["n"])

    def test_fluid_comes_to_rest(self):
        fluid = self.make()
        settle(fluid, 300)
        self.assertLess(fluid.stats()["mean_speed"], 2.0)
        self.assertEqual(fluid.stats()["nan"], 0)
        self.assertEqual(fluid.stats()["outside"], 0)

    def test_mouse_force_carves_a_hole(self):
        base = settle(self.make())
        mx, my = 40.5, 37.0  # row 18.5, inside the settled pool
        before = count_near(base, mx, my, 8.0)
        self.assertGreater(before, 60)

        pushed = settle(self.make())
        pushed.set_mouse(40, 18)
        for _ in range(45):
            pushed.step(1.0 / 60.0)
        after = count_near(pushed, mx, my, 8.0)
        self.assertLess(after, before * 0.35)
        self.assertLess(after, 30)
        stats = pushed.stats()
        self.assertEqual(stats["nan"], 0)
        self.assertEqual(stats["outside"], 0)
        self.assertLess(stats["max_speed"], 120.0)

    def test_mouse_force_points_outward(self):
        fluid = self.make(40, 20, particles=240)
        # Replace the fluid with two probe particles on either side of the
        # force centre.  Gravity is off so only the repulsion acts.
        fluid.px = [20.5, 18.5]
        fluid.py = [20.0, 20.0]
        fluid.vx = [0.0, 0.0]
        fluid.vy = [0.0, 0.0]
        fluid.gravity_on = False
        fluid.mouse = (20.0, 20.0)
        fluid.mouse_radius = 10.0
        fluid.mouse_strength = 300.0
        fluid.rest_density = 1.0
        for _ in range(10):
            fluid.step(1.0 / 60.0)
        self.assertGreater(fluid.px[0], 20.5)
        self.assertLess(fluid.px[1], 18.5)
        self.assertGreater(fluid.vx[0], 0.0)
        self.assertLess(fluid.vx[1], 0.0)

    def test_mouse_cleared_means_no_force(self):
        fluid = self.make()
        fluid.set_mouse(40, 18)
        self.assertIsNotNone(fluid.mouse)
        fluid.clear_mouse()
        self.assertIsNone(fluid.mouse)

    def test_click_pulse_decays(self):
        fluid = self.make()
        fluid.click()
        self.assertEqual(fluid.pulse, 1.0)
        for _ in range(60):
            fluid.step(1.0 / 60.0)
        self.assertLess(fluid.pulse, 0.01)

    def test_deterministic_with_seed(self):
        left = self.make(seed=7)
        right = self.make(seed=7)
        for _ in range(60):
            left.step(1.0 / 60.0)
            right.step(1.0 / 60.0)
        self.assertEqual(left.px, right.px)
        self.assertEqual(left.py, right.py)

    def test_reset_puts_liquid_back_at_the_top(self):
        fluid = self.make()
        settle(fluid, 120)
        self.assertGreater(fluid.stats()["mean_y_frac"], 0.5)
        fluid.reset()
        self.assertLess(fluid.stats()["mean_y_frac"], 0.30)
        self.assertEqual(fluid.stats()["outside"], 0)

    def test_resize_keeps_particles_valid(self):
        fluid = self.make()
        settle(fluid, 60)
        fluid.resize(60, 20)
        stats = fluid.stats()
        self.assertEqual(stats["outside"], 0)
        self.assertEqual(stats["nan"], 0)
        lines = fluid.render()
        self.assertEqual(len(lines), 20)
        self.assertTrue(all(len(line) == 60 for line in lines))
        self.assertTrue(all(set(line) <= ALLOWED for line in lines))

    def test_rest_density_is_sensible(self):
        fluid = self.make()
        self.assertGreater(fluid.rest_density, 0.05)
        self.assertLess(fluid.rest_density, 10.0)

    def test_clear_mouse_and_gravity_toggle(self):
        fluid = self.make()
        self.assertTrue(fluid.gravity_on)
        fluid.toggle_gravity()
        self.assertFalse(fluid.gravity_on)
        before = fluid.stats()["mean_y_frac"]
        for _ in range(20):
            fluid.step(1.0 / 60.0)
        # Gravity is off: pressure may rearrange the block, but it must not
        # fall towards the bottom.
        self.assertLessEqual(fluid.stats()["mean_y_frac"], before + 0.02)


if __name__ == "__main__":
    unittest.main()
