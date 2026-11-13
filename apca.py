#!/usr/bin/env python3
"""
apca.py — a contrast gate for dark interfaces.

WCAG 2's contrast ratio overstates contrast between dark colours. It false-passes
dark interfaces: text that clears 4.5:1 and is genuinely hard to read at night.
APCA is a perceptual contrast model developed as a candidate for WCAG 3, and it
catches what the ratio misses.

Usage
  apca.py "#DEDEDE" "#121212"                one pair: text on background
  apca.py "#DEDEDE" "#121212" --require 75   gate the pair at an Lc level
  apca.py --tokens tokens.json               every declared pair in a token file
  apca.py --selftest                         verify this implementation

Exit codes: 0 every gated pair passes, 1 a pair fails its required level,
2 the input could not be read (bad colour, bad token file, bad arguments).

Algorithm: APCA-W3 0.1.9 (0.0.98G-4g-base-W3), Andrew Somers / Myndex.
Constants verified 2026-09-15 against the SAPC-APCA LaTeX specification and
the apca-w3 package documentation. The reference values in --selftest and in
tests/ were produced by running apca-w3 0.1.9 itself. Run --selftest to
confirm this file reproduces them before trusting a number from it.
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

# The Lc ladder. Levels and wording are condensed from the published APCA
# use-case levels ("APCA in a Nutshell", shipped in apca-w3/docs).
# [SOURCED] APCA readability criterion — not this repo's measurement.
LADDER = [
    (90, "preferred level for body text, 14px/400 and up"),
    (75, "minimum for columns of body text at 18px/400"),
    (60, "minimum for content text you intend people to read, 24px/400 or 16px/700"),
    (45, "minimum for large headline text, 36px/400 or 24px/700"),
    (30, "absolute minimum for any text: placeholder, disabled and spot text only"),
]

# Text on background, expected Lc. The first eight pairs and their values are
# the test vectors in apca-w3 0.1.9 (test/index.js). The black/white pair was
# computed by running the same package. tests/ holds 512 more pairs.
REFERENCE = [
    ("#888", "#fff", 63.056469930209424), ("#fff", "#888", -68.54146436644962),
    ("#000", "#aaa", 58.146262578561334), ("#aaa", "#000", -56.24113336839742),
    ("#123", "#def", 91.66830811481631), ("#def", "#123", -93.06770049484275),
    ("#123", "#444", 8.32326136957393), ("#444", "#123", -7.526878460278154),
    ("#000", "#fff", 106.04067321268862), ("#fff", "#000", -107.88473318309848),
]
SELFTEST_TOLERANCE = 1e-9


def _hex_to_rgb(s):
    """'#RGB' or '#RRGGBB' (the '#' is optional) to an (r, g, b) tuple of 0-255."""
    if not isinstance(s, str):
        raise ValueError(f"not a hex colour: {s!r}")
    digits = s.strip()
    if digits.startswith("#"):
        digits = digits[1:]
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    if len(digits) != 6 or any(c not in "0123456789abcdefABCDEF" for c in digits):
        raise ValueError(f"not a hex colour: {s!r} (expected #RGB or #RRGGBB, no alpha)")
    return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))


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
    ok = True
    print("APCA-W3 0.1.9 self-test — computed vs apca-w3 reference\n")
    for txt, bg, expect in REFERENCE:
        got = lc(txt, bg)
        good = abs(got - expect) <= SELFTEST_TOLERANCE
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {txt} on {bg}   "
              f"expected Lc {expect:>10.5f}   got Lc {got:>10.5f}")
    print("\n" + ("Implementation reproduces the reference values."
                  if ok else "MISMATCH — do not use this gate until fixed."))
    return 0 if ok else 1


def _report_pair(txt, bg, required=None, label=None):
    value = lc(txt, bg)
    level, meaning = describe(value)
    ratio = wcag2(txt, bg)
    polarity = ("light text on dark" if value < 0 else
                "dark text on light" if value > 0 else "below the low-contrast clip")
    head = f"{label + ': ' if label else ''}{txt} on {bg}"
    print(f"\n{head}")
    print(f"  APCA    Lc {value:+.1f}  ({polarity})")
    if level:
        print(f"  clears  Lc {level}, {meaning}")
    else:
        print(f"  clears  nothing, {meaning}")
    print(f"  WCAG 2  {ratio:.2f}:1  {'PASS' if ratio >= 4.5 else 'fail'} at 4.5:1")
    if ratio >= 4.5 and abs(value) < 60:
        print("  ** DISAGREEMENT: passes WCAG 2 at 4.5:1, under the APCA minimum for content text (Lc 60).")
    if required is not None:
        passed = verdict(value, required)
        print(f"  gate    needs Lc {required} → {'PASS' if passed else 'FAIL'}")
        return passed
    return True


def _load_tokens(path):
    """Read and validate a token file before anything is printed."""
    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}: not valid JSON ({e})")
    pairs = data.get("pairs") if isinstance(data, dict) else data
    if not isinstance(pairs, list):
        raise ValueError(f"{path}: expected a list of pairs or {{\"pairs\": [...]}}")
    for i, entry in enumerate(pairs, 1):
        if not isinstance(entry, dict) or "text" not in entry or "bg" not in entry:
            raise ValueError(f"{path}: pair {i} needs \"text\" and \"bg\"")
        _hex_to_rgb(entry["text"]), _hex_to_rgb(entry["bg"])
        req = entry.get("require")
        if req is not None and (isinstance(req, bool) or not isinstance(req, (int, float))):
            raise ValueError(f"{path}: pair {i} \"require\" must be a number, got {req!r}")
    return pairs


def main():
    p = argparse.ArgumentParser(description="APCA contrast gate (APCA-W3 0.1.9)")
    p.add_argument("text", nargs="?", help="text colour, hex")
    p.add_argument("bg", nargs="?", help="background colour, hex")
    p.add_argument("--require", type=int, default=None,
                   help="required Lc level for this pair (90/75/60/45/30)")
    p.add_argument("--tokens", help="JSON file: {\"pairs\":[{\"label\":..,\"text\":..,\"bg\":..,\"require\":60}]}")
    p.add_argument("--selftest", action="store_true", help="verify against apca-w3 reference values")
    a = p.parse_args()

    if a.selftest:
        sys.exit(_selftest())

    try:
        if a.tokens:
            pairs = _load_tokens(a.tokens)
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
    except (ValueError, OSError) as e:
        # A bad input must not look like a contrast failure (exit 1) to a build.
        print(f"apca.py: error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
