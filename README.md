# e-Protec Kerherve

Intégration Home Assistant non officielle pour e-Protec, l'espace bénévole de la Protection Civile. Usage personnel.

## Principes

- **Lecture seule** : aucune inscription ni désinscription à une mission.
- **1 connexion par compte et par 24 h**, à heure fixe, plus un bouton « Actualiser ».
- **Aucune relance automatique** en cas d'échec de connexion.
- Les dernières données sont conservées localement : un redémarrage de Home Assistant ne déclenche pas de nouvelle connexion si la dernière a moins de 24 h.
- Les identifiants restent dans Home Assistant et ne figurent jamais dans ce dépôt.

## Installation

1. HACS → menu ⋮ → Dépôts personnalisés → ajouter ce dépôt, type « Intégration ».
2. Installer « e-Protec Kerherve », puis redémarrer Home Assistant.
3. Paramètres → Appareils et services → Ajouter une intégration → « e-Protec ».
4. Ajouter un compte par bénévole.

## Entités (par compte)

| Entité | État en v0.1 |
| --- | --- |
| Connexion (ok / erreur / en_attente) | fonctionnel |
| Dernière synchronisation | fonctionnel |
| Bouton Actualiser | fonctionnel |
| Missions à venir | « inconnu » jusqu'à la v0.2 |
| Prochaine mission | « inconnu » jusqu'à la v0.2 |

## Feuille de route

- **v0.2** : lecture des pages « Calendrier » et « Événements » (missions, lieu, rôle), calendrier par bénévole.
- **v0.3** : formations et échéances de recyclage.
