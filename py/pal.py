"""
PAL composite (CVBS) synthesiser for TBC development.

Generates 8-bit ADC samples of a PAL B/G signal (625/50, 75% colour bars)
as a 27 MSPS free-running ADC would see it, with VHS-like timebase errors:
  * slow tape-speed / capstan wander
  * head-drum flutter (25 Hz)
  * per-line random jitter (smooth, so lines also stretch)
  * head-switch timing step ~6.5 lines before each vertical sync
plus white noise, a 6 MHz 5th-order anti-alias filter and 8-bit quantisation.

It also returns ground truth: the ADC-time position (in samples) of every
sync pulse's 50% leading and trailing edge, so detectors can be scored.

ADC scaling (matches the front end assumed in the RTL):
    code = 16 + (volts + 0.3) * 200    -> sync tip 16, blank 76, white 216
"""

import numpy as np
from scipy import signal

# ---- PAL timing (seconds) -------------------------------------------------
H = 64e-6                  # line period
FSC = 4.43361875e6         # colour subcarrier
FS = 27e6                  # ADC sample rate -> exactly 1728 samples/line
SPL = int(round(H * FS))   # 1728
OVS = 4                    # oversampling for the analogue model
HSYNC_W = 4.7e-6
EQ_W = 2.35e-6
BROAD_W = 27.3e-6
SYNC_EDGE = 0.30e-6        # full raised-cosine width (~0.18 us 10-90%)
BURST_START, BURST_LEN = 5.6e-6, 2.25e-6
ACTIVE_START, ACTIVE_END = 10.5e-6, 62.35e-6

# ADC transfer
CODES_PER_VOLT = 200.0
CODE_SYNC_TIP = 16.0

# pulse types (shared with the RTL / model)
EQ, HS, BROAD, BAD = 0, 1, 2, 3
TYPE_NAME = {EQ: "eq", HS: "hsync", BROAD: "broad", BAD: "bad"}
_W = {"H": HSYNC_W, "E": EQ_W, "B": BROAD_W}


def line_pulses(ln):
    """(first-half, second-half) sync pulse types for frame line 1..625."""
    if ln in (1, 2, 314, 315):
        return ("B", "B")
    if ln == 3:
        return ("B", "E")
    if ln == 313:
        return ("E", "B")
    if ln in (4, 5, 311, 312, 316, 317, 624, 625):
        return ("E", "E")
    if ln == 318:
        return ("E", None)
    if ln == 623:
        return ("H", "E")
    return ("H", None)


_PULSE_TABLE = [line_pulses(ln) for ln in range(1, 626)]
_KINDS = [np.array([p[h] or "" for p in _PULSE_TABLE]) for h in (0, 1)]

# 75% colour bars: white yellow cyan green magenta red blue black
_BARS = [(1, 1, 1), (1, 1, 0), (0, 1, 1), (0, 1, 0),
         (1, 0, 1), (1, 0, 0), (0, 0, 1), (0, 0, 0)]


def _bar_yuv():
    out = []
    for r, g, b in _BARS:
        r, g, b = 0.75 * r, 0.75 * g, 0.75 * b
        y = 0.299 * r + 0.587 * g + 0.114 * b
        out.append((0.7 * y, 0.7 * 0.493 * (b - y), 0.7 * 0.877 * (r - y)))
    return out


BAR_YUV = _bar_yuv()


def _smooth_step(x, x0, width):
    """0 -> 1 raised-cosine step centred on x0 (50% point at x0)."""
    u = np.clip((x - x0) / width + 0.5, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * u)


def _pulse(x, a, b, width):
    return _smooth_step(x, a, width) - _smooth_step(x, b, width)


def cvbs(tau):
    """Ideal PAL composite voltage at source time tau (array, seconds).
    tau = 0 is the start (sync leading edge) of frame line 1."""
    L = np.floor(tau / H).astype(np.int64)
    x = tau - L * H
    ln = (L % 625)                     # 0-based frame line
    low = np.zeros_like(tau)
    # sync pulses of this line, plus the first pulse of the next line
    # (its leading edge starts slightly before the line boundary)
    for lnn, xx in ((ln, x), ((ln + 1) % 625, x - H)):
        for half in (0, 1):
            k = _KINDS[half][lnn]
            for name, w in _W.items():
                m = k == name
                if not np.any(m):
                    continue
                t0 = half * H / 2
                low[m] += _pulse(xx[m], t0, t0 + w, SYNC_EDGE)
    ln1 = ln + 1
    ph = 2 * np.pi * FSC * tau
    vsw = np.where(L % 2 == 0, 1.0, -1.0)          # PAL V-switch
    # burst (blanked in the vertical interval)
    has_burst = ((ln1 >= 7) & (ln1 <= 309)) | ((ln1 >= 320) & (ln1 <= 621))
    env = _pulse(x, BURST_START, BURST_START + BURST_LEN, 0.3e-6) * has_burst
    a = 0.15 / np.sqrt(2)
    burst = env * (-a * np.sin(ph) + vsw * a * np.cos(ph))
    # active picture: colour bars
    active = ((ln1 >= 23) & (ln1 <= 310)) | ((ln1 >= 336) & (ln1 <= 622))
    bw = (ACTIVE_END - ACTIVE_START) / 8
    Y = np.zeros_like(tau); U = np.zeros_like(tau); V = np.zeros_like(tau)
    for i, (y, u, v) in enumerate(BAR_YUV):
        p = _pulse(x, ACTIVE_START + i * bw, ACTIVE_START + (i + 1) * bw, 0.15e-6)
        Y += y * p; U += u * p; V += v * p
    pic = (Y + U * np.sin(ph) + vsw * V * np.cos(ph)) * active
    return pic + burst - 0.3 * np.clip(low, 0, 1)


