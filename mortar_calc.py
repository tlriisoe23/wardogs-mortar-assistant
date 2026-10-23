"""
WARDOGS Mortar & Artillery Ballistics Engine
Includes Pythagorean theorem range calculation, bearing (azimuth),
L81 Mortar & SPH-2 Self-Propelled Howitzer elevation lookup tables (aligned with
wardogs-artillery.com v1.10.5 & wardog-fire-control.pages.dev),
SPH-2 5.0° fore/aft chassis pitch compensation, height differential (ΔZ) adjustment,
and Forward Observer (FO) fire adjustments.
"""

import math
from typing import Dict, List, Optional, Tuple

# Official WARDOGS L81 Mortar Ballistics Table [distance_m, elevation_mils]
# Standard flat-ground sight limits: 150 - 850 MIL (132m - 684m).
# Rows outside 150-850 MIL (80m-127m and 688m-697m) require terrain slope.
L81_MORTAR_TABLE: List[Tuple[float, float]] = [
    (80, 950), (87, 940), (93, 930), (99, 920), (105, 910),
    (110, 900), (115, 890), (118, 880), (122, 870), (127, 860),
    (132, 850), (140, 840), (151, 830), (163, 820), (175, 810),
    (187, 800), (198, 790), (208, 780), (219, 770), (229, 760),
    (239, 750), (250, 740), (260, 730), (270, 720), (280, 710),
    (290, 700), (300, 690), (310, 680), (319, 670), (329, 660),
    (339, 650), (348, 640), (358, 630), (367, 620), (376, 610),
    (385, 600), (394, 590), (403, 580), (412, 570), (420, 560),
    (429, 550), (437, 540), (446, 530), (454, 520), (462, 510),
    (470, 500), (478, 490), (486, 480), (494, 470), (501, 460),
    (509, 450), (516, 440), (524, 430), (531, 420), (538, 410),
    (545, 400), (552, 390), (559, 380), (565, 370), (572, 360),
    (578, 350), (585, 340), (591, 330), (597, 320), (603, 310),
    (609, 300), (615, 290), (620, 280), (626, 270), (631, 260),
    (636, 250), (641, 240), (646, 230), (651, 220), (656, 210),
    (661, 200), (666, 190), (670, 180), (675, 170), (680, 160),
    (684, 150), (688, 140), (693, 130), (697, 120)
]

# Official WARDOGS SPH-2 Self-Propelled Howitzer High Arc Table (780m - 2,629m, 610 - 1,390 MIL)
# Aligned with wardogs-artillery.com v1.10.5 (clamped to 1,390 MIL sight limit; 2,629m apex plateau 610-620 MIL)
SPH2_HIGH_TABLE: List[Tuple[float, float]] = [
    (780, 1390), (825, 1380), (869, 1370), (913, 1360),
    (956, 1350), (999, 1340), (1041, 1330), (1083, 1320), (1124, 1310),
    (1165, 1300), (1205, 1290), (1245, 1280), (1285, 1270), (1324, 1260),
    (1363, 1250), (1401, 1240), (1438, 1230), (1475, 1220), (1512, 1210),
    (1547, 1200), (1582, 1190), (1616, 1180), (1650, 1170), (1684, 1160),
    (1717, 1150), (1750, 1140), (1782, 1130), (1813, 1120), (1844, 1110),
    (1875, 1100), (1905, 1090), (1934, 1080), (1963, 1070), (1991, 1060),
    (2019, 1050), (2046, 1040), (2072, 1030), (2098, 1020), (2123, 1010),
    (2147, 1000), (2171, 990), (2194, 980), (2217, 970), (2239, 960),
    (2261, 950), (2282, 940), (2303, 930), (2323, 920), (2342, 910),
    (2360, 900), (2378, 890), (2395, 880), (2412, 870), (2429, 860),
    (2444, 850), (2460, 840), (2474, 830), (2488, 820), (2501, 810),
    (2513, 800), (2524, 790), (2536, 780), (2546, 770), (2557, 760),
    (2567, 750), (2576, 740), (2584, 730), (2592, 720), (2599, 710),
    (2604, 700), (2609, 690), (2613, 680), (2617, 670), (2621, 660),
    (2624, 650), (2626, 640), (2628, 630), (2629, 620), (2629, 610)
]

