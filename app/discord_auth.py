import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass

import requests

from .config import APP_NAME, APP_VERSION, DISCORD_ADMIN_ID, DISCORD_CLIENT_ID, DISCORD_REDIRECT_URI, GITHUB_URL

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
SCOPE = "identify"
HEADERS = {"User-Agent": f"{APP_NAME} ({GITHUB_URL}, {APP_VERSION})"}
KEYRING_SERVICE = APP_NAME
KEYRING_USER = "discord"

REDIRECT = urllib.parse.urlparse(DISCORD_REDIRECT_URI)

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Otomatik</title>
<style>body{{background:#0b0f14;color:#e7edf5;font-family:Segoe UI,sans-serif;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0}}
div{{text-align:center}}h1{{color:{color}}}</style></head>
<body><div><h1>{title}</h1><p>{text}</p></div></body></html>"""


class DiscordError(Exception):
    pass


@dataclass
class DiscordUser:
    id: str
    name: str
    avatar: bytes = b""

    @property
    def is_admin(self):
        return self.id == DISCORD_ADMIN_ID


class CallbackServer(http.server.HTTPServer):
    result = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != REDIRECT.path:
            self.send_error(404)
            return

        params = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        self.server.result = params

        if "code" in params:
            page = PAGE.format(color="#4ade80", title="Connexion réussie", text="Tu peux fermer cet onglet et revenir sur Otomatik.")
        else:
            page = PAGE.format(color="#f87171", title="Connexion refusée", text="Retourne sur Otomatik pour plus de détails.")

        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def make_pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def token_request(data):
    try:
        response = requests.post(TOKEN_URL, data=data, headers=HEADERS, timeout=15)
    except requests.RequestException as error:
        raise DiscordError(f"Impossible de contacter Discord : {error}")

    if response.status_code == 200:
        return response.json()

    try:
        error_code = response.json().get("error", "")
    except ValueError:
        error_code = ""

    if response.status_code in (400, 401) and error_code == "invalid_client":
        raise DiscordError(
            "Discord refuse la connexion sans secret client.\n\n"
            "Dans le Developer Portal, ouvre ton application > OAuth2 puis active « Public Client »."
        )
    raise DiscordError(f"Discord a refusé la connexion ({response.status_code} {error_code}).")


def fetch_avatar(user_id, avatar_hash):
    if avatar_hash:
        url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size=64"
    else:
        url = f"https://cdn.discordapp.com/embed/avatars/{(int(user_id) >> 22) % 6}.png"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        return response.content if response.status_code == 200 else b""
    except requests.RequestException:
        return b""


def fetch_user(access_token):
    try:
        response = requests.get(USER_URL, headers={**HEADERS, "Authorization": f"Bearer {access_token}"}, timeout=15)
    except requests.RequestException as error:
        raise DiscordError(f"Impossible de contacter Discord : {error}")

    if response.status_code != 200:
        raise DiscordError(f"Impossible de lire le profil Discord ({response.status_code}).")

    data = response.json()
    return DiscordUser(
        id=data["id"],
        name=data.get("global_name") or data["username"],
        avatar=fetch_avatar(data["id"], data.get("avatar")),
    )


class DiscordAuth:
    def __init__(self):
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def login(self, timeout=180):
        self.cancel_event.clear()
        verifier, challenge = make_pkce_pair()
        state = secrets.token_urlsafe(16)

        query = urllib.parse.urlencode({
            "client_id": DISCORD_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": DISCORD_REDIRECT_URI,
            "scope": SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })

        try:
            server = CallbackServer((REDIRECT.hostname, REDIRECT.port), CallbackHandler)
        except OSError:
            raise DiscordError(f"Le port {REDIRECT.port} est déjà utilisé (une connexion est peut-être déjà en cours).")

        server.timeout = 0.5
        try:
            if not webbrowser.open(f"{AUTHORIZE_URL}?{query}"):
                raise DiscordError("Impossible d'ouvrir le navigateur.")

            deadline = time.time() + timeout
            while server.result is None:
                if self.cancel_event.is_set():
                    raise DiscordError("Connexion annulée.")
                if time.time() > deadline:
                    raise DiscordError(
                        "Aucune réponse de Discord.\n\n"
                        f"Vérifie que {DISCORD_REDIRECT_URI} est bien ajouté dans "
                        "Developer Portal > OAuth2 > Redirects."
                    )
                server.handle_request()
        finally:
            server.server_close()

        params = server.result
        if "error" in params:
            reason = "Autorisation refusée." if params["error"] == "access_denied" else params.get("error_description", params["error"])
            raise DiscordError(reason)
        if params.get("state") != state:
            raise DiscordError("Réponse Discord invalide (state incorrect).")

        tokens = token_request({
            "client_id": DISCORD_CLIENT_ID,
            "grant_type": "authorization_code",
            "code": params["code"],
            "redirect_uri": DISCORD_REDIRECT_URI,
            "code_verifier": verifier,
        })
        user = fetch_user(tokens["access_token"])
        self.save_tokens(tokens)
        return user

    def restore(self):
        try:
            import keyring

            saved = json.loads(keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or "")
            if saved["expires_at"] < time.time() + 60:
                tokens = token_request({
                    "client_id": DISCORD_CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": saved["refresh_token"],
                })
                self.save_tokens(tokens)
                saved = {"access_token": tokens["access_token"]}
            return fetch_user(saved["access_token"])
        except Exception:
            return None

    def logout(self):
        try:
            import keyring

            keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        except Exception:
            pass

    def save_tokens(self, tokens):
        try:
            import keyring

            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, json.dumps({
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token", ""),
                "expires_at": time.time() + int(tokens.get("expires_in", 0)),
            }))
        except Exception:
            pass
