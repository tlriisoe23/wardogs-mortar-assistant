"""FSA-15 regression tests: ballistic solver boundaries, malformed input and parser hardening."""
import math
import os

import pytest
from bs4 import BeautifulSoup

import mortar_calc
from mortar_calc import (
    SPH_PRIMARY_MODELS,
    _sph_drag_coeff,
    _sph_height_at_distance,
    L81_MORTAR_TABLE,
    SPH2_HIGH_TABLE,
    SPH2_LOW_TABLE,
    MortarCalculator,
    get_terrain_elevation,
    interpolate_elevation,
    interpolate_table,
    solve_sph2_terrain_mils,
    sph_platform_correct_aim,
)
from ocr_sniff import parse_chat_coord_line

import random

NAN = float("nan")
INF = float("inf")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _solve(tx, ty, weapon="mortar", arc="high", mx=0.0, my=0.0, **attrs):
    calc = MortarCalculator(mx, my, weapon=weapon, arc=arc)
    for k, v in attrs.items():
        setattr(calc, k, v)
    calc.set_target(tx, ty)
    return calc.calculate_solution()


# --- Ballistic tables --------------------------------------------------------

@pytest.mark.parametrize("table", [L81_MORTAR_TABLE, SPH2_HIGH_TABLE, SPH2_LOW_TABLE])
def test_tables_are_sorted_by_distance_and_monotonic_in_mils(table):
    for (d0, m0), (d1, m1) in zip(table, table[1:]):
        assert d0 <= d1
        assert m0 != m1
    mils = [m for _, m in table]
    assert mils == sorted(mils) or mils == sorted(mils, reverse=True)


@pytest.mark.parametrize("table", [L81_MORTAR_TABLE, SPH2_HIGH_TABLE, SPH2_LOW_TABLE])
def test_interpolation_hits_every_table_row_exactly(table):
    plateau = {d for d, _ in table if sum(1 for dd, _ in table if dd == d) > 1}
    for d, m in table:
        if d not in plateau:
            assert interpolate_table(table, d) == pytest.approx(m)


@pytest.mark.parametrize("table", [L81_MORTAR_TABLE, SPH2_HIGH_TABLE, SPH2_LOW_TABLE])
def test_interpolation_stays_between_neighbouring_rows(table):
    for (d0, m0), (d1, m1) in zip(table, table[1:]):
        if d0 == d1:
            continue
        mid = interpolate_table(table, (d0 + d1) / 2.0)
        assert min(m0, m1) <= mid <= max(m0, m1)


def test_sph2_high_plateau_averages_apex_rows():
    assert interpolate_elevation(2629.0, "sph2", "high") == pytest.approx(615.0)
    assert interpolate_elevation(2629.0, "sph2", "low") == pytest.approx(600.0)


@pytest.mark.parametrize("bad", [NAN, INF, -INF])
def test_interpolate_table_rejects_non_finite_distance(bad):
    assert interpolate_table(L81_MORTAR_TABLE, bad) is None


def test_interpolate_table_empty_and_just_outside_bounds():
    assert interpolate_table([], 100.0) is None
    assert interpolate_elevation(79.999, "mortar") is None
    assert interpolate_elevation(697.001, "mortar") is None
    assert interpolate_elevation(779.9, "sph2", "high") is None
    assert interpolate_elevation(1180.9, "sph2", "low") is None
    assert interpolate_elevation(2629.1, "sph2", "low") is None


# --- Drag Coefficient Hot-path Equivalence -------------------------------------

def test_sph_drag_coeff_bisect_equivalence():
    """Ensure the bisect optimization returns exact bit-for-bit results."""
    def old_drag(speed: float) -> float:
        if speed <= mortar_calc.SPH_GC_X[0]:
            return mortar_calc.SPH_GC_Y[0]
        if speed >= mortar_calc.SPH_GC_X[-1]:
            return mortar_calc.SPH_GC_Y[-1]
        lo, hi = 0, len(mortar_calc.SPH_GC_X) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if mortar_calc.SPH_GC_X[mid] <= speed:
                lo = mid
            else:
                hi = mid
        frac = (speed - mortar_calc.SPH_GC_X[lo]) / (mortar_calc.SPH_GC_X[hi] - mortar_calc.SPH_GC_X[lo])
        return mortar_calc.SPH_GC_Y[lo] + (mortar_calc.SPH_GC_Y[hi] - mortar_calc.SPH_GC_Y[lo]) * frac

    test_vals = []
    test_vals.extend(mortar_calc.SPH_GC_X)
    for i in range(len(mortar_calc.SPH_GC_X) - 1):
        test_vals.append((mortar_calc.SPH_GC_X[i] + mortar_calc.SPH_GC_X[i+1]) / 2.0)
    test_vals.extend([-10.0, -0.1, 600.1, 1000.0])

    random.seed(42)
    for _ in range(500):
        test_vals.append(random.uniform(-100.0, 700.0))

    for v in test_vals:
        assert old_drag(v) == mortar_calc._sph_drag_coeff(v)

    # Also verify that solve_sph2_terrain_mils matches expected baseline
    # for a few representative inputs to ensure the outer solver is unharmed.
    assert solve_sph2_terrain_mils("high", 2000.0, 1000.0, 50.0) == pytest.approx(997.2, abs=0.5)
    assert solve_sph2_terrain_mils("low", 1500.0, 450.0, -25.0) == pytest.approx(433.0, abs=0.5)

