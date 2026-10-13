# Scénarios

Toutes les simulations se lancent par le harnais (`python harness/campaign.py run --scenario <nom> ...`)
ou directement par Maven (`mvn gatling:test -Dgatling.simulationClass=com.attijariwafa.titres.perf.simulations.<nom>Simulation -Dperf.env=recette -Dperf.campaignId=... -Dperf.runDir=...`).

## Requêtes élémentaires (`actions/`)

| Nom dans le rapport | Requête | Vérification |
|---|---|---|
| `book` | `POST /xcastrade/book`, ordre à cours limité reposant, `source=PERF` | HTTP 200 (ou 409 = verrou compte+ISIN occupé, compté à part) ; `returnCode` 0/200 sinon échec |
| `poll-order` (groupe `time-to-submitted`) | `GET /xcastrade/v2/listorders` filtré sur la référence client, toutes les 500 ms, jusqu'au statut 105/106/107/102/103 ou 20 s | statut final ≠ 102 ; sinon l'itération est en échec |
| `cancel` | `POST /xcastrade/cancel` | HTTP 200, `returnCode` 0/200 |
| `listvalued-hot` | `GET /position/listvalued` sur le compte du client (cache 60 s) | 200/204 |
| `listvalued-cold` | `GET /position/listvalued` sur un couple de comptes du pool (clé de cache distincte) | 200/204 |
| `listorders` | `GET /xcastrade/v2/listorders?take=50` | 200/204 |
| `secaccounts` | `GET /secaccount/getbycashaccounts` | 200/204 |
| `tradableassets` | `GET /tradableasset/v2/listforxcastrade` | 200 |
| `cash-balances` | `POST /cash/balances` (appel synchrone PositionMinute) | 200, `returnCode` 0 |

## Simulations

| Simulation | Modèle de charge | Paramètres (`--option` du harnais / `-Dperf.*`) | Seuils initiaux |
|---|---|---|---|
| `Smoke` | 2 clients, 10 ordres chacun, 2 s entre deux ordres | aucun | tous les `book` OK ; `time-to-submitted` max < 10 s |
| `OrderFlow` | fermé : un client par compte du pool pendant `duration`, un ordre toutes les `pace` secondes | `--duration PT10M`, `--pace 5`, `--users N`, `--side SELL`, `--cancel` | `book` p95 < 500 ms, p99 < 1 s ; `time-to-submitted` p95 < 3 s, p99 < 5 s ; échecs < 1 % |
| `PortfolioRead` | ouvert : montée vers `targetRate` écrans/s (2 min) puis palier ; 45 % listvalued chaud, 20 % froid, 25 % listorders, 10 % comptes | `--duration`, `--target-rate 10` | listvalued chaud p95 < 1 s, froid p95 < 5 s ; listorders p95 < 1 s ; 5xx = 0 |
| `MobileMix` | ouvert : listvalued 40 %, listorders 20 %, actifs 15 %, comptes 10 %, solde 5 %, ordre 10 % ; `nominal` 5 req/s, `peak` 25 req/s (repères provisoires) | `--profile nominal|peak`, `--target-rate`, `--duration` | p95 par requête ; échecs < 1 % |
| `CapacityRamp` | ouvert sur la prise d'ordres : paliers de +`targetRate` ordres/s, 2 min chacun, 30 s de rampe, `levels` paliers | `--target-rate 0.5`, `--levels 8`, `--max-orders 3000` (obligatoire : le plafond par défaut de 500 arrête la rampe) | pas de seuil ; coude calculé par le harnais |
| `Soak` | mélange nominal pendant `duration` (référence : 2 h) + 1 ordre/min | `--duration PT2H` | échecs < 2 % ; dérive p95 premier/dernier quart d'heure, HikariCP en attente, mémoire : lus dans le dossier |
| `Spike` | nominal 3 min, ×10 pendant 2 min, nominal 5 min | aucun | échecs < 2 % ; temps de retour du p95 sous le niveau nominal : lu dans le dossier |

Les seuils sont centralisés dans `support/Thresholds.java` et seront révisés avec le métier (phase 3).

## Lecture du rapport Gatling

- Temps en millisecondes ; pour les groupes, c'est la **durée du groupe** qui est affichée et
  assertée (`gatling.charting.useGroupDurationMetric`), donc, pour `time-to-submitted`, le délai
  réception → marché vu du client, attentes comprises.
- Un `book` en 409 n'est pas un échec : l'API sérialise les ordres d'un même compte et ISIN.
  Le dossier en donne le nombre ; au-delà de 0,5 % le pool de comptes est trop petit pour le débit demandé.
- Un ordre terminé en 102 (rejeté) met l'itération en échec et apparaît dans la section Rejets
  du dossier avec sa cause (`fail_reason_code`).
