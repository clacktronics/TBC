"""Decode the event_logger UART stream (10-byte packets starting 0xA5)."""


def parse(data):
    """bytes -> list of dicts. Resynchronises on 0xA5 if bytes are lost."""
    out, i = [], 0
    while i + 10 <= len(data):
        if data[i] != 0xA5:
            i += 1
            continue
        flags = data[i + 1]
        lead = int.from_bytes(data[i + 2:i + 6], "big")
        trail = int.from_bytes(data[i + 6:i + 10], "big")
        out.append(dict(marker=bool(flags & 0x80), field=(flags >> 6) & 1,
                        type=flags & 3, lead=lead, trail=trail))
        i += 10
    return out


def expected(events, fields, decim):
    """What event_logger should send, given the model's event list."""
    out, h, fi = [], 0, 0
    seen_broad, last_h = True, None
    for typ, lf, tf in events:
        if typ == 1:
            if h == 0:
                out.append(dict(marker=False, field=0, type=1,
                                lead=lf & 0xFFFFFFFF, trail=tf & 0xFFFFFFFF))
            h = 0 if h == decim - 1 else h + 1
            seen_broad = False
        elif typ == 2 and not seen_broad:
            seen_broad = True
            fld = fields[fi][0]
            fi += 1
            h = 0
            out.append(dict(marker=True, field=fld, type=2,
                            lead=lf & 0xFFFFFFFF, trail=tf & 0xFFFFFFFF))
    return out


class Unwrapper:
    """Turn 24.8 wrapping timestamps into a monotonic float (samples)."""

    def __init__(self):
        self.base = 0
        self.last = None

    def __call__(self, v):
        if self.last is not None and v < self.last - (1 << 31):
            self.base += 1 << 32
        self.last = v
        return (self.base + v) / 256.0