# --- Range boundaries ----------------------------------------------------------

@pytest.mark.parametrize("dist_m,in_range,slope_only", [
    (131.0, False, True),    # below 850 MIL flat sight limit, table still covers it
    (132.0, True, False),    # 850 MIL
    (684.0, True, False),    # 150 MIL
    (688.0, False, True),    # 140 MIL slope-only row
    (697.0, False, True),
    (698.0, False, False),   # beyond the table entirely
    (79.0, False, False),
])
def test_mortar_flat_ground_range_boundaries(dist_m, in_range, slope_only):
    sol = _solve(0.0, dist_m / 100.0)
    assert sol["in_range"] is in_range
    assert sol["slope_only"] is slope_only
    if dist_m > 697 or dist_m < 80:
        assert sol["elevation_mils"] is None


@pytest.mark.parametrize("arc,dist_m,in_range", [
    ("high", 779.0, False), ("high", 780.0, True), ("high", 2629.0, True), ("high", 2630.0, False),
    ("low", 1180.0, False), ("low", 1181.0, True), ("low", 2629.0, True), ("low", 2630.0, False),
])
def test_sph2_range_boundaries(arc, dist_m, in_range):
    sol = _solve(0.0, dist_m / 100.0, weapon="sph2", arc=arc)
    assert sol["in_range"] is in_range
    assert sol["slope_only"] is False


def test_mortar_height_correction_beyond_sight_limit_is_not_in_range():
    # 135 m flat is in range, but a target 15 m below needs ~861 MIL (> 850 sight limit).
    sol = _solve(0.0, 1.35, delta_z_m=-15.0)
    assert sol["elevation_mils"] > 850.4
    assert sol["in_range"] is False
    assert sol["slope_only"] is True


def test_mortar_height_correction_direction():
    flat = _solve(0.0, 4.0)["elevation_mils"]
    above = _solve(0.0, 4.0, delta_z_m=20.0)
    below = _solve(0.0, 4.0, delta_z_m=-20.0)
    # Higher target behaves like a longer shot (lower elevation) and vice versa.
    assert above["effective_distance_meters"] > 400.0
    assert below["effective_distance_meters"] < 400.0
    assert above["elevation_mils"] < flat < below["elevation_mils"]
    assert above["in_range"] and below["in_range"]


def test_tiny_height_differential_is_ignored():
    flat = _solve(0.0, 4.0)
    tiny = _solve(0.0, 4.0, delta_z_m=0.05)
    assert tiny["elevation_mils"] == flat["elevation_mils"]
    assert tiny["effective_distance_meters"] == 400.0


@pytest.mark.parametrize("bad", [NAN, INF, -INF])
def test_non_finite_height_differential_falls_back_to_flat(bad):
    flat = _solve(0.0, 4.0)
    sol = _solve(0.0, 4.0, delta_z_m=bad)
    assert sol["elevation_mils"] == flat["elevation_mils"]
    sph = _solve(0.0, 15.0, weapon="sph2", delta_z_m=bad)
    assert sph["elevation_mils"] == pytest.approx(interpolate_elevation(1500.0, "sph2", "high"))


def test_sph2_high_arc_height_correction_direction():
    # On the descending high-arc branch an elevated target behaves like a longer shot.
    flat = _solve(0.0, 15.0, weapon="sph2")["elevation_mils"]
    up = _solve(0.0, 15.0, weapon="sph2", delta_z_m=50.0)["elevation_mils"]
    down = _solve(0.0, 15.0, weapon="sph2", delta_z_m=-50.0)["elevation_mils"]
    assert up is not None and down is not None
    assert up < flat < down