# Official WARDOGS SPH-2 Self-Propelled Howitzer Low Arc Table (1,181m - 2,629m, 20 - 600 MIL)
SPH2_LOW_TABLE: List[Tuple[float, float]] = [
    (1181, 20), (1232, 30), (1283, 40), (1334, 50), (1384, 60),
    (1433, 70), (1482, 80), (1529, 90), (1576, 100), (1622, 110),
    (1666, 120), (1709, 130), (1751, 140), (1792, 150), (1832, 160),
    (1870, 170), (1907, 180), (1944, 190), (1979, 200), (2014, 210),
    (2046, 220), (2079, 230), (2110, 240), (2139, 250), (2168, 260),
    (2196, 270), (2223, 280), (2249, 290), (2273, 300), (2296, 310),
    (2319, 320), (2341, 330), (2362, 340), (2383, 350), (2403, 360),
    (2422, 370), (2439, 380), (2456, 390), (2471, 400), (2485, 410),
    (2499, 420), (2513, 430), (2526, 440), (2538, 450), (2550, 460),
    (2561, 470), (2570, 480), (2579, 490), (2586, 500), (2593, 510),
    (2599, 520), (2605, 530), (2610, 540), (2615, 550), (2620, 560),
    (2623, 570), (2626, 580), (2628, 590), (2629, 600)
]


def interpolate_table(table: List[Tuple[float, float]], distance_m: float) -> Optional[float]:
    """Linearly interpolate elevation in mils from a [distance_m, mils] table."""
    if not table or distance_m < table[0][0] or distance_m > table[-1][0]:
        return None
    # Check multi-value plateau at identical distance (e.g., SPH-2 High Arc 2629m -> 610..620 MIL)
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


def interpolate_elevation(distance_m: float, weapon: str = "mortar", arc: str = "high") -> Optional[float]:
    """Interpolate elevation in mils for L81 Mortar or SPH-2 Howitzer."""
    if weapon == "sph2":
        tbl = SPH2_LOW_TABLE if arc == "low" else SPH2_HIGH_TABLE
        return interpolate_table(tbl, distance_m)
    return interpolate_table(L81_MORTAR_TABLE, distance_m)


def sph_platform_correct_aim(
    baseline_mil: float,
    target_azimuth_deg: float,
    hull_heading_deg: Optional[float],
    baseline_pitch_deg: float = 5.0
) -> Dict[str, float]:
    """
    Port of wardogs-artillery.com sphPlatformCorrectAim:
    Compensates the SPH-2 5.0° fore/aft hull pitch component when the turret is
    rotated away from the forward hull direction (relative yaw != 0°).
    """
    if hull_heading_deg is None:
        return {"corrected_mil": baseline_mil, "mil_delta": 0.0, "relative_yaw_deg": 0.0}

    pitch = math.radians(baseline_pitch_deg)
    cp, sp = math.cos(pitch), math.sin(pitch)

    # Reference local bore (relative yaw = 0)
    elev_rad = baseline_mil / 1000.0
    ref_local_x = math.cos(elev_rad)
    ref_local_y = 0.0
    ref_local_z = math.sin(elev_rad)

    # Rotate local -> world with forward=(cp,0,sp), right=(0,1,0), up=(-sp,0,cp)
    ref_world_x = ref_local_x * cp - ref_local_z * sp
    ref_world_y = ref_local_y
    ref_world_z = ref_local_x * sp + ref_local_z * cp

    desired_elev = math.atan2(ref_world_z, math.hypot(ref_world_x, ref_world_y))
    rel_yaw_deg = ((target_azimuth_deg - hull_heading_deg + 180.0) % 360.0) - 180.0
    rel_yaw_rad = math.radians(rel_yaw_deg)

    cos_el = math.cos(desired_elev)
    des_world_x = cos_el * math.cos(rel_yaw_rad)
    des_world_y = cos_el * math.sin(rel_yaw_rad)
    des_world_z = math.sin(desired_elev)

    # Rotate world -> local
    corr_local_x = des_world_x * cp + des_world_z * sp
    corr_local_y = des_world_y
    corr_local_z = -des_world_x * sp + des_world_z * cp

    corr_mil = math.atan2(corr_local_z, math.hypot(corr_local_x, corr_local_y)) * 1000.0
    return {
        "corrected_mil": corr_mil,
        "mil_delta": corr_mil - baseline_mil,
        "relative_yaw_deg": rel_yaw_deg
    }


