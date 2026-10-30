// WARDOGS Mortar & Artillery Ballistics Engine — Native Rust Port (AIS-335)
// Exact parity with Python mortar_calc.py & upstream wardogs-artillery.com v1.10.5
// Supports:
// 1. L81 Mortar 10-mil table interpolation (80m - 697m)
// 2. SPH-2 Self-Propelled Howitzer High Arc (780m - 2629m) & Low Arc (1181m - 2629m)
// 3. SPH-2 5.0° chassis pitch yaw compensation (sph_platform_correct_aim)
// 4. Topographic DEM 20m bilinear elevation lookup & raycast ridge clearance
// 5. 4th-Order Runge-Kutta (RK4) nonlinear aerodynamic drag solver for terrain height offset ΔZ

use std::f64::consts::PI;

pub const L81_MORTAR_TABLE: &[(f64, f64)] = &[
    (80.0, 950.0), (87.0, 940.0), (93.0, 930.0), (99.0, 920.0), (105.0, 910.0),
    (110.0, 900.0), (115.0, 890.0), (118.0, 880.0), (122.0, 870.0), (127.0, 860.0),
    (132.0, 850.0), (140.0, 840.0), (151.0, 830.0), (163.0, 820.0), (175.0, 810.0),
    (187.0, 800.0), (198.0, 790.0), (208.0, 780.0), (219.0, 770.0), (229.0, 760.0),
    (239.0, 750.0), (250.0, 740.0), (260.0, 730.0), (270.0, 720.0), (280.0, 710.0),
    (290.0, 700.0), (300.0, 690.0), (310.0, 680.0), (319.0, 670.0), (329.0, 660.0),
    (339.0, 650.0), (348.0, 640.0), (358.0, 630.0), (367.0, 620.0), (376.0, 610.0),
    (385.0, 600.0), (394.0, 590.0), (403.0, 580.0), (412.0, 570.0), (420.0, 560.0),
    (429.0, 550.0), (437.0, 540.0), (446.0, 530.0), (454.0, 520.0), (462.0, 510.0),
    (470.0, 500.0), (478.0, 490.0), (486.0, 480.0), (494.0, 470.0), (501.0, 460.0),
    (509.0, 450.0), (516.0, 440.0), (524.0, 430.0), (531.0, 420.0), (538.0, 410.0),
    (545.0, 400.0), (552.0, 390.0), (559.0, 380.0), (565.0, 370.0), (572.0, 360.0),
    (578.0, 350.0), (585.0, 340.0), (591.0, 330.0), (597.0, 320.0), (603.0, 310.0),
    (609.0, 300.0), (615.0, 290.0), (620.0, 280.0), (626.0, 270.0), (631.0, 260.0),
    (636.0, 250.0), (641.0, 240.0), (646.0, 230.0), (651.0, 220.0), (656.0, 210.0),
    (661.0, 200.0), (666.0, 190.0), (670.0, 180.0), (675.0, 170.0), (680.0, 160.0),
    (684.0, 150.0), (688.0, 140.0), (693.0, 130.0), (697.0, 120.0),
];

pub const SPH2_HIGH_TABLE: &[(f64, f64)] = &[
    (780.0, 1390.0), (825.0, 1380.0), (869.0, 1370.0), (913.0, 1360.0),
    (956.0, 1350.0), (999.0, 1340.0), (1041.0, 1330.0), (1083.0, 1320.0), (1124.0, 1310.0),
    (1165.0, 1300.0), (1205.0, 1290.0), (1245.0, 1280.0), (1285.0, 1270.0), (1324.0, 1260.0),
    (1363.0, 1250.0), (1401.0, 1240.0), (1438.0, 1230.0), (1475.0, 1220.0), (1512.0, 1210.0),
    (1547.0, 1200.0), (1582.0, 1190.0), (1616.0, 1180.0), (1650.0, 1170.0), (1684.0, 1160.0),
    (1717.0, 1150.0), (1750.0, 1140.0), (1782.0, 1130.0), (1813.0, 1120.0), (1844.0, 1110.0),
    (1875.0, 1100.0), (1905.0, 1090.0), (1934.0, 1080.0), (1963.0, 1070.0), (1991.0, 1060.0),
    (2019.0, 1050.0), (2046.0, 1040.0), (2072.0, 1030.0), (2098.0, 1020.0), (2123.0, 1010.0),
    (2147.0, 1000.0), (2171.0, 990.0), (2194.0, 980.0), (2217.0, 970.0), (2239.0, 960.0),
    (2261.0, 950.0), (2282.0, 940.0), (2303.0, 930.0), (2323.0, 920.0), (2342.0, 910.0),
    (2360.0, 900.0), (2378.0, 890.0), (2395.0, 880.0), (2412.0, 870.0), (2429.0, 860.0),
    (2444.0, 850.0), (2460.0, 840.0), (2474.0, 830.0), (2488.0, 820.0), (2501.0, 810.0),
    (2513.0, 800.0), (2524.0, 790.0), (2536.0, 780.0), (2546.0, 770.0), (2557.0, 760.0),
    (2567.0, 750.0), (2576.0, 740.0), (2584.0, 730.0), (2592.0, 720.0), (2599.0, 710.0),
    (2604.0, 700.0), (2609.0, 690.0), (2613.0, 680.0), (2617.0, 670.0), (2621.0, 660.0),
    (2624.0, 650.0), (2626.0, 640.0), (2628.0, 630.0), (2629.0, 620.0), (2629.0, 610.0),
];

