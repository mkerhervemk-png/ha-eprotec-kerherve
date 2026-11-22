# e-Protec Kerherve

Intégration Home Assistant non officielle pour e-Protec, l'espace bénévole de la Protection Civile. Usage personnel.

## Principes

- **Lecture seule** : aucune inscription ni désinscription à une mission.
- **1 connexion par compte et par 24 h**, à heure fixe. La règle des 24 h concerne le cycle automatique et le démarrage ; le bouton « Actualiser » permet une actualisation manuelle anticipée.
- **Aucune relance automatique** en cas d'échec de connexion.
- Les dernières données (60 jours passés et tout le futur) sont conservées localement : un redémarrage de Home Assistant ne déclenche pas de nouvelle connexion si la dernière a moins de 24 h.
- Les identifiants restent dans Home Assistant et ne figurent jamais dans ce dépôt.

## Installation

1. HACS → menu ⋮ → Dépôts personnalisés → ajouter ce dépôt, type « Intégration ».
2. Installer « e-Protec Kerherve », puis redémarrer Home Assistant.
3. Paramètres → Appareils et services → Ajouter une intégration → « e-Protec ».
4. Ajouter un compte par bénévole.

## Fonctionnement

Une fois par jour, l'intégration se connecte au Portail Protection Civile, ouvre la page « Synchronisation » d'e-Protec et lit l'agenda personnel au format iCal (la fonction officielle « Ajouter un calendrier par URL »). Elle lit ensuite le planning de l'antenne pour compter les places restantes. Quelques requêtes en lecture, rien d'autre.

## Entités (par compte)

| Entité | Contenu |
| --- | --- |
| Calendrier « Missions » | missions et activités de l'agenda personnel |
| Prochaine mission | date de début, avec titre, lieu, description et fin en attributs |
| Missions à venir | nombre, avec la liste en attribut |
| Postes à pourvoir | activités à venir de l'antenne où il reste des places, avec la liste en attribut |
| Calendrier « Activités antenne » | toutes les activités de l'antenne, avec inscrits/places |
| Anniversaires du jour | nombre, noms en attribut |
| Mes participations, Activité de l'antenne | compteurs de l'accueil |
| Heures de formation | heures de l'année en cours |
| Consigne opérationnelle, Actualité | dernier message, date et texte en attributs |
| Veille opérationnelle | personnes d'astreinte (noms et rôle, sans téléphone) |
| Remplacements, Mes activités, Main courante | nombre d'éléments |
| Connexion | ok / erreur / en_attente |
| Dernière synchronisation | horodatage |
| Bouton Actualiser | synchronisation manuelle |

## Feuille de route

- Compétences et échéances de recyclage.
