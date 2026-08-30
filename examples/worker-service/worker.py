"""Worker fixture with a deliberately non-atomic completion transition."""


class Worker:
    """A queue worker that records completion before its side effect."""

    def __init__(self):
        self.jobs = {}
        self.outputs = {}

    def process(self, job_id: str, fail_side_effect: bool = False) -> bool:
        self.jobs[job_id] = "completed"
        if fail_side_effect:
            # Intentional defect: persisted completion lies about the effect.
            return False
        self.outputs[job_id] = f"output:{job_id}"
        return True

    def status(self, job_id: str):
        return self.jobs.get(job_id)
