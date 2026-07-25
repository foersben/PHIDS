"""Tests for spatial placement generation functions."""

from phids.engine.core.placement import generate_banded, generate_clustered, generate_uniform


def test_generate_uniform() -> None:
    """Test uniform entity placement."""
    coords = generate_uniform(10, 10, 0.5)
    # Should generate roughly 50 points (expected value is 50, but it's random)
    # We just check bounds
    assert isinstance(coords, list)
    for x, y in coords:
        assert 0 <= x < 10
        assert 0 <= y < 10


def test_generate_clustered() -> None:
    """Test clustered entity placement."""
    coords = generate_clustered(20, 20, cluster_count=2, variance=1.5)
    assert isinstance(coords, list)
    for x, y in coords:
        assert 0 <= x < 20
        assert 0 <= y < 20
    # Length should be > 0
    assert len(coords) > 0


def test_generate_banded_horizontal() -> None:
    """Test horizontal banded entity placement."""
    coords = generate_banded(20, 20, band_count=2, orientation="horizontal")
    assert isinstance(coords, list)
    for x, y in coords:
        assert 0 <= x < 20
        assert 0 <= y < 20
    assert len(coords) > 0


def test_generate_banded_vertical() -> None:
    """Test vertical banded entity placement."""
    coords = generate_banded(20, 20, band_count=2, orientation="vertical")
    assert isinstance(coords, list)
    for x, y in coords:
        assert 0 <= x < 20
        assert 0 <= y < 20
    assert len(coords) > 0
