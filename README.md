# Otomatik 1.1.0

Application Python / PySide6 (thème noir et bleu) pour FiveM.

- **AutoFish** : pêche automatique, pause globale (F8 par défaut), paramètres enregistrés.
- **Compteur** : lit la notification de poisson (OCR) et calcule ce que rapporte la pêche.
- **AntiAFK** : S puis Z à intervalle réglable (20 min par défaut).
- **Mises à jour** : compare la version installée avec `updates/manifest.json` sur GitHub.
- **Connexion Discord** : OAuth2 avec PKCE (aucun secret dans l'application).

Les réglages sont enregistrés dans `%APPDATA%\Otomatik\settings.json`.

## Lancer depuis les sources

```
Setup.bat
```

ou à la main : `py -3.13 -m pip install -r requirements.txt` puis `py -3.13 run.py`.

## Créer l'EXE et l'installeur

1. Lance `build.bat` : installe les dépendances et crée `dist\Otomatik.exe`.
2. Ouvre `installer\Otomatik.iss` dans Inno Setup 6.3 ou plus récent, puis **Build > Compile**.
3. L'installeur est créé dans `installer\installer_output\`.

L'EXE contient déjà toutes les dépendances Python : il n'y a rien à faire avec `requirements.txt` sur le PC final.
La seule dépendance externe est **Tesseract OCR** (Compteur) : l'installeur la télécharge et l'installe si elle est absente,
et il copie `tessdata\fra.traineddata` (français) à côté de l'application.

## Connexion Discord

Dans le [Developer Portal](https://discord.com/developers/applications), ouvre l'application puis **OAuth2** :

1. Ajoute la redirection `http://127.0.0.1:8765/callback` (exactement cette valeur).
2. Active **Public Client** (l'application n'embarque pas de secret client).

Le compte administrateur est défini par `DISCORD_ADMIN_ID` dans `app/config.py`.

## Mises à jour

`updates/manifest.json` doit être poussé sur la branche `main` du dépôt :

```json
{
  "version": "1.1.0",
  "notes": "Texte affiché dans l'application.",
  "url": "https://github.com/Chitollie/Otomatik/releases/latest",
  "files": []
}
```

Si `url` est renseigné, le bouton **Télécharger** l'ouvre dans le navigateur. Sinon, les fichiers de `files`
(`{"name": "...", "sha256": "..."}`) sont téléchargés et vérifiés.

À chaque nouvelle version, change le numéro dans `app/config.py`, `installer/Otomatik.iss` et `updates/manifest.json`.
