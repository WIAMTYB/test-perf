# Données de test

## Comptes clients : `data/<env>/accounts.csv`

| Colonne | Rôle |
|---|---|
| `secaccount` | compte titres (10 chiffres), `clientSecAccount` de l'ordre |
| `cashaccount` | compte espèces (`\d{6}[A-Z]\d{9}`), `clientCashAccount` de l'ordre |
| `label` | libellé libre |
| `cashBudgetMad` | espèces disponibles au moment du relevé (information, non utilisé par le code) |
| `sellIsins` | ISIN en position pour les ventes, séparés par `|` |
| `enabled` | `true` pour inclure le compte dans le pool |

Un client virtuel possède un compte et ne passe qu'un ordre à la fois : l'API verrouille le
couple compte + ISIN le temps de la réservation (HTTP 409 sinon). Le nombre de comptes
activés est donc le nombre maximal de clients simultanés des modèles fermés (OrderFlow).

**Contrat du pool** (à établir avec l'équipe plateforme et PositionMinute) : chaque compte
doit couvrir `ordres par compte × NET_CLIENT × 2`, où la réservation `NET_CLIENT` vaut
brut + frais + marge de couverture de 30 % ; avec quantité 1 et un cours limite à 70 % du
cours de référence, un ordre réserve environ 1,3 × 0,7 × cours. Pour les ventes, des
positions sur les `sellIsins`.

Le pool actuel de recette (quatre comptes ayant déjà passé des ordres) suffit au smoke et à
un premier OrderFlow ; il doit être étendu et approvisionné avant les montées en charge.
Un rejet `REJECTED_NO_CASH` est signalé en bandeau dans le dossier : c'est un pool à
réapprovisionner, pas une limite de la plateforme.

## Instruments : `data/<env>/instruments.csv`

`isin,symbol,tickSize,enabled`. Au démarrage d'une simulation, `InstrumentCatalog` lit
`/tradableasset/v2/listforxcastrade` et retient, parmi les instruments activés, ceux qui
ont un cours de référence (`price`, cours de clôture Megara) ; un instrument sans cours est
écarté (l'ordre passerait la validation mais le broker le refuserait). Les instruments
retenus et leur cours sont consignés dans `campaign.json`.

## Prix

`LimitPriceStrategy` : achat à `cours × (1 − 30 %)`, vente à `cours × (1 + 30 %)`, arrondi
au pas de cotation vers le cours de référence, deux décimales. La bande de validation est
de 35 % (`orders.validation.price-band-percent`) : l'ordre passe la validation, part au
broker et repose dans le carnet sans s'exécuter. Un tir à prix exécutable
(`orders.priceOffsetPercent=0`) est une campagne distincte, approuvée par le métier, car il
déclenche des exécutions et le règlement-livraison réel.

## Attribution

- `source = PERF` sur tous les ordres (valeur du profil, vérifiée par `EnvGuard`).
- `clientReference = PERF-<campagne>-<client>-<n°>` ; l'index unique `ORDERS_UK2`
  (source + référence client) garantit l'unicité, et `cleanup`/`analyze` retrouvent les
  ordres par ce préfixe.
- Les appels partenaires sont rattachés par `BANK_ORDER_ID` (NTS) ou par le code
  d'opération des réservations (= identifiant d'ordre bancaire, PositionMinute et MegaTrade).

## Ce qu'un tir laisse derrière lui

- Des ordres `SUBMITTED` au broker recette, validité jour. `cancel-all` envoie un
  `ORDERCANCEL` pour chacun ; le broker recette ne renvoie pas de `ORDER_CANCELLED` pour un
  ordre en file, l'ordre reste donc `SUBMITTED` en base et sa **réservation espèces reste
  active chez PositionMinute** jusqu'à un événement de clôture. Le dossier liste ces
  réservations (section « Réservations laissées ») ; dimensionner le pool pour le pire cas.
- Des lignes d'audit (évidence du tir). Le nettoyage en base (`cleanup --yes`) n'est fait
  qu'avant une campagne formelle qui exige des tables propres, et seulement quand tous les
  ordres sont terminaux et qu'aucune réservation n'est active.
