"""Temporary probe for validating central GitNexus automatic indexing."""

GITNEXUS_UPDATE_PROBE_VERSION = "2026-08-16-v1"


def gitnexus_update_probe() -> str:
    """Return the unique version of the GitNexus update probe."""
    return GITNEXUS_UPDATE_PROBE_VERSION


class GitNexusUpdateProbe:
    """Unique symbol used only to verify GitNexus index refresh."""

    version = GITNEXUS_UPDATE_PROBE_VERSION
