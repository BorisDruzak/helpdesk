"""Minimal compatibility shim for environments without win32_setctime."""


def setctime(_path, _timestamp):
    return None

