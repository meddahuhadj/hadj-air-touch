"""Geometry helpers: homography, perspective transform, triangulation.

Works in pure Python (tested) and optionally uses numpy when available.
"""
from __future__ import annotations

import math
from typing import Sequence

from app.utils.vectors import Tup2, HAS_NUMPY

if HAS_NUMPY:
    import numpy as np


# ---------------------------------------------------------------------------
# 3x3 matrix helpers (row-major lists of lists)
# ---------------------------------------------------------------------------
Mat3 = list[list[float]]


def _mat3_identity() -> Mat3:
    return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def _mat3_mul(A: Mat3, B: Mat3) -> Mat3:
    return [
        [sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]


def _mat3_apply(H: Mat3, pt: Tup2) -> Tup2:
    x, y = pt
    w = H[2][0] * x + H[2][1] * y + H[2][2]
    if abs(w) < 1e-12:
        return (0.0, 0.0)
    return (
        (H[0][0] * x + H[0][1] * y + H[0][2]) / w,
        (H[1][0] * x + H[1][1] * y + H[1][2]) / w,
    )


# ---------------------------------------------------------------------------
# DLT-based homography (4+ point pairs)
# ---------------------------------------------------------------------------

def _build_dlt_matrix(pts_src: Sequence[Tup2], pts_dst: Sequence[Tup2]) -> list[list[float]]:
    """Build the 2N x 9 DLT matrix from corresponding point pairs."""
    rows: list[list[float]] = []
    for (x, y), (u, v) in zip(pts_src, pts_dst):
        rows.append([-x, -y, -1, 0, 0, 0, x * u, y * u, u])
        rows.append([0, 0, 0, -x, -y, -1, x * v, y * v, v])
    return rows


def _null_vector_via_gaussian(A: list[list[float]]) -> list[float]:
    """Find the null space of an m x n matrix (m < n) via Gaussian elimination.

    Solves A x = 0 by fixing the last variable to 1 and performing a
    least-squares solve on the remaining columns, then normalising.
    This is robust for the small DLT matrix (default: 8 x 9).
    """
    import copy

    m = len(A)
    n = len(A[0])
    if m < 1 or n < 1:
        raise ValueError("Empty matrix")

    # Solve  A[:, :-1] x = -A[:, -1]  using Gaussian elimination
    rhs = [-row[-1] for row in A]
    M = [row[:-1] for row in A]

    # Forward elimination with partial pivoting
    for col in range(min(m, n - 1)):
        # Find pivot
        pivot_row = col
        max_val = abs(M[col][col]) if col < len(M[col]) else 0.0
        for r in range(col, m):
            if col < len(M[r]) and abs(M[r][col]) > max_val:
                max_val = abs(M[r][col])
                pivot_row = r
        if max_val < 1e-12:
            continue
        # Swap rows
        M[col], M[pivot_row] = M[pivot_row], M[col]
        rhs[col], rhs[pivot_row] = rhs[pivot_row], rhs[col]
        # Eliminate below
        for r in range(col + 1, m):
            factor = M[r][col] / M[col][col] if abs(M[col][col]) > 1e-12 else 0.0
            if abs(factor) < 1e-15:
                continue
            for c in range(col, len(M[r])):
                M[r][c] -= factor * M[col][c]
            rhs[r] -= factor * rhs[col]

    # Back substitution on the top square part
    k = min(m, n - 1)
    x = [0.0] * (n - 1)
    for i in range(k - 1, -1, -1):
        diag = M[i][i] if i < len(M[i]) else 0.0
        if abs(diag) < 1e-12:
            continue
        s = rhs[i]
        for j in range(i + 1, n - 1):
            s -= M[i][j] * x[j] if j < len(M[i]) else 0.0
        x[i] = s / diag

    h = x + [1.0]
    # Normalise to unit length (avoid all-zero when underdetermined)
    norm = math.sqrt(sum(v * v for v in h))
    if norm < 1e-12:
        # Fallback: pure identity homography
        return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    return [v / norm for v in h]


def solve_homography(
    pts_src: Sequence[Tup2],
    pts_dst: Sequence[Tup2],
) -> Mat3:
    """Compute homography H (3x3) mapping pts_src -> pts_dst.

    Requires >= 4 point pairs.  Returns row-major 3x3 matrix.
    """
    if len(pts_src) < 4 or len(pts_src) != len(pts_dst):
        raise ValueError("At least 4 corresponding point pairs required.")

    A = _build_dlt_matrix(pts_src, pts_dst)
    h = _null_vector_via_gaussian(A)

    H = [h[0:3], h[3:6], h[6:9]]
    # Normalise so H[2][2] == 1
    if abs(H[2][2]) > 1e-12:
        H = [[v / H[2][2] for v in row] for row in H]
    return H


def apply_homography(H: Mat3, pt: Tup2) -> Tup2:
    return _mat3_apply(H, pt)


def inverse_homography(H: Mat3) -> Mat3:
    """Invert a 3x3 homography via the cofactor/adjugate method."""
    if HAS_NUMPY:
        Hnp = np.array(H, dtype=np.float64)
        Hinv = np.linalg.inv(Hnp)
        return Hinv.tolist()

    # Cofactor expansion for 3x3 inverse
    def _minor(m: Mat3, row: int, col: int) -> float:
        vals = [m[r][c] for r in range(3) for c in range(3) if r != row and c != col]
        return vals[0] * vals[3] - vals[1] * vals[2]

    cofactors = [[(-1) ** (r + c) * _minor(H, r, c) for c in range(3)] for r in range(3)]
    det = sum(H[0][c] * cofactors[0][c] for c in range(3))
    if abs(det) < 1e-12:
        raise ValueError("Singular homography")
    adj = [[cofactors[c][r] for c in range(3)] for r in range(3)]
    return [[adj[r][c] / det for c in range(3)] for r in range(3)]


# ---------------------------------------------------------------------------
# Numpy-accelerated variants (used when numpy is available)
# ---------------------------------------------------------------------------

if HAS_NUMPY:
    def solve_homography_np(
        pts_src: Sequence[Tup2],
        pts_dst: Sequence[Tup2],
    ) -> Mat3:
        A_np = np.array(_build_dlt_matrix(pts_src, pts_dst), dtype=np.float64)
        _, _, Vt = np.linalg.svd(A_np)
        h = Vt[-1]
        H = h.reshape(3, 3)
        H /= H[2, 2]
        return H.tolist()

    def apply_homography_np(H: Mat3, pt: Tup2) -> Tup2:
        Hnp = np.array(H, dtype=np.float64)
        pt_h = np.array([pt[0], pt[1], 1.0])
        r = Hnp @ pt_h
        return (float(r[0] / r[2]), float(r[1] / r[2]))