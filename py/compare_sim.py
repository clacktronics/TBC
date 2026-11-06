"""Compare RTL simulation output with the Python model (bit-exact)."""
import os
import sys

root = os.path.join(os.path.dirname(__file__), "..", "sim")
exp = open(os.path.join(root, "vectors", "expected_events.txt")).read().split("\n")
exp_e = [l for l in exp if l.startswith("E")]
exp_f = [l for l in exp if l.startswith("F")]
got_e = open(os.path.join(root, "out", "rtl_events.txt")).read().split("\n")
got_e = [l for l in got_e if l]
got_f = [l for l in open(os.path.join(root, "out", "rtl_fields.txt")).read().split("\n") if l]

ok = True
for name, e, g in (("events", exp_e, got_e), ("fields", exp_f, got_f)):
    if len(e) != len(g):
        print(f"{name}: count mismatch, model {len(e)} vs RTL {len(g)}")
        ok = False
    bad = [(i, a, b) for i, (a, b) in enumerate(zip(e, g)) if a != b]
    for i, a, b in bad[:10]:
        print(f"{name}[{i}]: model '{a}'  RTL '{b}'")
    if bad:
        ok = False
    print(f"{name}: {len(g)} from RTL, {len(bad)} mismatches")
print("PASS: RTL matches model bit-exactly" if ok else "FAIL")
sys.exit(0 if ok else 1)
