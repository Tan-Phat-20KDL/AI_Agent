import pytest

from core.scene import PatchError, apply_patch


def test_basic_ops_do_not_mutate_input():
    doc = {"a": {"b": [1, 2, 3]}, "x": 1}
    out = apply_patch(doc, [
        {"op": "replace", "path": "/x", "value": 2},
        {"op": "add", "path": "/a/b/-", "value": 4},
        {"op": "remove", "path": "/a/b/0"},
        {"op": "copy", "from": "/x", "path": "/y"},
        {"op": "move", "from": "/y", "path": "/z"},
        {"op": "test", "path": "/z", "value": 2},
    ])
    assert out == {"a": {"b": [2, 3, 4]}, "x": 2, "z": 2}
    assert doc == {"a": {"b": [1, 2, 3]}, "x": 1}


def test_pointer_escapes():
    assert apply_patch({"a/b": 1, "m~n": 2}, [{"op": "replace", "path": "/a~1b", "value": 9},
                                             {"op": "remove", "path": "/m~0n"}]) == {"a/b": 9}


@pytest.mark.parametrize("patch", [
    [{"op": "replace", "path": "/missing", "value": 1}],
    [{"op": "remove", "path": "/a/b/9"}],
    [{"op": "test", "path": "/x", "value": 99}],
    [{"op": "explode", "path": "/x"}],
    [{"op": "add", "path": "x", "value": 1}],
    [{"op": "add", "path": "/a/b/01", "value": 1}],
])
def test_invalid(patch):
    with pytest.raises(PatchError):
        apply_patch({"a": {"b": [1]}, "x": 1}, patch)
