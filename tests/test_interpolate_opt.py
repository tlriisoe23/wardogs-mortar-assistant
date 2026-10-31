import pytest
import math
from mortar_calc import interpolate_table, L81_MORTAR_TABLE, SPH2_HIGH_TABLE, SPH2_LOW_TABLE

def orig_interpolate_table(table, distance_m):
    if not table or distance_m < table[0][0] or distance_m > table[-1][0]:
        return None
    # Check multi-value plateau at identical distance
    same_dist = [m for d, m in table if abs(d - distance_m) < 1e-6]
    if len(same_dist) > 1:
        return sum(same_dist) / len(same_dist)

    for i in range(len(table) - 1):
        d0, m0 = table[i]
        d1, m1 = table[i + 1]
        if d0 <= distance_m <= d1:
            if abs(d1 - d0) < 1e-6:
                return (m0 + m1) / 2.0
            ratio = (distance_m - d0) / (d1 - d0)
            return m0 + ratio * (m1 - m0)
    return None

def test_interpolate_table_parity():
    tables = [L81_MORTAR_TABLE, SPH2_HIGH_TABLE, SPH2_LOW_TABLE]

    # 1. Edge case tables
    plateau = [(100.0, 800.0), (100.0, 820.0)]
    tables.append(plateau)
    single = [(100.0, 800.0)]
    tables.append(single)
    empty = []
    tables.append(empty)

    for tbl in tables:
        if not tbl:
            assert interpolate_table(tbl, 100.0) == orig_interpolate_table(tbl, 100.0)
            continue

        points_to_test = []
        # Every table point exactly, +-1e-7, +-1e-5, below-min, above-max
        for d, _ in tbl:
            points_to_test.extend([
                d,
                d - 1e-7,
                d + 1e-7,
                d - 1e-5,
                d + 1e-5,
            ])

        # midpoints
        for i in range(len(tbl) - 1):
            points_to_test.append((tbl[i][0] + tbl[i+1][0]) / 2.0)

        # outside range
        points_to_test.extend([tbl[0][0] - 10.0, tbl[-1][0] + 10.0])

        for val in points_to_test:
            o = orig_interpolate_table(tbl, val)
            n = interpolate_table(tbl, val)
            if o is None:
                assert n is None
            else:
                assert n is not None
                assert math.isclose(o, n, rel_tol=1e-12)
