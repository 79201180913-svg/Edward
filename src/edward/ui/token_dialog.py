"""Native Windows token input dialog with reliable clipboard support."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_KEYDOWN = 0x0100
WM_CHAR = 0x0102
WM_PASTE = 0x0302
WM_COPY = 0x0301
WM_CUT = 0x0300
WM_CLEAR = 0x0303
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
EM_SETPASSWORDCHAR = 0x00CC
EM_SETSEL = 0x00B1
EM_REPLACESEL = 0x00C2
ES_PASSWORD = 0x0020
ES_AUTOHSCROLL = 0x0080
ES_LEFT = 0x0000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_BORDER = 0x00800000
WS_TABSTOP = 0x00010000
WS_EX_CLIENTEDGE = 0x00000200
BS_DEFPUSHBUTTON = 0x00000001
BS_PUSHBUTTON = 0x00000000
SW_SHOW = 5
CW_USEDEFAULT = 0x80000000
IDC_ARROW = 32512

EDIT_ID = 1001
OK_ID = 1002
CANCEL_ID = 1003


class TokenDialog:
    """Small native Win32 dialog.

    Uses the Windows EDIT control directly, so clipboard operations such as
    Ctrl+V are handled by Windows itself rather than by Tkinter bindings.
    """

    def __init__(self, title: str = "Edward Trading Platform") -> None:
        self.title = title
        self.token: str | None = None
        self.hwnd = None
        self.edit = None

    def show(self) -> str | None:
        hinstance = kernel32.GetModuleHandleW(None)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", wintypes.WINFUNCTYPE(wintypes.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HCURSOR),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        @wintypes.WINFUNCTYPE(wintypes.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_COMMAND:
                control_id = wparam & 0xFFFF
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
        class_name = "EdwardTokenDialog"
        wc = WNDCLASSW()
        wc.lpfnWndProc = wnd_proc
        wc.hInstance = hinstance
        wc.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        wc.hbrBackground = ctypes.c_void_p(5)
        wc.lpszClassName = class_name

        user32.RegisterClassW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(
            0,
            class_name,
            self.title,
            WS_VISIBLE | 0x00CF0000,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            560,
            230,
            None,
            None,
            hinstance,
            None,
        )

        user32.CreateWindowExW(
            0,
            "STATIC",
            "Введите T-Invest API Token:",
            WS_CHILD | WS_VISIBLE,
            30, 30, 480, 25,
            self.hwnd, None, hinstance, None,
        )

        self.edit = user32.CreateWindowExW(
            WS_EX_CLIENTEDGE,
            "EDIT",
            "",
            WS_CHILD | WS_VISIBLE | WS_BORDER | WS_TABSTOP | ES_AUTOHSCROLL | ES_PASSWORD | ES_LEFT,
            30, 65, 480, 30,
            self.hwnd, EDIT_ID, hinstance, None,
        )
        user32.SendMessageW(self.edit, EM_SETPASSWORDCHAR, ord("•"), 0)

        user32.CreateWindowExW(
            0,
            "STATIC",
            "Токен будет сохранён в защищённом хранилище Windows.",
            WS_CHILD | WS_VISIBLE,
            30, 105, 480, 25,
            self.hwnd, None, hinstance, None,
        )

        ok = user32.CreateWindowExW(
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
        user32.SendMessageW(self.edit, EM_SETSEL, 0, -1)
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        return self.token

    def _accept(self) -> None:
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


def ask_for_token() -> str | None:
    """Show the native Windows token dialog and return the entered token."""
    return TokenDialog().show()
