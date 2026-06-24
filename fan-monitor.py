#!/usr/bin/env python3
"""
PWM Fan Monitor — Real-time terminal dashboard for Raspberry Pi.

Monitors CPU/GPU temperature, fan duty, CPU load.
Line-graph display with curve position and event log.

Keys: F=toggle C/F  Space=pause/resume  q=quit
"""

import curses
import time
import sys
import signal
import subprocess
import re
from collections import deque
from datetime import datetime

GAMING_CURVE = [
    (40, 10), (45, 30), (50, 55),
    (55, 75), (60, 90), (65, 100),
]


class FanMonitor:
    def __init__(self):
        self.cpu_temps = deque(maxlen=60)
        self.gpu_temps = deque(maxlen=60)
        self.fan_duties = deque(maxlen=60)
        self.cpu_loads = deque(maxlen=60)
        self.events = deque(maxlen=8)
        self.celsius = True
        self.paused = False
        self.running = True
        self.last_fan_duty = None
        self.last_update = 0
        self.update_interval = 2.0
        self.start_time = time.time()
        self.current_cpu_temp = None
        self.current_gpu_temp = None
        self.current_duty = None
        self.current_cpu_load = None
        self.peak_cpu_temp = None
        self.peak_gpu_temp = None
        self.prev_idle = 0
        self.prev_total = 0

    def read_cpu_temp(self):
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return int(f.read().strip()) / 1000.0
        except Exception:
            return None

    def read_gpu_temp(self):
        try:
            r = subprocess.run(['vcgencmd', 'measure_temp'],
                               capture_output=True, text=True, timeout=2)
            m = re.search(r'temp=([\d.]+)', r.stdout)
            return float(m.group(1)) if m else None
        except Exception:
            return None

    def read_cpu_load(self):
        try:
            with open('/proc/stat', 'r') as f:
                parts = f.readline().split()
            idle = int(parts[4])
            total = sum(int(p) for p in parts[1:])
            di = idle - self.prev_idle
            dt = total - self.prev_total
            self.prev_idle = idle
            self.prev_total = total
            return (1.0 - di / dt) * 100.0 if dt else 0.0
        except Exception:
            return None

    def read_fan_duty(self):
        try:
            r = subprocess.run(
                ['journalctl', '-u', 'pwm-fan', '-n', '10', '--no-pager'],
                capture_output=True, text=True, timeout=3)
            for line in reversed(r.stdout.split('\n')):
                m = re.search(r'fan (\d+)%', line)
                if m:
                    return int(m.group(1))
        except Exception:
            pass
        return None

    def get_curve_duty(self, temp_c):
        if temp_c is None:
            return 0
        if temp_c <= GAMING_CURVE[0][0]:
            return GAMING_CURVE[0][1]
        if temp_c >= GAMING_CURVE[-1][0]:
            return GAMING_CURVE[-1][1]
        for i in range(len(GAMING_CURVE) - 1):
            t1, d1 = GAMING_CURVE[i]
            t2, d2 = GAMING_CURVE[i + 1]
            if t1 <= temp_c <= t2:
                return int(d1 + (temp_c - t1) / (t2 - t1) * (d2 - d1))
        return 0

    def fmt_temp(self, t):
        if t is None:
            return "--.-"
        if self.celsius:
            return "{:.1f}C".format(t)
        return "{:.1f}F".format(t * 9.0 / 5.0 + 32.0)

    def fmt_uptime(self):
        s = int(time.time() - self.start_time)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return "{}h {:02d}m".format(h, m) if h else "{}m {:02d}s".format(m, s)

    def update(self):
        now = time.time()
        if now - self.last_update < self.update_interval or self.paused:
            return
        self.last_update = now

        ct = self.read_cpu_temp()
        gt = self.read_gpu_temp()
        fd = self.read_fan_duty()
        cl = self.read_cpu_load()

        if ct is not None:
            self.current_cpu_temp = ct
            self.cpu_temps.append(ct)
            if self.peak_cpu_temp is None or ct > self.peak_cpu_temp:
                self.peak_cpu_temp = ct
        if gt is not None:
            self.current_gpu_temp = gt
            self.gpu_temps.append(gt)
            if self.peak_gpu_temp is None or gt > self.peak_gpu_temp:
                self.peak_gpu_temp = gt
        if cl is not None:
            self.current_cpu_load = cl
            self.cpu_loads.append(cl)
        if fd is not None:
            self.current_duty = fd
            self.fan_duties.append(fd)
            if self.last_fan_duty is not None and self.last_fan_duty != fd:
                self.events.appendleft({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'temp': ct, 'old': self.last_fan_duty, 'new': fd
                })
            self.last_fan_duty = fd

    # ---- drawing helpers ----

    def put(self, scr, y, x, text, attr=0):
        h, w = scr.getmaxyx()
        if 0 <= y < h and 0 <= x < w:
            try:
                scr.addstr(y, x, str(text)[:w - x], attr)
            except curses.error:
                pass

    def draw_line_graph(self, scr, y0, x0, gw, gh, data, lo, hi, title):
        """Draw a line graph. Each column gets one character at the row
        corresponding to its value. Columns below are filled with a
        lighter character to create an area chart effect."""
        self.put(scr, y0, x0, title, curses.A_BOLD)

        spread = float(hi - lo) if hi != lo else 1.0
        label_w = 7
        plot_w = gw - label_w - 1
        if plot_w < 5:
            return

        points = list(data)[-plot_w:]

        # Y-axis labels
        for ri in range(gh):
            gy = y0 + 1 + ri
            if ri == 0:
                lbl = "{:.0f}".format(hi)
            elif ri == gh - 1:
                lbl = "{:.0f}".format(lo)
            elif ri == gh // 2:
                lbl = "{:.0f}".format(lo + spread / 2)
            else:
                lbl = ""
            self.put(scr, gy, x0, "{:>6}".format(lbl))
            self.put(scr, gy, x0 + label_w - 1, "|")

        # Plot each data column
        for ci, val in enumerate(points):
            frac = (max(lo, min(hi, val)) - lo) / spread
            # row 0 = top = hi, row gh-1 = bottom = lo
            data_row = int(round((1.0 - frac) * (gh - 1)))

            for ri in range(gh):
                gy = y0 + 1 + ri
                gx = x0 + label_w + ci
                if ri == data_row:
                    self.put(scr, gy, gx, "@")
                elif ri > data_row:
                    self.put(scr, gy, gx, ":")

        # Bottom axis
        ax_y = y0 + 1 + gh
        self.put(scr, ax_y, x0 + label_w - 1,
                 "+" + "-" * min(plot_w, len(points)))
        self.put(scr, ax_y + 1, x0 + label_w,
                 "{}s ago".format(len(points) * 2))
        end = x0 + label_w + max(0, len(points) - 3)
        self.put(scr, ax_y + 1, end, "now")

    # ---- main draw ----

    def draw(self, scr):
        h, w = scr.getmaxyx()
        w = min(w, 120)
        scr.erase()

        # Header
        title = " PWM Fan Monitor "
        st = "PAUSED" if self.paused else "LIVE"
        ul = "C" if self.celsius else "F"
        self.put(scr, 0, 0, "=" * (w - 1), curses.A_DIM)
        self.put(scr, 0, 2, title, curses.A_BOLD)
        rt = "[{}] [{}]".format(ul, st)
        self.put(scr, 0, w - len(rt) - 2, rt, curses.A_BOLD)

        # Metrics
        r = 2
        self.put(scr, r, 0, "CPU Temp:", curses.A_BOLD)
        self.put(scr, r, 10, self.fmt_temp(self.current_cpu_temp))
        self.put(scr, r, 22, "Peak:", curses.A_DIM)
        self.put(scr, r, 28, self.fmt_temp(self.peak_cpu_temp))
        self.put(scr, r, 40, "CPU Load:", curses.A_BOLD)
        load_s = "{:.0f}%".format(self.current_cpu_load) if self.current_cpu_load is not None else "--%"
        self.put(scr, r, 50, load_s)

        r += 1
        self.put(scr, r, 0, "GPU Temp:", curses.A_BOLD)
        self.put(scr, r, 10, self.fmt_temp(self.current_gpu_temp))
        self.put(scr, r, 22, "Peak:", curses.A_DIM)
        self.put(scr, r, 28, self.fmt_temp(self.peak_gpu_temp))
        self.put(scr, r, 40, "Uptime:", curses.A_BOLD)
        self.put(scr, r, 50, self.fmt_uptime())

        r += 1
        self.put(scr, r, 0, "Fan Duty:", curses.A_BOLD)
        ds = "{}%".format(self.current_duty) if self.current_duty is not None else "--%"
        self.put(scr, r, 10, ds)
        self.put(scr, r, 22, "Target:", curses.A_DIM)
        self.put(scr, r, 30, "{}%".format(self.get_curve_duty(self.current_cpu_temp)))

        # Separator
        r += 1
        self.put(scr, r, 0, "-" * (w - 1), curses.A_DIM)

        # Graphs — side by side
        r += 1
        gh = min(10, max(5, h - r - 18))
        half_w = (w - 3) // 2

        if gh > 3 and half_w > 15:
            self.draw_line_graph(scr, r, 0, half_w, gh,
                                self.cpu_temps, 38, 68,
                                "CPU Temperature")
            self.draw_line_graph(scr, r, half_w + 2, half_w, gh,
                                self.fan_duties, 0, 100,
                                "Fan Duty %")

        # Curve position
        r += gh + 3
        if r < h - 8 and self.current_cpu_temp is not None:
            self.put(scr, r, 0, "Curve Position:", curses.A_BOLD)
            r += 1
            bw = min(50, w - 10)
            if bw > 10:
                markers = list(" " * bw)
                labels = list(" " * bw)
                for t, d in GAMING_CURVE:
                    pos = int(d / 100.0 * (bw - 1))
                    if pos < bw:
                        markers[pos] = "|"
                    lbl = str(t)
                    for ci, ch in enumerate(lbl):
                        if pos + ci < bw:
                            labels[pos + ci] = ch
                self.put(scr, r, 0, "".join(markers))
                r += 1
                self.put(scr, r, 0, "".join(labels))
                r += 1
                pct = self.get_curve_duty(self.current_cpu_temp)
                fill = int(pct / 100.0 * bw)
                bar = "#" * fill + "-" * (bw - fill)
                self.put(scr, r, 0, "[{}] {}%".format(bar, pct))
                r += 1
                arrow = " " * min(fill + 1, bw) + "^"
                self.put(scr, r, 0, arrow)
                self.put(scr, r, min(fill + 3, w - 20),
                         "{} @ {}%".format(self.fmt_temp(self.current_cpu_temp), pct))

        # Events
        r += 2
        if r < h - 3 and self.events:
            self.put(scr, r, 0, "Events:", curses.A_BOLD)
            r += 1
            for ev in self.events:
                if r >= h - 2:
                    break
                t = self.fmt_temp(ev['temp']) if ev['temp'] else "--.-"
                self.put(scr, r, 0,
                         "  {} | {} | {}% -> {}%".format(
                             ev['time'], t, ev['old'], ev['new']))
                r += 1

        # Footer
        foot = " [F] Toggle C/F   [Space] Pause/Resume   [q] Quit "
        self.put(scr, h - 1, 0, "=" * (w - 1), curses.A_DIM)
        self.put(scr, h - 1, max(0, (w - len(foot)) // 2), foot, curses.A_DIM)

        scr.refresh()

    def run(self, scr):
        curses.curs_set(0)
        scr.nodelay(1)
        scr.timeout(200)
        while self.running:
            self.update()
            self.draw(scr)
            k = scr.getch()
            if k == ord('q'):
                self.running = False
            elif k in (ord('f'), ord('F')):
                self.celsius = not self.celsius
            elif k == ord(' '):
                self.paused = not self.paused


def main():
    mon = FanMonitor()
    signal.signal(signal.SIGINT, lambda s, f: setattr(mon, 'running', False))
    try:
        curses.wrapper(mon.run)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
