"""Re-extract the original ASIC, recover the region map, solve, and simulate.

Python 3.10+, standard library only. The extractor/simulator are from Mubin
Shaikh's MIT-licensed solution; the GDS reader and independent grid solver
were developed during this task. See THIRD_PARTY.md for attribution.
"""
import argparse
from collections import Counter
from hashlib import sha256
import itertools
import json
import os
from pathlib import Path
import pickle
import random
import re
import time

import extract2
from star_solver import solve

GDS_HASH = "8913ea4be5367b484d5886c3c5f7608942b67544a0dbe364b17223503b8d851a"
# Region accumulator flop pairs identified in the published circuit analysis.
# Their indexes are fixed for the exact original GDS hash above.
REGION_PAIRS = [(32,29),(31,28),(33,35),(85,80),(84,78),(34,81),
                (86,79),(90,89),(91,77),(83,87),(82,88)]


def new_sim(nl):
    from sim import Sim
    s = Sim(nl)
    for name in ("rst_n", "enable", "I"):
        s.set_port(name, 0)
    for _ in range(4):
        s.step()
    assert s.get_port("success") == 0
    s.set_port("rst_n", 1)
    for _ in range(2):
        s.step()
    s.set_port("enable", 1)
    return s


def input_board(nl, bits):
    assert len(bits) == 121
    s = new_sim(nl)
    for bit in bits:
        s.set_port("I", bit)
        s.step()
    return s


def read_answer(nl, bits):
    s = input_board(nl, bits)
    s.set_port("enable", 0)
    chars, successes = [], []
    for _ in range(16):
        s.step()
        chars.append(sum(s.get_port(f"O[{j}]") << j for j in range(8)))
        successes.append(s.get_port("success"))
    return {"success_trace": successes, "O_bytes": chars,
            "text": "".join(chr(c) for c in chars if c)}


def recover_regions(nl):
    baseline = input_board(nl, [0] * 121)
    base = [tuple(baseline.q[i] for i in p) for p in REGION_PAIRS]
    mapping = []
    for index in range(121):
        bits = [0] * 121
        bits[index] = 1
        s = input_board(nl, bits)
        hits = [j for j, p in enumerate(REGION_PAIRS)
                if tuple(s.q[i] for i in p) != base[j]]
        assert len(hits) == 1, (index, hits)
        mapping.append(chr(ord("A") + hits[0]))
    return ["".join(mapping[r*11:(r+1)*11]) for r in range(11)]


def check_board(bits, regions):
    stars = [divmod(i, 11) for i, bit in enumerate(bits) if bit]
    rows = [sum(bits[r*11:(r+1)*11]) for r in range(11)]
    columns = [sum(bits[r*11+c] for r in range(11)) for c in range(11)]
    counts = Counter(regions[r][c] for r, c in stars)
    touching = [(a, b) for a, b in itertools.combinations(stars, 2)
                if max(abs(a[0]-b[0]), abs(a[1]-b[1])) <= 1]
    return {"row_counts": rows, "column_counts": columns,
            "region_counts": dict(sorted(counts.items())),
            "touching_pairs": touching, "star_count": len(stars)}


def replay_vcd(nl, path):
    from sim import Sim
    source = path.read_text()
    names = {code: (name, int(width)) for width, code, name in re.findall(
        r"\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+).*?\$end", source)}
    groups, current = [], None
    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("#") and line[1:].isdigit():
            current = [int(line[1:]), {}]
            groups.append(current)
        elif current is not None:
            if len(line)>1 and line[0] in "01xz" and line[1:] in names:
                current[1][names[line[1:]][0]] = line[0]
            elif line.startswith("b"):
                value, code = line[1:].split()
                if code in names:
                    current[1][names[code][0]] = value
    state, mismatches = {}, []
    s = Sim(nl)
    edges = output_checks = success_checks = 0
    for timestamp, changes in groups:
        previous_clk = state.get("clk")
        state.update(changes)
        for name in ("clk", "rst_n", "enable", "I"):
            if state.get(name) in ("0", "1"):
                s.set_port(name, int(state[name]))
        s.comb(); s.apply_async(); s.comb()
        if previous_clk == "0" and state.get("clk") == "1":
            edges += 1
            s.step()
            actual = {"O": sum(s.get_port(f"O[{j}]") << j for j in range(8)),
                      "success": s.get_port("success")}
            for name in ("O", "success"):
                expected = state.get(name, "x")
                if not any(c in expected.lower() for c in "xz"):
                    if name == "O": output_checks += 8
                    else: success_checks += 1
                    if int(expected, 2) != actual[name]:
                        mismatches.append([timestamp, name, expected, actual[name]])
    assert not mismatches, mismatches[:5]
    return {"rising_edges": edges, "output_bit_checks": output_checks,
            "success_bit_checks": success_checks, "mismatch_count": 0}


