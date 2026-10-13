"""Đặt đồ tự động lên sàn: bàn giữa phòng, ghế xếp quanh bàn, không chồng, không xuyên tường.

Mỗi object mang sẵn kích thước: "dims_mm": [rộng x, sâu z, cao y].

Nguyên tắc giữ context: chỉ thêm vị trí cho instance CÒN THIẾU (len(instances) < qty);
instance đã có vị trí không bao giờ bị dời. Va chạm kiểm tra bằng hình chữ nhật
chiếu xuống sàn (AABB trên mặt x-z), góc quay làm tròn về bội số 90°.

Chiến lược theo trường "placement" của object:
- center        : gần tâm phòng nhất
- against_wall  : sát tường sau → trái → phải → trước, mặt quay vào phòng
- free          : như center
- around:<id>   : xếp quanh object <id> (vd ghế quanh bàn), mặt quay vào nó
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from .._util import snap_rotation


class PlacementError(RuntimeError):
    pass


@dataclass(frozen=True)
class Rect:
    cx: float
    cz: float
    w: float  # kích thước theo x
    d: float  # kích thước theo z

    @property
    def x0(self) -> float:
        return self.cx - self.w / 2

    @property
    def x1(self) -> float:
        return self.cx + self.w / 2

    @property
    def z0(self) -> float:
        return self.cz - self.d / 2

    @property
    def z1(self) -> float:
        return self.cz + self.d / 2

    def overlaps(self, o: "Rect", gap: float = 0.0) -> bool:
        return not (self.x1 + gap <= o.x0 or o.x1 + gap <= self.x0 or
                    self.z1 + gap <= o.z0 or o.z1 + gap <= self.z0)

    def inside(self, room_w: float, room_d: float, margin: float = 0.0) -> bool:
        eps = 1e-6
        return (self.x0 >= margin - eps and self.z0 >= margin - eps and
                self.x1 <= room_w - margin + eps and self.z1 <= room_d - margin + eps)


def footprint(width_mm: float, depth_mm: float, rotation_deg: float) -> tuple[float, float]:
    r = snap_rotation(rotation_deg)
    return (depth_mm, width_mm) if r in (90, 270) else (width_mm, depth_mm)


def _dims(obj: dict) -> tuple[int, int]:
    try:
        w, d = obj["dims_mm"][:2]
    except (KeyError, TypeError, ValueError):
        raise PlacementError(f"object '{obj.get('id')}' thiếu dims_mm [rộng, sâu, cao]") from None
    return int(w), int(d)


def instance_rects(scene: dict) -> list[tuple[str, int, Rect]]:
    out = []
    for o in scene.get("objects", []):
        w, d = _dims(o)
        for i, it in enumerate(o.get("instances", [])):
            fw, fd = footprint(w, d, it.get("rotation_deg", 0))
            x, z = it["position_mm"]
            out.append((o["id"], i, Rect(x, z, fw, fd)))
    return out


def find_collisions(scene: dict, gap_mm: float = 50) -> set[str]:
    """Id các object đang chồng nhau hoặc lòi ra ngoài phòng (dùng sau W2 đổi biến thể khác kích thước)."""
    W, D = scene["room"]["width_mm"], scene["room"]["depth_mm"]
    rects = instance_rects(scene)
    bad: set[str] = set()
    for i, (oid, _, r) in enumerate(rects):
        if not r.inside(W, D):
            bad.add(oid)
        for oid2, _, r2 in rects[i + 1:]:
            if r.overlaps(r2, gap_mm - 1):  # -1: dung sai làm tròn mm
                bad.update((oid, oid2))
    return bad


def _order(objects: list[dict]) -> list[dict]:
    """Object 'around:X' phải đặt sau X."""
    placed: list[dict] = []
    pending = list(objects)
    ids_done: set[str] = set()
    while pending:
        progress = False
        for o in list(pending):
            p = o.get("placement", "center")
            dep = p.split(":", 1)[1] if p.startswith("around:") else None
            if dep is None or dep in ids_done:
                placed.append(o)
                ids_done.add(o["id"])
                pending.remove(o)
                progress = True
        if not progress:
            raise PlacementError("placement 'around' bị vòng lặp: " + ", ".join(o["id"] for o in pending))
    return placed


def _center_candidates(room_w, room_d, w, d, step):
    cands = []
    nx = int((room_w - w) // step) + 1
    nz = int((room_d - d) // step) + 1
    if nx <= 0 or nz <= 0:
        return cands
    for i in range(nx):
        for j in range(nz):
            cx = w / 2 + i * step
            cz = d / 2 + j * step
            cands.append((math.hypot(cx - room_w / 2, cz - room_d / 2), cx, cz))
    cands.sort()
    return [(cx, cz) for _, cx, cz in cands]


def _wall_candidates(room_w, room_d, w, d, step, wall_gap):
    """(cx, cz, rotation) dọc 4 tường; mặt trước quay vào phòng."""
    out = []
    # tường sau z=0, mặt nhìn +z → rot 0
    for cx in _along(room_w, w, step):
        out.append((cx, wall_gap + d / 2, 0))
    # tường trái x=0, nhìn +x → rot 90 (footprint xoay: rộng theo z)
    for cz in _along(room_d, w, step):
        out.append((wall_gap + d / 2, cz, 90))
    # tường phải x=W, nhìn -x → rot 270
    for cz in _along(room_d, w, step):
        out.append((room_w - wall_gap - d / 2, cz, 270))
    # tường trước z=D, nhìn -z → rot 180
    for cx in _along(room_w, w, step):
        out.append((cx, room_d - wall_gap - d / 2, 180))
    return out


def _along(length, size, step):
    """Vị trí tâm dọc 1 cạnh, ưu tiên giữa cạnh rồi lan ra hai bên."""
    n = int((length - size) // step) + 1
    if n <= 0:
        return []
    pos = [size / 2 + i * step for i in range(n)]
    mid = length / 2
    return sorted(pos, key=lambda c: (abs(c - mid), c))


def _around_slots(target: Rect, cw: float, cd: float, qty: int, gap: float):
    """Chia ghế vào các cạnh của bàn: 2 cạnh dài trước (chia đều), rồi 2 cạnh ngắn."""
    long_x = target.w >= target.d
    # (tên cạnh, chiều dài cạnh, rotation)
    if long_x:
        sides = [("south", target.w, 180), ("north", target.w, 0), ("east", target.d, 270), ("west", target.d, 90)]
    else:
        sides = [("east", target.d, 270), ("west", target.d, 90), ("south", target.w, 180), ("north", target.w, 0)]
    cap = {name: max(0, int((length + gap) // (cw + gap))) for name, length, _ in sides}
    counts = {name: 0 for name, _, _ in sides}
    remaining = qty
    for group in (sides[:2], sides[2:]):
        while remaining > 0 and any(counts[n] < cap[n] for n, _, _ in group):
            for n, _, _ in group:
                if remaining > 0 and counts[n] < cap[n]:
                    counts[n] += 1
                    remaining -= 1

    def slots_for(name, length, rot, n):
        res = []
        for k in range(n):
            off = -length / 2 + (k + 0.5) * length / n
            if name == "south":
                res.append((target.cx + off, target.z1 + gap + cd / 2, rot))
            elif name == "north":
                res.append((target.cx + off, target.z0 - gap - cd / 2, rot))
            elif name == "east":
                res.append((target.x1 + gap + cd / 2, target.cz + off, rot))
            else:
                res.append((target.x0 - gap - cd / 2, target.cz + off, rot))
        return res

    preferred = [s for name, length, rot in sides for s in slots_for(name, length, rot, counts[name])]
    fallback = [s for name, length, rot in sides for s in slots_for(name, length, rot, cap[name])]
    return preferred + fallback


def place_missing(scene: dict, gap_mm: float = 50, wall_gap_mm: float = 20,
                  step_mm: float = 50, reset_ids: set[str] | frozenset[str] = frozenset()) -> dict:
    """Trả về scene MỚI đã có đủ vị trí cho mọi instance; không sửa scene đầu vào.

    reset_ids: object được phép xếp lại TOÀN BỘ (vd người dùng đổi số ghế 4 → 6 thì 4 ghế cũ
    phải giãn ra). Chỉ truyền id nằm trong phạm vi sửa; object khác luôn giữ nguyên vị trí.
    """
    s = copy.deepcopy(scene)
    for o in s["objects"]:
        if o["id"] in reset_ids:
            o["instances"] = []
    room_w, room_d = s["room"]["width_mm"], s["room"]["depth_mm"]
    occupied: list[Rect] = [r for _, _, r in instance_rects(s)]
    by_id = {o["id"]: o for o in s["objects"]}

    def fits(r: Rect) -> bool:
        return r.inside(room_w, room_d) and not any(r.overlaps(o, gap_mm) for o in occupied)

    for obj in _order(s["objects"]):
        inst = obj.setdefault("instances", [])
        need = obj["qty"] - len(inst)
        if need <= 0:
            continue
        w, d = _dims(obj)
        mode = obj.get("placement", "center")

        if mode.startswith("around:"):
            tgt = by_id[mode.split(":", 1)[1]]
            if not tgt.get("instances"):
                raise PlacementError(f"'{obj['id']}' xếp quanh '{tgt['id']}' nhưng '{tgt['id']}' chưa có vị trí")
            tw, td = _dims(tgt)
            t0 = tgt["instances"][0]
            fw, fd = footprint(tw, td, t0.get("rotation_deg", 0))
            target = Rect(t0["position_mm"][0], t0["position_mm"][1], fw, fd)
            cands = _around_slots(target, w, d, obj["qty"], gap_mm)
        elif mode == "against_wall":
            cands = _wall_candidates(room_w, room_d, w, d, step_mm, wall_gap_mm)
        else:
            cands = [(cx, cz, 0) for cx, cz in _center_candidates(room_w, room_d, w, d, step_mm)]
            cands += [(cx, cz, 90) for cx, cz in _center_candidates(room_w, room_d, d, w, step_mm)]

        for cx, cz, rot in cands:
            if need == 0:
                break
            cx, cz = round(cx), round(cz)  # lưu mm nguyên, kiểm tra đúng giá trị sẽ lưu
            fw, fd = footprint(w, d, rot)
            r = Rect(cx, cz, fw, fd)
            if fits(r):
                inst.append({"position_mm": [cx, cz], "rotation_deg": rot})
                occupied.append(r)
                need -= 1
        if need > 0:
            raise PlacementError(
                f"Không đủ chỗ đặt '{obj['id']}': còn thiếu {need}/{obj['qty']} "
                f"(phòng {room_w}×{room_d} mm). Giảm số lượng hoặc đặt tay.")
    return s
