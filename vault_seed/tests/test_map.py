from vault_seed.agents.map import map_products, map_users, _norm_ea, _to_int, _to_bool


def test_norm_ea_zero_pad():
    assert _norm_ea("1130") == "01130"
    assert _norm_ea("01130") == "01130"
    assert _norm_ea("1130.0") == "01130"
    assert _norm_ea("ABCDE") == "ABCDE"
    assert _norm_ea("") == ""
    assert _norm_ea("nan") == ""
    assert _norm_ea(None) == ""


def test_to_int():
    assert _to_int("12") == 12
    assert _to_int("12.0") == 12
    assert _to_int("") is None
    assert _to_int(None) is None
    assert _to_int("bad") is None


def test_to_bool():
    for v in ("true", "TRUE", "1", "yes", "y"):
        assert _to_bool(v) is True
    for v in ("false", "0", "no", "", None):
        assert _to_bool(v) is False


def test_map_products_dedupes_and_skips_blank():
    rows = [
        {"ea_code": "1130", "name": "A", "price": "100"},
        {"ea_code": "1130", "name": "dup", "price": "999"},
        {"ea_code": "", "name": "blank"},
        {"ea_code": "1200", "name": "B"},
    ]
    out, errors = map_products(rows)
    assert [r["ea_code"] for r in out] == ["01130", "01200"]
    assert out[0]["price"] == 100
    assert any("duplicate" in e for e in errors)
    assert any("missing ea_code" in e for e in errors)


def test_map_users_invalid_role_defaults_to_staff():
    rows = [
        {"name": "alice", "role": "admin"},
        {"name": "bob", "role": "owner"},
        {"name": "", "role": "staff"},
    ]
    out, errors = map_users(rows)
    assert [u["name"] for u in out] == ["alice", "bob"]
    assert out[1]["role"] == "staff"
    assert any("invalid role" in e for e in errors)
