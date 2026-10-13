"""Portable, standard-library-only evidence for VCD and region-map Easter eggs.

Usage:
  python analyze_signals.py --vcd example_inputs.vcd \
      --verification verification.json --out-dir evidence

The code samples the original VCD, not a simulation or a reference transcript.
The JSON argument supplies the already recovered region map and star solution.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
from html import escape
from itertools import combinations
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def field(text, name):
    match = re.search(r"\$" + name + r"\s+(.*?)\s*\$end", text, re.S)
    if not match:
        raise ValueError("Missing VCD field: " + name)
    return match.group(1).strip()


def sample_inputs(text):
    definitions, changes = text.split("$enddefinitions $end", 1)
    identifiers = {}
    for match in re.finditer(r"\$var\s+\S+\s+(\d+)\s+(\S+)\s+(\S+)(.*?)\$end", definitions):
        identifiers[match.group(3)] = {
            "width": int(match.group(1)), "identifier": match.group(2)
        }
    for name in ("clk", "rst_n", "enable", "I"):
        assert identifiers[name]["width"] == 1, (name, identifiers[name])
    ids = {name: identifiers[name]["identifier"] for name in identifiers}
    state = {}
    blocks = []
    active_block = None
    rising_edges = []
    for block in re.finditer(r"#(\d+)\s*(.*?)(?=#\d+|\Z)", changes, re.S):
        time_ps = int(block.group(1))
        previous_clock = state.get(ids["clk"])
        for line in block.group(2).splitlines():
            line = line.strip()
            if line and line[0] in "01xz":
                state[line[1:]] = line[0]
            elif line and line[0] in "bB":
                value, identifier = line[1:].split()
                state[identifier] = value
        if previous_clock == "0" and state.get(ids["clk"]) == "1":
            rising_edges.append(time_ps)
            input_active = state.get(ids["rst_n"]) == "1" and state.get(ids["enable"]) == "1"
            if input_active:
                if active_block is None:
                    active_block = []
                    blocks.append(active_block)
                bit = state.get(ids["I"])
                assert bit in "01", (time_ps, bit)
                active_block.append({"time_ps": time_ps, "bit": int(bit)})
            else:
                active_block = None
    return identifiers, rising_edges, blocks


def crop_mask(regions, region):
    cells = [(r, c) for r, row in enumerate(regions)
             for c, value in enumerate(row) if value == region]
    top, left = min(r for r, _ in cells), min(c for _, c in cells)
    bottom, right = max(r for r, _ in cells), max(c for _, c in cells)
    mask = ["".join("#" if regions[r][c] == region else "."
                    for c in range(left, right + 1))
            for r in range(top, bottom + 1)]
    return {"region": region, "cell_count": len(cells),
            "bounding_box_one_based": {"row_min": top + 1, "row_max": bottom + 1,
                                       "column_min": left + 1, "column_max": right + 1},
            "occupied_cells_one_based": [[r + 1, c + 1] for r, c in cells],
            "mask_top_to_bottom_left_to_right": mask}


def svg_start(width, height, title, description):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            f'<title>{escape(title)}</title>', f'<desc>{escape(description)}</desc>',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            '<g font-family="DejaVu Sans, Arial, sans-serif" fill="#172334">']


def text(parts, x, y, value, size=16, anchor="start", weight="normal"):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{escape(value)}</text>')


def star_points(x, y, radius=13):
    import math
    return " ".join(f"{x + (radius if i % 2 == 0 else radius * .42) * math.cos(-math.pi / 2 + i * math.pi / 5):.2f},"
                    f"{y + (radius if i % 2 == 0 else radius * .42) * math.sin(-math.pi / 2 + i * math.pi / 5):.2f}"
                    for i in range(10))


def board_svg(regions, grid, path, show_stars=False):
    n, size, ox, oy = len(regions), 40, 55, 85
    width, height = 550, 605
    title = "Recovered Star Battle solution" if show_stars else "Recovered region geometry"
    parts = svg_start(width, height, title, "The 11 by 11 recovered board, in serial input row-major orientation.")
    text(parts, 28, 30, title, 23, weight="bold")
    text(parts, 28, 53, "Rows increase downward; columns increase rightward.", 13)
    colors = {"I": "#acd5f2", "H": "#d8bbee", "K": "#b6e4c5"}
    if show_stars:
        palette = ["#e8eff7", "#fbf0dd", "#e0f0ea", "#f4e5e8", "#ede7f7", "#dfeef1", "#f1eee2", "#e5ebf6", "#f8e7d9", "#e3f2e0", "#f4e9f1"]
        colors = dict(zip(sorted(set("".join(regions))), palette))
    for r in range(n):
        for c in range(n):
            x, y = ox + c * size, oy + r * size
            parts.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="{colors.get(regions[r][c], "#f0f2f5")}" stroke="#d4d9df" stroke-width=".6"/>')
            if show_stars and grid[r][c] == "1":
                parts.append(f'<polygon points="{star_points(x + size / 2, y + size / 2)}" fill="#172334"/>')
    # Boundary edges are determined only by cell membership.
    for r in range(n):
        for c in range(n):
            x, y = ox + c * size, oy + r * size
            if r == 0 or regions[r][c] != regions[r - 1][c]:
                parts.append(f'<path d="M{x},{y}h{size}" stroke="#172334" stroke-width="2.4"/>')
            if c == 0 or regions[r][c] != regions[r][c - 1]:
                parts.append(f'<path d="M{x},{y}v{size}" stroke="#172334" stroke-width="2.4"/>')
    parts.append(f'<path d="M{ox},{oy + n * size}h{n * size}M{ox + n * size},{oy}v{n * size}" stroke="#172334" stroke-width="2.4"/>')
    for i in range(n):
        text(parts, ox + (i + .5) * size, oy - 13, str(i + 1), 12, "middle")
        text(parts, ox - 14, oy + (i + .5) * size + 4, str(i + 1), 12, "middle")
    if show_stars:
        text(parts, 28, 558, "22 stars: two in every row, column and region.", 14)
        text(parts, 28, 581, "No pair touches horizontally, vertically or diagonally.", 13)
    else:
        text(parts, 28, 558, "Blue: region I | Purple: region H | Green: region K", 14)
        text(parts, 28, 581, "These occupied-cell silhouettes read J, S and C.", 13)
    parts += ["</g>", "</svg>"]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    ET.parse(path)


def masks_svg(shapes, path):
    parts = svg_start(680, 370, "Three recovered region masks", "Three five-row by three-column regions whose occupied-cell silhouettes resemble J, S and C. No letter glyph is superimposed.")
    text(parts, 25, 31, "Three recovered region masks", 23, weight="bold")
    text(parts, 25, 54, "Filled squares are the original occupied cells; orientation is unchanged.", 13)
    colors = {"I": "#5aa6d5", "H": "#a274c7", "K": "#60ab7a"}
    for index, shape in enumerate(shapes):
        ox, oy, size = 40 + index * 220, 105, 37
        text(parts, ox, 85, "Region " + shape["region"], 18, weight="bold")
        for r, row in enumerate(shape["mask_top_to_bottom_left_to_right"]):
            for c, value in enumerate(row):
                parts.append(f'<rect x="{ox + c * size}" y="{oy + r * size}" width="{size}" height="{size}" fill="{colors[shape["region"]] if value == "#" else "#ffffff"}" stroke="#c9cfd7" stroke-width="1"/>')
        box = shape["bounding_box_one_based"]
        text(parts, ox, 315, f'Rows {box["row_min"]}–{box["row_max"]}; columns {box["column_min"]}–{box["column_max"]}', 12)
        text(parts, ox, 335, str(shape["cell_count"]) + " recovered cells", 12)
    parts += ["</g>", "</svg>"]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    ET.parse(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vcd", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    vcd_bytes = args.vcd.read_bytes()
    vcd = vcd_bytes.decode("utf-8")
    verification_bytes = args.verification.read_bytes()
    verification = json.loads(verification_bytes)
    signals, edges, attempts = sample_inputs(vcd)
    assert len(attempts) == 2 and all(len(attempt) == 121 for attempt in attempts)
    rows = []
    for attempt_number, attempt in enumerate(attempts, 1):
        for row in range(11):
            samples = attempt[row * 11:(row + 1) * 11]
            bits = "".join(str(sample["bit"]) for sample in samples)
            value = sum(int(bits[c]) << c for c in range(7))
            assert bits[7:] == "0000", (attempt_number, row, bits)
            rows.append({"attempt": attempt_number, "grid_row_one_based": row + 1,
                         "serial_bit_start_one_based_in_attempt": row * 11 + 1,
                         "row_bits_in_capture_order": bits,
                         "character_bits_lsb_first": bits[:7], "unused_last_four_bits": bits[7:],
                         "ascii_decimal": value, "ascii_hex": f"{value:02x}",
                         "character": chr(value), "first_sample_time_ps": samples[0]["time_ps"],
                         "last_sample_time_ps": samples[-1]["time_ps"]})
    decoded = "".join(row["character"] for row in rows)
    assert decoded == "The night sky awaits  ", repr(decoded)
    header_date = field(vcd, "date")
    version = field(vcd, "version")
    assert header_date == "Sat Dec 31 23:59:60 2016"
    assert date(2016, 12, 31).weekday() == 5  # Saturday; locale-independent.
    assert version == "Leave no stone unturned! But for this file, consider looking at it in a waveform viewer instead."
    regions, grid = verification["region_map"], verification["grid"]
    assert len(regions) == len(grid) == 11 and all(len(row) == 11 for row in regions + grid)
    assert all(set(row) <= {"0", "1"} for row in grid)
    stars = [(r, c) for r in range(11) for c in range(11) if grid[r][c] == "1"]
    board_checks = {
        "row_counts": [row.count("1") for row in grid],
        "column_counts": [sum(grid[r][c] == "1" for r in range(11)) for c in range(11)],
        "region_counts": dict(sorted(Counter(regions[r][c] for r, c in stars).items())),
        "touching_pairs_one_based": [[[r1 + 1, c1 + 1], [r2 + 1, c2 + 1]]
                                      for (r1, c1), (r2, c2) in combinations(stars, 2)
                                      if max(abs(r1 - r2), abs(c1 - c2)) <= 1],
        "star_count": len(stars),
    }
    assert board_checks["row_counts"] == board_checks["column_counts"] == [2] * 11
    assert set(board_checks["region_counts"]) == set("".join(regions))
    assert len(board_checks["region_counts"]) == 11 and all(v == 2 for v in board_checks["region_counts"].values())
    assert not board_checks["touching_pairs_one_based"] and len(stars) == 22
    shapes = [crop_mask(regions, region) for region in ("I", "H", "K")]
    expected_masks = {
        "I": ["..#", "..#", "..#", "#.#", "###"],
        "H": ["###", "#..", "###", "..#", "###"],
        "K": ["###", "#..", "#..", "#..", "###"],
    }
    letters = {"I": "J", "H": "S", "K": "C"}
    for shape in shapes:
        assert shape["mask_top_to_bottom_left_to_right"] == expected_masks[shape["region"]]
        shape["visual_reading"] = letters[shape["region"]]
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "source_files": {
            "vcd": {"name": args.vcd.name, "sha256": hashlib.sha256(vcd_bytes).hexdigest()},
            "verification": {"name": args.verification.name, "sha256": hashlib.sha256(verification_bytes).hexdigest()},
        },
        "vcd_header": {
            "date": header_date, "version": version, "timescale": field(vcd, "timescale"),
            "weekday_check": True,
            "leap_second_interpretation": "The unusual second 60 exactly matches the UTC leap second on 2016-12-31. The VCD field does not name a timezone or prove a real file-creation time.",
            "authoritative_sources_checked_on": "2026-10-13",
            "sources": [
                {"title": "IERS Bulletin C 52 (6 July 2016)",
                 "url": "https://datacenter.iers.org/data/16/bulletinc-052.txt",
                 "claim": "Announces a positive leap second and explicitly lists 2016 December 31, 23h 59m 60s between 23h 59m 59s and 2017 January 1, 0h 0m 0s."},
                {"title": "NIST: Leap second and UT1-UTC information",
                 "url": "https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds",
                 "claim": "Lists 2016-12-31 as a positive leap-second date (MJD 57753), and gives the 23:59:59, 23:59:60, 00:00:00 sequence."},
            ],
        },
        "vcd_input_decode": {
            "signals": signals, "total_clock_rising_edges": len(edges),
            "sampling_rule": "At each rising edge of clk, use I when rst_n=1 and enable=1; collect each continuous enabled run as an attempt.",
            "attempt_count": len(attempts), "attempt_bit_counts": [len(a) for a in attempts],
            "attempt_bitstrings": ["".join(str(sample["bit"]) for sample in a) for a in attempts],
            "attempt_first_last_sample_time_ps": [[a[0]["time_ps"], a[-1]["time_ps"]] for a in attempts],
            "character_rule": "Each attempt is 11 rows of 11 serial bits. The first 7 bits of each row are ASCII, least-significant bit first; the last 4 bits are zero. Rows and attempts retain capture order.",
            "decoded_including_padding": decoded,
            "decoded_message": decoded.rstrip(" "),
            "trailing_space_characters": len(decoded) - len(decoded.rstrip(" ")),
            "decoded_per_attempt": ["".join(r["character"] for r in rows if r["attempt"] == a) for a in (1, 2)],
            "rows": rows,
        },
        "region_geometry": {
            "orientation": "Same as input grid: rows top to bottom; columns left to right. No rotation or reflection.",
            "label_caveat": "A–K are extraction labels for sets of cells, not a premise for the glyph reading.",
            "region_cell_counts": dict(sorted(Counter("".join(regions)).items())),
            "reading": "JSC", "interpretation": "Three spatially ordered 5x3 occupied-cell silhouettes resemble J, S and C, plausibly Jane Street Capital's initials. This identification is a visual inference from the extracted masks.",
            "masks": shapes,
        },
        "star_board_constraints": board_checks,
        "figures": {"region_map": "recovered_regions.svg", "glyph_masks": "region_masks.svg", "star_solution": "star_board.svg"},
    }
    (out_dir / "signals_evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    board_svg(regions, grid, out_dir / "recovered_regions.svg")
    board_svg(regions, grid, out_dir / "star_board.svg", show_stars=True)
    masks_svg(shapes, out_dir / "region_masks.svg")
    md = ["# VCD and region-geometry evidence", "",
          "The original sample VCD contains two enabled input attempts of 121 bits each. Sampling `I` at rising edges of `clk` while `rst_n=1` and `enable=1` produces the captured bits below. The file has " + str(len(edges)) + " rising clock edges in total.", "",
          "Split each attempt into eleven consecutive 11-bit rows. Interpret columns 1–7 as a 7-bit ASCII value with column 1 carrying bit 0; columns 8–11 are zero in every row. Preserve the original row and attempt order. The exact result is **`The night sky awaits` followed by two spaces**. Thus the source message is mixed case; its uppercase rendering is a transcription choice.", "",
          "| Attempt | Row | Eleven bits in capture order | Seven LSB-first bits | ASCII | Character | First–last rising-edge time (ps) |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        character = "NUL" if row["ascii_decimal"] == 0 else "SPACE" if row["ascii_decimal"] == 32 else row["character"]
        md.append(f'| {row["attempt"]} | {row["grid_row_one_based"]} | `{row["row_bits_in_capture_order"]}` | `{row["character_bits_lsb_first"]}` | {row["ascii_decimal"]} / 0x{row["ascii_hex"]} | {character} | {row["first_sample_time_ps"]}–{row["last_sample_time_ps"]} |')
    md += ["", "The `$version` field reads:", "", "> " + version, "",
           "The `$date` field is **`Sat Dec 31 23:59:60 2016`**. The weekday is correct, and second 60 was a real UTC leap second: [IERS Bulletin C 52](https://datacenter.iers.org/data/16/bulletinc-052.txt) announces it explicitly, while [NIST's leap-second table](https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds) lists 2016-12-31. These primary sources were checked on 2026-10-13. The VCD date is an embedded clue, not evidence that the file was created at that moment.", "",
           "## Recovered silhouettes", "",
           "The region masks come directly from `verification.json`. Keep their top-to-bottom and left-to-right orientation. Region I occupies rows 2–6 and columns 1–3 (8 cells); H occupies rows 4–8 and columns 5–7 (11 cells); K occupies rows 6–10 and columns 9–11 (9 cells). Their left-to-right silhouettes resemble J, S and C. Interpreting this as Jane Street Capital's initials is a visual inference. The extraction's arbitrary region labels are unrelated to that inference.", "",
           "```text", "Region I       Region H       Region K", ""]
    for r in range(5):
        md.append("               ".join(shape["mask_top_to_bottom_left_to_right"][r] for shape in shapes))
    md += ["```", "", "![Recovered region memberships](recovered_regions.svg)", "",
           "![Cropped occupied-cell masks](region_masks.svg)", "",
           "![Winning star board](star_board.svg)", "",
           "Reproduce with Python 3.10+ (standard library only):", "",
           "```text", "python analyze_signals.py --vcd example_inputs.vcd --verification verification.json --out-dir evidence", "```", ""]
    (out_dir / "signals_evidence.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"message": evidence["vcd_input_decode"]["decoded_message"],
                      "decoded_repr": repr(decoded), "attempt_lengths": [len(a) for a in attempts],
                      "rising_edges": len(edges), "region_reading": "JSC",
                      "region_shapes": shapes, "out_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
