"""TEST ONLY: terminate the actual parallel node after one durable lane commit.

Never imported by app/ or exposed as an API/production worker flag.
"""
from contextlib import contextmanager
import os
from threading import Barrier, Event, Lock
from uuid import UUID
import sys

from app.workflow import Workflow
from tools.workflow_demo import run_local


class CrashWorkflow(Workflow):
    def research(self, state):
        original_lane = self.research_store.lane
        original_save = self.research_store.save_task
        entered = Barrier(3, timeout=10)
        blocked = Event()
        selected = []
        selection = Lock()

        @contextmanager
        def lane(context, cid):
            # All real ThreadPoolExecutor lanes must start before the winner proceeds.
            entered.wait()
            with selection:
                if not selected:
                    selected.append(cid)
            if cid != selected[0]:
                blocked.wait(20)
                raise AssertionError("test_crash_not_triggered")
            with original_lane(context, cid):
                yield

        def save(*args, **kwargs):
            original_save(*args, **kwargs)
            os._exit(23)  # No finally/lease release: emulates a lost worker process.

        self.research_store.lane = lane
        self.research_store.save_task = save
        return super().research(state)


if __name__ == "__main__":
    if os.environ.get("LATHER_WORKFLOW_FAULT") != "DEMO-process-crash":
        raise SystemExit("test_fault_not_authorized")
    run_local(UUID(sys.argv[1]), workflow_factory=CrashWorkflow, lease_seconds=2)