# Topographic DEM elevation lookup & SPH-2 RK4 Drag Solver (A3-04)
_TERRAIN_DEM_CACHE = None

def get_terrain_elevation(map_id: str, x: float, y: float) -> Optional[float]:
    """Bilinear lookup of terrain elevation (meters) from data/terrain/terrain_dem.json."""
    global _TERRAIN_DEM_CACHE
    if map_id == "firing_range":
        return 0.0
    if _TERRAIN_DEM_CACHE is None:
        import json
        import os
        dem_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "terrain", "terrain_dem.json")
        if os.path.exists(dem_path):
            with open(dem_path, "r", encoding="utf-8") as f:
                _TERRAIN_DEM_CACHE = json.load(f)
        else:
            _TERRAIN_DEM_CACHE = {}
    dem = _TERRAIN_DEM_CACHE.get(map_id)
    if not dem or "heights" not in dem:
        return None
    heights = dem["heights"]
    n = dem.get("gridSize", len(heights))
    fx = ((x - dem["minX"]) / (dem["maxX"] - dem["minX"])) * (n - 1)
    fy = ((y - dem["minY"]) / (dem["maxY"] - dem["minY"])) * (n - 1)
    if fx < 0 or fx > n - 1 or fy < 0 or fy > n - 1:
        return None
    x0 = max(0, min(n - 1, int(math.floor(fx))))
    y0 = max(0, min(n - 1, int(math.floor(fy))))
    x1 = min(n - 1, x0 + 1)
    y1 = min(n - 1, y0 + 1)
    tx = fx - x0
    ty = fy - y0
    top = heights[y0][x0] + (heights[y0][x1] - heights[y0][x0]) * tx
    bot = heights[y1][x0] + (heights[y1][x1] - heights[y1][x0]) * tx
    return top + (bot - top) * ty


SPH_GC_X = [0, 30, 61, 91, 122, 150, 183, 213, 244, 274, 300, 335, 366, 396, 427, 450, 488, 518, 549, 579, 600]
SPH_GC_Y = [0.71, 0.69, 0.66, 0.64, 0.65, 0.66, 0.68, 0.72, 0.80, 0.92, 1.10, 1.25, 1.33, 1.39, 1.44, 1.48, 1.50, 1.54, 1.57, 1.58, 1.60]
SPH_PRIMARY_MODELS = {
    "high": {"speed": 9389.43881652221, "gravity": 147.2063947858103, "drag": 0.0008516971618643472, "offset": -960.0413878819479},
    "low":  {"speed": 300.0, "gravity": 8.85397505384648, "drag": 0.0007351626163587786, "offset": 95.03019643400405}
}


def _sph_drag_coeff(speed: float) -> float:
    if speed <= SPH_GC_X[0]:
        return SPH_GC_Y[0]
    if speed >= SPH_GC_X[-1]:
        return SPH_GC_Y[-1]
    lo, hi = 0, len(SPH_GC_X) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if SPH_GC_X[mid] <= speed:
            lo = mid
        else:
            hi = mid
    frac = (speed - SPH_GC_X[lo]) / (SPH_GC_X[hi] - SPH_GC_X[lo])
    return SPH_GC_Y[lo] + (SPH_GC_Y[hi] - SPH_GC_Y[lo]) * frac


