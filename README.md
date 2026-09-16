# apca.py — a contrast gate that does not lie in the dark

WCAG 2's contrast ratio is a light-mode formula. On a dark interface it false-passes: text that clears 4.5:1, ships with a green tick, and is genuinely hard to read at night. APCA is the perceptual model headed into WCAG 3, and it catches what the ratio misses.

This is one file, no dependencies, and it verifies itself before you trust a number from it.

```
python3 apca.py "#DEDEDE" "#121212" --require 75
python3 apca.py --tokens tokens.example.json     # exits 1 on any failure, so it gates a build
python3 apca.py --selftest                       # reproduces the published reference values
```

## What the false pass actually costs

Measured with this script against a `#1a1f2b` ground:

| WCAG 2 says | APCA says | Verdict |
|---|---|---|
| 4.47 : 1 ✅ passes | Lc 35 | fails even the decorative floor |
| 6.04 : 1 ✅ passes | Lc 47 | decorative only |
| 9.03 : 1 ✅ passes | Lc 67 | readable, still under the body-text minimum |
| **11.0 : 1** | **Lc 78** | the first row that clears body text |

On a dark ground you need roughly **11:1** to reach the body-text minimum. A dark screen shipped at "4.5:1, accessible ✓" sits near Lc 35, which is under the floor for text at any size.

## The ladder

| Level | Use |
|---|---|
| Lc 90 | fluent body text, 14px/400 and up — the preferred level |
| Lc 75 | minimum for columns of body text at 18px/400 |
| Lc 60 | minimum for content text you intend people to read |
| Lc 45 | large or decorative text only |
| below Lc 30 | the surface carries no text at all |

## Why you should not take my word for it

Run `--selftest`. It computes four pairs whose APCA values are published, and prints computed against expected:

```
PASS  #000000 on #FFFFFF   expected Lc  106.04   got Lc  106.04
PASS  #FFFFFF on #000000   expected Lc -107.88   got Lc -107.88
PASS  #888888 on #FFFFFF   expected Lc   63.06   got Lc   63.06
PASS  #FFFFFF on #888888   expected Lc  -68.54   got Lc  -68.54
```

If those four do not reproduce, the tool tells you not to use it.

## Detail

Implements APCA-W3 0.1.9 (`0.0.98G-4g-base-W3`), Andrew Somers / Myndex. Constants were checked against the SAPC-APCA specification and the `apca-w3` package documentation before this was written, rather than recalled. The script also reports the WCAG 2 ratio alongside the Lc value and flags the pairs where the two disagree, because the disagreement is the point.

APCA itself is licensed by its author for use with W3/AGWG guidelines; this is an independent implementation for checking your own tokens, not a certification tool.
