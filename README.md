# brvm-py

Données de marché de la **Bourse Régionale des Valeurs Mobilières** (BRVM, UEMOA) en Python : cours
des actions, indices, dividendes, fiches des sociétés et fondamentaux. Les données sont **traitées**
(divisions du nominal appliquées, dividendes ramenés au nominal des cours et contrôlés) et mises à
jour chaque jour de séance après la clôture.

```bash
pip install git+https://github.com/DylaneTrader/brvm-py
```

```python
import brvm

brvm.cours("SNTS")                         # Sonatel : ouverture, plus haut, plus bas, clôture, volumes
brvm.cours("ORAC", debut="2025-01-01")     # Orange CI depuis le 1er janvier 2025
brvm.indice("BRVMC")                       # BRVM Composite
brvm.panneau("cloture")                    # une colonne par action
brvm.dividendes("ORAC")                    # dividendes, nets d'IRVM pour un particulier
brvm.dividendes(profil="institutionnel", retenus=True)
brvm.societes()                            # fiches des sociétés
brvm.fondamentaux("SNTS")                  # comptes par exercice
brvm.infos()                               # date de la dernière séance, divisions appliquées…
```

Toutes les fonctions rendent des `pandas.DataFrame`. Les codes s'écrivent comme on veut : `snts`,
`SNTS` ou `SNTS.sn`.

## Les données

| Fonction | Contenu |
|---|---|
| `tickers()` | codes des actions cotées (`SNTS.sn` : code et pays) |
| `cours(ticker, debut, fin)` | une ligne par séance où le titre a échangé ; montants en FCFA |
| `indice(code, debut, fin)` | indices publiés : `BRVMC`, `BRVM30`, `BRVMPR`, indices sectoriels… |
| `indices()` | liste des indices, nom, ISIN, période couverte |
| `panneau(champ, titres)` | un champ de `cours()` pour plusieurs titres, NaN les jours sans échange |
| `seances()` | calendrier des séances (dates du BRVM Composite) |
| `dividendes(ticker, profil, retenus)` | dividendes passés et à venir, par action |
| `societes()`, `societe(ticker)` | nom, ISIN, pays, secteur, titres, flottant, capitalisation, description |
| `fondamentaux(ticker)` | chiffre d'affaires, résultat net, BNPA, dividende par exercice |
| `infos()` | description de l'export |

### Traitements

- **Divisions du nominal** : tout l'historique des cours est exprimé au nominal le plus récent.
  Sonatel, divisée par 10 le 26/10/2026 : les cours d'avant sont divisés par 10, les volumes en
  titres multipliés par 10, les volumes en FCFA inchangés. Les opérations appliquées sont listées
  dans `brvm.infos()["operations_titres"]`.
- **Dividendes au nominal des cours** : un dividende publié avant une division est divisé par son
  rapport, pour pouvoir être comparé aux cours. `montant_publie_fcfa` garde le montant publié et
  `rapport_division` le rapport appliqué.
- **IRVM** : depuis l'exercice 2024, la BRVM publie le dividende brut des titres ivoiriens.
  `montant_net_fcfa` est alors net de 12 % pour un particulier (`profil="particulier"`, par défaut)
  ou de 10 % pour une personne morale (`profil="institutionnel"`). Les autres dividendes sont
  publiés nets : le même montant vaut pour tous.
- **Contrôle des dividendes** : `retenu` est vrai quand le montant est cohérent avec les cours, soit
  au plus 15 % du cours de la veille du détachement, soit au-delà avec une baisse du cours d'au
  moins 60 % du montant ce jour-là, soit après correction vérifiée. `part_du_cours` et
  `baisse_du_jour` donnent les deux mesures. Pour un rendement total, ne créditer que les
  dividendes retenus (`retenus=True`). Un dividende à venir n'est pas encore vérifiable : il n'est
  pas retenu.
- **Fondamentaux** : le PER publié par la source n'est pas fourni, car il est calculé au cours du
  jour de la collecte et n'a donc pas de date. Recalculez-le avec `cours()` et `bnpa_fcfa`.

### Ce qu'il faut savoir sur la BRVM

- Un titre qui n'échange pas un jour n'a pas de ligne ce jour-là. `panneau()` met NaN.
- La variation d'un titre est limitée à ±7,5 % par séance.
- La dernière séance peut être provisoire si les cours ont été relevés avant la clôture :
  `brvm.infos()["derniere_seance_close"]`.

## Cache et configuration

Les fichiers sont téléchargés depuis la branche [`donnees`](https://github.com/DylaneTrader/brvm-py/tree/donnees)
de ce dépôt et gardés dans `~/.cache/brvm-py` pendant une heure. Sans réseau, la dernière copie est
utilisée avec un avertissement.

```python
brvm.configurer(ttl=6 * 3600)              # cache de 6 heures
brvm.configurer(url="/chemin/vers/donnees") # dossier local (une copie de la branche donnees)
brvm.vider_cache()
```

Variables d'environnement : `BRVM_DONNEES` (adresse ou dossier), `BRVM_CACHE`, `BRVM_TTL`.

Les fichiers sont des CSV UTF-8 ordinaires (virgule, point décimal, dates ISO) et se lisent aussi
sans le paquet :

```python
import pandas as pd
pd.read_csv("https://raw.githubusercontent.com/DylaneTrader/brvm-py/donnees/actions/SNTS.sn.csv")
```

## Sources et avertissement

Les données sont collectées sur [Sikafinance](https://www.sikafinance.com) et
[brvm.org](https://www.brvm.org) (avis de paiement des dividendes), puis traitées par
l'application BRVM Analytics. Elles sont fournies telles quelles, sans garantie d'exactitude ni
d'exhaustivité, et ne constituent pas un conseil en investissement. Vérifiez auprès des
publications officielles de la BRVM avant toute décision.

Licence du code : MIT.
