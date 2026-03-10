# Changelog

All notable changes to the Netskope Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-10

### Added

- **NetskopeClient** and **AsyncNetskopeClient** — sync and async entry points
- **Hierarchical resource namespaces**: `client.alerts`, `client.events`, `client.url_lists`, `client.publishers`, `client.private_apps`, `client.scim`, `client.incidents`, `client.steering`
- **Automatic pagination** with lazy iterators, `.pages()`, `.to_list()`, and `.first()`
- **Pydantic v2 response models** for all resources: Alert, Event, Publisher, UrlList, PrivateApp, ScimUser, ScimGroup, Incident, and more
- **Rich exception hierarchy**: NetskopeError, APIError, AuthenticationError, ForbiddenError, NotFoundError, ConflictError, RateLimitError, ServerError, ValidationError, ConnectionError, TimeoutError
- **Automatic retries** with exponential backoff, jitter, and Retry-After header support
- **Credential resolution chain**: explicit params → environment variables
- **Context manager support** for both sync and async clients
- **Full type annotations** with `py.typed` marker (PEP 561)
- **Comprehensive test suite**: 80+ unit tests, 19 integration tests
- **Examples directory**: quickstart, async usage, event monitoring, URL list management, multi-tenant
- **Documentation site**: GitHub Pages with Tailwind CSS
