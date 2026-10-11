from __future__ import annotations


def snap_rotation(deg: float) -> int:
    """Làm tròn góc quay về 0/90/180/270."""
    return int(round((deg % 360) / 90.0)) % 4 * 90
