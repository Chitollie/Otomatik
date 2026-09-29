from PySide6.QtCore import QObject, Signal


class Bus(QObject):
    log = Signal(str, str)
    login_done = Signal(object)
    login_failed = Signal(str)
    update_checked = Signal(object)
    update_failed = Signal(str)
    update_downloaded = Signal(str)