# --- Zero distance & azimuth -----------------------------------------------------

def test_zero_distance_is_finite_and_out_of_range():
    for weapon, arc in (("mortar", "high"), ("sph2", "high"), ("sph2", "low")):
        sol = _solve(5.0, 5.0, weapon=weapon, arc=arc, mx=5.0, my=5.0)
        assert sol["distance_meters"] == 0.0
        assert sol["bearing_deg"] == 0.0
        assert sol["bearing_mils"] == 0
        assert sol["elevation_mils"] is None
        assert sol["in_range"] is False


@pytest.mark.parametrize("tx,ty,deg,mils", [
    (0.0, 5.0, 0.0, 0), (5.0, 0.0, 90.0, 1600), (0.0, -5.0, 180.0, 3200),
    (-5.0, 0.0, 270.0, 4800), (5.0, 5.0, 45.0, 800), (-5.0, 5.0, 315.0, 5600),
])
def test_north_up_cardinal_bearings(tx, ty, deg, mils):
    sol = _solve(tx, ty)
    assert sol["bearing_deg"] == pytest.approx(deg)
    assert sol["bearing_mils"] == mils


def test_bearing_mils_wraps_just_west_of_north():
    # 359.9994° rounds to 6400 mils, which must wrap to 0.
    sol = _solve(-0.0001, 10.0)
    assert sol["bearing_deg"] > 359.99
    assert sol["bearing_mils"] == 0
    for x in (-3.0, -0.5, -0.01, -1e-6):
        assert 0 <= _solve(x, 10.0)["bearing_mils"] < 6400


# --- Malformed input -------------------------------------------------------------

@pytest.mark.parametrize("x,y", [(NAN, 0.0), (0.0, INF), (-INF, 1.0), ("12", 1.0), (None, 1.0), (True, 1.0)])
def test_malformed_coordinates_rejected(x, y):
    with pytest.raises(ValueError):
        MortarCalculator(x, y)
    calc = MortarCalculator()
    with pytest.raises(ValueError):
        calc.set_target(x, y)
    with pytest.raises(ValueError):
        calc.set_mortar(x, y)


@pytest.mark.parametrize("weapon,arc", [("foo", "high"), ("sph2", "medium"), (None, "high"), ("mortar", "")])
def test_unknown_weapon_or_arc_rejected(weapon, arc):
    with pytest.raises(ValueError):
        MortarCalculator(weapon=weapon, arc=arc)


def test_unknown_weapon_set_after_construction_rejected_on_solve():
    calc = MortarCalculator()
    calc.set_target(0.0, 4.0)
    calc.weapon = "rocket"
    with pytest.raises(ValueError):
        calc.calculate_solution()


def test_weapon_and_arc_are_normalised():
    calc = MortarCalculator(weapon=" SPH2 ", arc="LOW")
    assert (calc.weapon, calc.arc) == ("sph2", "low")


@pytest.mark.parametrize("rng,dfl", [(NAN, 0.0), (0.0, INF)])
def test_non_finite_adjustment_does_not_corrupt_target(rng, dfl):
    calc = MortarCalculator()
    calc.set_target(1.0, 2.0)
    with pytest.raises(ValueError):
        calc.adjust_relative(rng, dfl)
    with pytest.raises(ValueError):
        calc.adjust_impact_point(NAN, 2.0)
    assert (calc.target_x, calc.target_y) == (1.0, 2.0)


def test_impact_point_correction_mirrors_target():
    calc = MortarCalculator()
    calc.set_target(4.0, 4.0)
    calc.adjust_impact_point(4.5, 3.5)
    assert (calc.target_x, calc.target_y) == pytest.approx((3.5, 4.5))


def test_deflection_is_right_of_gun_target_line():
    calc = MortarCalculator()
    calc.set_target(0.0, 4.0)  # firing North
    calc.adjust_relative(0.0, 50.0)  # RIGHT 50 -> East
    assert (calc.target_x, calc.target_y) == pytest.approx((0.5, 4.0))


# --- Hull pitch compensation -----------------------------------------------------

@pytest.mark.parametrize("hull", [NAN, INF])
def test_non_finite_hull_heading_is_ignored(hull):
    res = sph_platform_correct_aim(1000.0, 45.0, hull)
    assert res == {"corrected_mil": 1000.0, "mil_delta": 0.0, "relative_yaw_deg": 0.0}
    sol = _solve(0.0, 15.0, weapon="sph2", hull_heading_deg=hull)
    assert math.isfinite(sol["elevation_mils"])
    assert sol["hull_delta_mils"] == 0.0


