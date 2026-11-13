#!/usr/bin/env python3
"""Compare a freshly generated reference file against the committed one.

Usage: compare_reference.py regenerated.json tests/reference_apca_w3_0.1.9.json

The colour pairs must be identical and in the same order. The Lc values may
differ by 1e-9: Math.pow is not bit-identical across Node versions and
platforms, and the last one or two digits of a double move with it.
"""
import json
import sys

TOLERANCE = 1e-9


def main(fresh_path, committed_path):
    with open(fresh_path) as f:
        fresh = json.load(f)["pairs"]
    with open(committed_path) as f:
        committed = json.load(f)["pairs"]
    if [(t, b) for t, b, _ in fresh] != [(t, b) for t, b, _ in committed]:
        print("The colour pairs differ. Regenerate the fixture with tools/gen_reference.mjs.")
        return 1
    worst = max(abs(a[2] - b[2]) for a, b in zip(fresh, committed))
    bad = [(a, b) for a, b in zip(fresh, committed) if abs(a[2] - b[2]) > TOLERANCE]
    for a, b in bad:
        print(f"MISMATCH {a[0]} on {a[1]}: apca-w3 gives {a[2]!r}, committed {b[2]!r}")
    print(f"{len(fresh)} pairs compared, {len(bad)} beyond {TOLERANCE}, largest difference {worst:.3g}.")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
