"""
handlers/__init__.py — handlers package

Uses OLD handlers files for backward compatibility.
"""
from .admin import register as register_admin
from .quests import register_handlers as register_quests
from .user import register as register_user
from .maps import register_handlers as register_maps
from .jobs import register as register_jobs
from .listeners import register as register_listeners
from .alignment import register as register_alignment


def register_all(app):
    """Register all handlers."""
    register_admin(app)
    register_quests(app)
    register_user(app)
    register_maps(app)
    register_jobs(app)
    register_listeners(app)
    register_alignment(app)