def test_hull_correction_symmetry_and_relative_yaw_wrap():
    left = sph_platform_correct_aim(1000.0, 270.0, 0.0)
    right = sph_platform_correct_aim(1000.0, 90.0, 0.0)
    assert left["relative_yaw_deg"] == pytest.approx(-90.0)
    assert left["corrected_mil"] == pytest.approx(right["corrected_mil"])
    wrapped = sph_platform_correct_aim(1000.0, 10.0, 350.0)
    assert wrapped["relative_yaw_deg"] == pytest.approx(20.0)
    # Turret aligned with the hull needs no correction
    assert sph_platform_correct_aim(1000.0, 123.0, 123.0)["mil_delta"] == pytest.approx(0.0, abs=1e-9)


# --- SPH-2 terrain solver guards --------------------------------------------------

@pytest.mark.parametrize("args", [
    ("high", 0.0, 1000.0, 50.0),
    ("high", -5.0, 1000.0, 50.0),
    ("high", NAN, 1000.0, 50.0),
    ("high", 1500.0, NAN, 50.0),
    ("high", 1500.0, 1000.0, NAN),
    ("high", 1500.0, None, 50.0),
])
def test_sph2_terrain_solver_rejects_malformed_inputs(args):
    assert solve_sph2_terrain_mils(*args) is None


# --- DEM lookup ------------------------------------------------------------------

def test_dem_lookup_degenerate_and_malformed(monkeypatch):
    monkeypatch.setattr(mortar_calc, "_TERRAIN_DEM_CACHE", {
        "flat_x": {"minX": 5, "maxX": 5, "minY": 0, "maxY": 10, "heights": [[1, 2], [3, 4]]},
        "single": {"minX": 0, "maxX": 10, "minY": 0, "maxY": 10, "heights": [[7]], "gridSize": 1},
        "ok": {"minX": 0, "maxX": 10, "minY": 0, "maxY": 10, "heights": [[0, 10], [20, 30]]},
    })
    assert get_terrain_elevation("flat_x", 5, 5) is None
    assert get_terrain_elevation("single", 5, 5) is None
    assert get_terrain_elevation("ok", NAN, 5) is None
    assert get_terrain_elevation("ok", 5, INF) is None
    assert get_terrain_elevation("ok", 5, 5) == pytest.approx(15.0)


def test_dem_partial_coverage_falls_back_to_flat(monkeypatch):
    monkeypatch.setattr(mortar_calc, "_TERRAIN_DEM_CACHE", {
        "m": {"minX": 0, "maxX": 2, "minY": 0, "maxY": 2, "heights": [[0, 0], [0, 0]]},
    })
    calc = MortarCalculator(1.0, 1.0, map_id="m")
    calc.set_target(1.0, 5.0)  # target outside DEM bounds
    sol = calc.calculate_solution()
    assert sol["effective_distance_meters"] == sol["distance_meters"]
    assert sol["in_range"] is True


# --- Grid coordinate parsing ------------------------------------------------------

@pytest.mark.parametrize("line,expected", [
    ("X:78.50Y:69.50", (78.5, 69.5)),            # OCR dropped the space
    ("X: 78.50 / Y 69.50", (78.5, 69.5)),
    ("x=100,y=120", (100.0, 120.0)),
    ("[12:34] 78.5 69.5", (78.5, 69.5)),         # timestamp is not a coordinate
    ("7850-6950", (78.5, 69.5)),
    ("15500 15500", (155.0, 155.0)),
])
def test_coordinate_lines_parse(line, expected):
    res = parse_chat_coord_line(line)
    assert res is not None
    assert (res["x"], res["y"]) == expected


@pytest.mark.parametrize("line", [
    "X: 78 Y: 1234",        # previously truncated to Y=123.0
    "X: 1078 Y: 69",
    "X: 78.50 Y: 69.505",   # over-precise token is malformed, not truncated
    "X: -78 Y: 69",
    "X: 999 Y: 999",
    "14.9 85",
    "78.5.69.5",
    "X:nan Y:inf",
    "",
    "   ",
    None,
])
def test_malformed_coordinate_lines_rejected(line):
    assert parse_chat_coord_line(line) is None


# --- UI accessibility -----------------------------------------------------------