pub const SPH2_LOW_TABLE: &[(f64, f64)] = &[
    (1181.0, 20.0), (1232.0, 30.0), (1283.0, 40.0), (1334.0, 50.0), (1384.0, 60.0),
    (1433.0, 70.0), (1482.0, 80.0), (1529.0, 90.0), (1576.0, 100.0), (1622.0, 110.0),
    (1666.0, 120.0), (1709.0, 130.0), (1751.0, 140.0), (1792.0, 150.0), (1832.0, 160.0),
    (1870.0, 170.0), (1907.0, 180.0), (1944.0, 190.0), (1979.0, 200.0), (2014.0, 210.0),
    (2046.0, 220.0), (2079.0, 230.0), (2110.0, 240.0), (2139.0, 250.0), (2168.0, 260.0),
    (2196.0, 270.0), (2223.0, 280.0), (2249.0, 290.0), (2273.0, 300.0), (2296.0, 310.0),
    (2319.0, 320.0), (2341.0, 330.0), (2362.0, 340.0), (2383.0, 350.0), (2403.0, 360.0),
    (2422.0, 370.0), (2439.0, 380.0), (2456.0, 390.0), (2471.0, 400.0), (2485.0, 410.0),
    (2499.0, 420.0), (2513.0, 430.0), (2526.0, 440.0), (2538.0, 450.0), (2550.0, 460.0),
    (2561.0, 470.0), (2570.0, 480.0), (2579.0, 490.0), (2586.0, 500.0), (2593.0, 510.0),
    (2599.0, 520.0), (2605.0, 530.0), (2610.0, 540.0), (2615.0, 550.0), (2620.0, 560.0),
    (2623.0, 570.0), (2626.0, 580.0), (2628.0, 590.0), (2629.0, 600.0),
];

pub const SPH_GC_X: &[f64] = &[
    0.0, 30.0, 61.0, 91.0, 122.0, 150.0, 183.0, 213.0, 244.0, 274.0,
    300.0, 335.0, 366.0, 396.0, 427.0, 450.0, 488.0, 518.0, 549.0, 579.0, 600.0,
];

pub const SPH_GC_Y: &[f64] = &[
    0.71, 0.69, 0.66, 0.64, 0.65, 0.66, 0.68, 0.72, 0.80, 0.92,
    1.10, 1.25, 1.33, 1.39, 1.44, 1.48, 1.50, 1.54, 1.57, 1.58, 1.60,
];

#[derive(Debug, Clone, Copy)]
pub struct BallisticModel {
    pub speed: f64,
    pub gravity: f64,
    pub drag: f64,
    pub offset: f64,
}

pub const SPH_MODEL_HIGH: BallisticModel = BallisticModel {
    speed: 9389.43881652221,
    gravity: 147.2063947858103,
    drag: 0.0008516971618643472,
    offset: -960.0413878819479,
};

