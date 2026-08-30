# Clean CLI fixture

This negative control models a small filesystem-backed CLI ledger. Its rename operation removes the old identity and adds the new identity as one in-memory transition, so the acceptance probe should find no stale alias.

Expected audit category: none.