@pytest.mark.parametrize("page", ["index.html", "recon.html", "classic-fire-control.html"])
def test_canvases_have_accessible_names(page):
    with open(os.path.join(ROOT, page), encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    for canvas in soup.find_all("canvas"):
        assert canvas.get("role") == "img", canvas.get("id")
        assert canvas.get("aria-label", "").strip(), canvas.get("id")


def test_index_bearing_mils_wraps_like_python():
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert "let bearingMils = Math.round(bearingDeg * (6400 / 360)) % 6400;" in html


def _sph_height_at_distance_old(angle: float, distance: float, model: dict, dt: float = 0.02) -> float | None:
    if angle <= 0 or angle >= math.pi / 2 or distance <= 0:
        return None
    x, z = 0.0, 0.0
    vx = model["speed"] * math.cos(angle)
    vz = model["speed"] * math.sin(angle)
    g = model["gravity"]
    drag = model["drag"]
    dt_half = dt * 0.5
    max_steps = int(math.ceil(120.0 / dt))
    for _ in range(max_steps):
        s1 = math.hypot(vx, vz)
        q1 = drag * _sph_drag_coeff(s1) * s1
        a1x, a1z = -q1 * vx, -g - q1 * vz
        v2x, v2z = vx + a1x * dt_half, vz + a1z * dt_half
        s2 = math.hypot(v2x, v2z)
        q2 = drag * _sph_drag_coeff(s2) * s2
        a2x, a2z = -q2 * v2x, -g - q2 * v2z
        v3x, v3z = vx + a2x * dt_half, vz + a2z * dt_half
        s3 = math.hypot(v3x, v3z)
        q3 = drag * _sph_drag_coeff(s3) * s3
        a3x, a3z = -q3 * v3x, -g - q3 * v3z
        v4x, v4z = vx + a3x * dt, vz + a3z * dt
        s4 = math.hypot(v4x, v4z)
        q4 = drag * _sph_drag_coeff(s4) * s4
        next_x = x + dt * (vx + 2 * v2x + 2 * v3x + v4x) / 6.0
        next_z = z + dt * (vz + 2 * v2z + 2 * v3z + v4z) / 6.0
        if next_x >= distance:
            return float(z + (next_z - z) * (distance - x) / (next_x - x) + model["offset"])
        vx += dt * (a1x + 2 * a2x + 2 * a3x - q4 * v4x) / 6.0
        vz += dt * (a1z + 2 * a2z + 2 * a3z - g - q4 * v4z) / 6.0
        x, z = next_x, next_z
        if vx <= 1e-7:
            return None
    return None

def _sph_drag_coeff_old(speed: float) -> float:
    from mortar_calc import SPH_GC_X, SPH_GC_Y, SPH_GC_LOOKUP
    if speed <= SPH_GC_X[0]:
        return SPH_GC_Y[0]
    if speed >= SPH_GC_X[-1]:
        return SPH_GC_Y[-1]
    lo = SPH_GC_LOOKUP[int(speed)]
    hi = lo + 1
    frac = (speed - SPH_GC_X[lo]) / (SPH_GC_X[hi] - SPH_GC_X[lo])
    return SPH_GC_Y[lo] + (SPH_GC_Y[hi] - SPH_GC_Y[lo]) * frac

def test_sph_drag_coeff_equivalence():
    from mortar_calc import _sph_drag_coeff, SPH_GC_X
    test_speeds = [-10.0, 0.0, 15.0, 30.0, 30.5, 600.0, 650.0]
    # Sweeping from 0 to 610 in small increments
    for i in range(-5, int(SPH_GC_X[-1]) + 15):
        speed = float(i)
        old_val = _sph_drag_coeff_old(speed)
        new_val = _sph_drag_coeff(speed)
        assert old_val == new_val, f"Mismatch at speed {speed}: old={old_val}, new={new_val}"
        speed_frac = speed + 0.5
        old_val = _sph_drag_coeff_old(speed_frac)
        new_val = _sph_drag_coeff(speed_frac)
        assert old_val == new_val, f"Mismatch at speed {speed_frac}: old={old_val}, new={new_val}"


def test_sph_height_at_distance_equivalence():
    model = SPH_PRIMARY_MODELS["high"]
    distances = [500.0, 1500.0, 2500.0]
    angles = [0.1, 0.5, 1.0, 1.4]

    for dist in distances:
        for ang in angles:
            res_old = _sph_height_at_distance_old(ang, dist, model)
            res_new = _sph_height_at_distance(ang, dist, model)
            assert res_old == res_new, f"Mismatch at distance {dist}, angle {ang}: old={res_old}, new={res_new}"
