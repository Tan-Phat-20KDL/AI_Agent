"""Database giai đoạn đầu = thư mục CSV (SRS mục 4, ràng buộc C-2).

Mọi code khác chỉ đọc/ghi qua module này, để sau đổi sang PostgreSQL
không phải sửa logic nghiệp vụ.

Quy ước: UTF-8 (chấp nhận BOM của Excel), dấu phẩy, dòng đầu là tên cột,
tiền là số nguyên VND, kích thước là mm, nhiều giá trị trong 1 ô ngăn bằng ';'.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from core.io import write_text_atomic

ASSET_STATUSES = ("pending", "approved", "rejected")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    style_tags: tuple[str, ...]
    width_mm: int
    depth_mm: int
    height_mm: int
    description: str = ""


@dataclass(frozen=True)
class Variant:
    variant_id: str
    sku: str
    color_name: str
    material_id: str
    price_vnd: int
    image_paths: tuple[str, ...]
    asset_glb: str
    asset_status: str
    tint_hex: str

    @property
    def is_usable(self) -> bool:
        """Chỉ asset đã duyệt mới được dùng cho khách (FR-04)."""
        return self.asset_status == "approved" and bool(self.asset_glb)


@dataclass(frozen=True)
class Material:
    material_id: str
    name: str
    group: str
    unit: str
    unit_price_vnd: int
    pbr_texture_dir: str


@dataclass(frozen=True)
class LaborRate:
    process: str
    unit: str
    unit_price_vnd: int


@dataclass(frozen=True)
class CsvIssue:
    file: str
    line: int  # số dòng trong file, dòng header = 1
    column: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} [{self.column}] {self.message}"


class CsvValidationError(Exception):
    def __init__(self, issues: list[CsvIssue]):
        self.issues = issues
        lines = "\n".join(f"  - {i}" for i in issues[:50])
        more = f"\n  ... và {len(issues) - 50} lỗi khác" if len(issues) > 50 else ""
        super().__init__(f"CSV không hợp lệ ({len(issues)} lỗi):\n{lines}{more}")


# ---------------------------------------------------------------- parse helpers

_Parser = Callable[[str], object]


def _req_str(v: str) -> str:
    if not v.strip():
        raise ValueError("bắt buộc, không được trống")
    return v.strip()


def _opt_str(v: str) -> str:
    return v.strip()


def _pos_int(v: str) -> int:
    v = v.strip().replace("_", "")
    if not re.fullmatch(r"\d+", v):
        raise ValueError(f"phải là số nguyên không âm, nhận '{v}'")
    n = int(v)
    return n


def _dim_mm(v: str) -> int:
    n = _pos_int(v)
    if n <= 0:
        raise ValueError("kích thước phải > 0 mm")
    return n


def _list(v: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in v.split(";") if x.strip())


def _status(v: str) -> str:
    v = v.strip() or "pending"
    if v not in ASSET_STATUSES:
        raise ValueError(f"phải là một trong {ASSET_STATUSES}, nhận '{v}'")
    return v


def _hex(v: str) -> str:
    v = v.strip()
    if v and not _HEX.match(v):
        raise ValueError(f"mã màu phải dạng #RRGGBB, nhận '{v}'")
    return v


def _decimal(v: str) -> Decimal:
    try:
        return Decimal(v.strip())
    except InvalidOperation:
        raise ValueError(f"phải là số, nhận '{v}'") from None


SCHEMAS: dict[str, dict[str, _Parser]] = {
    "products.csv": {
        "sku": _req_str,
        "name": _req_str,
        "category": _req_str,
        "style_tags": _list,
        "width_mm": _dim_mm,
        "depth_mm": _dim_mm,
        "height_mm": _dim_mm,
        "description": _opt_str,
    },
    "variants.csv": {
        "variant_id": _req_str,
        "sku": _req_str,
        "color_name": _req_str,
        "material_id": _opt_str,
        "price_vnd": _pos_int,
        "image_paths": _list,
        "asset_glb": _opt_str,
        "asset_status": _status,
        "tint_hex": _hex,
    },
    "materials.csv": {
        "material_id": _req_str,
        "name": _req_str,
        "group": _req_str,
        "unit": _req_str,
        "unit_price_vnd": _pos_int,
        "pbr_texture_dir": _opt_str,
    },
    "pricing_rules.csv": {
        "key": _req_str,
        "value": _decimal,
        "note": _opt_str,
    },
    "labor_rates.csv": {
        "process": _req_str,
        "unit": _req_str,
        "unit_price_vnd": _pos_int,
    },
}

REQUIRED_FILES = ("products.csv", "variants.csv", "pricing_rules.csv")
OPTIONAL_FILES = ("materials.csv", "labor_rates.csv")
REQUIRED_RULES = ("vat_pct",)


def _read_rows(path: Path, schema: dict[str, _Parser], issues: list[CsvIssue]) -> list[dict]:
    name = path.name
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [c for c in schema if c not in header]
    for c in missing:
        issues.append(CsvIssue(name, 1, c, "thiếu cột"))
    if missing:
        return []
    rows: list[dict] = []
    for line_no, raw in enumerate(reader, start=2):
        if not any((v or "").strip() for v in raw.values()):
            continue  # bỏ dòng trống
        row: dict = {}
        ok = True
        for col, parse in schema.items():
            try:
                row[col] = parse(raw.get(col) or "")
            except ValueError as e:
                issues.append(CsvIssue(name, line_no, col, str(e)))
                ok = False
        if ok:
            row["_line"] = line_no
            rows.append(row)
    return rows


def _unique(rows: list[dict], key: str, file: str, issues: list[CsvIssue]) -> None:
    seen: dict[str, int] = {}
    for r in rows:
        k = r[key]
        if k in seen:
            issues.append(CsvIssue(file, r["_line"], key, f"trùng mã '{k}' (đã có ở dòng {seen[k]})"))
        else:
            seen[k] = r["_line"]


def _strip_line(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "_line"}


@dataclass
class Catalog:
    data_dir: Path
    products: dict[str, Product]
    variants: dict[str, Variant]
    materials: dict[str, Material] = field(default_factory=dict)
    labor_rates: dict[str, LaborRate] = field(default_factory=dict)
    pricing_rules: dict[str, Decimal] = field(default_factory=dict)

    # ----------------------------------------------------------- tra cứu
    def product(self, sku: str) -> Product:
        try:
            return self.products[sku]
        except KeyError:
            raise KeyError(f"Không có SKU '{sku}' trong products.csv") from None

    def variant(self, variant_id: str) -> Variant:
        try:
            return self.variants[variant_id]
        except KeyError:
            raise KeyError(f"Không có biến thể '{variant_id}' trong variants.csv") from None

    def product_of(self, variant_id: str) -> Product:
        return self.product(self.variant(variant_id).sku)

    def variants_of(self, sku: str, usable_only: bool = False) -> list[Variant]:
        vs = [v for v in self.variants.values() if v.sku == sku]
        return [v for v in vs if v.is_usable] if usable_only else vs

    def usable_variants(self) -> list[Variant]:
        return [v for v in self.variants.values() if v.is_usable]

    def search(self, text: str, usable_only: bool = True, limit: int = 10) -> list[Variant]:
        """Tìm biến thể theo từ khoá (tên, nhóm, tag, màu). Dùng cho form và tool-call của LLM.

        Không bao giờ trả về biến thể chưa duyệt khi usable_only=True (FR-04).
        """
        tokens = [t for t in _norm(text).split() if t]
        scored: list[tuple[int, str, Variant]] = []
        pool = self.usable_variants() if usable_only else list(self.variants.values())
        for v in pool:
            p = self.products.get(v.sku)
            if p is None:
                continue
            hay = _norm(" ".join([v.variant_id, v.sku, v.color_name, p.name, p.category, *p.style_tags]))
            score = sum(1 for t in tokens if t in hay)
            if score or not tokens:
                scored.append((score, v.variant_id, v))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [v for _, _, v in scored[:limit]]

    def rule(self, key: str, default: Decimal | int | str | None = None) -> Decimal:
        if key in self.pricing_rules:
            return self.pricing_rules[key]
        if default is None:
            raise KeyError(f"Thiếu tham số '{key}' trong pricing_rules.csv")
        return Decimal(str(default))


def _norm(s: str) -> str:
    """Chữ thường + bỏ dấu tiếng Việt để tìm 'ghe' cũng ra 'ghế'."""
    import unicodedata

    s = s.lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def load_catalog(data_dir: str | Path) -> Catalog:
    """Đọc và kiểm tra toàn bộ CSV. Có lỗi → CsvValidationError liệt kê đúng dòng/cột,
    không nạp nửa chừng (FR-01)."""
    data_dir = Path(data_dir)
    issues: list[CsvIssue] = []
    tables: dict[str, list[dict]] = {}
    for name in REQUIRED_FILES + OPTIONAL_FILES:
        path = data_dir / name
        if not path.exists():
            if name in REQUIRED_FILES:
                issues.append(CsvIssue(name, 0, "-", "thiếu file"))
            tables[name] = []
            continue
        tables[name] = _read_rows(path, SCHEMAS[name], issues)

    _unique(tables["products.csv"], "sku", "products.csv", issues)
    _unique(tables["variants.csv"], "variant_id", "variants.csv", issues)
    _unique(tables["materials.csv"], "material_id", "materials.csv", issues)
    _unique(tables["pricing_rules.csv"], "key", "pricing_rules.csv", issues)

    skus = {r["sku"] for r in tables["products.csv"]}
    mats = {r["material_id"] for r in tables["materials.csv"]}
    has_materials = (data_dir / "materials.csv").exists()
    for r in tables["variants.csv"]:
        if r["sku"] not in skus:
            issues.append(CsvIssue("variants.csv", r["_line"], "sku", f"SKU '{r['sku']}' không có trong products.csv"))
        if r["material_id"] and has_materials and r["material_id"] not in mats:
            issues.append(
                CsvIssue("variants.csv", r["_line"], "material_id", f"'{r['material_id']}' không có trong materials.csv")
            )
        if r["asset_status"] == "approved" and not r["asset_glb"]:
            issues.append(CsvIssue("variants.csv", r["_line"], "asset_glb", "approved nhưng chưa có file GLB"))

    rule_keys = {r["key"] for r in tables["pricing_rules.csv"]}
    for k in REQUIRED_RULES:
        if (data_dir / "pricing_rules.csv").exists() and k not in rule_keys:
            issues.append(CsvIssue("pricing_rules.csv", 0, "key", f"thiếu tham số bắt buộc '{k}'"))

    if issues:
        raise CsvValidationError(issues)

    return Catalog(
        data_dir=data_dir,
        products={r["sku"]: Product(**_strip_line(r)) for r in tables["products.csv"]},
        variants={r["variant_id"]: Variant(**_strip_line(r)) for r in tables["variants.csv"]},
        materials={r["material_id"]: Material(**_strip_line(r)) for r in tables["materials.csv"]},
        labor_rates={r["process"]: LaborRate(**_strip_line(r)) for r in tables["labor_rates.csv"]},
        pricing_rules={r["key"]: r["value"] for r in tables["pricing_rules.csv"]},
    )


def set_variant_asset(data_dir: str | Path, variant_id: str, asset_glb: str | None = None,
                      asset_status: str | None = None) -> Variant:
    """Cập nhật cột asset của 1 biến thể (dùng bởi I1 và bước duyệt asset), ghi atomic.

    Giữ nguyên thứ tự cột/dòng và mọi ô khác của file.
    """
    if asset_status is not None and asset_status not in ASSET_STATUSES:
        raise ValueError(f"asset_status phải thuộc {ASSET_STATUSES}")
    path = Path(data_dir) / "variants.csv"
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    rows = list(reader)
    found = None
    for r in rows:
        if (r.get("variant_id") or "").strip() == variant_id:
            if asset_glb is not None:
                r["asset_glb"] = asset_glb
            if asset_status is not None:
                r["asset_status"] = asset_status
            found = r
    if found is None:
        raise KeyError(f"Không có biến thể '{variant_id}' trong variants.csv")
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    write_text_atomic(path, out.getvalue())
    # đọc lại qua validator để chắc file vẫn hợp lệ
    return load_catalog(data_dir).variant(variant_id)


__all__ = [
    "ASSET_STATUSES",
    "Catalog",
    "CsvIssue",
    "CsvValidationError",
    "LaborRate",
    "Material",
    "Product",
    "Variant",
    "load_catalog",
    "set_variant_asset",
]
