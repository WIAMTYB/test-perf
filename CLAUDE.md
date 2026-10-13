# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

Gatling (Java DSL, Maven) performance campaigns against the selfcare trading API
(`api-titres-selfcare`, sibling repository), plus a Python harness that wraps every run
with an environment snapshot, per-pod metrics sampling, a database analysis of the
campaign's orders and partner calls, and a self-contained French HTML dossier. Campaigns
target real environments (recette, then preprod) in declared maintenance windows and go
through the real partners (NTS broker, PositionMinute, MegaTrade, MegaCustody). The admin
BFF and client are out of scope. Documentation is in French under `docs/`.

## Commands

```bash
mvn test                                   # compiles simulations, runs the few JUnit tests (surefire excludes simulations)
python -m unittest discover -s harness/tests -t harness
python harness/campaign.py run --env recette --scenario Smoke --campaign SMOKE-20261015A --cancel-all
python harness/campaign.py analyze|dossier|logs|cancel-all --run-dir campaigns/recette/<run>
python harness/campaign.py cleanup --campaign <id> [--yes]
mvn gatling:test -Dgatling.simulationClass=com.attijariwafa.titres.perf.simulations.SmokeSimulation -Dperf.env=recette -Dperf.campaignId=X -Dperf.runDir=<dir>
```

On this workstation Maven is the wrapper distribution under `~/.m2/wrapper/dists/apache-maven-3.9.9`
(set `PERF_MVN` in `.env`) and the JDK is GraalVM 25; the code compiles with `release 21`.

## Layout and conventions

- `src/test/java/com/attijariwafa/titres/perf/`: `config` (PerfConfig resolution order: `-Dperf.*` > `PERF_*` env > `.env` > `profiles/<env>.properties`; `EnvGuard` host allowlist, `source=PERF`, campaign id `[A-Z0-9-]{4,24}`), `data` (account pool, instrument catalog with live reference prices, limit price strategy, campaign references), `protocol`, `actions` (one request chain per endpoint, named after `Thresholds` constants), `scenarios`, `simulations`, `support` (ledger, abort guard, campaign context, workloads, thresholds).
- Every `-Dperf.*` must be declared in the pom (`<properties>` and the plugin `systemProperties`) to reach the simulation JVM.
- Orders: `source=PERF`, `clientReference=PERF-<campaignId>-<user>-<seq>`, limit price 30 % from the reference (inside the 35 % band, never fills), Day validity, quantity 1. The poll reads `/xcastrade/v2/listorders`; status `105` = at market; JSON keys of that endpoint are Oracle column labels, read in both cases.
- `harness/perf/`: `config`, `oc` (proxies cleared on every call), `snapshot`, `promtext` + `sampler` (scrape via `oc exec python3`, key on stdin), `db` + `analysis` + `sql/*.sql` (binds `:prefix`, `:start_ts`, `:end_ts`), `logs`, `svg` + `dossier`, `cancel`, `cleanup`. Audit tables stamped by the DB clock (`POSITION_MINUTE_AUDIT`, `SECURITY_MOVEMENT_AUDIT`, `CUSTODY_INSTRUCTION_AUDIT`) get a window shifted by the measured DB clock offset.
- Secrets only in `.env` (git-ignored) or the environment; never print them, never commit `tokens-*.sql`.
- `campaigns/` is git-ignored output; a run is `campaigns/<env>/<yyyyMMdd-HHmm>-<scenario>/`.

## Facts about the platform the code relies on

See `../api-titres-selfcare/CLAUDE.md` for the saga. Key points: booking is serialised per account + ISIN (HTTP 409), `SUBMITTED` is written at submission (no callback needed for status 105), the recette broker never sends `ORDER_CANCELLED` for queued orders (holds stay active), `/actuator/prometheus` needs an API key authorized on that path, Gatling groups are reported by duration (`useGroupDurationMetric`).
