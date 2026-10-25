#!/usr/bin/env python3
"""Generate a self-contained HTML animation of the termfluid engine.

This is a presentation/demo helper, not part of the interactive CLI.  It runs
the same particle simulation headlessly, records one frame per video frame and
embeds the frames (pure ASCII) in an HTML player.

    python3 tools/make_demo.py [output.html]
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from fluid import Fluid

WIDTH = 100
HEIGHT = 30
FPS = 30
DURATION = 9.0
RING = "o"


def overlay_ring(frame, mouse, width, height):
    if mouse is None:
        return frame
    mx = int(mouse[0])
    my = int(mouse[1] / 2.0)
    rows = [list(line) for line in frame]
    marks = set()
    for angle in range(0, 360, 30):
        x = int(round(mx + 3.0 * math.cos(math.radians(angle))))
        y = int(round(my + 1.5 * math.sin(math.radians(angle))))
        if 0 <= x < width and 0 <= y < height:
            marks.add((x, y))
    for x, y in marks:
        rows[y][x] = RING
    return [''.join(row) for row in rows]


def phase_for(t):
    if t < 3.0:
        return 'gravity only'
    if t < 4.8:
        return 'mouse repulsion'
    if t < 5.4:
        return 'click burst'
    return 'settling'


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "demo.html")
    fluid = Fluid(WIDTH, HEIGHT, seed=2024, mouse_strength=200.0, mouse_radius=12.0)
    frames = []
    clicked = False
    for index in range(int(round(FPS * DURATION))):
        t = index / FPS
        mouse = None
        if t < 3.0:
            fluid.clear_mouse()
        elif t < 4.8:
            u = t - 3.0
            mx = WIDTH * 0.5 + 18.0 * math.sin(2.0 * u)
            my = 24.5 + 1.5 * math.sin(3.0 * u + 0.4)
            mouse = (mx, my * 2.0)
            fluid.set_mouse(mx, my)
        elif t < 5.4:
            mouse = (WIDTH * 0.5, 23.0 * 2.0)
            fluid.set_mouse(WIDTH * 0.5, 23.0)
            if not clicked:
                fluid.click()
                clicked = True
        else:
            mouse = None
            fluid.clear_mouse()
        for _ in range(2):
            fluid.step(1.0 / 60.0)
        frame = fluid.render()
        if mouse is not None:
            frame = overlay_ring(frame, mouse, WIDTH, HEIGHT)
        frames.append('\n'.join(frame))

    phases = [phase_for(i / FPS) for i in range(len(frames))]
    payload = json.dumps(frames, separators=(",", ":"))
    phases_json = json.dumps(phases, separators=(",", ":"))
    stats = fluid.stats()

    html = TEMPLATE.format(
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration=DURATION,
        frames=payload,
        phases=phases_json,
        n=stats["n"],
        rest=round(fluid.rest_density, 2),
    )
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(html)
    print("wrote", output, "frames", len(frames), "bytes", len(html))


TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>termfluid - ASCII liquid</title>
<style>
  :root {{
    color-scheme: dark;
    --ink: #b9ffcf;
    --dim: #4d8f66;
    --bg: #050b07;
    --panel: #0b1710;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; background: var(--bg); }}
  body {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 18px; padding: 24px; color: var(--ink);
    font-family: "DejaVu Sans Mono", "SFMono-Regular", Menlo, Consolas, monospace;
  }}
  header {{ text-align: center; }}
  h1 {{ font-size: 22px; letter-spacing: 0.12em; margin: 0 0 6px; font-weight: 600; }}
  .sub {{ color: var(--dim); font-size: 12px; letter-spacing: 0.08em; }}
  .screen-wrap {{
    width: min(96vw, 1180px);
    background: radial-gradient(circle at 50% 30%, #0c1a11 0%, #050b07 70%);
    border: 1px solid #1c3a27; border-radius: 10px;
    box-shadow: 0 0 60px rgba(60, 255, 140, 0.08), inset 0 0 40px rgba(0, 0, 0, 0.6);
    padding: 14px 18px;
  }}
  pre {{
    margin: 0;
    font-family: inherit;
    font-size: clamp(5px, 1.02vw, 13px);
    line-height: 1.0;
    letter-spacing: 0;
    white-space: pre;
    color: var(--ink);
    text-shadow: 0 0 5px rgba(80, 255, 150, 0.28);
    user-select: none;
    overflow: hidden;
  }}
  .status {{
    width: min(96vw, 1180px);
    display: flex; flex-wrap: wrap; gap: 14px; align-items: center; justify-content: space-between;
    color: var(--dim); font-size: 12px;
  }}
  .status strong {{ color: var(--ink); font-weight: 600; }}
  .controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  button {{
    background: #0d2015; color: var(--ink); border: 1px solid #24583a; border-radius: 6px;
    padding: 7px 14px; font: inherit; font-size: 12px; cursor: pointer;
  }}
  button:hover {{ background: #143321; }}
  input[type=range] {{ width: min(38vw, 320px); accent-color: #58e58b; }}
  .meta {{ color: var(--dim); font-size: 11px; letter-spacing: 0.05em; }}
  .legend {{ color: var(--dim); font-size: 11px; }}
  .legend b {{ color: var(--ink); font-weight: 600; }}
  @media (max-width: 720px) {{
    body {{ padding: 12px; gap: 12px; }}
    pre {{ font-size: 1.6vw; }}
  }}
</style>
</head>
<body>
<header>
  <h1>TERMFLUID</h1>
  <div class="sub">ASCII LIQUID &middot; GRAVITY &middot; MOUSE REPULSION</div>
</header>
<div class="screen-wrap"><pre id="screen"></pre></div>
<div class="status">
  <div class="controls">
    <button id="toggle">pause</button>
    <button id="restart">restart</button>
    <input id="seek" type="range" min="0" max="{duration}" step="0.033" value="0">
    <span id="clock">0.0s</span>
  </div>
  <div class="legend"><b>o</b> = mouse / force centre &nbsp; | &nbsp; <b>- + = % # @</b> = liquid density</div>
</div>
<div class="meta">
  {width}x{height} cells &middot; {n} particles &middot; {fps} fps &middot; rest density {rest}
</div>
<script>
const frames = {frames};
const phases = {phases};
const fps = {fps};
const duration = {duration};
const screen = document.getElementById('screen');
const seek = document.getElementById('seek');
const clock = document.getElementById('clock');
const toggle = document.getElementById('toggle');
const restart = document.getElementById('restart');
let index = 0;
let playing = true;
let last = 0;
let accumulator = 0;

function show(i) {{
  index = Math.max(0, Math.min(frames.length - 1, i));
  screen.textContent = frames[index];
  const t = index / fps;
  seek.value = t.toFixed(2);
  clock.textContent = t.toFixed(1) + 's  ·  ' + phases[index];
}}

function loop(now) {{
  if (!last) last = now;
  const delta = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (playing) {{
    accumulator += delta;
    while (accumulator >= 1 / fps) {{
      accumulator -= 1 / fps;
      if (index + 1 >= frames.length) {{
        index = 0;
      }} else {{
        index += 1;
      }}
    }}
    show(index);
  }}
  requestAnimationFrame(loop);
}}

toggle.addEventListener('click', () => {{
  playing = !playing;
  toggle.textContent = playing ? 'pause' : 'play';
  last = 0;
}});
restart.addEventListener('click', () => {{
  index = 0; accumulator = 0; show(0); playing = true; toggle.textContent = 'pause'; last = 0;
}});
seek.addEventListener('input', () => {{
  playing = false; toggle.textContent = 'play';
  index = Math.round(parseFloat(seek.value) * fps);
  accumulator = 0;
  show(index);
}});
show(0);
requestAnimationFrame(loop);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
