"""Constantes de l'intégration e-Protec (Protection Civile)."""

DOMAIN = "eprotec"

BASE_URL = "https://eprotec.protection-civile.org/"
PORTAL_HOST = "portail.protection-civile.org"
AGENDA_PAGE = "upd_personnel.php?myagenda=1&tab=100"

CONF_PRENOM = "prenom"
CONF_HEURE = "heure"
DEFAULT_HEURE = 7

# Une seule connexion par compte et par 24 h.
MIN_INTERVAL_HOURS = 24
REQUEST_TIMEOUT = 30

USER_AGENT = "HomeAssistant-eProtec-Kerherve/0.2 (usage personnel, 1 connexion/jour)"
