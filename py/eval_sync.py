"""
Score the sync edge detector against ground truth, and write test vectors
for the RTL testbench.

    python3 py/eval_sync.py                # all scenarios, prints a table
    python3 py/eval_sync.py --vectors      # also write sim/vectors/*
    python3 py/eval_sync.py --plot out.png # timing-error plot (matplotlib)
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import pal                                  # noqa: E402
from sync_model import SyncDetector, HS, EQ, BROAD  # noqa: E402

NS_PER_SAMPLE = 1e9 / pal.FS

SCENARIOS = {
    # name: (snr_db, timebase kwargs)
    "clean, stable":       (None, dict(enabled=False)),
    "clean, VHS timebase": (None, dict()),
    "45 dB, stable":       (45.0, dict(enabled=False)),
    "45 dB, VHS timebase": (45.0, dict()),
    "38 dB, VHS timebase": (38.0, dict()),
}


def match(events, truth):
    """Pair detected events with ground-truth pulses (nearest leading edge)."""
    tl = np.array([t[1] for t in truth])
    pairs = []
    for ev in events:
        lead = ev[1] / 256.0
        i = int(np.argmin(np.abs(tl - lead)))
        if abs(tl[i] - lead) < 20:
            pairs.append((ev, truth[i]))
    return pairs


def score(codes, truth, det):
    pairs = match(det.events, truth)
    types_ok = sum(ev[0] == tr[0] for ev, tr in pairs)
    hs = [(ev, tr) for ev, tr in pairs if ev[0] == HS and tr[0] == HS]
    el = np.array([ev[1] / 256 - tr[1] for ev, tr in hs])
    et = np.array([ev[2] / 256 - tr[2] for ev, tr in hs])
    mid = (el + et) / 2
    return dict(n_truth=len(truth), n_det=len(det.events), matched=len(pairs),
                types_ok=types_ok, hs=len(hs),
                lead_mean=el.mean(), lead_std=el.std(), lead_max=np.abs(el - el.mean()).max(),
                trail_std=et.std(), mid_std=mid.std(),
                fields=det.fields)


def run(name, n_lines, start_line=600):
    snr, tbk = SCENARIOS[name]
    tb = pal.Timebase(n_lines=n_lines + start_line + 10, **tbk)
    codes, truth = pal.synth(n_lines=n_lines, start_line=start_line, snr_db=snr, tb=tb)
    det = SyncDetector().run(codes)
    return codes, truth, det, tb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=700)
    ap.add_argument("--vectors", action="store_true")
    ap.add_argument("--vector-lines", type=int, default=700)
    ap.add_argument("--plot")
    args = ap.parse_args()

    print(f"{'scenario':22s} {'pulses':>6s} {'det':>5s} {'type ok':>8s} "
          f"{'lead σ':>8s} {'trail σ':>8s} {'mid σ':>8s} {'lead max':>9s}  fields")
    for name in SCENARIOS:
        codes, truth, det, _ = run(name, args.lines)
        s = score(codes, truth, det)
        f = "".join(str(x[0] + 1) for x in s["fields"])
        print(f"{name:22s} {s['n_truth']:6d} {s['n_det']:5d} {s['types_ok']:4d}/{s['matched']:<4d}"
              f"{s['lead_std'] * NS_PER_SAMPLE:7.2f}ns {s['trail_std'] * NS_PER_SAMPLE:7.2f}ns "
              f"{s['mid_std'] * NS_PER_SAMPLE:7.2f}ns "
              f"{s['lead_max'] * NS_PER_SAMPLE:8.2f}ns  {f}")
    print(f"(constant lead offset from AA-filter delay ≈ {s['lead_mean']:.2f} samples; "
          f"σ/max are after removing it)")

    if args.vectors:
        root = os.path.join(os.path.dirname(__file__), "..", "sim", "vectors")
        os.makedirs(root, exist_ok=True)
        codes, truth, det, _ = run("45 dB, VHS timebase", args.vector_lines)
        with open(os.path.join(root, "cvbs.hex"), "w") as f:
            f.write("\n".join(f"{c:02x}" for c in codes.tolist()) + "\n")
        with open(os.path.join(root, "expected_events.txt"), "w") as f:
            for typ, lf, tf in det.events:
                f.write(f"E {typ} {lf:010x} {tf:010x}\n")
            for fld, k in det.fields:
                f.write(f"F {fld} {k:08x}\n")
        with open(os.path.join(root, "n_samples.vh"), "w") as f:
            f.write(f"`define N_SAMPLES {len(codes)}\n")
        print(f"wrote {len(codes)} samples, {len(det.events)} events, "
              f"{len(det.fields)} fields to sim/vectors/")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        codes, truth, det, tb = run("45 dB, VHS timebase", 1250)
        hs = [(ev, tr) for ev, tr in match(det.events, truth) if ev[0] == HS]
        lead = np.array([ev[1] / 256 for ev, _ in hs])
        tl = np.array([tr[1] for _, tr in hs])
        n = np.round((tl - tl[0]) / pal.SPL)        # line number
        ideal = np.polyval(np.polyfit(n, tl, 1), n)
        fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        ax[0].plot(n, (tl - ideal) * NS_PER_SAMPLE, lw=2, label="true timebase error")
        ax[0].plot(n, (lead - lead.mean() + tl.mean() - ideal) * NS_PER_SAMPLE, lw=0.7,
                   label="measured (sync_detect)")
        ax[0].set_ylabel("H timing vs. linear fit (ns)")
        ax[0].legend()
        err = (lead - tl) - (lead - tl).mean()
        ax[1].plot(n, err * NS_PER_SAMPLE, ".", ms=2)
        ax[1].set_ylabel("measurement error (ns)")
        ax[1].set_xlabel("line  (two fields, simulated VHS @ 45 dB SNR)")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=120)
        print("wrote", args.plot)


if __name__ == "__main__":
    main()
