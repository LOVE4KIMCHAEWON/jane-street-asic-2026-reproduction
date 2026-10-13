"""Independently verify and solve the recovered 11x11 Star Battle.

Uses only Python's standard library. The solver enumerates legal two-star
row patterns, propagates exact counts, and enforces adjacency by arc
consistency. It does not import or reuse the reference solver.
"""
import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import time


def iter_bits(value):
    while value:
        bit = value & -value
        yield bit.bit_length() - 1
        value -= bit


def solve(regions, limit=2):
    n = len(regions)
    names = sorted(set("".join(regions)))
    region_index = {name: i for i, name in enumerate(names)}
    pairs = [p for p in combinations(range(n), 2) if p[1] - p[0] > 1]
    masks = [(1 << a) | (1 << b) for a, b in pairs]
    all_candidates = (1 << len(pairs)) - 1
    # Compatibility holds when neither row's stars touch the other row's.
    supports = []
    for mask in masks:
        forbidden = mask | (mask << 1) | (mask >> 1)
        supports.append(sum(1 << i for i, other in enumerate(masks)
                            if not other & forbidden))
    count_constraints = []
    for column in range(n):
        count_constraints.append([
            [int(column in p) for p in pairs] for _ in range(n)
        ])
    for name in names:
        count_constraints.append([
            [sum(regions[row][column] == name for column in p) for p in pairs]
            for row in range(n)
        ])
    bins = []
    for constraint in count_constraints:
        bins.append([
            [sum(1 << i for i, count in enumerate(counts) if count == k)
             for k in range(3)]
            for counts in constraint
        ])
    stats = {"search_nodes": 0, "propagation_passes": 0,
             "failed_nodes": 0, "row_patterns": len(pairs)}

    def propagate(domains):
        domains = list(domains)
        while True:
            stats["propagation_passes"] += 1
            changed = False
            for row in range(n - 1):
                for source, target in ((row, row + 1), (row + 1, row)):
                    kept = 0
                    for candidate in iter_bits(domains[source]):
                        if supports[candidate] & domains[target]:
                            kept |= 1 << candidate
                    if not kept:
                        return None
                    if kept != domains[source]:
                        domains[source] = kept
                        changed = True
            for constraint_bins in bins:
                minima = []
                maxima = []
                for row in range(n):
                    possible = [k for k in range(3)
                                if constraint_bins[row][k] & domains[row]]
                    if not possible:
                        return None
                    minima.append(min(possible))
                    maxima.append(max(possible))
                total_min = sum(minima)
                total_max = sum(maxima)
                if total_min > 2 or total_max < 2:
                    return None
                for row in range(n):
                    other_min = total_min - minima[row]
                    other_max = total_max - maxima[row]
                    acceptable = 0
                    for k in range(3):
                        if other_min <= 2 - k <= other_max:
                            acceptable |= constraint_bins[row][k]
                    kept = domains[row] & acceptable
                    if not kept:
                        return None
                    if kept != domains[row]:
                        domains[row] = kept
                        changed = True
            if not changed:
                return tuple(domains)

    solutions = []

    def search(domains):
        stats["search_nodes"] += 1
        domains = propagate(domains)
        if domains is None:
            stats["failed_nodes"] += 1
            return
        unresolved = [r for r in range(n) if domains[r].bit_count() > 1]
        if not unresolved:
            grid = []
            for domain in domains:
                pair = pairs[next(iter_bits(domain))]
                grid.append("".join("1" if c in pair else "0" for c in range(n)))
            solutions.append(grid)
            return
        row = min(unresolved, key=lambda r: domains[r].bit_count())
        for candidate in iter_bits(domains[row]):
            child = list(domains)
            child[row] = 1 << candidate
            search(child)
            if len(solutions) >= limit:
                return

    search([all_candidates] * n)
    return solutions, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    grid = reference["grid"]
    regions = reference["region_map"]
    n = len(grid)
    assert n == 11 and len(regions) == n
    assert all(len(row) == n and set(row) <= {"0", "1"} for row in grid)
    assert all(len(row) == n for row in regions)
    stars = [(r, c) for r in range(n) for c in range(n) if grid[r][c] == "1"]
    row_counts = [sum(grid[r][c] == "1" for c in range(n)) for r in range(n)]
    column_counts = [sum(grid[r][c] == "1" for r in range(n)) for c in range(n)]
    names = sorted(set("".join(regions)))
    assert len(names) == n
    region_counts = {name: sum(regions[r][c] == name for r, c in stars)
                     for name in names}
    touching = [((a + 1, b + 1), (c + 1, d + 1))
                for (a, b), (c, d) in combinations(stars, 2)
                if max(abs(a - c), abs(b - d)) <= 1]
    input_bits = "".join(grid)
    checks = {
        "all_rows_have_two_stars": row_counts == [2] * n,
        "all_columns_have_two_stars": column_counts == [2] * n,
        "all_regions_have_two_stars": all(v == 2 for v in region_counts.values()),
        "no_stars_touch_including_diagonally": not touching,
        "input_is_row_major": input_bits == reference["input_bits"],
        "input_has_121_bits": len(input_bits) == 121,
        "has_22_stars": len(stars) == 22,
    }
    assert all(checks.values()), checks
    started = time.perf_counter()
    solutions, stats = solve(regions)
    elapsed = time.perf_counter() - started
    checks["independent_solver_finds_exactly_one_solution"] = len(solutions) == 1
    checks["independent_solution_matches_reference"] = solutions == [grid]
    assert all(checks.values()), checks
    result = {
        "passed": all(checks.values()),
        "source": str(args.reference.resolve()),
        "checks": checks,
        "row_counts": row_counts,
        "column_counts": column_counts,
        "region_counts": region_counts,
        "touching_pairs": touching,
        "star_coordinates_one_based": [[r + 1, c + 1] for r, c in stars],
        "input_bits": input_bits,
        "independent_solution_count": len(solutions),
        "exhaustive_search_complete": len(solutions) < 2,
        "solver_stats": stats,
        "solver_elapsed_seconds": elapsed,
        "unique_grid": solutions[0] if len(solutions) == 1 else None,
        "scope": "Verifies mathematical Star Battle constraints and row-major "
                 "string consistency; does not independently establish the "
                 "ASIC's interpretation of the region map or input ordering.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
