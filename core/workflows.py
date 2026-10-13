"""Use-case W1/W2: ghép các phần core lại. Node ComfyUI, script, web sau này đều gọi qua đây.

Không ghi file — chỉ trả về scene mới; việc lưu do SceneStore làm, nên lỗi ở bất kỳ bước nào
đều không sinh version dở dang.
"""

from __future__ import annotations

from core.placement import find_collisions, place_missing
from core.repository import Catalog
from core.scene import EditScope, ScopeViolation, apply_patch, check_scope


def plan_edit(before: dict, patch: list[dict], scope: EditScope, catalog: Catalog) -> dict:
    """W2: áp patch, kiểm phạm vi, xếp lại riêng món cần xếp.

    Món trong phạm vi được xếp lại khi: đổi số lượng (4 → 6 ghế phải giãn ra), hoặc đổi sang
    biến thể khác kích thước làm chồng/lòi khỏi phòng. Món ngoài phạm vi không bao giờ bị dời.
    """
    after = apply_patch(before, patch)
    violations = check_scope(before, after, scope)
    if violations:
        raise ScopeViolation(violations)
    old_qty = {o["id"]: o["qty"] for o in before["objects"]}
    reset = {o["id"] for o in after["objects"]
             if o["id"] in scope.targets and old_qty.get(o["id"]) not in (None, o["qty"])}
    reset |= find_collisions(after, catalog) & scope.targets
    return place_missing(after, catalog, reset_ids=reset)
