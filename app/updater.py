import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from .config import APP_NAME, APP_VERSION, GITHUB_BRANCH, GITHUB_OWNER, GITHUB_REPO, GITHUB_URL

HEADERS = {"User-Agent": f"{APP_NAME} ({GITHUB_URL}, {APP_VERSION})"}


class UpdateError(Exception):
    pass


@dataclass
class UpdateInfo:
    version: str
    is_newer: bool
    notes: str = ""
    url: str = ""
    files: list = field(default_factory=list)
    setup_url: str = ""
    setup_sha256: str = ""


def parse_version(text):
    parts = re.findall(r"\d+", str(text))
    if not parts:
        raise UpdateError(f"Numéro de version invalide : {text!r}")
    return tuple(int(part) for part in parts)


class Updater:
    @property
    def base(self):
        return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/updates"

    def fetch_manifest(self):
        try:
            response = requests.get(self.base + "/manifest.json", headers=HEADERS, timeout=10)
        except requests.RequestException as error:
            raise UpdateError(f"Impossible de contacter GitHub : {error}")

        if response.status_code == 404:
            raise UpdateError("Aucun manifeste publié : ajoute updates/manifest.json au dépôt GitHub.")
        if response.status_code != 200:
            raise UpdateError(f"GitHub a répondu {response.status_code}.")
        try:
            return response.json()
        except ValueError:
            raise UpdateError("Le manifeste n'est pas un JSON valide.")

    def check(self):
        data = self.fetch_manifest()
        try:
            version = str(data["version"])
        except (KeyError, TypeError):
            raise UpdateError("Le manifeste ne contient pas de version.")

        url = str(data.get("url", ""))

        # Le Setup doit venir des releases de ce dépôt ; sinon on prend l'adresse par défaut.
        release_prefix = f"{GITHUB_URL}/releases/"
        setup_url = str(data.get("setup_url", ""))
        if not setup_url.startswith(release_prefix):
            setup_url = f"{release_prefix}latest/download/{APP_NAME}_Setup_{version}.exe"

        setup_sha256 = str(data.get("setup_sha256", "")).strip().lower()
        if setup_sha256 and not re.fullmatch(r"[0-9a-f]{64}", setup_sha256):
            raise UpdateError("Le champ setup_sha256 du manifeste est invalide (64 caractères hexadécimaux attendus).")

        return UpdateInfo(
            version=version,
            is_newer=parse_version(version) > parse_version(APP_VERSION),
            notes=str(data.get("notes", "")),
            url=url if url.startswith("https://") else "",
            files=data.get("files", []),
            setup_url=setup_url,
            setup_sha256=setup_sha256,
        )

    def download(self, info, dest):
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)

        for entry in info.files:
            name = entry["name"]
            if Path(name).name != name:
                raise UpdateError(f"Nom de fichier refusé : {name}")

            try:
                response = requests.get(f"{self.base}/{name}", headers=HEADERS, timeout=30)
            except requests.RequestException as error:
                raise UpdateError(f"Téléchargement impossible : {error}")

            if response.status_code != 200:
                raise UpdateError(f"{name} : GitHub a répondu {response.status_code}.")
            if hashlib.sha256(response.content).hexdigest().lower() != entry["sha256"].lower():
                raise UpdateError(f"Vérification SHA-256 échouée pour {name}.")
            (dest / name).write_bytes(response.content)

        return dest

    def download_setup(self, info, dest, progress=None):
        """Télécharge le Setup de la release dans `dest` et renvoie son chemin.

        `progress(reçu, total)` est appelé pendant le téléchargement (total = 0 si inconnu).
        """
        if not info.setup_url:
            raise UpdateError("Aucun Setup indiqué pour cette version.")

        name = Path(unquote(urlparse(info.setup_url).path)).name
        if not name.lower().endswith(".exe"):
            raise UpdateError(f"Nom de Setup refusé : {name!r}")

        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / name
        part = dest / (name + ".part")
        digest = hashlib.sha256()

        try:
            with requests.get(info.setup_url, headers=HEADERS, stream=True, timeout=30) as response:
                if response.status_code == 404:
                    raise UpdateError(
                        f"Setup introuvable sur GitHub : {name}. Vérifie qu'il est ajouté à la dernière release "
                        "(pas en brouillon ni en pré-version) avec ce nom exact."
                    )
                if response.status_code != 200:
                    raise UpdateError(f"GitHub a répondu {response.status_code} pour {name}.")

                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                with open(part, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        digest.update(chunk)
                        received += len(chunk)
                        if progress:
                            progress(received, total)

            with open(part, "rb") as handle:
                if handle.read(2) != b"MZ":
                    raise UpdateError("Le fichier téléchargé n'est pas un programme Windows valide.")
            if info.setup_sha256 and digest.hexdigest() != info.setup_sha256:
                raise UpdateError(f"Vérification SHA-256 échouée pour {name}.")

            part.replace(target)
        except requests.RequestException as error:
            part.unlink(missing_ok=True)
            raise UpdateError(f"Téléchargement impossible : {error}")
        except Exception:
            part.unlink(missing_ok=True)
            raise

        return target

    def run_setup(self, setup_path):
        """Lance le Setup en silence puis relance Otomatik. L'appelant doit fermer l'application juste après."""
        setup_path = Path(setup_path)
        if sys.platform != "win32":
            raise UpdateError("L'installation automatique n'est disponible que sous Windows.")
        if not setup_path.is_file():
            raise UpdateError(f"Setup introuvable : {setup_path}")

        command = [
            "cmd.exe", "/d", "/c",
            "ping", "-n", "3", "127.0.0.1", ">nul",
            "&", "start", "/wait", "", str(setup_path),
            "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
        ]
        if getattr(sys, "frozen", False):
            command += ["&", "start", "", sys.executable]

        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(command, creationflags=flags, close_fds=True)