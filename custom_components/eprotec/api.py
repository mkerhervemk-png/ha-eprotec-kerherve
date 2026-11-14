"""Client e-Protec : connexion via le Portail Protection Civile, lecture seule."""

from __future__ import annotations

import asyncio
import html as html_lib
import re

import aiohttp

from .const import BASE_URL, PORTAL_HOST, REQUEST_TIMEOUT, USER_AGENT

_FORM_RE = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
_ACTION_RE = re.compile(r"""action\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_OTP_RE = re.compile(r"""name\s*=\s*["'](otp|totp)["']""", re.IGNORECASE)


class EProtecError(Exception):
    """Erreur générique (réseau, page inattendue)."""


class EProtecAuthError(EProtecError):
    """Identifiant ou mot de passe refusé."""


class EProtecMfaRequired(EProtecError):
    """Le portail demande un code supplémentaire : non automatisable."""


def _find_login_action(page: str) -> str | None:
    """Retourne l'URL d'envoi du formulaire de connexion du portail."""
    forms = _FORM_RE.findall(page)
    # Le formulaire de connexion du portail en priorité, sinon le premier.
    forms.sort(key=lambda tag: "kc-form-login" not in tag)
    for tag in forms:
        match = _ACTION_RE.search(tag)
        if match:
            return html_lib.unescape(match.group(1))
    return None


class EProtecClient:
    """Une instance par compte, avec sa propre session (cookies séparés)."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._headers = {"User-Agent": USER_AGENT}

    async def _get(self, url: str) -> tuple[str, str, str]:
        async with self._session.get(
            url, headers=self._headers, allow_redirects=True
        ) as resp:
            resp.raise_for_status()
            return await resp.text(), resp.url.host or "", str(resp.url)

    async def fetch(self, url: str) -> tuple[int, str, str]:
        """Lit une page (GET uniquement) dans la session en cours."""
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with self._session.get(
                url, headers=self._headers, allow_redirects=True
            ) as resp:
                return resp.status, await resp.text(), str(resp.url)

    async def login(self) -> tuple[str, str]:
        """Se connecte et retourne (HTML, URL) de la page d'accueil e-Protec.

        Une seule tentative : aucune relance automatique en cas d'échec.
        """
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                page, host, final_url = await self._get(BASE_URL)
                if host != PORTAL_HOST:
                    # Session encore valide : pas de nouvelle authentification.
                    return page, final_url

                action = _find_login_action(page)
                if not action:
                    raise EProtecError("Formulaire de connexion introuvable")

                async with self._session.post(
                    action,
                    headers=self._headers,
                    data={
                        "username": self._username,
                        "password": self._password,
                        "credentialId": "",
                    },
                    allow_redirects=True,
                ) as resp:
                    page = await resp.text()
                    host = resp.url.host or ""
                    final_url = str(resp.url)
                    status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise EProtecError(f"Portail injoignable : {err}") from err

        if host != PORTAL_HOST and status < 400:
            return page, final_url
        if _OTP_RE.search(page):
            raise EProtecMfaRequired("Le portail demande un code de vérification")
        if host == PORTAL_HOST:
            raise EProtecAuthError("Identifiant ou mot de passe refusé")
        raise EProtecError(f"Réponse inattendue (HTTP {status})")
