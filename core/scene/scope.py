"""Chặn sửa vượt phạm vi — cơ chế chính để giữ context (SPEC mục 4, FR-11).

Kiểm tra dựa trên KẾT QUẢ (so before/after theo id object), không dựa vào đường dẫn
trong patch, nên patch viết kiểu nào (index, move, replace cả mảng...) cũng không lách được.

Ví dụ: "bàn đen + 4 ghế nâu, chỉ đổi ghế sang xanh"
    scope = EditScope(targets={"chair_1"})
→ bàn đổi bất kỳ trường nào, hoặc số ghế đổi từ 4 sang 6, đều bị từ chối.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Trường cấp gốc được phép khác giữa 2 version (do store tự quản lý)
_MANAGED_KEYS = {"version", "parent_version", "created_at", "note"}


@dataclass(frozen=True)
class EditScope:
    targets: frozenset[str] = field(default_factory=frozenset)
    allow_qty: bool = False        # chỉ bật khi người dùng nói rõ số lượng
    allow_add: bool = False        # thêm object mới (id mới phải nằm trong targets)
    allow_remove: bool = False     # xoá object (id phải nằm trong targets)
    allow_room: bool = False       # sửa kích thước/ảnh phòng

    @staticmethod
    def of(*targets: str, **flags: bool) -> "EditScope":
        return EditScope(targets=frozenset(targets), **flags)


def _by_id(scene: dict) -> dict[str, dict]:
    return {o["id"]: o for o in scene.get("objects", []) if isinstance(o, dict) and "id" in o}


def check_scope(before: dict, after: dict, scope: EditScope) -> list[str]:
    v: list[str] = []
    for key in set(before) | set(after):
        if key in _MANAGED_KEYS or key in ("objects", "room"):
            continue
        if before.get(key) != after.get(key):
            v.append(f"không được sửa trường gốc '{key}'")
    if before.get("room") != after.get("room") and not scope.allow_room:
        v.append("không được sửa phòng (room) trong lần sửa này")

    b, a = _by_id(before), _by_id(after)
    for oid, ob in b.items():
        if oid not in a:
            if not (scope.allow_remove and oid in scope.targets):
                v.append(f"object '{oid}' bị xoá nhưng không được yêu cầu")
            continue
        oa = a[oid]
        if oid not in scope.targets:
            if oa != ob:
                changed = sorted(k for k in set(ob) | set(oa) if ob.get(k) != oa.get(k))
                v.append(f"object '{oid}' không được yêu cầu sửa nhưng bị đổi: {', '.join(changed)}")
            continue
        if ob.get("qty") != oa.get("qty") and not scope.allow_qty:
            v.append(f"object '{oid}': không được đổi số lượng {ob.get('qty')} → {oa.get('qty')} "
                     "khi người dùng không yêu cầu")
    for oid in a.keys() - b.keys():
        if not scope.allow_add:
            v.append(f"thêm object mới '{oid}' khi không được phép")
        elif oid not in scope.targets:
            v.append(f"object mới '{oid}' không nằm trong danh sách được sửa")
    return v
