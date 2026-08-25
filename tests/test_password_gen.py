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


def test_generate_security_answer():
    from core.password_gen import generate_security_answer, SECURITY_ANSWERS
    
    # Test maiden name question
    maiden_ans = [generate_security_answer("What is your mother's maiden name?") for _ in range(10)]
    assert any(a in SECURITY_ANSWERS["maiden"] for a in maiden_ans)
    assert len(set(maiden_ans)) > 1  # Verify randomness
    
    # Test pet question
    pet_ans = [generate_security_answer("What was your first pet's name?") for _ in range(10)]
    assert any(a in SECURITY_ANSWERS["pet"] for a in pet_ans)
    assert len(set(pet_ans)) > 1
    
    # Test city question
    city_ans = [generate_security_answer("In what city or town were you born?") for _ in range(10)]
    assert any(a in SECURITY_ANSWERS["city"] for a in city_ans)
    
    # Test school question
    school_ans = [generate_security_answer("What was the name of your primary school?") for _ in range(10)]
    assert any(a in SECURITY_ANSWERS["school"] for a in school_ans)
    
    # Test sports team question
    team_ans = [generate_security_answer("What is your favourite football team?") for _ in range(10)]
    assert any(a in SECURITY_ANSWERS["team"] for a in team_ans)

