"""Public page and iterator types returned by Netskope resource methods."""

from netskope._pagination import (
    AsyncPaginatedResponse,
    AsyncScimPaginatedResponse,
    Page,
    SyncPaginatedResponse,
    SyncScimPaginatedResponse,
)

__all__ = [
    "AsyncPaginatedResponse",
    "AsyncScimPaginatedResponse",
    "Page",
    "SyncPaginatedResponse",
    "SyncScimPaginatedResponse",
]
