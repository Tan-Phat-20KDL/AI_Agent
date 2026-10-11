import pytest

from core.repository import CsvValidationError, load_catalog, set_variant_asset


def test_load_sample(catalog):
    assert catalog.product("TB01").width_mm == 1600
    assert catalog.variant("CH01-BRN").image_paths == ("img/CH01-BRN-1.jpg", "img/CH01-BRN-2.jpg")
    assert catalog.rule("vat_pct") == 10


def test_unapproved_not_searchable(catalog):
    ids = {v.variant_id for v in catalog.search("ban an")}
    assert "TB01-BLK" in ids
    assert "TB01-WAL" not in ids  # pending
    assert "TV01-WHT" not in {v.variant_id for v in catalog.search("ke tivi")}  # rejected


def test_search_without_accents(catalog):
    assert catalog.search("ghe xanh")[0].variant_id == "CH01-GRN"


def test_error_reports_line_and_column(data_dir):
    p = data_dir / "products.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("1600,900,750", "1600,abc,750"), encoding="utf-8")
    with pytest.raises(CsvValidationError) as e:
        load_catalog(data_dir)
    issue = e.value.issues[0]
    assert (issue.file, issue.line, issue.column) == ("products.csv", 2, "depth_mm")


def test_cross_file_reference(data_dir):
    p = data_dir / "variants.csv"
    p.write_text(p.read_text(encoding="utf-8") + "X-1,NOPE,Đỏ,,100,,,pending,\n", encoding="utf-8")
    with pytest.raises(CsvValidationError) as e:
        load_catalog(data_dir)
    assert any(i.column == "sku" and "NOPE" in i.message for i in e.value.issues)


def test_duplicate_id(data_dir):
    p = data_dir / "products.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
    with pytest.raises(CsvValidationError) as e:
        load_catalog(data_dir)
    assert any("trùng" in i.message for i in e.value.issues)


def test_set_variant_asset_roundtrip(data_dir):
    v = set_variant_asset(data_dir, "TB01-WAL", asset_glb="assets/TB01/WAL.glb", asset_status="approved")
    assert v.is_usable
    # các dòng khác giữ nguyên
    assert load_catalog(data_dir).variant("CH01-GRN").tint_hex == "#4A5D4F"


def test_approved_without_glb_rejected(data_dir):
    with pytest.raises(CsvValidationError):
        set_variant_asset(data_dir, "TV01-WHT", asset_status="approved")
