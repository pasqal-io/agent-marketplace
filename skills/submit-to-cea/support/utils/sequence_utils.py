import numpy as np
from scipy.spatial.distance import pdist
from pulser import Register, Sequence, Pulse
from pulser.waveforms import InterpolatedWaveform
from pulser.register.register_layout import RegisterLayout
import warnings
from pulser.devices import Device, AnalogDevice

import utils.pulser_utils as pu
import utils.rhombus_utils as ru


def compute_hexagon_coords(n, R, center=[0, 0]):
    if n < 1 or R <= 0:
        return np.empty((0, 2))

    L = n * R  # Side length
    angles = np.deg2rad(np.arange(0, 360, 60))
    corners = L * np.c_[np.cos(angles), np.sin(angles)]

    pts = []
    for i in range(6):
        a, b = corners[i], corners[(i + 1) % 6]
        t = np.linspace(0, 1, n, endpoint=False)
        pts.append((1 - t)[:, None] * a + t[:, None] * b)

    xy = np.vstack(pts) + center
    return xy


def compute_circle_coords(N, R, center=np.array([[0, 0]])):
    if N > 1:
        return np.round(
            center
            + R
            / np.sqrt(2 - 2 * np.cos(2 * np.pi / (N)))
            * np.array(
                [[np.cos(e), np.sin(e)] for e in 2 * np.pi * np.linspace(0, 1, N + 1)]
            )[:-1],
            3,
        )
    else:
        return center


def perpendicular_pairs(points, R):
    pts = np.atleast_2d(points).astype(float)
    x, y = pts[:, 0], pts[:, 1]
    n = np.sqrt(x**2 + y**2)
    if np.any(n == 0):
        raise ValueError("Points cannot include the origin.")
    u = np.stack([-y / n, x / n], axis=1)
    p1, p2 = pts + (R / 2) * u, pts - (R / 2) * u
    return (
        np.concatenate([p1[0], p2[0]])
        if np.ndim(points) == 1
        else np.concatenate([p1, p2])
    )


