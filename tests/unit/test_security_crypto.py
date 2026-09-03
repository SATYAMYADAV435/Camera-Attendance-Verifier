import pytest
from app.core.security import biometric_crypto, create_access_token, decode_access_token, get_password_hash, verify_password

def test_password_hashing():
    pwd = "SuperSecretPassword123!"
    hashed = get_password_hash(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_token_lifecycle():
    payload = {"sub": "USER-99", "role": "SECURITY_ADMIN", "custom_key": "val123"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "USER-99"
    assert decoded["role"] == "SECURITY_ADMIN"
    assert decoded["custom_key"] == "val123"

def test_biometric_aes256_encryption_decryption():
    original_vector = [0.123, -0.456, 0.789, 0.0, -0.001] * 100 # 500 dims
    encrypted_str = biometric_crypto.encrypt_vector(original_vector)
    
    assert isinstance(encrypted_str, str)
    assert len(encrypted_str) > 50
    assert encrypted_str != str(original_vector)

    decrypted_vector = biometric_crypto.decrypt_vector(encrypted_str)
    assert len(decrypted_vector) == len(original_vector)
    for orig, dec in zip(original_vector, decrypted_vector):
        assert abs(orig - dec) < 1e-5
