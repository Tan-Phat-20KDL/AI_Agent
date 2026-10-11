"""Báo giá cho sản phẩm có sẵn (FR-13, SRS mục 4) — code tất định, không dùng AI (C-5).

    Tổng = [Σ price_k·qty_k·(1 − discount) + delivery + install]·(1 + vat)
    install = install_pct × (tổng hàng sau chiết khấu)

Mọi tham số lấy từ pricing_rules.csv. Tiền là số nguyên VND, làm tròn half-up ở từng bước.
Object custom (hàng đặt) không tự tính giá — đưa vào danh sách cần báo giá tay.
Báo giá lưu kèm snapshot đơn giá, nên giá CSV đổi sau này không làm đổi báo giá cũ.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from core.io import write_bytes_atomic, write_json_atomic
from core.repository import Catalog

_RULE_DEFAULTS = {"discount_pct": 0, "delivery_fee_vnd": 0, "install_pct": 0}


def _vnd(x: Decimal) -> int:
    return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class QuoteLine:
    object_id: str
    variant_id: str
    sku: str
    name: str
    color: str
    qty: int
    unit_price_vnd: int
    amount_vnd: int


@dataclass
class Quote:
    scene_id: str
    scene_version: int
    lines: list[QuoteLine]
    subtotal_vnd: int
    discount_pct: str
    discount_vnd: int
    delivery_vnd: int
    install_pct: str
    install_vnd: int
    vat_pct: str
    vat_vnd: int
    total_vnd: int
    manual_items: list[str] = field(default_factory=list)  # object cần báo giá tay
    rules_snapshot: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["lines"] = [asdict(line) for line in self.lines]
        return d


def compute_quote(scene: dict, catalog: Catalog) -> Quote:
    lines: list[QuoteLine] = []
    manual: list[str] = []
    for o in scene.get("objects", []):
        if o.get("custom"):
            manual.append(o["id"])
            continue
        v = catalog.variant(o["variant_id"])
        p = catalog.product(v.sku)
        qty = int(o["qty"])
        lines.append(QuoteLine(o["id"], v.variant_id, p.sku, p.name, v.color_name, qty,
                               v.price_vnd, v.price_vnd * qty))

    rule = {k: catalog.rule(k, _RULE_DEFAULTS.get(k)) for k in ("vat_pct", *_RULE_DEFAULTS)}
    subtotal = sum(line.amount_vnd for line in lines)
    discount = _vnd(Decimal(subtotal) * rule["discount_pct"] / 100)
    after_discount = subtotal - discount
    install = _vnd(Decimal(after_discount) * rule["install_pct"] / 100)
    delivery = _vnd(rule["delivery_fee_vnd"]) if lines else 0
    before_vat = after_discount + delivery + install
    vat = _vnd(Decimal(before_vat) * rule["vat_pct"] / 100)
    return Quote(
        scene_id=scene["scene_id"],
        scene_version=int(scene.get("version", 0)),
        lines=lines,
        subtotal_vnd=subtotal,
        discount_pct=str(rule["discount_pct"]),
        discount_vnd=discount,
        delivery_vnd=delivery,
        install_pct=str(rule["install_pct"]),
        install_vnd=install,
        vat_pct=str(rule["vat_pct"]),
        vat_vnd=vat,
        total_vnd=before_vat + vat,
        manual_items=manual,
        rules_snapshot={k: str(v) for k, v in catalog.pricing_rules.items()},
    )


def quote_to_csv(q: Quote) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["Hạng mục", "Mã", "Màu", "SL", "Đơn giá (VND)", "Thành tiền (VND)"])
    for line in q.lines:
        w.writerow([line.name, line.variant_id, line.color, line.qty, line.unit_price_vnd, line.amount_vnd])
    w.writerow([])
    w.writerow(["Tổng hàng", "", "", "", "", q.subtotal_vnd])
    w.writerow([f"Chiết khấu {q.discount_pct}%", "", "", "", "", -q.discount_vnd])
    w.writerow(["Vận chuyển", "", "", "", "", q.delivery_vnd])
    w.writerow([f"Lắp đặt {q.install_pct}%", "", "", "", "", q.install_vnd])
    w.writerow([f"VAT {q.vat_pct}%", "", "", "", "", q.vat_vnd])
    w.writerow(["TỔNG CỘNG", "", "", "", "", q.total_vnd])
    for oid in q.manual_items:
        w.writerow([f"Cần báo giá tay: {oid}"])
    return out.getvalue()


def save_quote(q: Quote, root: str | Path) -> tuple[Path, Path]:
    """Lưu quotes/<scene_id>/v<N>.json và .csv (CSV có BOM để Excel đọc đúng tiếng Việt)."""
    base = Path(root) / q.scene_id / f"v{q.scene_version}"
    j = write_json_atomic(base.with_suffix(".json"), q.to_dict())
    c = write_bytes_atomic(base.with_suffix(".csv"), quote_to_csv(q).encode("utf-8-sig"))
    return j, c
