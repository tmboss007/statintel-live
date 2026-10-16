import time
import functools
import threading
from typing import Any, Callable, Optional

_lock = threading.Lock()
_cache_store: dict[str, tuple[float, Any]] = {}

def get_cache(key: str) -> Optional[Any]:
    with _lock:
        item = _cache_store.get(key)
        if not item:
            return None
        expires_at, val = item
        if time.time() > expires_at:
            del _cache_store[key]
            return None
        return val

def set_cache(key: str, val: Any, ttl_seconds: int = 60):
    with _lock:
        _cache_store[key] = (time.time() + ttl_seconds, val)

def invalidate_cache(prefix: Optional[str] = None):
    with _lock:
        if not prefix:
            _cache_store.clear()
        else:
            keys_to_del = [k for k in _cache_store if k.startswith(prefix)]
            for k in keys_to_del:
                del _cache_store[k]

def cached(prefix: str, ttl_seconds: int = 60):
    """Decorator to cache function returns for sub-10ms response times."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Create a string key from args/kwargs that can be represented
            arg_str = "_".join(str(a) for a in args if not hasattr(a, "execute"))
            kw_str = "_".join(f"{k}:{v}" for k, v in sorted(kwargs.items()) if not hasattr(v, "execute"))
            cache_key = f"{prefix}:{fn.__name__}:{arg_str}:{kw_str}"
            
            cached_val = get_cache(cache_key)
            if cached_val is not None:
                return cached_val
            
            result = fn(*args, **kwargs)
            set_cache(cache_key, result, ttl_seconds=ttl_seconds)
            return result
        return wrapper
    return decorator
