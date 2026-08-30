"""Negative-control CLI-style ledger with an atomic rename operation."""


class CleanLedger:
    def __init__(self):
        self.records = {"old": "present"}

    def rename(self, old: str, new: str) -> None:
        if old not in self.records:
            return
        value = self.records.pop(old)
        self.records[new] = value

    def lookup(self, key: str):
        return self.records.get(key)
