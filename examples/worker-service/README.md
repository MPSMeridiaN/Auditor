# Worker/service fixture

This fixture represents a queue worker with a durable job status and an external output side effect. The worker records `completed` before the side effect succeeds. A failure leaves a completed job without its output and prevents a safe retry.

Expected audit category: `partial-commit`.
