"""Native Windows token input dialog with reliable clipboard support."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from edward.security.token_store import TokenStore

# Keep the module importable on non-Windows systems (CI, tests, tooling).
# Win32 handles are loaded only when the native dialog is actually used.
user32 = None
kernel32 = None

# Explicit Win32 signatures are important on 64-bit Python. Without them,
# ctypes may default to 32-bit integers and Windows message parameters can
# overflow before they reach the window procedure.
LRESULT = ctypes.c_ssize_t

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
EM_SETPASSWORDCHAR = 0x00CC
ES_PASSWORD = 0x0020
ES_AUTOHSCROLL = 0x0080
ES_LEFT = 0x0000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_TABSTOP = 0x00010000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_EX_CLIENTEDGE = 0x00000200
BS_DEFPUSHBUTTON = 0x00000001
BS_PUSHBUTTON = 0x00000000
SW_SHOW = 5
CW_USEDEFAULT = 0x80000000
IDC_ARROW = 32512

EDIT_ID = 1001
OK_ID = 1002
CANCEL_ID = 1003


def _load_win32() -> tuple[object, object]:
    """Load and configure Win32 APIs only when running the native dialog."""
    if os.name != "nt":
        raise RuntimeError("The native token dialog is available only on Windows")

    loaded_user32 = ctypes.windll.user32
    loaded_kernel32 = ctypes.windll.kernel32

    loaded_user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    loaded_user32.DefWindowProcW.restype = LRESULT
    loaded_user32.DestroyWindow.argtypes = [wintypes.HWND]
    loaded_user32.DestroyWindow.restype = wintypes.BOOL
    loaded_user32.PostQuitMessage.argtypes = [ctypes.c_int]
    loaded_user32.PostQuitMessage.restype = None
    return loaded_user32, loaded_kernel32


class TokenDialog:
    """Native Win32 token dialog using the standard Windows EDIT control.

    Clipboard shortcuts, including Ctrl+C/Ctrl+V, are handled by the
    standard Windows EDIT control.
    """

    def __init__(self, title: str = "Edward Trading Platform") -> None:
        self.title = title
        self.token: str | None = None
        self.hwnd = None
        self.edit = None
        self._wnd_proc = None

    def show(self) -> str | None:
        global user32, kernel32
        user32, kernel32 = _load_win32()
        hinstance = kernel32.GetModuleHandleW(None)
        wnd_proc_type = ctypes.WINFUNCTYPE(
            LRESULT,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        @wnd_proc_type
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_COMMAND:
                control_id = int(wparam) & 0xFFFF
                if control_id == OK_ID:
                    self._accept()
                    return 0
                if control_id == CANCEL_ID:
                    self.token = None
                    user32.DestroyWindow(hwnd)
                    return 0
            elif msg == WM_CLOSE:
                self.token = None
                user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wnd_proc = wnd_proc

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", wnd_proc_type),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HCURSOR),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        class_name = "EdwardTokenDialog"
        wc = WNDCLASSW()
        wc.lpfnWndProc = wnd_proc
        wc.hInstance = hinstance
        wc.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        wc.hbrBackground = ctypes.cast(5, wintypes.HBRUSH)
        wc.lpszClassName = class_name
        user32.RegisterClassW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(
            0, class_name, self.title,
            WS_VISIBLE | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
            CW_USEDEFAULT, CW_USEDEFAULT, 560, 230,
            None, None, hinstance, None,
        )
        user32.CreateWindowExW(
            0, "STATIC", "Введите T-Invest API Token:", WS_CHILD | WS_VISIBLE,
            30, 30, 480, 25, self.hwnd, None, hinstance, None,
        )
        self.edit = user32.CreateWindowExW(
            WS_EX_CLIENTEDGE, "EDIT", "",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL | ES_PASSWORD | ES_LEFT,
            30, 65, 480, 30, self.hwnd, EDIT_ID, hinstance, None,
        )
        user32.SendMessageW(self.edit, EM_SETPASSWORDCHAR, ord("•"), 0)
        user32.CreateWindowExW(
            0, "STATIC", "Ctrl+V — вставить токен. Токен сохранится локально.",
            WS_CHILD | WS_VISIBLE, 30, 105, 480, 25, self.hwnd, None, hinstance, None,
        )
        user32.CreateWindowExW(
            0, "BUTTON", "Сохранить и продолжить",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
            250, 145, 170, 35, self.hwnd, OK_ID, hinstance, None,
        )
        user32.CreateWindowExW(
            0, "BUTTON", "Отмена",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            430, 145, 80, 35, self.hwnd, CANCEL_ID, hinstance, None,
        )
        user32.SetFocus(self.edit)
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        return self.token

    def _accept(self) -> None:
        if user32 is None:
            raise RuntimeError("Win32 dialog is not initialized")
        length = user32.SendMessageW(self.edit, WM_GETTEXTLENGTH, 0, 0)
        if not length:
            user32.MessageBoxW(self.hwnd, "Введите API Token.", "Edward", 0x10)
            return
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(self.edit, WM_GETTEXT, length + 1, ctypes.byref(buffer))
        value = buffer.value.strip()
        if not value:
            user32.MessageBoxW(self.hwnd, "Введите API Token.", "Edward", 0x10)
            return
        self.token = value
        user32.DestroyWindow(self.hwnd)


def request_and_save_token(store: TokenStore) -> str | None:
    """Request a token using the native Windows dialog and save it."""
    token = TokenDialog().show()
    if not token:
        return None
    store.save(token)
    return token


def ask_for_token() -> str | None:
    """Show the native Windows token dialog without saving it."""
    return TokenDialog().show()