def _sph_height_at_distance(angle: float, distance: float, model: Dict, dt: float = 0.02) -> Optional[float]:
    if angle <= 0 or angle >= math.pi / 2 or distance <= 0:
        return None
    x, z = 0.0, 0.0
    vx = model["speed"] * math.cos(angle)
    vz = model["speed"] * math.sin(angle)
    g = model["gravity"]
    drag = model["drag"]
    max_steps = int(math.ceil(120.0 / dt))
    for _ in range(max_steps):
        s1 = math.hypot(vx, vz)
        q1 = drag * _sph_drag_coeff(s1) * s1
        a1x, a1z = -q1 * vx, -g - q1 * vz
        v2x, v2z = vx + a1x * dt * 0.5, vz + a1z * dt * 0.5
        s2 = math.hypot(v2x, v2z)
        q2 = drag * _sph_drag_coeff(s2) * s2
        a2x, a2z = -q2 * v2x, -g - q2 * v2z
        v3x, v3z = vx + a2x * dt * 0.5, vz + a2z * dt * 0.5
        s3 = math.hypot(v3x, v3z)
        q3 = drag * _sph_drag_coeff(s3) * s3
        a3x, a3z = -q3 * v3x, -g - q3 * v3z
        v4x, v4z = vx + a3x * dt, vz + a3z * dt
        s4 = math.hypot(v4x, v4z)
        q4 = drag * _sph_drag_coeff(s4) * s4
        next_x = x + dt * (vx + 2 * v2x + 2 * v3x + v4x) / 6.0
        next_z = z + dt * (vz + 2 * v2z + 2 * v3z + v4z) / 6.0
        if next_x >= distance:
            return z + (next_z - z) * (distance - x) / (next_x - x) + model["offset"]
        vx += dt * (a1x + 2 * a2x + 2 * a3x - q4 * v4x) / 6.0
        vz += dt * (a1z + 2 * a2z + 2 * a3z - g - q4 * v4z) / 6.0
        x, z = next_x, next_z
        if vx <= 1e-7:
            return None
    return None


def _sph_bisect(fn, left: float, right: float, tol: float) -> Optional[float]:
    fl, fr = fn(left), fn(right)
    if fl is None or fr is None or fl * fr > 0:
        return None
    if abs(fl) < 1e-8:
        return left
    if abs(fr) < 1e-8:
        return right
    for _ in range(40):
        if right - left <= tol:
            break
        mid = 0.5 * (left + right)
        fm = fn(mid)
        if fm is None:
            return None
        if abs(fm) < 1e-8:
            return mid
        if fl * fm <= 0:
            right, fr = mid, fm
        else:
            left, fl = mid, fm
    return 0.5 * (left + right)


def _sph_on_arc(arc: str, fn, root: float, step: float) -> bool:
    c, l, r = fn(root), fn(root - step), fn(root + step)
    if c is None:
        return False
    slope = (r - l) if (l is not None and r is not None) else ((c - l) if l is not None else ((r - c) if r is not None else None))
    return slope is not None and (slope > 0 if arc == "low" else slope < 0)


def solve_sph2_terrain_mils(arc: str, distance_m: float, flat_mils: Optional[float], delta_z_m: float) -> Optional[float]:
    """Exact upstream wardogs-artillery.com RK4 drag solver for SPH-2 terrain height offset ΔZ."""
    if flat_mils is None:
        return None
    if abs(delta_z_m) <= 0.05:
        return flat_mils
    model = SPH_PRIMARY_MODELS.get(arc)
    if not model:
        return flat_mils
    center = flat_mils / 1000.0
    min_a = 0.0001 if arc == "low" else 0.3
    max_a = 1.0 if arc == "low" else 1.55
    fn0 = lambda a: _sph_height_at_distance(a, distance_m, model)
    f0 = fn0(center)
    ref = None
    for span in (0.002, 0.005, 0.01, 0.02, 0.04, 0.08, 0.12, 0.2, 0.3):
        l, r = max(min_a, center - span), min(max_a, center + span)
        cands = []
        if f0 is not None:
            for edge in (l, r):
                val = fn0(edge)
                if val is not None and val * f0 <= 0:
                    root = _sph_bisect(fn0, min(edge, center), max(edge, center), 1e-7)
                    if root is not None and _sph_on_arc(arc, fn0, root, 1e-5):
                        cands.append(root)
        if cands:
            cands.sort(key=lambda a: abs(a - center))
            ref = cands[0]
            break
    if ref is None:
        prev = None
        best = None
        for i in range(61):
            angle = min_a + (max_a - min_a) * i / 60.0
            val = fn0(angle)
            if val is not None and prev is not None and prev[1] * val <= 0:
                root = _sph_bisect(fn0, prev[0], angle, 1e-7)
                if root is not None and _sph_on_arc(arc, fn0, root, 1e-5):
                    if best is None or abs(root - center) < abs(best - center):
                        best = root
            prev = None if val is None else (angle, val)
        ref = best
    if ref is None:
        return None
    min_cmd = 20.0 if arc == "low" else 610.0
    max_cmd = 600.0 if arc == "low" else 1390.0
    fn_h = lambda cmd: (lambda h: None if h is None else h - delta_z_m)(_sph_height_at_distance(ref + (cmd - flat_mils) / 1000.0, distance_m, model))
    f_flat = fn_h(flat_mils)
    direction = (1.0 if arc == "low" else -1.0) * (1.0 if delta_z_m >= 0 else -1.0)
    if f_flat is not None:
        for span in (15.0, 35.0, 70.0, 140.0, 260.0, 450.0, 780.0):
            edge = max(min_cmd, min(max_cmd, flat_mils + direction * span))
            f_edge = fn_h(edge)
            if f_edge is not None and f_flat * f_edge <= 0:
                root = _sph_bisect(fn_h, min(flat_mils, edge), max(flat_mils, edge), 0.025)
                if root is not None and _sph_on_arc(arc, fn_h, root, 0.05):
                    return root
    return None


