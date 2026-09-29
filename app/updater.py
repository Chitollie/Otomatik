import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

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
        return UpdateInfo(
            version=version,
            is_newer=parse_version(version) > parse_version(APP_VERSION),
            notes=str(data.get("notes", "")),
            url=url if url.startswith("https://") else "",
            files=data.get("files", []),
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
