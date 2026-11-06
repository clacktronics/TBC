"""
Bit-exact reference model of rtl/sync_detect.v (incl. field detect).

Every integer operation here has a 1:1 counterpart in the RTL; the
testbench output must match this model exactly (py/compare_sim.py).

Algorithm, per 27 MHz input sample:
  1. Smooth: s4[m] = x[m-1] + 2 x[m] + x[m+1]   ([1 2 1], i.e. 4 x value).
     Index m lags the input by one sample; all timestamps use m.
  2. Distance from the slicing level, in 1/32-code units:
        A[m] = 8 * s4[m] - (tip_q + blank_q)        (tip_q, blank_q are 8.4)
     A >= 0 above the 50% point, A < 0 below.
  3. Remember the latest falling (A[m-1] >= 0 > A[m]) and rising
     (A[m-1] <= 0 < A[m]) zero crossings.
  4. Slicer with hysteresis (A <= -HYS_A enters sync, A >= +HYS_A leaves).
     On entry/exit, the remembered crossing gives the sub-sample edge:
        edge = (m_c - 1) + |a| / (|a| + |b|)     (a, b = A either side)
     computed as an 8-bit fraction by one small divide.
  5. Pulse width classifies eq / hsync / broad; < 1 us lows are glitches.
  6. Sync tip measured inside each hsync, blanking on the back porch after
     the burst, both IIR-filtered (>> 3) -> they set the slicing level.
     The back-porch window is also output as the AD9280 CLAMP pulse.
  7. Field detect: the first broad pulse after the last hsync comes ~3
     lines later in field 1, ~3.5 lines later in field 2.

Edge timestamps are 32.8 fixed point (1/256 sample) in the free-running
sample counter's time base.
"""

EQ, HS, BROAD, BAD = 0, 1, 2, 3

HYS_A = 96        # 3 codes of hysteresis, in A units (1/32 code)
GLITCH = 27       # < 1.0 us low: ignore
EQ_MAX = 80       # < 2.96 us: equalising pulse   (nominal 2.35 us = 63)
HS_MAX = 200      # < 7.4 us : hsync               (nominal 4.70 us = 127)
BAD_MAX = 400     # < 14.8 us: invalid, >= : broad (nominal 27.3 us = 737)
LOWCNT_MAX = 1023
TIP_OFS = 24      # tip measured on samples k_lead + [24, 55]
BP_OFS = 100      # blank measured on samples k_trail + [100, 131]
CLAMP_ON, CLAMP_OFF = 96, 136
LVL_SHIFT = 3
BUSY = 12         # samples after a trailing edge before a new pulse may start
FIELD2_DELTA = 5616   # 3.25 lines: split between 3 and 3.5 lines
MASK32 = (1 << 32) - 1
MASK40 = (1 << 40) - 1


def frac8(a, b):
    """rtl/div_frac.v: floor(|a| * 256 / (|a| + |b|)), always 0..255."""
    a, b = abs(a), abs(b)
    return (a << 8) // (a + b)


class SyncDetector:
    def __init__(self, tip0=16, blank0=76):
        self.m = MASK32 - 1        # first processed centre index is -1
        self.x1 = 0                # x[m]   (previous input)
        self.x2 = 0                # x[m-1]
        self.a_prev = 0
        self.tip_q = tip0 << 4
        self.blank_q = blank0 << 4
        self.fall = (0, 0, 1)      # (m_c, a, b) latest falling crossing
        self.rise = (0, 0, 1)
        self.low = False
        self.lowcnt = 0
        self.busy = 0
        self.lead_fx = 0
        self.typ = 0
        self.tip_acc = 0
        self.bp_active = False
        self.bp_cnt = 0
        self.bp_acc = 0
        self.clamp = 0
        self.last_h = 0
        self.seen_broad = True
        self.events = []      # (type, lead_fx, trail_fx)
        self.fields = []      # (field, int(lead) of first broad pulse)

    def step(self, x):
        # 1. smoothing; this step processes index m+1 using x[m+2]
        m = (self.m + 1) & MASK32
        s4 = self.x2 + 2 * self.x1 + x
        self.x2, self.x1 = self.x1, x
        # 2. slicing-level distance
        A = (s4 << 3) - (self.tip_q + self.blank_q)
        a = self.a_prev
        # 3. crossings (from the previous sample to this one)
        if a >= 0 > A:
            self.fall = (m, a, A)
        if a <= 0 < A:
            self.rise = (m, a, A)
        self.a_prev = A
        new_tip = new_blank = None

        if self.busy:
            self.busy -= 1

        # 4. back porch window / clamp gate (state from earlier samples)
        if self.bp_active:
            self.bp_cnt += 1
            c = self.bp_cnt
            if BP_OFS <= c < BP_OFS + 32:
                self.bp_acc += s4
            if c == BP_OFS + 31:
                new_blank = self.blank_q + (((self.bp_acc >> 3) - self.blank_q) >> LVL_SHIFT)
            self.clamp = 1 if CLAMP_ON <= c < CLAMP_OFF else 0
            if c >= CLAMP_OFF:
                self.bp_active = False
        else:
            self.clamp = 0

        # 5. slicer (overrides back-porch state)
        if not self.low:
            if A <= -HYS_A and self.busy == 0:
                self.low = True
                self.lowcnt = 0
                mc, fa, fb = self.fall
                self.lead_fx = ((((mc - 1) & MASK32) << 8) + frac8(fa, fb)) & MASK40
                self.tip_acc = 0
                self.bp_active = False
        else:
            if self.lowcnt < LOWCNT_MAX:
                self.lowcnt += 1
            lc = self.lowcnt
            if TIP_OFS <= lc < TIP_OFS + 32:
                self.tip_acc += s4
            if A >= HYS_A:
                self.low = False
                if lc >= GLITCH:
                    if lc < EQ_MAX:
                        typ = EQ
                    elif lc < HS_MAX:
                        typ = HS
                    elif lc < BAD_MAX:
                        typ = BAD
                    else:
                        typ = BROAD
                    mc, ra, rb = self.rise
                    trail_fx = ((((mc - 1) & MASK32) << 8) + frac8(ra, rb)) & MASK40
                    self._emit(typ, self.lead_fx, trail_fx)
                    self.busy = BUSY
                    if typ == HS:
                        new_tip = self.tip_q + (((self.tip_acc >> 3) - self.tip_q) >> LVL_SHIFT)
                        self.bp_active = True
                        self.bp_cnt = 0
                        self.bp_acc = 0

        if new_tip is not None:
            self.tip_q = new_tip
        if new_blank is not None:
            self.blank_q = new_blank
        self.m = m

    def _emit(self, typ, lead_fx, trail_fx):
        self.events.append((typ, lead_fx, trail_fx))
        k = lead_fx >> 8
        if typ == HS:
            self.last_h = k
            self.seen_broad = False
        elif typ == BROAD and not self.seen_broad:
            self.seen_broad = True
            delta = (k - self.last_h) & MASK32
            self.fields.append((1 if delta > FIELD2_DELTA else 0, k))

    def run(self, codes):
        step = self.step
        for x in codes.tolist():
            step(x)
        return self