class MortarCalculator:
    def __init__(
        self,
        mortar_x: float = 0.0,
        mortar_y: float = 0.0,
        weapon: str = "mortar",
        arc: str = "high",
        map_id: Optional[str] = None
    ):
        self.mortar_x = mortar_x
        self.mortar_y = mortar_y
        self.target_x = 0.0
        self.target_y = 0.0
        self.weapon = weapon
        self.arc = arc
        self.map_id = map_id
        self.delta_z_m: Optional[float] = None
        self.hull_heading_deg: Optional[float] = None
        self.has_target = False

    def set_mortar(self, x: float, y: float):
        self.mortar_x = x
        self.mortar_y = y

    def set_target(self, x: float, y: float):
        self.target_x = x
        self.target_y = y
        self.has_target = True

    def calculate_solution(self) -> Dict:
        """
        Calculate fire solution using Pythagorean theorem and coordinate geometry.
        1 game unit = 100 meters.
        """
        dx_units = self.target_x - self.mortar_x
        dy_units = self.target_y - self.mortar_y
        
        # Legs of right triangle in meters
        dx_meters = dx_units * 100.0
        dy_meters = dy_units * 100.0
        
        # Pythagorean theorem: c = sqrt(a^2 + b^2)
        distance_meters = math.hypot(dx_meters, dy_meters)
        
        # Azimuth calculation:
        # +Y is North (0°/360°), +X is East (90°), -Y is South (180°), -X is West (270°)
        bearing_rad = math.atan2(dx_meters, dy_meters)
        bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0
        bearing_mils = round(bearing_deg * (6400.0 / 360.0))
        
        # Sight range bounds per weapon
        if self.weapon == "sph2":
            min_range = 1181.0 if self.arc == "low" else 780.0
            max_range = 2629.0
        else:
            # Level-ground sight limits for L81 Mortar: 132m (850 MIL) to 684m (150 MIL)
            min_range = 132.0
            max_range = 684.0

        # Resolve height differential ΔZ (manual override or auto DEM lookup if map_id is set)
        dz_m = self.delta_z_m
        if dz_m is None and self.map_id:
            gz = get_terrain_elevation(self.map_id, self.mortar_x, self.mortar_y)
            tz = get_terrain_elevation(self.map_id, self.target_x, self.target_y)
            dz_m = (tz - gz) if (gz is not None and tz is not None) else 0.0
        elif dz_m is None:
            dz_m = 0.0

        eff_distance_m = distance_meters
        hull_delta_mils = 0.0
        if self.weapon == "mortar":
            base_mils = interpolate_elevation(distance_meters, "mortar", "high")
            if abs(dz_m) > 0.05 and base_mils is not None:
                plunge_rad = max(0.18, min(1.38, base_mils / 1000.0))
                eff_distance_m = distance_meters + (dz_m / math.tan(plunge_rad)) * 0.65
            elevation_mils = interpolate_elevation(eff_distance_m, "mortar", "high")
        else:
            flat_mils = interpolate_elevation(distance_meters, "sph2", self.arc)
            elevation_mils = solve_sph2_terrain_mils(self.arc, distance_meters, flat_mils, dz_m)
            if elevation_mils is not None and self.hull_heading_deg is not None:
                corr = sph_platform_correct_aim(elevation_mils, bearing_deg, self.hull_heading_deg)
                elevation_mils = corr["corrected_mil"]
                hull_delta_mils = corr["mil_delta"]

        in_effective_range = (min_range <= distance_meters <= max_range and elevation_mils is not None)
        slope_only = (
            self.weapon == "mortar"
            and elevation_mils is not None
            and (distance_meters < 132.0 or distance_meters > 684.0)
        )
        
        return {
            "weapon": self.weapon,
            "arc": self.arc,
            "mortar": (self.mortar_x, self.mortar_y),
            "target": (self.target_x, self.target_y),
            "dx_meters": dx_meters,
            "dy_meters": dy_meters,
            "distance_meters": distance_meters,
            "effective_distance_meters": eff_distance_m,
            "bearing_deg": bearing_deg,
            "bearing_mils": bearing_mils,
            "elevation_mils": elevation_mils,
            "hull_delta_mils": hull_delta_mils,
            "in_range": in_effective_range,
            "slope_only": slope_only,
            "min_range": min_range,
            "max_range": max_range
        }

    def adjust_relative(self, range_meters: float, deflection_meters: float) -> Dict:
        """
        Forward Observer correction relative to the Gun-Target Line of Fire:
        range_meters: positive = ADD (push target farther), negative = DROP (pull closer)
        deflection_meters: positive = RIGHT, negative = LEFT
        """
        dx = self.target_x - self.mortar_x
        dy = self.target_y - self.mortar_y
        length = math.hypot(dx, dy)
        
        if length == 0:
            # Fallback pointing North
            u_along_x, u_along_y = 0.0, 1.0
            u_right_x, u_right_y = 1.0, 0.0
        else:
            u_along_x = dx / length
            u_along_y = dy / length
            # Perpendicular vector to the right (dy, -dx)
            u_right_x = dy / length
            u_right_y = -dx / length
            
        # Convert correction from meters to map coordinate units (1 unit = 100m)
        r_units = range_meters / 100.0
        w_units = deflection_meters / 100.0
        
        shift_x = (u_along_x * r_units) + (u_right_x * w_units)
        shift_y = (u_along_y * r_units) + (u_right_y * w_units)
        
        self.target_x += shift_x
        self.target_y += shift_y
        
        return self.calculate_solution()

    def adjust_missed_shot(self, long_short_meters: float, left_right_meters: float) -> Dict:
        """
        Adjust based on where the shot missed:
        long_short_meters: + = landed long (overshot), - = landed short (undershot)
        left_right_meters: + = landed right, - = landed left
        """
        range_correction = -long_short_meters
        deflection_correction = -left_right_meters
        return self.adjust_relative(range_correction, deflection_correction)

    def adjust_impact_point(self, impact_x: float, impact_y: float) -> Dict:
        """
        Adjust target when spotter reports exact coordinates of impact.
        New Aim = Target - (Impact - Target) = 2*Target - Impact
        """
        shift_x = self.target_x - impact_x
        shift_y = self.target_y - impact_y
        
        self.target_x += shift_x
        self.target_y += shift_y
        return self.calculate_solution()

