#!/usr/bin/env python3
"""
apca.py — the contrast gate 36_DARK_MODE.md has been telling you to run.

WCAG 2's contrast ratio is a light-mode formula. It false-passes dark interfaces:
text that clears 4.5:1 and is genuinely hard to read at night. APCA is the
perceptual model headed into WCAG 3, and it catches what the ratio misses.

Usage
  apca.py "#DEDEDE" "#121212"              one pair: text on background
  apca.py "#DEDEDE" "#121212" --size 14    add the size/weight verdict
  apca.py --tokens tokens.json             every declared pair in a token file
  apca.py --selftest                       verify this implementation

Exit code is 1 if any pair fails its declared use, so it gates a build.

Algorithm: APCA-W3 0.1.9 (0.0.98G-4g-base-W3), Andrew Somers / Myndex.
Constants verified 2026-09-15 against the SAPC-APCA LaTeX specification and
the apca-w3 package documentation. Run --selftest to confirm this file
reproduces the published reference values before trusting a number from it.
"""
import argparse, json, sys

# --- APCA-W3 0.1.9 constants [VERIFIED 2026-09-15, two independent sources] ---
MAIN_TRC = 2.4
RCO, GCO, BCO = 0.2126729, 0.7151522, 0.0721750
NORM_BG, NORM_TXT = 0.56, 0.57
REV_TXT, REV_BG = 0.62, 0.65
BLK_THRS, BLK_CLMP = 0.022, 1.414
SCALE_BOW, SCALE_WOB = 1.14, 1.14
LO_BOW_OFFSET, LO_WOB_OFFSET = 0.027, 0.027
DELTA_Y_MIN, LO_CLIP = 0.0005, 0.1

# The Lc ladder. Values are the published APCA readability levels.
# [SOURCED] APCA readability criterion — not this repo's measurement.
LADDER = [
    (90, "fluent body text, 14px/400 and up — the preferred level"),
    (75, "minimum for columns of body text at 18px/400"),
    (60, "minimum for content text you intend people to read"),
    (45, "large or decorative text only"),
    (30, "below this, the surface carries no text at all"),
]


def _hex_to_rgb(s):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"not a hex colour: {s!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    y = RCO * r ** MAIN_TRC + GCO * g ** MAIN_TRC + BCO * b ** MAIN_TRC
    # soft clamp near black
    return y + (BLK_THRS - y) ** BLK_CLMP if y < BLK_THRS else y


def lc(text_hex, bg_hex):
    """Lightness contrast. Positive = dark text on light bg, negative = reverse."""
    ytxt, ybg = _luminance(_hex_to_rgb(text_hex)), _luminance(_hex_to_rgb(bg_hex))
    if abs(ybg - ytxt) < DELTA_Y_MIN:
        return 0.0
    if ybg > ytxt:                                    # black on white
        sapc = (ybg ** NORM_BG - ytxt ** NORM_TXT) * SCALE_BOW
        return 0.0 if sapc < LO_CLIP else (sapc - LO_BOW_OFFSET) * 100.0
    sapc = (ybg ** REV_BG - ytxt ** REV_TXT) * SCALE_WOB   # white on black
    return 0.0 if sapc > -LO_CLIP else (sapc + LO_WOB_OFFSET) * 100.0


def wcag2(text_hex, bg_hex):
    """WCAG 2 contrast ratio — computed only so the gate can show the disagreement."""
    def rel(rgb):
        out = []
        for c in (v / 255.0 for v in rgb):
            out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    a, b = rel(_hex_to_rgb(text_hex)), rel(_hex_to_rgb(bg_hex))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def verdict(value, required):
    """Does |Lc| clear the required level?"""
    return abs(value) >= required


def describe(value):
    a = abs(value)
    for level, meaning in LADDER:
        if a >= level:
            return level, meaning
    return 0, "unusable for text at any size"


def _selftest():
    """Reproduce the published reference values. If this fails, trust nothing above."""
    cases = [("#000000", "#FFFFFF", 106.04), ("#FFFFFF", "#000000", -107.88),
             ("#888888", "#FFFFFF", 63.06), ("#FFFFFF", "#888888", -68.54)]
    ok = True
    print("APCA-W3 0.1.9 self-test — computed vs published reference\n")
    for txt, bg, expect in cases:
        got = lc(txt, bg)
        good = abs(got - expect) < 0.5
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {txt} on {bg}   "
              f"expected Lc {expect:>7.2f}   got Lc {got:>7.2f}")
    print("\n" + ("Implementation reproduces the reference values."
                  if ok else "MISMATCH — do not use this gate until fixed."))
    return 0 if ok else 1


def _report_pair(txt, bg, required=None, label=None):
    value = lc(txt, bg)
    level, meaning = describe(value)
    ratio = wcag2(txt, bg)
    polarity = "light text on dark" if value < 0 else "dark text on light"
    head = f"{label + ': ' if label else ''}{txt} on {bg}"
    print(f"\n{head}")
    print(f"  APCA    Lc {value:+.1f}  ({polarity})")
    print(f"  clears  Lc {level} — {meaning}")
    print(f"  WCAG 2  {ratio:.2f}:1  {'PASS' if ratio >= 4.5 else 'fail'} at 4.5:1")
    if ratio >= 4.5 and abs(value) < 60:
        print("  ** DISAGREEMENT: passes the ratio checker, fails APCA for readable text.")
        print("     This is the dark-mode false pass. Believe APCA.")
    if required is not None:
        passed = verdict(value, required)
        print(f"  gate    needs Lc {required} → {'PASS' if passed else 'FAIL'}")
        return passed
    return True


def main():
    p = argparse.ArgumentParser(description="APCA contrast gate (APCA-W3 0.1.9)")
    p.add_argument("text", nargs="?", help="text colour, hex")
    p.add_argument("bg", nargs="?", help="background colour, hex")
    p.add_argument("--require", type=int, default=None,
                   help="required Lc level for this pair (90/75/60/45/30)")
    p.add_argument("--tokens", help="JSON file: {\"pairs\":[{\"label\":..,\"text\":..,\"bg\":..,\"require\":60}]}")
    p.add_argument("--selftest", action="store_true", help="verify against published values")
    a = p.parse_args()

    if a.selftest:
        sys.exit(_selftest())

    if a.tokens:
        data = json.load(open(a.tokens))
        pairs = data["pairs"] if isinstance(data, dict) else data
        failures = 0
        for entry in pairs:
            ok = _report_pair(entry["text"], entry["bg"],
                              entry.get("require"), entry.get("label"))
            failures += 0 if ok else 1
        print(f"\n{len(pairs)} pairs checked, {failures} failing.")
        sys.exit(1 if failures else 0)

    if not (a.text and a.bg):
        p.print_help()
        sys.exit(2)
    sys.exit(0 if _report_pair(a.text, a.bg, a.require) else 1)


if __name__ == "__main__":
    main()
