"""Authorization scope and ownership guards shared by every entry point."""

from jc.authz.ownership import require_owned_profile, require_owned_references
from jc.authz.scope import RunScope

__all__ = ["RunScope", "require_owned_profile", "require_owned_references"]
