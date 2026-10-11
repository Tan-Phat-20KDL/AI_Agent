"""Dựng hộp phòng 3D từ 1 ảnh — chế độ A (FR-06).

Đầu vào là output của MoGe-2 (chạy trên GPU, ngoài module này):
  points : (H, W, 3) hoặc (N, 3), mét, toạ độ camera OpenCV (x phải, y xuống, z tới trước)
  floor_mask : mask sàn (từ SAM 3, prompt "floor")
Module này chỉ dùng numpy nên test được trên laptop với dữ liệu giả lập.

Giới hạn đã biết: chiều rộng/sâu lấy từ phần sàn NHÌN THẤY trong ảnh nên có thể nhỏ hơn
phòng thật → cho phép hiệu chỉnh bằng 1 kích thước đo tay (calibration).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def fit_plane_ransac(points: np.ndarray, threshold: float = 0.02, iterations: int = 300,
                     seed: int = 0) -> tuple[np.ndarray, float, np.ndarray]:
    """Fit mặt phẳng n·p + d = 0 bền với nhiễu. Trả (n đơn vị, d, mask inlier)."""
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    pts = pts[np.isfinite(pts).all(axis=1)]
    if len(pts) < 3:
        raise ValueError("cần ít nhất 3 điểm để fit mặt phẳng")
    rng = np.random.default_rng(seed)
    best_mask, best_count = None, -1
    for _ in range(iterations):
        a, b, c = pts[rng.choice(len(pts), 3, replace=False)]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n = n / norm
        d = -float(n @ a)
        mask = np.abs(pts @ n + d) < threshold
        cnt = int(mask.sum())
        if cnt > best_count:
            best_mask, best_count = mask, cnt
    if best_mask is None:
        raise ValueError("không fit được mặt phẳng (điểm thẳng hàng?)")
    inl = pts[best_mask]
    centroid = inl.mean(axis=0)
    _, _, vt = np.linalg.svd(inl - centroid)  # tinh chỉnh bằng bình phương tối thiểu
    n = vt[-1] / np.linalg.norm(vt[-1])
    d = -float(n @ centroid)
    mask = np.abs(pts @ n + d) < threshold
    return n, d, mask


@dataclass(frozen=True)
class RoomEstimate:
    width_mm: int
    depth_mm: int
    height_mm: int
    camera_height_mm: int
    rotation: np.ndarray      # 3x3: toạ độ camera → toạ độ phòng (y lên)
    origin: np.ndarray        # điểm trên sàn ngay dưới camera, toạ độ camera
    offset_mm: tuple[int, int]  # dịch để góc phòng ở (0, 0): x_room = x + ox, z_room = z + oz
    scale: float              # hệ số hiệu chỉnh đã áp
    floor_inlier_ratio: float

    def to_room(self, pts_cam: np.ndarray) -> np.ndarray:
        """Đổi điểm từ toạ độ camera (mét) sang toạ độ phòng (mm, góc phòng là gốc)."""
        p = (np.asarray(pts_cam).reshape(-1, 3) - self.origin) @ self.rotation.T * self.scale * 1000.0
        p[:, 0] += self.offset_mm[0]
        p[:, 2] += self.offset_mm[1]
        return p


def estimate_room(points: np.ndarray, floor_mask: np.ndarray | None = None,
                  calibration: tuple[float, float] | None = None,
                  default_height_mm: int = 2700, pct: float = 2.0) -> RoomEstimate:
    """Ước lượng kích thước phòng.

    calibration = (giá_trị_đo_trên_mô_hình_mm, giá_trị_thật_mm), vd chiều cao trần đo tay.
    Thường dùng: chạy 1 lần không calibration → lấy height_mm → so với thước đo → chạy lại.
    """
    pts = np.asarray(points, dtype=np.float64)
    if floor_mask is not None:
        floor = pts[np.asarray(floor_mask, dtype=bool)]
    else:
        floor = pts.reshape(-1, 3)
    floor = floor.reshape(-1, 3)
    floor = floor[np.isfinite(floor).all(axis=1)]
    allp = pts.reshape(-1, 3)
    allp = allp[np.isfinite(allp).all(axis=1)]

    n, d, inl = fit_plane_ransac(floor)
    if d < 0:  # pháp tuyến phải hướng về phía camera (lên trên)
        n, d = -n, -d
    up = n
    fwd = np.array([0.0, 0.0, 1.0]) - up * up[2]  # trục nhìn của camera chiếu xuống sàn
    if np.linalg.norm(fwd) < 1e-6:
        raise ValueError("camera nhìn thẳng xuống sàn — không xác định được hướng phòng")
    fwd /= np.linalg.norm(fwd)
    right = np.cross(up, fwd)  # x = y × z (hệ tay phải, giống three.js)
    rot = np.stack([right, up, fwd])  # các hàng là trục phòng
    origin = -d * up  # điểm sàn ngay dưới camera

    scale = 1.0
    if calibration:
        measured, real = calibration
        if measured <= 0 or real <= 0:
            raise ValueError("calibration phải dương")
        scale = real / measured

    def to_room_m(p):
        return (p - origin) @ rot.T * scale

    f = to_room_m(floor[inl])
    a = to_room_m(allp)
    x0, x1 = np.percentile(f[:, 0], [pct, 100 - pct])
    z0, z1 = np.percentile(f[:, 2], [pct, 100 - pct])
    h = float(np.percentile(a[:, 1], 100 - pct))
    # Trần thường không lọt khung ảnh: điểm cao nhất < 2 m nghĩa là chưa thấy trần → dùng mặc định
    height_mm = int(round(h * 1000)) if h * 1000 > 2000 else default_height_mm
    return RoomEstimate(
        width_mm=int(round((x1 - x0) * 1000)),
        depth_mm=int(round((z1 - z0) * 1000)),
        height_mm=height_mm,
        camera_height_mm=int(round(d * scale * 1000)),
        rotation=rot,
        origin=origin,
        offset_mm=(int(round(-x0 * 1000)), int(round(-z0 * 1000))),
        scale=scale,
        floor_inlier_ratio=float(inl.mean()),
    )


def build_room_mesh(width_mm: int, depth_mm: int, height_mm: int, open_front: bool = True):
    """Hộp phòng (mét): sàn + tường sau/trái/phải (+ tường trước nếu open_front=False).

    Mặt quay vào trong phòng. Texture chiếu từ ảnh gắn sau ở bước GPU.
    """
    import trimesh

    W, D, H = width_mm / 1000.0, depth_mm / 1000.0, height_mm / 1000.0
    # mỗi quad: 4 đỉnh theo thứ tự sao cho pháp tuyến hướng vào trong
    quads = {
        "floor": [(0, 0, 0), (0, 0, D), (W, 0, D), (W, 0, 0)],
        "wall_back": [(0, 0, 0), (W, 0, 0), (W, H, 0), (0, H, 0)],
        "wall_left": [(0, 0, D), (0, 0, 0), (0, H, 0), (0, H, D)],
        "wall_right": [(W, 0, 0), (W, 0, D), (W, H, D), (W, H, 0)],
    }
    if not open_front:
        quads["wall_front"] = [(W, 0, D), (0, 0, D), (0, H, D), (W, H, D)]
    parts = {}
    for name, q in quads.items():
        v = np.array(q, dtype=np.float64)
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        parts[name] = trimesh.Trimesh(vertices=v, faces=faces, process=False)
    return parts
