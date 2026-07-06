import random
from typing import Any

from phids.api.schemas import BandedPlacement, ClusteredPlacement, PlacementStrategy, UniformPlacement


def generate_uniform(width: int, height: int, density: float) -> list[tuple[int, int]]:
    """Randomly scatter entities across the grid based on density."""
    coords = []
    for x in range(width):
        for y in range(height):
            if random.random() < density:
                coords.append((x, y))
    return coords


def generate_clustered(width: int, height: int, cluster_count: int, variance: float) -> list[tuple[int, int]]:
    """Create clusters of entities using a simple Gaussian spread."""
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
    """Place entities in dense lines/stripes across the grid."""
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


def apply_placement_strategy(width: int, height: int, strategy: PlacementStrategy | Any) -> list[tuple[int, int]]:
    """Resolve a specific PlacementStrategy into explicit (x, y) coordinates."""
    if isinstance(strategy, UniformPlacement) or getattr(strategy, "type", "") == "uniform":
        return generate_uniform(width, height, getattr(strategy, "density", 0.1))
    elif isinstance(strategy, ClusteredPlacement) or getattr(strategy, "type", "") == "clustered":
        return generate_clustered(
            width, height, getattr(strategy, "cluster_count", 1), getattr(strategy, "variance", 1.0)
        )
    elif isinstance(strategy, BandedPlacement) or getattr(strategy, "type", "") == "banded":
        return generate_banded(
            width, height, getattr(strategy, "band_count", 1), getattr(strategy, "orientation", "horizontal")
        )
    return []
