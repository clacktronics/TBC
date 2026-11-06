"""Check sim/out/rtl_uart.txt (tb_top) against the model's expected packets."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import packets  # noqa: E402
from sync_model import SyncDetector  # noqa: E402

root = os.path.join(os.path.dirname(__file__), "..", "sim")
codes = np.array([int(l, 16) for l in open(os.path.join(root, "vectors", "cvbs.hex")) if l.strip()],
                 np.uint8)
det = SyncDetector().run(codes)
exp = packets.expected(det.events, det.fields, decim=4)
raw = bytes(int(l, 16) for l in open(os.path.join(root, "out", "rtl_uart.txt")) if l.strip())
got = packets.parse(raw)
bad = sum(a != b for a, b in zip(exp, got))
print(f"packets: expected {len(exp)}, received {len(got)}, mismatches {bad}")
ok = bad == 0 and len(exp) == len(got)
print("PASS: UART stream matches model" if ok else "FAIL")
sys.exit(0 if ok else 1)
