"""Small web-style service fixture with a deliberately stale cache bug."""


class WebCache:
    """A store plus a derived read cache; delete forgets to invalidate the cache."""

    def __init__(self):
        self.database = {}
        self.cache = {}

    def create(self, key: str, value: str) -> None:
        self.database[key] = value
        self.cache[key] = value

    def get(self, key: str):
        if key in self.cache:
            return self.cache[key]
        return self.database.get(key)

    def delete(self, key: str) -> None:
        self.database.pop(key, None)
        # Intentional defect: the derived cache remains populated.
