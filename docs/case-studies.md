# Case studies

These small fixtures show the kind of cross-layer gaps the suite is designed
to surface. They are intentionally minimal: the examples demonstrate the
method, not the full complexity of a production system.

## Web cache staleness

`examples/web-cache/` models a repository where a delete operation updates the
authoritative database but leaves a derived cache entry behind. A normal unit
test can prove the database mutation; the coherence audit asks whether the
user-visible read path now describes the same state.

Probe: delete an item, read through the cache, then compare the result with the
database. Expected result: the deleted item is absent from both authorities, or
the cache reports a bounded, explicitly modeled stale state.

## Worker partial completion

`examples/worker-service/` models a worker that persists completion before a
side effect succeeds. A restart can therefore report success while the
external effect never happened.

Probe: fail the side effect after persistence, restart the worker, and inspect
whether the state machine can retry or reconcile the effect. Expected result:
the persisted state distinguishes completed, pending, and retryable outcomes.

## Clean CLI negative control

`examples/clean-cli/` is a correct rename flow used to measure false positives.
The audit should not report a lifecycle defect when the command updates the
authoritative state and the derived output together.

## What these cases do not prove

Passing the fixtures does not prove that an arbitrary production system is
coherent. The cases exercise representative stale-state, partial-failure, and
negative-control patterns. Production conclusions still require current
repository evidence, explicit contracts, runtime probes where safe, and
revalidation after changes.
