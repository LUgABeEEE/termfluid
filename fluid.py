"""ASCII particle liquid engine.

The simulation runs in terminal-cell units with a vertical aspect correction so
that round forces look round on screen (a character cell is roughly twice as
tall as it is wide).  Particles interact through a double-density relaxation
kernel similar to Clavet et al., "Particle-based Viscoelastic Fluid Simulation"
(2005).  Everything is pure Python standard library.

Coordinates:
    x in [0, width)              -- terminal columns
    y in [0, height * aspect)    -- terminal rows * 2
    row = y / aspect
"""

from __future__ import annotations

import math
import random

ASPECT = 2.0
RAMP = " .:-=+%#@"
MAX_PARTICLES = 3200
MIN_PARTICLES = 240


def _clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


class Fluid:
    """A 2D particle liquid that can be rendered into an ASCII character grid."""

    def __init__(
        self,
        width,
        height,
        *,
        particles=None,
        seed=1234,
        gravity=25.0,
        slab=0.35,
        radius=2.2,
        mouse_radius=14.0,
        mouse_strength=240.0,
        pressure=6.0,
        relax=0.020,
        viscosity=0.18,
        damping=0.991,
        max_speed=120.0,
    ):
        self.width = max(8, int(width))
        self.height = max(6, int(height))
        self.aspect = ASPECT
        self.slab = _clamp(float(slab), 0.12, 0.55)
        self.h = float(radius)
        self.mouse_radius = float(mouse_radius)
        self.mouse_strength = float(mouse_strength)
        self.gravity = float(gravity)
        self.gravity_on = True
        self.pressure = float(pressure)
        self.relax = float(relax)
        self.viscosity = float(viscosity)
        self.damping = float(damping)
        self.max_speed = float(max_speed)

        area = self.width * self.height
        if particles is None:
            particles = int(area * 0.55)
        self.target_particles = int(_clamp(particles, MIN_PARTICLES, MAX_PARTICLES))
        self.seed = int(seed)

        # particle state (parallel arrays)
        self.px = []
        self.py = []
        self.vx = []
        self.vy = []

        self.mouse = None          # (x, y) in simulation units, or None
        self.pulse = 0.0           # extra force after a click
        self.time = 0.0
        self.rest_density = 1.0
        self.density_scale = 1.0
        self.reset()

    # ------------------------------------------------------------------ setup
    def reset(self):
        """Fill the whole fluid into a slab at the very top of the screen."""
        self.time = 0.0
        self.pulse = 0.0
        self.mouse = None
        rng = random.Random(self.seed)

        n = self.target_particles
        w = self.width
        hu = self.height * self.aspect
        slab_h = hu * self.slab
        spacing = math.sqrt((w * slab_h) / max(1, n))
        cols = max(1, int(w / spacing))
        jitter = spacing * 0.28

        px, py = [], []
        for i in range(n):
            row, col = divmod(i, cols)
            x = (col + 0.5) * spacing + rng.uniform(-jitter, jitter)
            y = (row + 0.5) * spacing + rng.uniform(-jitter, jitter)
            px.append(_clamp(x, 0.6, w - 0.6))
            py.append(_clamp(y, 0.6, slab_h))
        self.px, self.py = px, py
        self.vx = [0.0] * n
        self.vy = [0.0] * n

        # Density scale for rendering: particles per occupied character cell.
        self.density_scale = n / max(1.0, self.slab * w * self.height)

        # Calibrate the rest density from the interior of the initial packing.
        pairs, density = self._pairs()
        if density:
            ordered = sorted(density)
            self.rest_density = max(0.05, ordered[int(len(ordered) * 0.75)])
        else:
            self.rest_density = 1.0

    def resize(self, width, height):
        """Resize the world.  Re-seeds the fluid to avoid cramped, exploding
        particles after a terminal shrink (documented in the status bar)."""
        self.width = max(8, int(width))
        self.height = max(6, int(height))
        self.target_particles = int(
            _clamp(int(self.width * self.height * 0.55), MIN_PARTICLES, MAX_PARTICLES)
        )
        self.reset()

    # ------------------------------------------------------------------ input
    def set_mouse(self, col, row):
        """Point the repulsion at a character cell (0-based)."""
        self.mouse = (
            _clamp(col + 0.5, 0.0, self.width),
            _clamp((row + 0.5) * self.aspect, 0.0, self.height * self.aspect),
        )

    def move_force_center(self, dcol, drow):
        if self.mouse is None:
            self.mouse = (self.width * 0.5, self.height * self.aspect * 0.5)
        x, y = self.mouse
        self.mouse = (
            _clamp(x + dcol, 0.0, self.width),
            _clamp(y + drow * self.aspect, 0.0, self.height * self.aspect),
        )

    def clear_mouse(self):
        self.mouse = None

    def click(self):
        self.pulse = 1.0

    def toggle_gravity(self):
        self.gravity_on = not self.gravity_on

    # ------------------------------------------------------------- simulation
    def step(self, dt=1.0 / 60.0):
        """Advance the simulation by dt seconds."""
        n = len(self.px)
        if n == 0:
            return
        dt = _clamp(float(dt), 1.0 / 240.0, 1.0 / 30.0)
        self.time += dt

        px, py, vx, vy = self.px, self.py, self.vx, self.vy
        w = self.width
        hu = self.height * self.aspect

        # 1. external forces: gravity and the mouse repulsion field
        if self.gravity_on and self.gravity:
            gdt = self.gravity * dt
            for i in range(n):
                vy[i] += gdt

        if self.mouse is not None:
            mx, my = self.mouse
            radius = self.mouse_radius
            r2 = radius * radius
            strength = self.mouse_strength * (1.0 + 2.0 * self.pulse)
            for i in range(n):
                dx = px[i] - mx
                dy = py[i] - my
                d2 = dx * dx + dy * dy
                if 1e-6 < d2 < r2:
                    d = math.sqrt(d2)
                    falloff = 1.0 - d / radius
                    accel = strength * falloff * falloff / d
                    vx[i] += dx * accel * dt
                    vy[i] += dy * accel * dt
        self.pulse *= max(0.0, 1.0 - 6.0 * dt)

        # 2. predict positions
        old_px = px[:]
        old_py = py[:]
        margin = 0.5
        for i in range(n):
            px[i] += vx[i] * dt
            py[i] += vy[i] * dt

        # 3. density and pressure relaxation at the predicted positions
        pairs, density = self._pairs()
        rest = self.rest_density
        pressure = self.pressure
        relax = self.relax
        press = [0.0] * n
        if pairs:
            for i in range(n):
                excess = density[i] - rest
                if excess > 0.0:
                    press[i] = excess * pressure
            max_push = 0.12
            for i, j, dx, dy, dist, q in pairs:
                push = (press[i] + press[j]) * q * relax
                if push <= 0.0:
                    continue
                if push > max_push:
                    push = max_push
                nx = dx / dist
                ny = dy / dist
                half = push * 0.5
                px[i] -= nx * half
                py[i] -= ny * half
                px[j] += nx * half
                py[j] += ny * half

        # 4. walls (fluid sticks to the glass)
        max_x = w - margin
        max_y = hu - margin
        for i in range(n):
            x = px[i]
            y = py[i]
            if x < margin:
                px[i] = margin
            elif x > max_x:
                px[i] = max_x
            if y < margin:
                py[i] = margin
            elif y > max_y:
                py[i] = max_y

        # 5. derive velocities from the corrected positions
        inv_dt = 1.0 / dt
        damp = self.damping
        vmax = self.max_speed
        vmax2 = vmax * vmax
        for i in range(n):
            nvx = (px[i] - old_px[i]) * inv_dt * damp
            nvy = (py[i] - old_py[i]) * inv_dt * damp
            speed2 = nvx * nvx + nvy * nvy
            if speed2 > vmax2:
                scale = vmax / math.sqrt(speed2)
                nvx *= scale
                nvy *= scale
            vx[i] = nvx
            vy[i] = nvy

        # 6. viscosity: damp relative velocities between close neighbours
        visc = self.viscosity
        if visc and pairs:
            for i, j, dx, dy, dist, q in pairs:
                f = visc * q * 0.5
                dvx = (vx[j] - vx[i]) * f
                dvy = (vy[j] - vy[i]) * f
                vx[i] += dvx
                vy[i] += dvy
                vx[j] -= dvx
                vy[j] -= dvy

    # ------------------------------------------------------------ neighbours
    def _pairs(self):
        """Return (pairs, density).

        Each pair is (i, j, dx, dy, dist, q) with i < j and q = 1 - dist/h.
        Density is the symmetric double-density kernel sum q^2.
        """
        n = len(self.px)
        if n == 0:
            return [], []
        h = self.h
        inv_h = 1.0 / h
        h2 = h * h
        buckets = {}
        px, py = self.px, self.py
        for i in range(n):
            key = (int(px[i] * inv_h), int(py[i] * inv_h))
            bucket = buckets.get(key)
            if bucket is None:
                buckets[key] = [i]
            else:
                bucket.append(i)

        pairs = []
        density = [0.0] * n
        for (cx, cy), indices in buckets.items():
            for i in indices:
                xi = px[i]
                yi = py[i]
                for ox in (-1, 0, 1):
                    bx = cx + ox
                    for oy in (-1, 0, 1):
                        bucket = buckets.get((bx, cy + oy))
                        if not bucket:
                            continue
                        for j in bucket:
                            if j <= i:
                                continue
                            dx = px[j] - xi
                            dy = py[j] - yi
                            d2 = dx * dx + dy * dy
                            if d2 >= h2:
                                continue
                            dist = math.sqrt(d2)
                            if dist < 1e-6:
                                dist = 1e-6
                            q = 1.0 - dist / h
                            pairs.append((i, j, dx, dy, dist, q))
                            w = q * q
                            density[i] += w
                            density[j] += w
        return pairs, density

    # -------------------------------------------------------------- rendering
    def render(self):
        """Render the current particle state as a list of ASCII rows."""
        w, h = self.width, self.height
        n = len(self.px)
        grid = [0.0] * (w * h)
        if n:
            aspect = self.aspect
            for i in range(n):
                # bilinear splat (cloud in cell)
                gx = self.px[i] - 0.5
                gy = self.py[i] / aspect - 0.5
                x0 = int(math.floor(gx))
                y0 = int(math.floor(gy))
                fx = gx - x0
                fy = gy - y0
                for oy, wy in ((0, 1.0 - fy), (1, fy)):
                    yy = y0 + oy
                    if yy < 0 or yy >= h or wy <= 0.0:
                        continue
                    row = yy * w
                    for ox, wx in ((0, 1.0 - fx), (1, fx)):
                        xx = x0 + ox
                        if xx < 0 or xx >= w or wx <= 0.0:
                            continue
                        grid[row + xx] += wx * wy
            # one separable 1-2-1 blur to close lattice holes
            grid = _blur(grid, w, h)

        scale = self.density_scale
        thresholds = (0.055, 0.15, 0.27, 0.41, 0.56, 0.71, 0.85, 1.0)
        ramp = RAMP
        lines = []
        for yy in range(h):
            row = yy * w
            chars = []
            for xx in range(w):
                v = grid[row + xx] / scale if scale > 0 else 0.0
                level = 0
                for limit in thresholds:
                    if v >= limit:
                        level += 1
                    else:
                        break
                chars.append(ramp[level])
            lines.append("".join(chars))
        return lines

    # ------------------------------------------------------------- diagnostics
    def stats(self):
        n = len(self.px)
        if n == 0:
            return {"n": 0}
        hu = self.height * self.aspect
        mean_y = sum(self.py) / n
        speeds = [math.hypot(self.vx[i], self.vy[i]) for i in range(n)]
        nan = sum(
            1
            for i in range(n)
            if not (
                math.isfinite(self.px[i])
                and math.isfinite(self.py[i])
                and math.isfinite(self.vx[i])
                and math.isfinite(self.vy[i])
            )
        )
        outside = sum(
            1
            for i in range(n)
            if self.px[i] < -0.001
            or self.px[i] > self.width + 0.001
            or self.py[i] < -0.001
            or self.py[i] > hu + 0.001
        )
        return {
            "n": n,
            "mean_y_frac": mean_y / hu,
            "max_speed": max(speeds),
            "mean_speed": sum(speeds) / n,
            "nan": nan,
            "outside": outside,
            "rest_density": self.rest_density,
        }


def _blur(grid, w, h):
    """Separable 1-2-1 blur with clamped borders (a single pass)."""
    tmp = [0.0] * (w * h)
    for y in range(h):
        row = y * w
        for x in range(w):
            left = grid[row + (x - 1 if x > 0 else 0)]
            right = grid[row + (x + 1 if x < w - 1 else w - 1)]
            tmp[row + x] = (left + 2.0 * grid[row + x] + right) * 0.25
    out = [0.0] * (w * h)
    for y in range(h):
        for x in range(w):
            up = tmp[(y - 1 if y > 0 else 0) * w + x]
            down = tmp[(y + 1 if y < h - 1 else h - 1) * w + x]
            out[y * w + x] = (up + 2.0 * tmp[y * w + x] + down) * 0.25
    return out
