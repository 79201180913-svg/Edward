from __future__ import annotations

import threading
from queue import Empty, Queue
from typing import Any, Callable

_EVENT_QUEUE_ATTR = "_thread_safe_after_queue_v06"
_MAIN_THREAD_ATTR = "_thread_safe_after_main_thread_v06"


def install_thread_safe_tk_after(app_class: type[Any], *, poll_ms: int = 20) -> None:
    """Marshal Tk `after` calls made by worker threads onto the GUI thread."""
    if getattr(app_class, "_thread_safe_after_v06_installed", False):
        return

    original_init = app_class.__init__
    original_after = app_class.after

    def drain(self: Any) -> None:
        queue: Queue[Callable[[], Any]] | None = getattr(self, _EVENT_QUEUE_ATTR, None)
        if queue is None:
            return
        for _ in range(100):
            try:
                callback = queue.get_nowait()
            except Empty:
                break
            try:
                callback()
            except Exception:
                pass
        try:
            if self.winfo_exists():
                original_after(self, poll_ms, lambda: drain(self))
        except Exception:
            pass

    def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
        setattr(self, _EVENT_QUEUE_ATTR, Queue())
        setattr(self, _MAIN_THREAD_ATTR, threading.get_ident())
        original_init(self, *args, **kwargs)
        original_after(self, poll_ms, lambda: drain(self))

    def wrapped_after(self: Any, ms: int, func: Callable[..., Any] | None = None, *args: Any):
        main_thread = getattr(self, _MAIN_THREAD_ATTR, threading.get_ident())
        if threading.get_ident() == main_thread or func is None:
            return original_after(self, ms, func, *args)
        queue: Queue[Callable[[], Any]] = getattr(self, _EVENT_QUEUE_ATTR)
        queue.put(lambda: func(*args))
        return "thread-queued"

    app_class.__init__ = wrapped_init
    app_class.after = wrapped_after
    app_class._execution_thread_safe_after_v06_installed = True
    app_class._thread_safe_after_v06_installed = True


__all__ = ["install_thread_safe_tk_after"]
