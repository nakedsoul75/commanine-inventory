from vault_seed.agents.diff import diff_products, diff_users


def test_diff_products_classifies_rows():
    seed = [
        {"ea_code": "01130", "code": "C1", "name": "A", "price": 100, "is_excluded": False},
        {"ea_code": "01131", "code": "C2", "name": "B", "price": 200, "is_excluded": False},
        {"ea_code": "01200", "code": "C3", "name": "C", "price": 300, "is_excluded": False},
    ]
    remote = [
        # unchanged
        {"ea_code": "01130", "code": "C1", "name": "A", "price": 100, "is_excluded": False},
        # changed (price differs)
        {"ea_code": "01131", "code": "C2", "name": "B", "price": 999, "is_excluded": False},
    ]
    inserts, updates, unchanged = diff_products(seed, remote)
    assert [r["ea_code"] for r in inserts] == ["01200"]
    assert [r["ea_code"] for r in updates] == ["01131"]
    assert unchanged == 1


def test_diff_users_only_role_triggers_update():
    seed = [
        {"name": "alice", "role": "admin"},
        {"name": "bob", "role": "staff"},
        {"name": "carol", "role": "staff"},
    ]
    remote = [
        {"name": "alice", "role": "staff"},  # role changed -> update
        {"name": "bob", "role": "staff"},    # unchanged
    ]
    inserts, updates, unchanged = diff_users(seed, remote)
    assert [u["name"] for u in inserts] == ["carol"]
    assert [u["name"] for u in updates] == ["alice"]
    assert unchanged == 1


def test_diff_products_empty_remote_all_inserts():
    seed = [{"ea_code": "01130", "name": "A", "code": None, "price": None, "is_excluded": False}]
    inserts, updates, unchanged = diff_products(seed, [])
    assert len(inserts) == 1
    assert len(updates) == 0
    assert unchanged == 0
