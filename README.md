# titres-trading-performance-tests

Campagnes de performance de la plateforme de trading Titres, côté client : prise d'ordres
par l'API selfcare (`api-titres-selfcare`), suivi de l'ordre jusqu'au marché (broker NTS),
annulation, et les lectures de portefeuille que fait l'application mobile autour d'un ordre.

Les tirs visent un environnement réel (recette, puis préproduction) dans une fenêtre de
maintenance déclarée. Les partenaires (NTS, PositionMinute, MegaTrade, MegaCustody) sont
sollicités au travers de la plateforme, jamais simulés : chaque campagne mesure où passe la
latence et à quelle charge chaque composant ou partenaire sature.

Chaque tir produit un dossier HTML autonome (`campaigns/<env>/<horodatage>-<scénario>/dossier.html`)
avec le rapport Gatling, l'état de l'environnement, le temps par étape de la saga, la latence
par appel partenaire, les métriques des pods et les journaux. C'est la matière de l'attestation
de performance demandée par le régulateur.

## Prérequis sur le poste

- JDK 21 ou 25 (`JAVA_HOME`), Maven 3.9 (`mvn`, ou `PERF_MVN` dans `.env` vers le binaire)
- Python 3.11+ avec `pip install -r harness/requirements.txt` (python-oracledb thin, sans client Oracle)
- `oc` connecté au cluster cible (`oc whoami` répond), variables `HTTP_PROXY`/`HTTPS_PROXY` absentes ou
  ignorées (le harnais les retire pour chaque appel `oc`)
- Accès réseau à la route selfcare de l'environnement et à CUSTPPRD (172.31.147.56:2016)
- Un fichier `.env` à la racine, copié de `.env.example` : clé API client, clé API métriques, compte Oracle.
  Création des clés : `docs/exploitation.md`.

## Lancer une campagne

```bash
python harness/campaign.py run --env recette --scenario Smoke --campaign SMOKE-20261015A --cancel-all
```

Le harnais enchaîne : contrôles préalables, snapshot de l'environnement, échantillonnage des
métriques, `mvn gatling:test`, snapshot de fin, journaux, analyse en base, dossier, puis
annulation des ordres restés ouverts. Les scénarios et leurs paramètres : `docs/scenarios.md`.

Exemples :

```bash
python harness/campaign.py run --env recette --scenario OrderFlow --campaign RCT-OF-01 --duration PT10M --pace 5
python harness/campaign.py run --env recette --scenario PortfolioRead --campaign RCT-PR-01 --duration PT10M --target-rate 10
python harness/campaign.py run --env recette --scenario CapacityRamp --campaign RCT-CAP-01 --target-rate 0.5 --levels 8 --max-orders 3000
python harness/campaign.py analyze --run-dir campaigns/recette/20261015-1030-Smoke      # ré-analyse d'un tir archivé
python harness/campaign.py cleanup --campaign SMOKE-20261015A                           # dry run ; --yes pour supprimer
```

Un identifiant de campagne (`[A-Z0-9-]{4,24}`) ne sert qu'une fois : tous les ordres du tir portent
`source = PERF` et une référence client `PERF-<campagne>-<client>-<n°>`, ce qui les rend attribuables
dans `ORDERS` et dans les tables d'audit des partenaires.

## Garde-fous

- Seules les routes `*.apps.ocpdev.attijariwafa.net` et `*.apps.ocppprd.attijariwafa.net` sont acceptées ;
  il n'existe pas de profil production.
- Ordres à cours limité à 30 % du dernier cours (dans la bande de 35 %), validité jour, quantité 1 :
  ils reposent dans le carnet et ne s'exécutent pas.
- Plafond d'ordres par campagne (`limits.maxOrdersPerCampaign`, 500), fichier `ABORT` posé par le
  harnais quand la part de réponses 5xx dépasse la limite, refus de démarrer si l'identifiant a déjà
  servi ou si les soumissions sont en pause.
- Le nettoyage en base est refusé tant qu'un ordre n'est pas terminal ou qu'une réservation est
  encore active chez un partenaire.

## Arborescence

```
src/test/java/com/attijariwafa/titres/perf/   simulations Gatling (Java DSL)
src/test/resources/profiles/                   recette.properties, preprod.properties (sans secret)
data/<env>/accounts.csv, instruments.csv       comptes clients et instruments du tir
harness/campaign.py, harness/perf/, harness/sql/   harnais Python : snapshot, métriques, analyse, dossier
docs/                                          méthodologie, scénarios, données de test, exploitation
campaigns/                                     sorties des tirs (hors git ; à archiver)
```

Documentation : `docs/methodologie.md`, `docs/scenarios.md`, `docs/donnees-de-test.md`, `docs/exploitation.md`.
