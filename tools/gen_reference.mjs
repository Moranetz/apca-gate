// Regenerates tests/reference_apca_w3_0.1.9.json by running the reference
// implementation, so the expected values in the test suite come from
// apca-w3 itself and were never typed by hand.
//
//   npm install --no-save apca-w3@0.1.9
//   node tools/gen_reference.mjs > tests/reference_apca_w3_0.1.9.json
//
// The pair list is deterministic. CI reruns this and fails if the output
// differs from the committed file.
import { APCAcontrast, sRGBtoY } from 'apca-w3';

const hex = (rgb) => '#' + rgb.map((v) => v.toString(16).padStart(2, '0')).join('');

// Small LCG so the "random" pairs are the same on every run and platform.
let seed = 20260915;
const next = (n) => {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return Math.floor((seed / 2147483648) * n);
};
const colour = (max = 256) => [next(max), next(max), next(max)];

const pairs = [];

// Every grey against every grey in steps of 0x11, both polarities: 256 pairs.
for (let t = 0; t < 256; t += 17) {
  for (let b = 0; b < 256; b += 17) pairs.push([[t, t, t], [b, b, b]]);
}
// 128 arbitrary colour pairs.
for (let i = 0; i < 128; i++) pairs.push([colour(), colour()]);
// 64 pairs of any text on a near-black ground, where the soft clamp applies.
for (let i = 0; i < 64; i++) pairs.push([colour(), colour(48)]);
// 64 pairs of near-black text on any ground.
for (let i = 0; i < 64; i++) pairs.push([colour(48), colour()]);

const out = pairs.map(([t, b]) => [hex(t), hex(b), APCAcontrast(sRGBtoY(t), sRGBtoY(b))]);

console.log('{');
console.log('  "source": "apca-w3 0.1.9, APCAcontrast(sRGBtoY(text), sRGBtoY(bg))",');
console.log('  "pairs": [');
console.log(out.map((row) => '    ' + JSON.stringify(row)).join(',\n'));
console.log('  ]');
console.log('}');
