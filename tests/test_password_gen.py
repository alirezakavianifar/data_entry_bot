import string
from core.password_gen import generate_password, generate_username, ALLOWED_SPECIAL


def test_generate_password_structure():
    for _ in range(20):
        pwd = generate_password(length=14)
        assert len(pwd) == 14
        assert any(c in string.ascii_uppercase for c in pwd)
        assert any(c in string.ascii_lowercase for c in pwd)
        assert any(c in string.digits for c in pwd)
        assert any(c in ALLOWED_SPECIAL for c in pwd)


def test_generate_username():
    user = generate_username("Courtney", "Weaver", "2001")
    assert len(user) > 5
    assert "courtney" in user
    assert "01" in user
