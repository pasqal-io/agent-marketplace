import numpy as np
from dataclasses import replace

from pulser import Sequence, Register, Pulse, Register3D
from pulser.devices import VirtualDevice, AnalogDevice
from pulser.channels import Rydberg
from pulser.channels.dmm import DMM
from pulser.waveforms import InterpolatedWaveform
from pulser.register.register_layout import RegisterLayout
from pulser.channels.eom import RydbergBeam, RydbergEOM


def virtual_device(device, n=75, mod_bandwidth=8):
    VirtualAnalog = device.to_virtual()
    VirtualAnalog = replace(
        VirtualAnalog,
        rydberg_level=n,
        reusable_channels=True,
        dmm_objects=[DMM()],
        dimensions=3,
        max_atom_num=None,
        max_radial_distance=None,
        min_atom_distance=1,
        max_sequence_duration=None,
        channel_objects=(
            Rydberg.Global(
                None,
                None,
                max_duration=None,
                mod_bandwidth=mod_bandwidth,
                eom_config=RydbergEOM(
                    limiting_beam=RydbergBeam.RED,
                    max_limiting_amp=30 * 2 * np.pi,
                    intermediate_detuning=450 * 2 * np.pi,
                    mod_bandwidth=40,
                    controlled_beams=(RydbergBeam.BLUE,),
                    custom_buffer_time=240,
                ),
            ),
        ),
    )
    return VirtualAnalog


def pulser_triang_romboid_register(Lx, Ly, R):
    r"""
    Compute the positions of the sites on a triangular lattice
    in a rhombus of sides Lx, Ly with lattice spacing R.

    The lattice is spanned by primitive vectors:
        a1 = (R, 0)
        a2 = (R/2, sqrt(3)R/2)

    Parameters
    ----------
    Lx, Ly : int
        Number of steps along the a1 and a2 directions.
    R : float
        Lattice spacing.


    Returns
    -------
    coords: array of tuples
        An array containing the register coordinates.
    plaquette_coords: array of tuples
        An array containing the reservoir coordinates.
    """
    N = Lx * Ly

    a1 = np.array([R, 0])
    a2 = np.array([R / 2, np.sqrt(3) / 2 * R])

    coords = np.array([i * a1 + j * a2 for i in range(Lx) for j in range(Ly)])

    # --- plaquette centers: shifted by (a1 + a2)/2 ---
    plaquettes = []

    up_shift = (a1 + a2) / 3.0
    down_shift = 2 * (a1 + a2) / 3.0

    for i in range(Lx):
        for j in range(Ly):
            if j < Ly - 1:
                # all rows except top: keep upward triangles
                plaquettes.append(i * a1 + j * a2 + up_shift)
            elif j == Ly - 1:
                # top row replaced by downward triangles in the row below
                plaquettes.append(i * a1 + (j - 1) * a2 + down_shift)
            if j == 0:
                plaquettes.append(i * a1 + (j) * a2 + down_shift)

            if i == 0 and (j > 1 and j != Ly - 1):
                plaquettes.append(i * a1 + (j - 1) * a2 + down_shift)

            if i == Lx - 2 and (j > 1 and j != Ly - 1):
                plaquettes.append(i * a1 + (j - 1) * a2 + down_shift)

    plaquette_coords_all = np.vstack(plaquettes)

    # remove reservoir traps that are further away of the origin than register traps

    max_dist = np.max(np.linalg.norm(coords, axis=1))
    keep_mask = np.linalg.norm(plaquette_coords_all, axis=1) <= max_dist
    plaquette_coords = plaquette_coords_all[keep_mask]

    center = np.mean(coords, axis=0)  # geometric center of all sites
    coords = coords - center
    plaquette_coords = plaquette_coords - center

    return coords, plaquette_coords


def create_interp_pulse(T, amp_params, det_params, interp_pts):
    return Pulse(
        InterpolatedWaveform(T * 1000, amp_params, times=interp_pts),
        InterpolatedWaveform(T * 1000, det_params, times=interp_pts),
        0,
    )


def para_pusho_sequence(
    trap_or_reg,
    device_used,
    m=1,
    interp_pts=None,
    t_before_and_after=0,
    U=1,
    Omega_still_on=False,
    delta_still_on=False,
):
    if isinstance(trap_or_reg, RegisterLayout):
        mapp_reg = trap_or_reg.make_mappable_register(trap_or_reg.number_of_traps // 2)
    elif isinstance(trap_or_reg, Register) or isinstance(trap_or_reg, Register3D):
        mapp_reg = trap_or_reg
    else:
        raise TypeError("Expected a Layout or a Register for 'trap_or_reg'.")
    seq = Sequence(mapp_reg, device_used)
    seq.declare_channel("rydberg", "rydberg_global")
    if interp_pts is not None:
        params = seq.declare_variable("params", size=2 * m + 1)
        P = create_interp_pulse(
            params[0], U * params[1 : m + 1], U * params[m + 1 :], interp_pts=interp_pts
        )
    else:
        params = seq.declare_variable("params", size=3 * m + 1)
        P = create_interp_pulse(
            params[0],
            U * params[1 : m + 1],
            U * params[m + 1 : 2 * m + 1],
            interp_pts=params[2 * m + 1 :],
        )
    seq.add(P, "rydberg")
    if not (Omega_still_on or delta_still_on):
        if t_before_and_after > 16:
            seq.add(
                Pulse.ConstantPulse(
                    t_before_and_after, U * params[m], U * params[2 * m], 0
                ),
                "rydberg",
            )
    else:
        seq.add(
            Pulse.ConstantPulse(
                5990 - params[0] * 1000,
                U * int(Omega_still_on) * params[m],
                U * params[2 * m] * int(delta_still_on),
                0,
            ),
            "rydberg",
        )
    seq.measure(basis="ground-rydberg")
    return seq
