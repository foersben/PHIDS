# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Spatial placement generation helpers.

Provides functions to compute coordinate vectors for uniform, clustered,
and banded initial entity distributions on the biotope grid.
"""

import random


def generate_uniform(width: int, height: int, density: float) -> list[tuple[int, int]]:
    """Randomly scatter entities across the grid based on density.

    Args:
        width: The horizontal bounds of the simulation grid environment.
        height: The vertical bounds of the simulation grid environment.
        density: Target density ratio.

    Returns:
        A list of generated (x, y) coordinates.

    """
    coords = []
    for x in range(width):
        for y in range(height):
            if random.random() < density:
                coords.append((x, y))
    return coords


def generate_clustered(width: int, height: int, cluster_count: int, variance: float) -> list[tuple[int, int]]:
    """Create clusters of entities using a simple Gaussian spread.

    Args:
        width: The horizontal bounds of the simulation grid environment.
        height: The vertical bounds of the simulation grid environment.
        cluster_count: Number of clusters to generate.
        variance: The spread variance scale around each cluster center.

    Returns:
        A list of unique generated (x, y) coordinates.

    """
    coords = set()
    for _ in range(cluster_count):
        cx = random.randint(0, width - 1)
        cy = random.randint(0, height - 1)
        # Generate roughly 10-50 entities per cluster based on variance scale
        points_in_cluster = int(max(10, variance * 10))
        for _ in range(points_in_cluster):
            # Simple Gaussian spread around centroid
            px = int(random.gauss(cx, variance))
            py = int(random.gauss(cy, variance))
            if 0 <= px < width and 0 <= py < height:
                coords.add((px, py))
    return list(coords)


def generate_banded(width: int, height: int, band_count: int, orientation: str) -> list[tuple[int, int]]:
    """Place entities in dense lines/stripes across the grid.

    Args:
        width: The horizontal bounds of the simulation grid environment.
        height: The vertical bounds of the simulation grid environment.
        band_count: Number of bands to split the grid into.
        orientation: The orientation direction ('horizontal' or 'vertical').

    Returns:
        A list of generated (x, y) coordinates.

    """
    coords = []
    if orientation == "horizontal":
        band_spacing = height / max(1, band_count)
        for b in range(band_count):
            cy = int(b * band_spacing + band_spacing / 2)
            for x in range(width):
                if random.random() < 0.6:  # 60% dense along the band
                    coords.append((x, max(0, min(height - 1, cy + random.randint(-2, 2)))))
    else:
        band_spacing = width / max(1, band_count)
        for b in range(band_count):
            cx = int(b * band_spacing + band_spacing / 2)
            for y in range(height):
                if random.random() < 0.6:
                    coords.append((max(0, min(width - 1, cx + random.randint(-2, 2))), y))
    return coords