def print_solution(sol: Dict):
    print("=" * 55)
    print(f" WEAPON: {sol.get('weapon', 'mortar').upper()} ({sol.get('arc', 'high').upper()} ARC)")
    print(f" GUN:    ({sol['mortar'][0]:.2f}, {sol['mortar'][1]:.2f})  -->  TARGET: ({sol['target'][0]:.2f}, {sol['target'][1]:.2f})")
    print(f" Legs:   dx = {sol['dx_meters']:.1f}m | dy = {sol['dy_meters']:.1f}m")
    print(f" Hypotenuse (Distance): {sol['distance_meters']:.1f} meters")
    print(f" Bearing (Azimuth):     {sol['bearing_deg']:05.1f}°  ({sol['bearing_mils']} mils)")
    if sol['elevation_mils'] is not None:
        status = "OK" if sol['in_range'] else ("SLOPE ONLY (>850/<150 MIL)" if sol.get('slope_only') else "OUT OF RANGE")
        print(f" Elevation:             {sol['elevation_mils']:.0f} mils  [{status}]")
    else:
        print(f" Elevation:             OUT OF RANGE (<{sol['min_range']:.0f}m or >{sol['max_range']:.0f}m)")
    print("=" * 55)

def interactive_cli():
    print("=" * 60)
    print("   WARDOGS MORTAR & ARTILLERY PYTHAGOREAN CALCULATOR")
    print("=" * 60)
    print("Commands:")
    print("  m <x> <y>      : Set Mortar/Gun coordinates")
    print("  t <x> <y>      : Set Target coordinates")
    print("  wpn <m|sph_h|sph_l> : Switch weapon (mortar, sph_h, sph_l)")
    print("  add <m>        : Push range further by <m> meters")
    print("  drop <m>       : Pull range closer by <m> meters")
    print("  right <m>      : Shift right by <m> meters")
    print("  left <m>       : Shift left by <m> meters")
    print("  miss <long> <right> : Inverse correction for missed shot")
    print("  impact <x> <y> : Adjust based on observed impact coordinates")
    print("  q              : Quit")
    print("=" * 60)
    
    calc = MortarCalculator(10.0, 10.0)
    calc.set_target(13.0, 14.0)
    print_solution(calc.calculate_solution())

    while True:
        try:
            raw = input("\n[WARDOGS-MORTAR]> ").strip().lower()
            if not raw:
                continue
            if raw in ('q', 'quit', 'exit'):
                break
            
            parts = raw.split()
            cmd = parts[0]
            
            if cmd == 'm' and len(parts) >= 3:
                calc.set_mortar(float(parts[1]), float(parts[2]))
                print_solution(calc.calculate_solution())
            elif cmd == 't' and len(parts) >= 3:
                calc.set_target(float(parts[1]), float(parts[2]))
                print_solution(calc.calculate_solution())
            elif cmd == 'wpn' and len(parts) >= 2:
                w = parts[1]
                if w in ('sph', 'sph_h', 'sph2'):
                    calc.weapon, calc.arc = 'sph2', 'high'
                elif w == 'sph_l':
                    calc.weapon, calc.arc = 'sph2', 'low'
                else:
                    calc.weapon, calc.arc = 'mortar', 'high'
                print_solution(calc.calculate_solution())
            elif cmd == 'add' and len(parts) >= 2:
                print_solution(calc.adjust_relative(float(parts[1]), 0))
            elif cmd == 'drop' and len(parts) >= 2:
                print_solution(calc.adjust_relative(-float(parts[1]), 0))
            elif cmd == 'right' and len(parts) >= 2:
                print_solution(calc.adjust_relative(0, float(parts[1])))
            elif cmd == 'left' and len(parts) >= 2:
                print_solution(calc.adjust_relative(0, -float(parts[1])))
            elif cmd == 'miss' and len(parts) >= 3:
                print_solution(calc.adjust_missed_shot(float(parts[1]), float(parts[2])))
            elif cmd == 'impact' and len(parts) >= 3:
                print_solution(calc.adjust_impact_point(float(parts[1]), float(parts[2])))
            elif cmd in ('calc', 'solution'):
                print_solution(calc.calculate_solution())
            else:
                print(f"Unknown command: '{raw}'. Type e.g. 't 14.5 16.2' or 'add 50' or 'left 20'.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        calc = MortarCalculator(10.0, 10.0)
        calc.set_target(13.0, 14.0)
        sol = calc.calculate_solution()
        print("--- Test Solution (L81 Mortar 500m) ---")
        print_solution(sol)
        calc_sph = MortarCalculator(10.0, 10.0, weapon="sph2", arc="high")
        calc_sph.set_target(22.0, 26.0)
        calc_sph.hull_heading_deg = 180.0
        sol_sph = calc_sph.calculate_solution()
        print("--- Test Solution (SPH-2 2000m, Hull 180 deg) ---")
        print_solution(sol_sph)
    else:
        interactive_cli()