class Timebase:
    """VHS-like timing error e(t): source time tau = t - e(t)."""

    def __init__(self, seed=1, slow_amp=1.0e-6, slow_f=3.0, drum_amp=150e-9,
                 line_jitter=10e-9, head_skew=400e-9, speed_ppm=100.0,
                 n_lines=4000, enabled=True):
        rng = np.random.default_rng(seed)
        self.enabled = enabled
        self.slow_amp, self.slow_f = slow_amp, slow_f
        self.drum_amp, self.drum_ph = drum_amp, rng.uniform(0, 2 * np.pi)
        self.k = speed_ppm * 1e-6
        self.grid = np.arange(n_lines + 2) * H
        self.jit = rng.normal(0, line_jitter, n_lines + 2)
        self.head_skew = head_skew

    def __call__(self, t):
        if not self.enabled:
            return np.zeros_like(t)
        e = self.slow_amp * np.sin(2 * np.pi * self.slow_f * t)
        e += self.drum_amp * np.sin(2 * np.pi * 25 * t + self.drum_ph)
        e += self.k * t
        e += np.interp(t, self.grid, self.jit)
        # head switch: ~6.5 lines before each field's vertical sync
        fl = (t / H) % 625.0
        head_a = (fl >= 305.6) & (fl < 617.6)
        e += np.where(head_a, 0.5, -0.5) * self.head_skew
        return e


def synth(n_lines=1250, start_line=600, snr_db=45.0, tb=None, seed=2):
    """Return (codes uint8 @27 MSPS, truth list).

    truth: list of (type, lead_samples, trail_samples, frame_line) where the
    edge positions are in ADC sample units (sample m is at t = m / FS),
    *before* the anti-alias filter's constant group delay (see eval)."""
    tb = tb or Timebase()
    rng = np.random.default_rng(seed)
    fso = FS * OVS
    t0 = start_line * H
    n_out = n_lines * SPL
    sos = signal.butter(5, 6e6, fs=fso, output="sos")
    zi = np.zeros((sos.shape[0], 2))
    sig_inband = 0.7 / 10 ** (snr_db / 20) if snr_db is not None else 0.0
    sig_white = sig_inband * np.sqrt((fso / 2) / 5e6)
    out = np.empty(n_out, np.uint8)
    chunk = 32 * SPL * OVS
    total = n_out * OVS
    first = True
    for c0 in range(0, total, chunk):
        n = np.arange(c0, min(total, c0 + chunk))
        t = t0 + n / fso
        v = cvbs(t - tb(t))
        if sig_white:
            v = v + rng.normal(0, sig_white, v.shape)
        if first:   # start the filter settled at blanking level
            zi = signal.sosfilt_zi(sos) * v[0]
            first = False
        v, zi = signal.sosfilt(sos, v, zi=zi)
        v = v[(n % OVS) == 0]
        codes = np.clip(np.round(CODE_SYNC_TIP + (v + 0.3) * CODES_PER_VOLT), 0, 255)
        out[c0 // OVS: c0 // OVS + len(codes)] = codes.astype(np.uint8)

    # ground truth: solve t - e(t) = tau for each edge
    def t_of(tau):
        t = np.array(tau, float)
        for _ in range(6):
            t = tau + tb(t)
        return t

    truth = []
    for L in range(start_line - 1, start_line + n_lines + 1):
        ln = L % 625
        for half, kind in enumerate(_PULSE_TABLE[ln]):
            if not kind:
                continue
            a = L * H + half * H / 2
            b = a + _W[kind]
            ta, tb_ = t_of(np.array([a]))[0], t_of(np.array([b]))[0]
            la, lb = (ta - t0) * FS, (tb_ - t0) * FS
            if 20 < la < n_out - 40:
                typ = {"H": HS, "E": EQ, "B": BROAD}[kind]
                truth.append((typ, la, lb, ln + 1))
    return out, truth


if __name__ == "__main__":
    codes, truth = synth(n_lines=20, start_line=620)
    print(len(codes), "samples,", len(truth), "pulses")
    print("min/max code", codes.min(), codes.max())