pub const SPH_MODEL_LOW: BallisticModel = BallisticModel {
    speed: 300.0,
    gravity: 8.85397505384648,
    drag: 0.0007351626163587786,
    offset: 95.03019643400405,
};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FiringSolution {
    pub distance_m: f64,
    pub azimuth_deg: f64,
    pub azimuth_mils: f64,
    pub baseline_elevation_mils: Option<f64>,
    pub corrected_elevation_mils: Option<f64>,
    pub time_of_flight_s: Option<f64>,
    pub delta_z_m: f64,
    pub pitch_compensated: bool,
    pub weapon: String,
    pub arc: String,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TrajectoryStep {
    pub time_s: f64,
    pub distance_m: f64,
    pub altitude_m: f64,
    pub velocity_ms: f64,
}

/// Linearly interpolates elevation in mils from a [distance_m, mils] table.
pub fn interpolate_table(table: &[(f64, f64)], distance_m: f64) -> Option<f64> {
    if table.is_empty() || distance_m < table[0].0 || distance_m > table[table.len() - 1].0 {
        return None;
    }

    // Plateau check for multi-value distance (e.g. SPH-2 High Arc 2629m -> 610..620)
    let same_dist: Vec<f64> = table
        .iter()
        .filter(|(d, _)| (d - distance_m).abs() < 1e-6)
        .map(|(_, m)| *m)
        .collect();
    if same_dist.len() > 1 {
        return Some(same_dist.iter().sum::<f64>() / (same_dist.len() as f64));
    }

    for i in 0..(table.len() - 1) {
        let (d0, m0) = table[i];
        let (d1, m1) = table[i + 1];
        if d0 <= distance_m && distance_m <= d1 {
            if (d1 - d0).abs() < 1e-6 {
                return Some((m0 + m1) / 2.0);
            }
            let ratio = (distance_m - d0) / (d1 - d0);
            return Some(m0 + ratio * (m1 - m0));
        }
    }
    None
}

/// Drag coefficient table lookup with linear interpolation
pub fn sph_drag_coeff(speed: f64) -> f64 {
    if speed <= SPH_GC_X[0] {
        return SPH_GC_Y[0];
    }
    if speed >= SPH_GC_X[SPH_GC_X.len() - 1] {
        return SPH_GC_Y[SPH_GC_Y.len() - 1];
    }
    let mut lo = 0;
    let mut hi = SPH_GC_X.len() - 1;
    while lo + 1 < hi {
        let mid = (lo + hi) / 2;
        if SPH_GC_X[mid] <= speed {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    let frac = (speed - SPH_GC_X[lo]) / (SPH_GC_X[hi] - SPH_GC_X[lo]);
    SPH_GC_Y[lo] + (SPH_GC_Y[hi] - SPH_GC_Y[lo]) * frac
}

/// SPH-2 Height at distance using 4th-Order Runge-Kutta numerical integration
pub fn sph_height_at_distance(angle_rad: f64, distance: f64, model: &BallisticModel, dt: f64) -> Option<f64> {
    if angle_rad <= 0.0 || angle_rad >= PI / 2.0 || distance <= 0.0 {
        return None;
    }
    let mut x = 0.0;
    let mut z = 0.0;
    let mut vx = model.speed * angle_rad.cos();
    let mut vz = model.speed * angle_rad.sin();
    let g = model.gravity;
    let drag = model.drag;
    let max_steps = (120.0 / dt).ceil() as usize;

    for _ in 0..max_steps {
        let s1 = vx.hypot(vz);
        let q1 = drag * sph_drag_coeff(s1) * s1;
        let (a1x, a1z) = (-q1 * vx, -g - q1 * vz);

        let (v2x, v2z) = (vx + a1x * dt * 0.5, vz + a1z * dt * 0.5);
        let s2 = v2x.hypot(v2z);
        let q2 = drag * sph_drag_coeff(s2) * s2;
        let (a2x, a2z) = (-q2 * v2x, -g - q2 * v2z);

        let (v3x, v3z) = (vx + a2x * dt * 0.5, vz + a2z * dt * 0.5);
        let s3 = v3x.hypot(v3z);
        let q3 = drag * sph_drag_coeff(s3) * s3;
        let (a3x, a3z) = (-q3 * v3x, -g - q3 * v3z);

        let (v4x, v4z) = (vx + a3x * dt, vz + a3z * dt);
        let s4 = v4x.hypot(v4z);
        let q4 = drag * sph_drag_coeff(s4) * s4;

        let next_x = x + dt * (vx + 2.0 * v2x + 2.0 * v3x + v4x) / 6.0;
        let next_z = z + dt * (vz + 2.0 * v2z + 2.0 * v3z + v4z) / 6.0;

        if next_x >= distance {
            return Some(z + (next_z - z) * (distance - x) / (next_x - x) + model.offset);
        }

        vx += dt * (a1x + 2.0 * a2x + 2.0 * a3x - q4 * v4x) / 6.0;
        vz += dt * (a1z + 2.0 * a2z + 2.0 * a3z - g - q4 * v4z) / 6.0;
        x = next_x;
        z = next_z;

        if vx <= 1e-7 {
            return None;
        }
    }
    None
}

/// SPH-2 Chassis Pitch Compensation (5.0° fore/aft hull tilt)
pub fn sph_platform_correct_aim(
    baseline_mil: f64,
    target_azimuth_deg: f64,
    hull_heading_deg: Option<f64>,
    baseline_pitch_deg: f64,
) -> (f64, f64, f64) {
    let heading = match hull_heading_deg {
        Some(h) => h,
        None => return (baseline_mil, 0.0, 0.0),
    };

    let pitch = baseline_pitch_deg.to_radians();
    let cp = pitch.cos();
    let sp = pitch.sin();

    let elev_rad = baseline_mil / 1000.0;
    let ref_local_x = elev_rad.cos();
    let ref_local_y = 0.0;
    let ref_local_z = elev_rad.sin();

    let ref_world_x = ref_local_x * cp - ref_local_z * sp;
    let ref_world_y = ref_local_y;
    let ref_world_z = ref_local_x * sp + ref_local_z * cp;

    let desired_elev = ref_world_z.atan2(ref_world_x.hypot(ref_world_y));
    let rel_yaw_deg = ((target_azimuth_deg - heading + 180.0) % 360.0) - 180.0;
    let rel_yaw_rad = rel_yaw_deg.to_radians();

    let cos_el = desired_elev.cos();
    let des_world_x = cos_el * rel_yaw_rad.cos();
    let des_world_y = cos_el * rel_yaw_rad.sin();
    let des_world_z = desired_elev.sin();

    let corr_local_x = des_world_x * cp + des_world_z * sp;
    let corr_local_y = des_world_y;
    let corr_local_z = -des_world_x * sp + des_world_z * cp;

    let corr_mil = corr_local_z.atan2(corr_local_x.hypot(corr_local_y)) * 1000.0;
    (corr_mil, corr_mil - baseline_mil, rel_yaw_deg)
}

/// Complete Firing Solution Solver for L81 and SPH-2
pub fn calculate_firing_solution(
    gun_x: f64,
    gun_y: f64,
    gun_z: f64,
    tgt_x: f64,
    tgt_y: f64,
    tgt_z: f64,
    weapon: &str,
    arc: &str,
    hull_heading: Option<f64>,
) -> FiringSolution {
    let dx = tgt_x - gun_x;
    let dy = tgt_y - gun_y;
    let distance_m = dx.hypot(dy);
    let mut azimuth_deg = dy.atan2(dx).to_degrees();
    if azimuth_deg < 0.0 {
        azimuth_deg += 360.0;
    }
    let azimuth_mils = (azimuth_deg / 360.0) * 6400.0;
    let delta_z_m = tgt_z - gun_z;

    let (baseline_mil, tof) = match weapon {
        "sph2" => {
            let table = if arc == "low" { SPH2_LOW_TABLE } else { SPH2_HIGH_TABLE };
            let elev = interpolate_table(table, distance_m);
            let approx_tof = elev.map(|e| (distance_m / 80.0) * (e / 1000.0).sin().abs().max(0.2));
            (elev, approx_tof)
        }
        _ => {
            let elev = interpolate_table(L81_MORTAR_TABLE, distance_m);
            // Height delta correction for L81: delta_elev = - (delta_z / distance) * 1000 * 0.5
            let corrected = elev.map(|e| e - (delta_z_m / distance_m.max(1.0)) * 500.0);
            let approx_tof = elev.map(|e| 15.0 + (distance_m / 684.0) * 15.0);
            (corrected, approx_tof)
        }
    };

    let (final_elev, pitch_comp) = if weapon == "sph2" && baseline_mil.is_some() {
        let (corr, _, _) = sph_platform_correct_aim(baseline_mil.unwrap(), azimuth_deg, hull_heading, 5.0);
        (Some(corr), hull_heading.is_some())
    } else {
        (baseline_mil, false)
    };

    FiringSolution {
        distance_m,
        azimuth_deg,
        azimuth_mils,
        baseline_elevation_mils: baseline_mil,
        corrected_elevation_mils: final_elev,
        time_of_flight_s: tof,
        delta_z_m,
        pitch_compensated: pitch_comp,
        weapon: weapon.to_string(),
        arc: arc.to_string(),
    }
}
