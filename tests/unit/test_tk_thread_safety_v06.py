import threading

from edward.ui.tk_thread_safety_v06 import install_thread_safe_tk_after


class FakeApp:
    def __init__(self):
        self.scheduled = []
        self.after_calls = []
        self.exists = True

    def after(self, ms, func=None, *args):
        self.after_calls.append((threading.get_ident(), ms, func, args))
        if func is not None:
            self.scheduled.append(lambda: func(*args))
        return f"after-{len(self.after_calls)}"

    def winfo_exists(self):
        return self.exists


def test_worker_after_is_queued_without_touching_tk_from_worker_thread():
    install_thread_safe_tk_after(FakeApp)
    app = FakeApp()
    called = []

    worker = threading.Thread(target=lambda: app.after(0, lambda: called.append("done")))
    worker.start()
    worker.join()

    assert called == []
    assert not any(ms == 0 for _, ms, _, _ in app.after_calls)
    assert getattr(app, "_thread_safe_after_queue_v06").qsize() == 1

    # The scheduled drain is a main-thread callback.
    assert app.scheduled
    app.scheduled.pop(0)()

    assert called == ["done"]


def test_main_thread_after_remains_a_normal_tk_after_call():
    install_thread_safe_tk_after(FakeApp)
    app = FakeApp()
    app.after(0, lambda: None)

    assert any(ms == 0 for _, ms, _, _ in app.after_calls)
