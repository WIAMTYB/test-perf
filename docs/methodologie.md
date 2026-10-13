# Méthodologie des campagnes de performance

Ce document décrit comment les campagnes sont conduites et ce qu'elles mesurent. Il est la
base du chapitre « méthodologie » de l'attestation de performance destinée au régulateur ;
les seuils et les volumes nominaux y seront fixés avec le métier (phase 3).

## Périmètre

Le système sous test est l'API selfcare de la plateforme Titres (`api-titres-selfcare`) et
la chaîne qu'un ordre client traverse : réception, validation et tarification, réservation
d'espèces (PositionMinute) ou de titres (MegaTrade), envoi au broker NTS, visibilité de
l'ordre au marché, annulation. S'y ajoutent les lectures de portefeuille de l'application
mobile : positions valorisées, liste des ordres, comptes, solde espèces.

Hors périmètre : le back-office (api-cargo et son client), les flux post-exécution
(règlement-livraison MegaCustody), l'application mobile elle-même.

## Environnements

Les tirs visent des environnements réels, sans simulateur :

| Environnement | Cluster | Route selfcare | Base |
|---|---|---|---|
| recette | OpenShift ocpdev, espace `recette-titres-selfcare-services` | `recette-api-titres-selfcare-services.apps.ocpdev.attijariwafa.net` | CUSTPPRD (Megara recette) |
| préproduction | OpenShift ocppprd | à confirmer | à confirmer |

Chaque campagne relève l'état de l'environnement avant et après le tir (images et digests,
réplicas, requêtes et limites CPU/mémoire, autoscaling, quota, propriétés montées avec
secrets masqués, paramètres de validation en base) et signale tout changement survenu
pendant le tir. Les partenaires sont ceux de l'environnement : NTS recette, PositionMinute
recette, MegaTrade recette.

## Générateur de charge

Gatling (Java DSL) exécuté depuis un poste de travail, à travers la route publique, comme
l'application mobile : clé API `X-Api-Key`, JSON, une connexion par client virtuel. Les
scénarios sont décrits dans `scenarios.md`. Chaque client virtuel possède un compte client
du pool (`donnees-de-test.md`) et ne passe qu'un ordre à la fois, comme l'API l'impose.

Déterminisme : graine aléatoire fixée (`perf.seed`), feeders circulaires, instruments et
prix de référence relevés au démarrage et consignés dans `campaign.json` avec tous les
paramètres, la version de Gatling et de Java et le commit du dépôt.

## Ce qui est mesuré

1. **Côté client (Gatling)** : pour chaque type de requête, nombre, échecs, min, p50, p75,
   p95, p99, max, moyenne, débit. Le groupe `time-to-submitted` mesure le délai entre l'envoi
   d'un ordre et le moment où le client le voit au marché (statut 105), interrogations
   comprises. Le ledger (`orders-ledger.csv`) garde ce délai exact par ordre.
2. **Dans la plateforme (base de données)** : le temps passé par les ordres de la campagne
   dans chaque état (`ORDER_STATE_HISTORY`), les états finaux, les rejets et leur cause.
3. **Chez les partenaires** : la durée et le statut de chaque appel sortant, tels que la
   plateforme les audite (`BROKER_CALL_AUDIT`, `POSITION_MINUTE_AUDIT`,
   `SECURITY_MOVEMENT_AUDIT`, `CUSTODY_INSTRUCTION_AUDIT`), pour les ordres de la campagne
   et, en comparaison, pour tout le trafic de la fenêtre. Le retard des callbacks du broker
   (`BROKER_EVENT_INBOX`).
4. **Ressources** : métriques Micrometer de chaque pod toutes les 15 s (débit et percentiles
   par route, appels partenaires, pool Oracle HikariCP, CPU, mémoire, jauges de la saga),
   `oc adm top`, file de la saga par état.
5. **Journaux** : avertissements et erreurs des pods pendant la fenêtre, regroupés par message.

Attribution : tous les ordres d'un tir portent `source = PERF` et une référence client
`PERF-<campagne>-<client>-<n°>`. Les appels partenaires sont rattachés par l'identifiant
d'ordre bancaire. Les tables horodatées par l'horloge de la base (audits PositionMinute,
MegaTrade, MegaCustody) sont lues avec le décalage d'horloge mesuré au moment de l'analyse,
consigné dans `analysis.json`.

## Familles de scénarios

| Famille | Question | Modèle |
|---|---|---|
| Smoke | la chaîne fonctionne-t-elle de bout en bout ? | 2 clients, 10 ordres chacun |
| OrderFlow | latence d'un ordre à charge constante | fermé, un client par compte |
| PortfolioRead | tenue des lectures de portefeuille | ouvert, montée puis palier |
| MobileMix | mélange réaliste de l'application mobile, nominal et pointe | ouvert, pondéré |
| CapacityRamp | à quelle charge la prise d'ordres décroche-t-elle ? | ouvert, paliers croissants |
| Soak | dérive sur la durée | mélange nominal, 2 h |
| Spike | reprise après une pointe soudaine | nominal, ×10, nominal |

## Critères et limites

Chaque scénario porte des seuils (`Thresholds.java`) qui font échouer le tir quand ils sont
dépassés. Les valeurs initiales sont des repères issus du comportement actuel de la recette
(temps réception → marché d'environ une seconde) ; elles seront arrêtées avec le métier.

La montée en charge (CapacityRamp) ne porte pas de seuil : le harnais calcule le palier
« coude », premier palier où le p95 réception → marché dépasse le double du premier palier
ou où les échecs dépassent 2 %, et le dossier rapproche ce palier des courbes de ressources
pour nommer le composant saturé (pod orders-worker, pool Oracle, partenaire).

## Sécurité des tirs

Ordres à cours limité à 30 % du cours de référence, validité jour, quantité 1 : dans la
bande de validation, donc envoyés au broker, mais jamais exécutés. Plafond d'ordres par
campagne. Interruption automatique quand la part de 5xx dépasse la limite. Aucun profil
production. Annulation des ordres ouverts en fin de tir ; les réservations laissées chez
les partenaires sont listées dans le dossier.

## Reproductibilité et archivage

Un tir est rejouable avec les mêmes paramètres (`campaign.json`). Le dossier est régénérable
depuis le répertoire du tir. Les répertoires `campaigns/` sont archivés hors git (archive
zip sur l'espace partagé de l'équipe, dépôt Nexus à terme) : ce sont les pièces citées par
l'attestation.
