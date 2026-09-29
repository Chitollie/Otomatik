import sys
import threading

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .antiafk import AntiAFK
from .autofish import AutoFish
from .bus import Bus
from .compteur import Compteur
from .config import APP_NAME, APP_VERSION, data_dir, load_settings
from .discord_auth import DiscordAuth, DiscordError
from .hotkey import HotkeyWatcher
from .pages import AntiAFKPage, AutoFishPage, CompteurPage, SettingsDialog, UpdatePage
from .theme import STYLE, make_button
from .updater import Updater, UpdateError

AVATAR_SIZE = 40


def round_pixmap(data, size):
    source = QPixmap()
    if not data or not source.loadFromData(data):
        return QPixmap()
    source = source.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, size, size))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, source)
    painter.end()
    return result


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1040, 700)
        self.setMinimumSize(920, 620)
        self.setStyleSheet(STYLE)

        self.cfg = load_settings()
        self.bus = Bus()
        self.autofish = AutoFish(self.cfg, self.logger("autofish"))
        self.antiafk = AntiAFK(self.cfg, self.logger("afk"))
        self.compteur = Compteur(self.logger("compteur"))
        self.updater = Updater()
        self.auth = DiscordAuth()
        self.user = None
        self.login_running = False

        self.pages = {
            "AutoFish": AutoFishPage(self.cfg, self.autofish, self.open_settings),
            "Compteur": CompteurPage(self.compteur),
            "AntiAFK": AntiAFKPage(self.cfg, self.antiafk),
            "Mises à jour": UpdatePage(self.check_updates, self.download_update),
        }
        self.log_targets = {
            "autofish": self.pages["AutoFish"].log,
            "compteur": self.pages["Compteur"].log,
            "afk": self.pages["AntiAFK"].log,
        }

        self.build_layout()
        self.connect_signals()

        self.hotkey = HotkeyWatcher(lambda: self.cfg["pause_key"], self.autofish.toggle_pause)
        self.hotkey.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_current)
        self.timer.start(300)

        threading.Thread(target=self.restore_discord, daemon=True).start()
        self.check_updates()

    def logger(self, channel):
        return lambda text: self.bus.log.emit(channel, text)

    def build_layout(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet("QFrame#sidebar { background: #0e151e; border-right: 1px solid #1c2a3a; }")
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 20, 16, 16)
        side.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setObjectName("title")
        version = QLabel(f"Version {APP_VERSION}")
        version.setObjectName("muted")
        side.addWidget(title)
        side.addWidget(version)

        self.nav = QListWidget()
        self.nav.addItems(list(self.pages))
        self.nav.setStyleSheet("QListWidget { border: 0; background: transparent; }")
        self.nav.currentRowChanged.connect(lambda row: self.stack.setCurrentIndex(row))
        side.addWidget(self.nav, 1)

        side.addWidget(self.build_discord_card())

        self.stack = QStackedWidget()
        for page in self.pages.values():
            self.stack.addWidget(page)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.nav.setCurrentRow(0)

    def build_discord_card(self):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        identity = QHBoxLayout()
        identity.setSpacing(10)
        self.avatar = QLabel()
        self.avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        self.avatar.setStyleSheet("background: #1c2a3a; border-radius: 20px;")
        names = QVBoxLayout()
        names.setSpacing(0)
        self.user_name = QLabel("Non connecté")
        self.user_role = QLabel("Discord")
        self.user_role.setObjectName("muted")
        names.addWidget(self.user_name)
        names.addWidget(self.user_role)
        identity.addWidget(self.avatar)
        identity.addLayout(names, 1)

        self.discord_button = make_button("Connexion Discord", self.toggle_discord)
        layout.addLayout(identity)
        layout.addWidget(self.discord_button)
        return card

    def connect_signals(self):
        self.bus.log.connect(lambda channel, text: self.log_targets[channel].add(text))
        self.bus.login_done.connect(self.on_login_done)
        self.bus.login_failed.connect(self.on_login_failed)
        self.bus.update_checked.connect(self.pages["Mises à jour"].show_result)
        self.bus.update_failed.connect(self.pages["Mises à jour"].show_error)
        self.bus.update_downloaded.connect(self.on_update_downloaded)

    def refresh_current(self):
        self.stack.currentWidget().refresh()

    def open_settings(self):
        if SettingsDialog(self.cfg, self).exec():
            self.bus.log.emit("autofish", "Paramètres enregistrés.")

    def toggle_discord(self):
        if self.user:
            self.auth.logout()
            self.user = None
            self.show_user(None)
        elif self.login_running:
            self.auth.cancel()
        else:
            self.login_running = True
            self.discord_button.setText("Annuler (navigateur ouvert)")
            self.discord_button.setProperty("variant", "secondary")
            self.discord_button.style().unpolish(self.discord_button)
            self.discord_button.style().polish(self.discord_button)
            threading.Thread(target=self.login_worker, daemon=True).start()

    def login_worker(self):
        try:
            user = self.auth.login()
        except DiscordError as error:
            self.bus.login_failed.emit(str(error))
        except Exception as error:
            self.bus.login_failed.emit(f"Erreur inattendue : {error}")
        else:
            self.bus.login_done.emit(user)

    def restore_discord(self):
        user = self.auth.restore()
        if user:
            self.bus.login_done.emit(user)

    def on_login_done(self, user):
        self.login_running = False
        self.user = user
        self.show_user(user)

    def on_login_failed(self, message):
        self.login_running = False
        self.show_user(None)
        if message != "Connexion annulée.":
            QMessageBox.warning(self, "Connexion Discord", message)

    def show_user(self, user):
        button = self.discord_button
        button.setProperty("variant", "secondary" if user else None)
        button.style().unpolish(button)
        button.style().polish(button)

        if user is None:
            self.user_name.setText("Non connecté")
            self.user_role.setText("Discord")
            self.avatar.setPixmap(QPixmap())
            button.setText("Connexion Discord")
            return

        self.user_name.setText(user.name)
        self.user_role.setText("Administrateur" if user.is_admin else "Connecté")
        pixmap = round_pixmap(user.avatar, AVATAR_SIZE)
        if not pixmap.isNull():
            self.avatar.setPixmap(pixmap)
        button.setText("Déconnexion")

    def check_updates(self):
        self.pages["Mises à jour"].show_checking()
        threading.Thread(target=self.check_worker, daemon=True).start()

    def check_worker(self):
        try:
            self.bus.update_checked.emit(self.updater.check())
        except UpdateError as error:
            self.bus.update_failed.emit(str(error))
        except Exception as error:
            self.bus.update_failed.emit(f"Vérification impossible : {error}")

    def download_update(self):
        info = self.pages["Mises à jour"].info
        if info is None:
            return
        if info.url:
            QDesktopServices.openUrl(QUrl(info.url))
            return
        folder = data_dir() / "updates" / info.version
        threading.Thread(target=self.download_worker, args=(info, folder), daemon=True).start()

    def download_worker(self, info, folder):
        try:
            self.updater.download(info, folder)
            self.bus.update_downloaded.emit(str(folder))
        except Exception as error:
            self.bus.update_failed.emit(str(error))

    def on_update_downloaded(self, folder):
        self.pages["Mises à jour"].show_downloaded(folder)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def closeEvent(self, event):
        self.hotkey.stop()
        self.antiafk.stop()
        self.compteur.stop()
        self.autofish.stop(wait=True)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = Main()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