def build_typical_register(
    N=6,
    device=pu.virtual_device(AnalogDevice),
    type="isolated",
    Omega_max=2 * np.pi * 2,
    ratio=1.0,
    automatic_layout=False,
):

    spacing = device.rydberg_blockade_radius(Omega_max * 1 / ratio)

    if type == "isolated":
        if N > 1:
            coords = np.concatenate(
                [
                    compute_circle_coords(1, spacing),
                    compute_circle_coords(N - 1, spacing),
                ]
            )
        else:
            coords = compute_circle_coords(1, spacing)

    elif type == "pairs":
        if N % 2 != 0:
            warnings.warn(
                f"Number of qubits ({N}) is not a multiple of 2 — "
                "Used the lowest adequate number."
            )
            N = int(N // 2) * 2
        if N // 2 != 1:
            c = compute_circle_coords(N // 2, 3 * spacing)
        else:
            c = np.array([[0, 0]]) + 1e-2
        coords = perpendicular_pairs(c, spacing)

    elif type == "circle":
        coords = compute_circle_coords(N, spacing)

    elif type == "hexagon":
        if N % 6 != 0:
            warnings.warn(
                f"Number of qubits ({N}) is not a multiple of 6 — "
                "Used the lowest adequate number."
            )
        coords = compute_hexagon_coords(int(N // 6), spacing)
        N = int(N // 6) * 6
    elif type == "rhombus":
        n = int(np.sqrt(N))
        if n**2 != N:
            warnings.warn(
                f"Number of qubits ({N}) is not a square — "
                "Using the lowest adequate number."
            )
        coords = ru.compute_rhombus_positions(
            n, n, spacing, angles=np.array([0, np.pi / 3])
        )
        N = n**2
    elif type == "rhombus_side":
        n = int(np.sqrt(N))
        if n**2 != N:
            warnings.warn(
                f"Number of qubits ({N}) is not a square — "
                "Using the lowest adequate number."
            )
        coords = ru.compute_rhombus_positions(
            n, n, spacing, angles=np.array([0, np.pi / 3])
        )
        N = n**2
    elif type == "square":
        n = int(np.sqrt(N))
        if n**2 != N:
            warnings.warn(
                f"Number of qubits ({N}) is not a square — "
                "Using the lowest adequate number."
            )
        coords = ru.compute_rhombus_positions(
            n, n, spacing, angles=np.array([0, np.pi / 2])
        )
        N = n**2

    register = Register.from_coordinates(
        coords,
        labels=[str(i) for i in range(N)],
    )
    if isinstance(device, Device):
        if type == "rhombus" or type == "rhombus_side" and not automatic_layout:
            c1, c2 = pu.pulser_triang_romboid_register(
                int(np.sqrt(N)), int(np.sqrt(N)), spacing
            )
            layout = RegisterLayout(np.concatenate([c1, c2]))
            trap_ids = layout.get_traps_from_coordinates(*c1)
            register = layout.define_register(*trap_ids)
        else:
            register = register.with_automatic_layout(device)
    return register


def build_para_annealing_sequence(
    N=6,
    device=pu.virtual_device(AnalogDevice),
    wait=0,
    type="isolated",
    m=10,
    Omega_max=2 * np.pi * 2,
    ratio=1.0,
    Omega_still_on=False,
    delta_still_on=False,
    automatic_layout=False,
):
    register = build_typical_register(
        N=N,
        device=device,
        type=type,
        Omega_max=Omega_max,
        ratio=ratio,
        automatic_layout=automatic_layout,
    )
    spacing = np.min(pdist(np.array(list(register.qubits.values()))))
    print(spacing)
    U = device.rabi_from_blockade(spacing)
    para_seq = pu.para_pusho_sequence(
        register,
        device,
        m=m,
        t_before_and_after=wait,
        U=U,
        Omega_still_on=Omega_still_on,
        delta_still_on=delta_still_on,
    )
    return para_seq


def build_ramp_schedule(
    t_down,
    delta_i=-1,
    delta_f=1,
    Omega_i=1e-9,
    Omega_f=1e-9,
    Omega_max=1,
    t_up=0.5,
    t_cst=0.5,
    m=10,
):

    t_tot = t_up + t_cst + t_down
    # Round t_tot up to nearest multiple of channel clock period (4 ns = 0.004 µs)
    clock_period_us = 0.004
    t_tot = np.ceil(t_tot / clock_period_us) * clock_period_us
    t = np.linspace(0, t_tot, m)

    # amplitude: ramp up -> constant -> ramp down
    amp = np.where(
        t <= t_up,
        Omega_i + (Omega_max - Omega_i) * t / t_up,
        np.where(
            t <= t_up + t_cst,
            Omega_max,
            Omega_f if t_down == 0 else Omega_max + (Omega_f - Omega_max) * (t - t_up - t_cst) / t_down,
        ),
    )
    # detuning: constant -> ramp -> constant
    det = np.where(
        t <= t_up,
        delta_i,
        np.where(
            t <= t_up + t_cst,
            delta_f if t_cst == 0 else delta_i + (delta_f - delta_i) * (t - t_up) / t_cst,
            delta_f,
        ),
    )

    return [t_tot] + amp.tolist() + det.tolist() + (t / t_tot).tolist()


def make_square_register(N: int, R: float, device: Device):
    return Register.square(N, R, prefix="").with_automatic_layout(device)


def compute_detuning(N: int, R: float, C6: float) -> float:
    """Detuning for a square lattice: 2*C6 * sum of 1/(4*r^6) over all sites,
    evaluated from the central site."""
    x = np.arange(N)
    X, Y = np.meshgrid(x, x)
    coords = np.column_stack((X.ravel(), Y.ravel())) * R
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    dist = np.linalg.norm(diff, axis=-1)
    np.fill_diagonal(dist, 1e10)
    central_site = (N // 2 - 1) * N + (N // 2 - 1)
    return 2 * C6 * np.sum(1 / (4 * dist[central_site, :] ** 6))


def build_para_tfall_sequence(
    N=36,
    device=pu.virtual_device(AnalogDevice),
    omega=4 * np.pi,
    hx=4.0,
    T1_ns=500,
    T2_ns=1000,
):
    n = int(np.sqrt(N))
    if n ** 2 != N:
        raise ValueError("N must be a perfect square")

    U = 2 * omega / hx
    spacing = device.rydberg_blockade_radius(U)
    register = make_square_register(n, spacing, device)

    para_seq = Sequence(register, device)
    para_seq.declare_channel("rydberg", "rydberg_global")

    # Declare variable first so the sequence is in parametric mode throughout
    T_fall = para_seq.declare_variable("params")  # fall duration in µs

    # Pulse 1 (fixed): Omega 0→omega, delta = -3U flat
    para_seq.add(
        Pulse(
            InterpolatedWaveform(T1_ns, [1e-9, omega], times=[0.0, 1.0]),
            InterpolatedWaveform(T1_ns, [-3 * U, -3 * U], times=[0.0, 1.0]),
            0,
        ),
        "rydberg",
    )

    # Pulse 2 (fixed): Omega flat at omega, delta -3U→2.3U (phase crossing)
    para_seq.add(
        Pulse(
            InterpolatedWaveform(T2_ns, [omega, omega], times=[0.0, 1.0]),
            InterpolatedWaveform(T2_ns, [-3 * U, 2.3 * U], times=[0.0, 1.0]),
            0,
        ),
        "rydberg",
    )

    # Pulse 3 (parametric): Omega omega→0, delta = 2.3U flat, duration = T_fall
    para_seq.add(
        Pulse(
            InterpolatedWaveform(T_fall * 1000, [omega, 1e-9], times=[0.0, 1.0]),
            InterpolatedWaveform(T_fall * 1000, [2.3 * U, 2.3 * U], times=[0.0, 1.0]),
            0,
        ),
        "rydberg",
    )

    return para_seq


def make_calibration_sequence(device):
    """Parametric EOM calibration sequence for Rydberg spectroscopy and Rabi oscillations.

    Uses a fixed 7-atom triangular register isolated from the lattice geometry.
    Variables: duration_0 (int, ns), amp_0 (float, rad/µs), detuning (float, rad/µs).
    """
    from pulser.register.special_layouts import TriangularLatticeLayout

    register = TriangularLatticeLayout(61, 8).define_register(*[4, 15, 18, 30, 42, 45, 56])
    register = register.with_automatic_layout(device)
    seq = Sequence(register, device)
    seq.declare_channel("ising", "rydberg_global")
    dt = seq.declare_variable("duration_0", dtype=int)
    Omega_eff = seq.declare_variable("amp_0", dtype=float)
    det = seq.declare_variable("detuning", dtype=float)
    seq.enable_eom_mode("ising", amp_on=Omega_eff, detuning_on=det)
    seq.add_eom_pulse("ising", duration=dt, phase=0.0)
    seq.disable_eom_mode("ising")
    return seq


def build_para_quench_sequence(
    N=6,
    device=pu.virtual_device(AnalogDevice),
    Omega_max=2 * np.pi * 2,
    hx=2.0,
):
    R = (hx * 2 * device.interaction_coeff / (4 * Omega_max)) ** (1 / 6)
    detuning = compute_detuning(N, R, device.interaction_coeff)
    register = make_square_register(N, R, device=device)
    para_seq = Sequence(register, device)
    para_seq.declare_channel("rydberg", "rydberg_global")
    T = para_seq.declare_variable("params")
    para_seq.enable_eom_mode("rydberg", amp_on=Omega_max, detuning_on=detuning)
    para_seq.add_eom_pulse("rydberg", duration=T * 1000, phase=0.0)
    para_seq.disable_eom_mode("rydberg")
    return para_seq
