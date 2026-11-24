"""Job queue and event bus. Jobs run one at a time, in submission order, on one worker thread: engine operations share the
workspace and the bundle library is not re-entrant. Every state change is published as an event; a UI subscribes instead of
polling. Stdlib only."""
import itertools
import queue
import threading
import time


class EventBus:
    """publish(type, data) fans out to every subscriber's queue. Slow subscribers lose the oldest events, never block."""

    def __init__(self, backlog=200):
        self._subs, self._lock, self._seq, self._backlog = [], threading.Lock(), itertools.count(1), backlog

    def subscribe(self):
        q = queue.Queue(self._backlog)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def publish(self, type_, data):
        ev = {"seq": next(self._seq), "type": type_, "time": time.time(), "data": data}
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(ev)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(ev)
                except (queue.Empty, queue.Full):
                    pass
        return ev


class Cancelled(Exception):
    """Raised by a cancellable job's function when it honours a cancel request; the first argument, when given, is its partial result."""


def cancel_with(partial_result=None):
    """Called by a cancellable job's function to end as cancelled, keeping `partial_result` as the job's result."""
    raise Cancelled(partial_result)


class Job:
    STATES = ("queued", "running", "done", "failed", "cancelled")

    def __init__(self, id_, label, fn, cancellable=False):
        self.id, self.label, self.fn = id_, label, fn
        self.cancellable, self.cancel_requested = cancellable, threading.Event()
        self.title = label                     # the label given at submit; 'label' follows the progress messages
        self.state, self.progress, self.error, self.result = "queued", 0.0, None, None
        self.created, self.started, self.finished = time.time(), None, None
        self.done = threading.Event()

    def view(self):
        return {"id": self.id, "title": self.title, "label": self.label, "state": self.state, "progress": self.progress,
                "error": self.error, "result": self.result if self.state in ("done", "cancelled") else None,
                "cancellable": self.cancellable, "cancel_requested": self.cancel_requested.is_set(),
                "created": self.created, "started": self.started, "finished": self.finished}

    def legacy(self):
        """The shape the first frontend polls: {running, label, progress, error, result}. A queued job counts as running."""
        return {"id": self.id, "running": self.state in ("queued", "running"), "label": self.label, "progress": self.progress,
                "error": self.error, "result": self.result}


class JobQueue:
    def __init__(self, events=None, keep=50):
        self.events = events or EventBus()
        self._jobs, self._order, self._q = {}, [], queue.Queue()
        self._ids, self._lock, self._keep = itertools.count(1), threading.Lock(), keep
        self._worker = threading.Thread(target=self._run, daemon=True, name="fm27se-jobs")
        self._worker.start()

    def submit(self, label, fn, cancellable=False):
        """fn(progress) -> result, where progress(message, fraction 0..1). A cancellable job's `progress.cancelled()` turns true when a cancel is requested and the
        function may raise Cancelled (optionally with a partial result). Returns the Job."""
        with self._lock:
            job = Job("j%d" % next(self._ids), label, fn, cancellable)
            self._jobs[job.id] = job
            self._order.append(job.id)
            for old in self._order[:-self._keep]:
                if self._jobs[old].state in ("done", "failed", "cancelled"):
                    self._jobs.pop(old)
                    self._order.remove(old)
        self.events.publish("job.queued", job.view())
        self._q.put(job)
        return job

    def get(self, id_):
        job = self._jobs.get(id_)
        if not job:
            raise KeyError("no such job: %s" % id_)
        return job

    def list(self):
        return [self._jobs[i].view() for i in self._order]

    def cancel(self, id_):
        """A job that has not started is cancelled at once. A running job is only asked to stop when it was submitted as cancellable (an inventory scan);
        a running bundle write is never interrupted."""
        job = self.get(id_)
        if job.state == "running" and job.cancellable:
            job.cancel_requested.set()
            return True
        if job.state != "queued":
            return False
        job.state, job.finished = "cancelled", time.time()
        job.done.set()
        self.events.publish("job.cancelled", job.view())
        return True

    def wait(self, id_, timeout=None):
        job = self.get(id_)
        job.done.wait(timeout)
        return job

    def latest_legacy(self):
        if not self._order:
            return {"running": False, "label": "", "progress": 0.0, "error": None, "result": None}
        return self._jobs[self._order[-1]].legacy()

    def _run(self):
        while True:
            job = self._q.get()
            if job.state != "queued":
                continue
            job.state, job.started = "running", time.time()
            self.events.publish("job.started", job.view())
            last = [0.0]

            def progress(message, fraction, job=job):
                job.label, job.progress = str(message), max(0.0, min(1.0, float(fraction)))
                now = time.time()
                if now - last[0] >= 0.1:                       # at most 10 progress events a second
                    last[0] = now
                    self.events.publish("job.progress", {"id": job.id, "label": job.label, "progress": job.progress})
            progress.cancelled = job.cancel_requested.is_set
            try:
                job.result = job.fn(progress)
                job.state = "done"
            except Cancelled as e:
                job.result = e.args[0] if e.args else None
                job.state = "cancelled"
            except Exception as e:
                job.error, job.state = "%s: %s" % (type(e).__name__, e), "failed"
            job.progress, job.finished = 1.0, time.time()
            job.done.set()
            self.events.publish({"done": "job.done", "cancelled": "job.cancelled"}.get(job.state, "job.failed"), job.view())
