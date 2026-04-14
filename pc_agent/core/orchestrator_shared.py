from loguru import logger as _logger


def _decode_mojibake_once(text: str) -> str:
    if not isinstance(text, str):
        return text
    if not any(marker in text for marker in ("Гђ", "Г‘", "Гў", "в‚¬", "в„ў")):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text


class _MojibakeFixingLogger:
    def __init__(self, base_logger):
        self._base_logger = base_logger

    def __getattr__(self, name):
        attr = getattr(self._base_logger, name)
        if not callable(attr):
            return attr

        def wrapper(*args, **kwargs):
            if args and isinstance(args[0], str):
                args = (_decode_mojibake_once(args[0]), *args[1:])
            return attr(*args, **kwargs)

        return wrapper


logger = _MojibakeFixingLogger(_logger)
