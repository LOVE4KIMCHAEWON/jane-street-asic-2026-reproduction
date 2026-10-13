# Jane Street ASIC 2026: reproducible solution and complete Easter-egg audit

The original GDS is re-extracted, its Star Battle region map is probed, its unique board is solved, and its reconstructed circuit emits:

```text
(* TWO STARS *)
```

**All six intended Easter eggs, plus the additional floating-wire defect, have been verified.** This is an AI-assisted reproduction conducted after Jane Street published its solution, with explicit attribution to the public extraction and simulation tools. It does not claim an independent first discovery or peer-reviewed status.

- [Technical paper (PDF)](paper/paper.pdf) and [editable Markdown source](paper/paper.md)
- [中文说明](README.zh-CN.md)
- [Winning 121-bit input](results/input_bits.txt), [recovered netlist](results/netlist.json), [Verilog export](results/recovered_netlist.v)
- [Machine-readable verification](results/verification.json) and [complete Easter-egg checklist](evidence/all_easter_eggs.json)

## Reproduce

Python 3.10+ is sufficient for the full circuit and Easter-egg audit. No third-party Python packages are needed.

```sh
git clone https://github.com/LOVE4KIMCHAEWON/jane-street-asic-2026-reproduction.git
cd jane-street-asic-2026-reproduction
git clone https://github.com/janestreet/asic-puzzle-2026.git data/asic-puzzle-2026
git -C data/asic-puzzle-2026 checkout ffd53e0ba24e2fc1c1b12dc824e8eac5888c19a9
python run_all.py --puzzle-dir data/asic-puzzle-2026
```

The runner validates the original GDS digest, re-extracts the circuit, checks all 319 warm-up cases and all 312 reference clock edges, probes all 121 positions, solves the board, checks successful and deliberately invalid inputs, extracts the logo and Morse geometry, decodes the sample input text, and audits the floating net. It writes fresh `results/` and `evidence/` records; elapsed time and evidence hashes can vary between runs. Committed PNGs are publication renderings of the generated SVG/source geometry.

Optional independent native-reader comparison:

```sh
python -m pip install gdstk
python verify_native.py --puzzle-dir data/asic-puzzle-2026
```

## Easter eggs and evidence

| # | Intended egg | Recovered result | Evidence |
|---|---|---|---|
| 1 | Sample input text | `The night sky awaits` plus two trailing spaces | [22 ASCII rows](evidence/signals/signals_evidence.json) |
| 2 | Date and version | Real 2016-12-31 leap-second clue; waveform-viewer hint | [Header and IERS/NIST sources](evidence/signals/signals_evidence.md) |
| 3 | Outside-die marks | `PER ARENAM AD ASTRA`; 36 original Morse marks | [Geometry and decoding](evidence/geometry/morse_geometry.json) |
| 4 | Failure messages | `EMPTY SKY`, `BIG BANG`, `TRY AGAIN`, adjacency hint | [Circuit experiments](results/verification.json) |
| 5 | Metal logo | 1,366 literal met2 pixels on a 57 x 57 grid | [Pixel geometry](evidence/geometry/logo_pixelmap.json) |
| 6 | Region silhouettes | Spatially ordered J/S/C masks from regions I/H/K | [Exact occupied-cell masks](evidence/signals/region_masks.svg) |
| Extra | Floating wire | Net 71909 feeds two A1 pins; failure readout depends on its assumed value | [Both binary assumptions](evidence/floating/floating_wire.json) |

![Recovered metal logo](figures/jane-street-logo.png)

![Recovered region silhouettes](figures/regions-jsc.png)

## Validation and limits

The recovered representation has 942 standard-cell records, 1,794 combinational primitive entries and 92 flip-flops. Native gdstk and the bundled source-specific reader produced equal extracted connectivity. All 2,801 pin entries map to one net, with zero missing pins and zero failed vias. Waveform replay compared 2,808 bits without mismatch. Independent constraint search proved the recovered board has one solution; it contains 22 stars and the success signal stays high across all 16 readout cycles.

The model is zero-delay, two-valued functional simulation. The GDS reader supports the subset used by these layouts, and the observed region-register indices are inherited from published circuit analysis. Visual identification of the logo and J/S/C silhouettes is an interpretation corroborated by the organizer. Physical timing, analog floating behavior and arbitrary input-protocol reachability are not proven. The Verilog export was not separately tested with an HDL simulator.

The undriven input defaults to zero, producing `TWO"NOT TOUCH` on the adjacency-failure branch. Holding it at one produces a different corrupted string, **not a repair**; the successful answer is identical under both binary assumptions.

## Attribution

- [Jane Street original puzzle](https://blog.janestreet.com/can-you-reverse-engineer-an-asic/) and [official results](https://blog.janestreet.com/asic-puzzle-results/)
- [Mubin Shaikh's MIT-licensed solution](https://github.com/shaikhmubin02/asic-puzzle-2026-solution): unchanged extractor/simulator, prior circuit analysis
- [SkyWater official cell models](https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd): parsed behavior database, Apache-2.0
- [Detailed provenance and third-party licenses](src/THIRD_PARTY.md)

New orchestration, the standard-library GDS adapter, independent board solver, evidence extraction and report were prepared with AI assistance. Third-party files preserve their licenses. Original GDS/VCD data are downloaded from upstream rather than redistributed here.
