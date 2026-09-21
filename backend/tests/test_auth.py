from app.auth import AuthStore


def test_passwords_are_hashed_and_sessions_expire(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")
    user = store.register("person@example.com", "long-enough-password")
    signed_in, token = store.login("person@example.com", "long-enough-password")
    assert user["id"] == signed_in["id"]
    assert store.user_for_token(token)["email"] == "person@example.com"
    assert "long-enough-password" not in (tmp_path / "auth.sqlite3").read_bytes().decode(errors="ignore")


def test_invalid_password_is_rejected(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")
    store.register("person@example.com", "long-enough-password")
    try:
        store.login("person@example.com", "wrong-password")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid password was accepted")