def warmup_check(puzzle_dir, out):
    from sim import Netlist, Sim
    data = extract2.run(str(puzzle_dir / "warmup" / "04_final.gds"))
    filename = out / "warmup.pkl"
    filename.write_bytes(pickle.dumps(data))
    nl = Netlist(str(filename))
    rng = random.Random(20261013)
    tests = [(a, 496-a) for a in range(241, 256)]
    tests += [(0,0),(255,255),(240,255),(255,240)]
    tests += [(rng.randrange(256),rng.randrange(256)) for _ in range(300)]
    for a, b in tests:
        s = Sim(nl)
        for name in ("rst_n", "en", "A", "B"):
            s.set_port(name, 0)
        s.comb(); s.apply_async(); s.comb()
        s.set_port("rst_n", 1); s.set_port("en", 1)
        for i in range(7, -1, -1):
            s.set_port("A", (a >> i) & 1); s.set_port("B", (b >> i) & 1)
            s.step()
        assert s.get_port("S") == int(a+b == 496), (a, b)
    return {"tests": len(tests), "all_passed": True}


def write_verilog(data, filename):
    nets = sorted({n for cell in data["cells"] for ns in cell["pins"].values() for n in ns})
    lines = ["// Recovered from original puzzle.gds. Requires SKY130 cell models.",
             "module puzzle_recovered(input clk, rst_n, enable, I, output success, output [7:0] O);"]
    lines += [f"  wire n{n};" for n in nets]
    for p in ("clk", "rst_n", "enable", "I", "VPWR", "VGND"):
        value = "1'b1" if p == "VPWR" else "1'b0" if p == "VGND" else p
        lines.append(f"  assign n{data['ports'][p][0]} = {value};")
    for p in ["success"] + [f"O[{j}]" for j in range(8)]:
        lines.append(f"  assign {p} = n{data['ports'][p][0]};")
    for cell in data["cells"]:
        assert all(len(ns) == 1 for ns in cell["pins"].values())
        pins = ", ".join(f".{p}(n{ns[0]})" for p, ns in cell["pins"].items())
        lines.append(f"  {cell['cell']} u{cell['idx']} ({pins});")
    lines.append("endmodule")
    filename.write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--puzzle-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("generated"))
    args = parser.parse_args()
    puzzle_dir, out = args.puzzle_dir.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.chdir(Path(__file__).resolve().parent)
    from sim import Netlist
    start = time.perf_counter()
    digest = sha256((puzzle_dir/"puzzle.gds").read_bytes()).hexdigest()
    assert digest == GDS_HASH, "This runner is specific to the original puzzle GDS."
    warmup = warmup_check(puzzle_dir, out)
    data = extract2.run(str(puzzle_dir/"puzzle.gds"), "puzzle")
    (out/"netlist.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    pkl = out/"netlist.pkl"
    pkl.write_bytes(pickle.dumps(data))
    write_verilog(data, out/"recovered_netlist.v")
    nl = Netlist(str(pkl))
    sample = replay_vcd(nl, puzzle_dir/"example_inputs.vcd")
    print("Sample VCD: all", sample["rising_edges"], "clock edges matched.")
    regions = recover_regions(nl)
    solutions, stats = solve(regions, limit=2)
    assert len(solutions) == 1, "Expected exactly one valid board."
    grid = solutions[0]
    bits = [int(b) for b in "".join(grid)]
    checks = check_board(bits, regions)
    assert checks["row_counts"] == checks["column_counts"] == [2]*11
    assert len(checks["region_counts"]) == 11 and set(checks["region_counts"].values()) == {2}
    assert not checks["touching_pairs"]
    winning = read_answer(nl, bits)
    assert winning["success_trace"] == [1]*16
    negative = {}
    cases = [("empty",[0]*121,"EMPTY SKY"),("full",[1]*121,"BIG BANG")]
    removed = bits.copy(); removed[removed.index(1)] = 0
    cases.append(("removed_star",removed,"TRY AGAIN"))
    for name, candidate, expected in cases:
        result = read_answer(nl, candidate)
        assert result["success_trace"] == [0]*16 and result["text"] == expected
        negative[name] = result
    adjacent = bits.copy()
    for index in (0, 7, 11, 18): adjacent[index] ^= 1
    counts = check_board(adjacent, regions)
    assert counts["row_counts"] == counts["column_counts"] == [2]*11
    assert set(counts["region_counts"].values()) == {2} and counts["touching_pairs"]
    rejected = read_answer(nl, adjacent)
    assert rejected["success_trace"] == [0]*16
    negative["count_preserving_adjacency"] = {"counts": counts, "simulation": rejected}
    result = {"answer": winning["text"], "input_bits": "".join(grid), "grid": grid,
              "region_map": regions, "source_sha256": digest,
              "netlist_counts": {"standard_cell_records": len(data["cells"]),
                                 "primitive_gates":len(nl.gates),"flip_flops":len(nl.ffs)},
              "warmup": warmup, "sample_vcd": sample, "board_checks": checks,
              "unique_solution": True, "solver_stats": stats, "winning": winning,
              "negative_tests": negative, "elapsed_seconds": time.perf_counter()-start}
    (out/"verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out/"answer.txt").write_text(winning["text"]+"\n", encoding="utf-8")
    (out/"input_bits.txt").write_text("".join(grid)+"\n", encoding="utf-8")
    (out/"solution.txt").write_text("\n".join(row.replace("0",".").replace("1","*") for row in grid)+"\n", encoding="utf-8")
    print("Unique solution:", "".join(grid))
    print("success held high:", winning["success_trace"] == [1]*16)
    print("O bytes:", winning["O_bytes"])
    print("ANSWER:", repr(winning["text"]))
    print("All checks passed in %.1f seconds." % result["elapsed_seconds"])


if __name__ == "__main__":
    main()
