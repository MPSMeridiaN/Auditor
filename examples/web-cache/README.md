# Web/cache fixture

This fixture represents a web application with an authoritative database and a derived read cache. `WebCache.delete()` removes the database row but leaves the cache entry, so a later read returns a resource that no longer exists.

Expected audit category: `stale-derived-state`.
