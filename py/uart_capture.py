"""
Capture sync timing from the board and plot the source's timebase error.

    pip install pyserial matplotlib numpy
    python3 py/uart_capture.py /dev/tty.usbserial-XXXX --seconds 5 --plot jitter.png
    python3 py/uart_capture.py --file capture.bin --plot jitter.png   # replay

Per field it prints the field id and the spread of the reported hsync
edges around a straight-line fit (i.e. how much the source's line timing
wanders within the field), which is exactly what the TBC has to remove.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import packets  # noqa: E402

FS = 27e6
NS = 1e9 / FS


def read_serial(port, baud, seconds, save):
    import serial
    data = bytearray()
    with serial.Serial(port, baud, timeout=0.1) as s:
        s.reset_input_buffer()
        t_end = time.time() + seconds
        while time.time() < t_end:
            data += s.read(4096)
    if save:
        open(save, "wb").write(data)
    return bytes(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=5)
    ap.add_argument("--save", help="write raw bytes here")
    ap.add_argument("--file", help="read raw bytes from a file instead")
    ap.add_argument("--decim", type=int, default=32, help="must match DECIM in top.v")
    ap.add_argument("--plot")
    a = ap.parse_args()

    raw = open(a.file, "rb").read() if a.file else read_serial(a.port, a.baud, a.seconds, a.save)
    pk = packets.parse(raw)
    if not pk:
        sys.exit("no packets - check wiring, baud and that sync is present (LED 0)")
    unwrap = packets.Unwrapper()
    fields, cur = [], None
    for p in pk:
        t = unwrap(p["lead"])
        if p["marker"]:
            cur = dict(id=p["field"], t0=t, h=[])
            fields.append(cur)
        elif cur is not None and p["type"] == 1:
            cur["h"].append(t)

    print(f"{len(pk)} packets, {len(fields)} fields")
    resid_all = []
    for i, f in enumerate(fields):
        h = np.array(f["h"])
        if len(h) < 4:
            continue
        n = np.round((h - h[0]) / 1728.0)          # line number within field
        fit = np.polyfit(n, h, 1)
        r = (h - np.polyval(fit, n)) * NS
        resid_all.append((f["id"], n, r))
        print(f"field {i:3d} ({f['id'] + 1}): {len(h):3d} lines, "
              f"line period {fit[0] / FS * 1e6:.4f} us, wander ±{np.abs(r).max():6.1f} ns "
              f"(rms {r.std():5.1f} ns)")

    if a.plot and resid_all:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4))
        for fid, n, r in resid_all[:20]:
            ax.plot(n, r, lw=0.8, color="C0" if fid == 0 else "C1")
        ax.set_xlabel("line within field (relative)")
        ax.set_ylabel("hsync timing vs. fit (ns)")
        ax.set_title("Source timebase wander per field (blue = field 1, orange = field 2)")
        fig.tight_layout()
        fig.savefig(a.plot, dpi=120)
        print("wrote", a.plot)


if __name__ == "__main__":
    main()
