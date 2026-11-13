"""Tests for apca.py.

The expected Lc values here are never this repo's own output. They come from
apca-w3 0.1.9: its published test vectors, and a fixture produced by running
the package (tools/gen_reference.mjs).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import apca  # noqa: E402

# Python's ** and JavaScript's Math.pow may differ in the last bit on some
# platforms. Lc values are reported to one decimal place.
TOL = 1e-9

# apca-w3 0.1.9, test/index.js: colour list and contrastResult array.
UPSTREAM_VECTORS = [
    ("#888", "#fff", 63.056469930209424),
    ("#fff", "#888", -68.54146436644962),
    ("#000", "#aaa", 58.146262578561334),
    ("#aaa", "#000", -56.24113336839742),
    ("#123", "#def", 91.66830811481631),
    ("#def", "#123", -93.06770049484275),
    ("#123", "#444", 8.32326136957393),
    ("#444", "#123", -7.526878460278154),
]

FIXTURE = json.loads((ROOT / "tests" / "reference_apca_w3_0.1.9.json").read_text())["pairs"]


# --- the algorithm -----------------------------------------------------------

@pytest.mark.parametrize("text,bg,expected", UPSTREAM_VECTORS)
def test_upstream_test_vectors(text, bg, expected):
    assert apca.lc(text, bg) == pytest.approx(expected, abs=TOL)


def test_fixture_covers_both_polarities_and_the_clip():
    values = [e for _, _, e in FIXTURE]
    assert len(FIXTURE) == 512
    assert sum(v > 0 for v in values) > 100
    assert sum(v < 0 for v in values) > 100
    assert sum(v == 0 for v in values) > 20


def test_matches_apca_w3_on_every_fixture_pair():
    worst = max(FIXTURE, key=lambda row: abs(apca.lc(row[0], row[1]) - row[2]))
    text, bg, expected = worst
    assert apca.lc(text, bg) == pytest.approx(expected, abs=TOL), (text, bg)


def test_constants_are_the_0_0_98g_4g_set():
    assert (apca.MAIN_TRC, apca.RCO, apca.GCO, apca.BCO) == (2.4, 0.2126729, 0.7151522, 0.0721750)
    assert (apca.NORM_BG, apca.NORM_TXT, apca.REV_TXT, apca.REV_BG) == (0.56, 0.57, 0.62, 0.65)
    assert (apca.BLK_THRS, apca.BLK_CLMP) == (0.022, 1.414)
    assert (apca.SCALE_BOW, apca.SCALE_WOB) == (1.14, 1.14)
    assert (apca.LO_BOW_OFFSET, apca.LO_WOB_OFFSET) == (0.027, 0.027)
    assert (apca.DELTA_Y_MIN, apca.LO_CLIP) == (0.0005, 0.1)


def test_polarity_sign():
    assert apca.lc("#000", "#fff") > 0      # dark text on light
    assert apca.lc("#fff", "#000") < 0      # light text on dark


def test_polarity_is_not_symmetric():
    assert abs(apca.lc("#fff", "#000")) != pytest.approx(abs(apca.lc("#000", "#fff")), abs=1)


def test_identical_colours_are_zero():
    for c in ("#000000", "#1a1f2b", "#808080", "#ffffff"):
        assert apca.lc(c, c) == 0.0


def test_low_contrast_is_clipped_to_zero():
    # Below the low clip the output is exactly 0, so no nonzero |Lc| under 7.3 exists.
    assert apca.lc("#222222", "#1a1f2b") == 0.0
    nonzero = [abs(e) for _, _, e in FIXTURE if e != 0]
    assert min(nonzero) >= (apca.LO_CLIP - apca.LO_BOW_OFFSET) * 100 - TOL


def test_extremes():
    assert apca.lc("#000", "#fff") == pytest.approx(106.04067321268862, abs=TOL)
    assert apca.lc("#fff", "#000") == pytest.approx(-107.88473318309848, abs=TOL)


# --- hex parsing -------------------------------------------------------------

@pytest.mark.parametrize("given,expected", [
    ("#DEDEDE", (222, 222, 222)), ("dedede", (222, 222, 222)),
    ("#abc", (170, 187, 204)), (" #1a1f2b ", (26, 31, 43)),
])
def test_hex_parsing(given, expected):
    assert apca._hex_to_rgb(given) == expected


@pytest.mark.parametrize("bad", ["", "#", "zzz", "#12", "#1234", "#12345", "#12345678",
                                 "#gggggg", "##ffffff", "+1+1+1", "rgb(0,0,0)", None, 255])
def test_bad_hex_is_rejected(bad):
    with pytest.raises(ValueError):
        apca._hex_to_rgb(bad)


# --- WCAG 2 ratio, shown beside Lc ------------------------------------------

def test_wcag2_known_ratios():
    assert apca.wcag2("#000", "#fff") == pytest.approx(21.0)
    assert apca.wcag2("#fff", "#000") == pytest.approx(21.0)
    assert apca.wcag2("#fff", "#fff") == pytest.approx(1.0)
    # The well-known AA boundary greys on white.
    assert apca.wcag2("#767676", "#fff") == pytest.approx(4.54, abs=0.005)
    assert apca.wcag2("#777777", "#fff") == pytest.approx(4.48, abs=0.005)


# --- the ladder --------------------------------------------------------------

@pytest.mark.parametrize("value,level", [
    (106.0, 90), (-90.0, 90), (89.9, 75), (-75.0, 75), (74.9, 60),
    (60.0, 60), (-59.9, 45), (45.0, 45), (44.9, 30), (-30.0, 30), (29.9, 0), (0.0, 0),
])
def test_describe_picks_the_highest_level_cleared(value, level):
    assert apca.describe(value)[0] == level


def test_verdict_uses_magnitude():
    assert apca.verdict(-77.9, 75)
    assert not apca.verdict(-74.9, 75)
    assert apca.verdict(60.0, 60)


# --- the command line --------------------------------------------------------

def run(*args):
    return subprocess.run([sys.executable, str(ROOT / "apca.py"), *args],
                          capture_output=True, text=True)


def test_selftest_passes():
    r = run("--selftest")
    assert r.returncode == 0
    assert "FAIL" not in r.stdout
    assert r.stdout.count("PASS") == len(apca.REFERENCE)


def test_selftest_contains_every_upstream_vector():
    assert set(UPSTREAM_VECTORS) <= set(apca.REFERENCE)


def test_selftest_fails_when_a_constant_is_wrong(monkeypatch, capsys):
    monkeypatch.setattr(apca, "NORM_BG", 0.55)
    assert apca._selftest() == 1
    assert "MISMATCH" in capsys.readouterr().out


def test_single_pair_gate_exit_codes():
    assert run("#DEDEDE", "#121212", "--require", "75").returncode == 0
    assert run("#DEDEDE", "#121212", "--require", "90").returncode == 1
    assert run("#DEDEDE", "#121212").returncode == 0


def test_disagreement_is_flagged_on_a_dark_ground():
    r = run("#868686", "#1a1f2b")
    assert "PASS at 4.5:1" in r.stdout
    assert "DISAGREEMENT" in r.stdout


def test_example_tokens_fail_the_gate_on_two_pairs():
    r = run("--tokens", str(ROOT / "tokens.example.json"))
    assert r.returncode == 1
    assert "4 pairs checked, 2 failing." in r.stdout


def test_passing_token_file_exits_zero(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(json.dumps([{"text": "#DEDEDE", "bg": "#121212", "require": 75}]))
    r = run("--tokens", str(f))
    assert r.returncode == 0
    assert "1 pairs checked, 0 failing." in r.stdout


@pytest.mark.parametrize("content", [
    "{not json",
    '{"pairs": "nope"}',
    '[{"text": "#fff"}]',
    '[{"text": "#fff", "bg": "#zzz"}]',
    '[{"text": "#fff", "bg": "#000", "require": "75"}]',
])
def test_bad_token_file_is_an_input_error_not_a_contrast_failure(tmp_path, content):
    f = tmp_path / "t.json"
    f.write_text(content)
    r = run("--tokens", str(f))
    assert r.returncode == 2
    assert "error" in r.stderr
    assert "Traceback" not in r.stderr


def test_bad_input_exits_two_without_a_traceback(tmp_path):
    for args in (("zzz", "#121212"), ("#fff",), (), ("--tokens", str(tmp_path / "missing.json"))):
        r = run(*args)
        assert r.returncode == 2, args
        assert "Traceback" not in r.stderr


# --- the README --------------------------------------------------------------

README = (ROOT / "README.md").read_text()
ROW = re.compile(r"^\| `(#[0-9a-fA-F]{6})` on `(#[0-9a-fA-F]{6})` \| ([\d.]+) : 1 \| Lc (-?[\d.]+) \|", re.M)


def test_readme_table_numbers_are_what_the_script_computes():
    rows = ROW.findall(README)
    assert len(rows) >= 5
    for text, bg, ratio, lc_value in rows:
        assert f"{apca.wcag2(text, bg):.2f}" == ratio, (text, bg)
        assert f"{apca.lc(text, bg):.1f}" == lc_value, (text, bg)


def test_readme_sample_output_is_what_the_script_prints():
    r = run("#868686", "#1a1f2b", "--require", "60")
    assert r.returncode == 1
    assert r.stdout.strip() in README


def test_readme_ladder_matches_the_code():
    for level, meaning in apca.LADDER:
        assert f"| Lc {level} | {meaning} |" in README
