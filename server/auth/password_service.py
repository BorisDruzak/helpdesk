"""
Stage 10: Хеширование и проверка паролей UI пользователей.
Формат: pbkdf2_sha256$iterations$salt$hash (совместим с Django PBKDF2).
"""
import hashlib
import secrets
from typing import Tuple

PBKDF2_ITERATIONS = 260000
SALT_LENGTH = 12
HASH_LENGTH = 32  # SHA256 = 32 bytes
ALGORITHM = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """
    Хеширует пароль в формате pbkdf2_sha256$iterations$salt$hash.
    
    Args:
        password: исходный пароль
        
    Returns:
        Строка вида pbkdf2_sha256$260000$<salt>$<hex_hash>
    """
    salt = secrets.token_hex(SALT_LENGTH // 2)
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    h = raw.hex()
    return f"{ALGORITHM}${PBKDF2_ITERATIONS}${salt}${h}"


def verify_password(password: str, encoded: str) -> bool:
    """
    Проверяет пароль против сохранённого хеша.
    
    Args:
        password: введённый пароль
        encoded: строка из БД (pbkdf2_sha256$iterations$salt$hash)
        
    Returns:
        True если пароль совпадает
    """
    if not password or not encoded or "$" not in encoded:
        return False
    parts = encoded.split("$", 3)
    if len(parts) != 4 or parts[0] != ALGORITHM:
        return False
    try:
        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]
    except (ValueError, IndexError):
        return False
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return raw.hex() == expected_hex


def parse_encoded(encoded: str) -> Tuple[int, str, str]:
    """
    Разбирает сохранённый хеш на iterations, salt, hash.
    Для внутреннего использования (например, rehash с другими iterations).
    """
    parts = encoded.split("$", 3)
    if len(parts) != 4:
        raise ValueError("Invalid encoded password format")
    return int(parts[1]), parts[2], parts[3]
