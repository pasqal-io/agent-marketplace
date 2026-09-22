import numpy as np


def get_basis_vectors(angles):
    """Return 2D unit vectors for the given angles."""
    return np.array([[np.cos(a), np.sin(a)] for a in angles])


def compute_rhombus_positions(
    Lx, Ly, spacing, angles=np.array([0, np.pi / 3]), ordering="columns"
):
    """
    Compute lattice positions for a 2D lattice with a given basis.

    Parameters:
        Lx, Ly: lattice dimensions
        spacing: lattice spacing
        angles: angles of the two basis vectors
        ordering: 'columns', 'lines', or 'diagonal' (determines site ordering)

    Returns:
        x, y: arrays of lattice coordinates, sorted according to ordering
    """
    if ordering not in {"columns", "lines", "diagonal_acute", "diagonal_obtuse"}:
        raise ValueError(
            f"Unknown ordering: {ordering!r}. Must be 'columns', 'lines', or 'diagonal_acute','diagonal_obtuse."
        )

    basis = spacing * get_basis_vectors(angles)  # lattice vectors
    a1, a2 = basis

    # Generate lattice indices
    i, j = np.meshgrid(np.arange(Lx), np.arange(Ly), indexing="ij")
    i_flat = i.ravel()
    j_flat = j.ravel()

    # Compute positions
    x = i_flat * a1[0] + j_flat * a2[0]
    y = i_flat * a1[1] + j_flat * a2[1]

    # Sorting keys
    sort_keys = {
        "columns": (j_flat, i_flat),
        "lines": (i_flat, j_flat),
        "diagonal_obtuse": (j_flat, i_flat - j_flat),
        "diagonal_acute": (j_flat - i_flat, i_flat + j_flat),
    }

    sort_idx = np.lexsort(sort_keys[ordering])
    return np.column_stack([x[sort_idx], y[sort_idx]])
