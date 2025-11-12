"""Tests for encryption utilities."""

import pytest
from src.utils.encryption import encrypt_api_key, decrypt_api_key


def test_encrypt_api_key():
    """Test encrypting an API key."""
    api_key = "test-api-key-12345"

    encrypted = encrypt_api_key(api_key)

    assert encrypted is not None
    assert encrypted != api_key
    assert len(encrypted) > len(api_key)


def test_decrypt_api_key():
    """Test decrypting an API key."""
    api_key = "test-api-key-12345"

    encrypted = encrypt_api_key(api_key)
    decrypted = decrypt_api_key(encrypted)

    assert decrypted == api_key


def test_encrypt_decrypt_roundtrip():
    """Test that encryption/decryption roundtrip works correctly."""
    original_keys = [
        "short",
        "medium-length-key-123",
        "very-long-api-key-with-special-chars-!@#$%^&*()",
        "12345-67890-ABCDE-FGHIJ",
    ]

    for original in original_keys:
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original


def test_encrypt_empty_string():
    """Test encrypting empty string."""
    encrypted = encrypt_api_key("")
    decrypted = decrypt_api_key(encrypted)

    assert decrypted == ""


def test_decrypt_invalid_data():
    """Test decrypting invalid data raises error."""
    with pytest.raises(Exception):
        decrypt_api_key("invalid-encrypted-data")


def test_encryption_produces_different_outputs():
    """Test that encrypting the same key twice produces different outputs (due to IV)."""
    api_key = "test-api-key"

    encrypted1 = encrypt_api_key(api_key)
    encrypted2 = encrypt_api_key(api_key)

    # Encrypted values should be different (different IVs)
    assert encrypted1 != encrypted2

    # But both should decrypt to the same value
    assert decrypt_api_key(encrypted1) == api_key
    assert decrypt_api_key(encrypted2) == api_key


def test_encrypt_none_returns_empty_string():
    """Test that encrypting None returns empty string (graceful handling)."""
    assert encrypt_api_key(None) == ""


def test_decrypt_none_returns_empty_string():
    """Test that decrypting None returns empty string (graceful handling)."""
    assert decrypt_api_key(None) == ""
