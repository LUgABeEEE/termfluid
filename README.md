# termfluid

[![CI](https://github.com/LUgABeEEE/termfluid/actions/workflows/ci.yml/badge.svg)](https://github.com/LUgABeEEE/termfluid/actions/workflows/ci.yml) · MIT · 纯 Python 标准库 · [English summary](#english-summary)

一个只用 **ASCII 字符** 和 **终端鼠标事件** 做的命令行流体玩具。

启动时全部液体挤在屏幕最上方，受重力下落、飞溅、在底部汇聚；终端会开启
xterm 鼠标上报，鼠标位置就是一个向外的圆形斥力场：液体被推开、挖洞、溅起，
移开鼠标后又会流回去。纯 Python 标准库，没有 numpy / curses / 图形库。

用浏览器打开 [demo.html](demo.html) 可以看一段 9 秒的离线演示（同一套模拟
引擎渲染的纯字符帧，带播放/暂停/进度条）。

## 效果预览

下面是 80×24 终端里运行 3 秒、再用鼠标在液体内部停留 0.5 秒后的一帧：

~~~text
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                                                                
                                  .::::::::::.                                  
                               .:--===-----==:--:.                              
.                           .:-=++==--::.::--:=++=:.                            
=-:..                   ..:-=+%#%=-:.       ..:=%%+=-:.                      .:-
@%+=--:::-::---------:---=+%#@@#=:.            :=####+=--::....           .:-=+%
@#%#%+++++++++++++++++%%#@@@@@@+:               :+@@@@##%+===------:::::--=+%%#@
@##@@##%#%%%%%%%%%%%##@@@@@@@@@+.               .=@@@@@@@@##%%%%+%%%++%%%%##@@@@
@@@@@@@@@@##@@##@#@@@@@@@@@@@@@%=-..         ..:-%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@#%+=-:::::::-==+#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@##%+++++%##@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
~~~

字符含义：- 稀薄，+ = % # @ 依次变浓；空白处没有液体。中间的洞口就是
鼠标斥力挖出来的。

## 运行

环境要求：

* Python 3.8+（只用标准库）
* 支持 xterm 鼠标上报的终端：Linux / macOS / WSL / SSH 均可
  （iTerm2、kitty、WezTerm、GNOME Terminal、Konsole、Windows Terminal + WSL 等）
* 原生 Windows 控制台不直接支持；请在 WSL 里运行，或通过 SSH 连到 Linux 运行。

~~~bash
cd termfluid
python3 termfluid.py
~~~

把鼠标移到终端画面上，液体就会被推开。程序退出（q / Esc / Ctrl-C）时
会恢复终端驱动、关闭鼠标上报并回到原来的屏幕。

## 操作

| 操作 | 效果 |
| --- | --- |
| 移动鼠标 | 在鼠标位置产生向外的斥力（主要交互方式） |
| 左键点击 | 脉冲：短时间更强的斥力，把液体炸开 |
| 滚轮 | 增强 / 减弱斥力（60–1200） |
| 方向键 / WASD | 没有鼠标上报时移动斥力中心 |
| space | 暂停 / 继续 |
| g | 开关重力 |
| r | 重置：液体回到屏幕顶部 |
| c | 显示 / 隐藏斥力中心的圆环 |
| + / - | 调整斥力强度 |
| q / Esc / Ctrl-C | 退出 |

如果终端只支持拖拽上报、不支持悬停上报，按住左键移动也能驱动斥力。

## 参数

~~~text
python3 termfluid.py --help

--fps FPS             目标帧率（默认 60）
--particles N         粒子数（默认按终端面积自动，约 0.55/格，范围 240–3200）
--seed N              随机种子（默认 1234）
--gravity G           重力（默认 25）
--force F             鼠标斥力强度（默认 240）
--radius R            斥力半径，模拟单位；2 单位约等于 1 行（默认 14）
--duration SECONDS    运行指定秒数后自动退出
--snapshot FILE       退出时（或 --headless 结束时）把最后一帧（字符画 + 状态栏）写到文件
--demo                自动移动斥力中心，不需要鼠标（录制/演示用）
--no-mouse            不开启终端鼠标上报（只用键盘）
--headless STEPS      无 TTY：先模拟 STEPS 帧，再输出一张字符画
--width / --height    --headless 使用的尺寸
--version
~~~

### 无终端时的静态预览

~~~bash
python3 termfluid.py --headless 0   --width 100 --height 30   # 初始：液体全在顶部
python3 termfluid.py --headless 180 --width 100 --height 30   # 3 秒后：落到底部
python3 termfluid.py --headless 240 --demo --width 100 --height 30
python3 termfluid.py --headless 180 --width 100 --height 30 --snapshot /tmp/frame.txt  # 同时落盘
~~~

### 自动演示

~~~bash
python3 termfluid.py --demo
python3 termfluid.py --demo --duration 10 --snapshot /tmp/termfluid.txt
~~~

## 实现要点

* **粒子液体**：约 1650 个粒子（100×30 终端），用类似 Clavet 2005
  “Particle-based Viscoelastic Fluid Simulation” 的双密度松弛计算局部压力；
  空间哈希做邻居查找；重力、壁面碰撞、粘性阻尼和鼠标径向加速度共同作用。
* **纵横比校正**：字符格通常约 2:1（高:宽），模拟坐标里 y 乘 2，所以屏幕上的
  斥力圆看起来是圆的，而不是上下拉长的椭圆。
* **字符渲染**：粒子用 bilinear splat 落到字符网格，做一次 1-2-1 平滑，再按
  归一化密度映射到  .:-=+%#@  八级字符。
* **鼠标输入**：启动时发送 ESC[?1000h ESC[?1002h ESC[?1003h ESC[?1006h，
  进入 xterm 的“任意移动 + SGR 扩展坐标”鼠标模式；解析
  ESC [ < Cb ; Cx ; Cy M/m，也兼容旧式 X10 三字节上报；序列可以跨
  read() 边界拆分。退出时关闭鼠标并恢复终端。
* **终端状态**：raw mode、alternate screen、隐藏光标；用上下文管理器和
  信号处理保证异常/正常退出都能还原终端。
* **无依赖**：仅 Python 标准库，方便拷贝到任何 Linux/macOS/WSL 机器。

## 测试

~~~bash
python3 -m unittest discover -s tests -v
~~~

共 37 个测试：

* 液体初始全部在顶部、重力下落、逐渐静止、数值稳定；
* 鼠标斥力会在液体内挖洞，且方向严格向外；
* 渲染尺寸、字符集、随机种子确定性、重置、resize；
* SGR / X10 鼠标序列、跨 read 拆分、滚轮、方向键、ESC 宽限；
* CLI 的 headless 输出、静态帧、无 TTY 报错和 --version；
* 状态栏在窄终端下的截断、圆环绘制、demo 轨迹边界。

在真实终端里做过的验收：--demo --duration 1.2 在 160×39 的真实 PTY 中
运行，退出码 0，stty -g 前后完全一致；--pipe-input 模式把真实 SGR 鼠标
字节喂进同一个主循环，状态栏显示最终鼠标坐标 mouse 39,13，证明
“鼠标字节 -> 解析 -> 更新斥力中心”这条链路可用。

## 常见问题

**移动鼠标没反应？**
终端可能只支持按键/拖拽上报，或者鼠标模式被 tmux/screen 截获。先在
iTerm2 / kitty / WezTerm / GNOME Terminal / Windows Terminal（WSL）里试；
在 tmux 里需要开启 set -g mouse on，或直接在普通终端里运行。也可以按住
左键拖动，或用方向键移动斥力中心。

**终端画面乱掉、按键回显？**
正常退出会恢复。若程序被 kill -9 或终端崩溃，可能残留 raw/鼠标模式；
执行 reset 或重新打开终端即可。程序自身对 SIGINT/SIGTERM/SIGHUP 做了恢复。

**很卡？**
减小终端尺寸，或 --particles 800；也可以把 --fps 降到 30。100×30 下
引擎单步约 8 ms，120×40 约 14 ms（SER8 / Python 3.12）。

**缩小终端后液体重置了？**
是的。resize 会重新初始化液体，避免粒子被挤在变小的边界里“爆炸”；状态栏
会提示 resized - liquid reset。

## 文件

~~~text
termfluid.py        主程序：终端 raw 模式、输入循环、状态栏
fluid.py            粒子流体引擎 + ASCII 渲染
inputparser.py      SGR/X10 鼠标与按键流解析
tests/              37 个 unittest
tools/make_demo.py  生成 demo.html 的离线演示脚本
demo.html           自包含的浏览器演示（由 tools/make_demo.py 生成）
~~~

## 说明

这个项目只使用 ASCII 字符（RAMP = " .:-=+%#@"）表现液体密度，不依赖
Unicode 方块、图片或颜色；终端里看到的每个像素都是一个字符。鼠标交互通过
标准 xterm 鼠标转义序列实现，所以 SSH 到远程机器时也能用（只要本地终端
把鼠标事件传过去）。

---

## English summary

**termfluid** is a terminal toy: a particle fluid rendered entirely with ASCII
characters (` .:-=+%#@`), pushed around by your mouse through xterm mouse
reporting. Gravity pulls it down; the pointer is an outward radial force, so you
can dig holes and make it splash. Pure Python standard library — no numpy, no
curses, no graphics stack — so it runs anywhere Python 3.8+ and a moderately
capable terminal are available, including over SSH.

```bash
python3 termfluid.py            # interactive (move the mouse over the terminal)
python3 termfluid.py --demo     # automatic pointer, good for recording
python3 termfluid.py --headless 180 --width 100 --height 30   # no TTY: one frame
```

Two details that make it look right: the simulation corrects for the ~2:1
character cell aspect ratio, and particles are splatted bilinearly onto the
character grid before being mapped to the eight density levels. The browser
demo in [`demo.html`](demo.html) replays nine seconds of the same engine.

`python -m unittest discover -s tests` runs 37 tests (engine, parser, rendering,
CLI). Licensed MIT.

## License

MIT — see [LICENSE](LICENSE).

