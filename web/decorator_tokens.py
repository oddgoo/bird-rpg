import secrets
import time
import threading

_tokens = {}  # token_str -> {user_id, entity_type, entity_id, expires_at}
_lock = threading.Lock()

TOKEN_EXPIRY_SECONDS = 3600  # 1 hour


def create_token(user_id, entity_type, entity_id):
    """Generate a token tied to a user and entity. Returns the token string."""
    _cleanup()
    token = secrets.token_urlsafe(32)
    with _lock:
        _tokens[token] = {
            "user_id": str(user_id),
            "entity_type": entity_type,  # "bird", "plant", or "nest"
            "entity_id": entity_id,       # bird/plant DB id, or user_id for nest
            "expires_at": time.time() + TOKEN_EXPIRY_SECONDS,
        }
    return token


def validate_token(token):
    """Returns token data dict if valid, None if expired/missing."""
    _cleanup()
    with _lock:
        data = _tokens.get(token)
        if data and data["expires_at"] > time.time():
            return dict(data)
    return None


def revoke_token(token):
    """Remove a token."""
    with _lock:
        _tokens.pop(token, None)


def _cleanup():
    """Remove expired tokens."""
    now = time.time()
    with _lock:
        expired = [k for k, v in _tokens.items() if v["expires_at"] <= now]
        for k in expired:
            del _tokens[k]
