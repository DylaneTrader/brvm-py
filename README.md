# brvm-py

Données de marché de la **Bourse Régionale des Valeurs Mobilières** (BRVM, UEMOA) en Python : cours
des actions, indices, dividendes, fiches des sociétés, fondamentaux, rapports publiés par les sociétés
et chiffres lus dans ces rapports. Les données sont **traitées**
(divisions du nominal appliquées, dividendes ramenés au nominal des cours et contrôlés) et mises à
jour chaque jour de séance après la clôture.

```bash
pip install brvm-py
```

Version en développement : `pip install git+https://github.com/DylaneTrader/brvm-py`.

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
brvm.rapports("SNTS", type="etats_financiers")   # rapports publiés sur brvm.org, avec leurs liens
brvm.chiffres("SNTS", periode="A", large=True)   # chiffres lus dans les rapports, une colonne par indicateur
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
| `rapports(ticker, type, exercice, periode)` | rapports publiés sur brvm.org (états financiers, rapports d'activité, annuels, semestriels, des commissaires aux comptes, RSE), avec le lien du PDF |
| `chiffres(ticker, indicateur, exercice, periode, large)` | chiffres lus dans les rapports, en millions de FCFA, annuels, semestriels et trimestriels, avec la page et le lien du document |
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

### Rapports des sociétés

`rapports()` reprend le catalogue des PDF publiés par chaque société cotée sur brvm.org : type,
exercice, période (`A` annuel, `S1` premier semestre, `T1`, `T3`, `T4` trimestres), statut (`audite`,
`provisoire`), date de publication et lien.

`chiffres()` donne les indicateurs lus dans les tableaux de ces PDF (chiffre d'affaires ou produit net
bancaire, résultats, total du bilan, capitaux propres, dépôts et crédits de la clientèle, coût du
risque, flux de trésorerie…), ramenés en millions de FCFA. Seules les lectures fiables sont publiées :

- contrôle `concordant` (chiffre d'affaires ou résultat net annuel égal à 2 % près à celui de
  Sikafinance) ou `non_controle` (pas de référence pour cet indicateur ou cette période) ; les
  écarts, les colonnes supposées, les unités inconnues et les montants en dollars (Ecobank
  Transnational) sont écartés ;
- unité annoncée par le document ou calée sur Sikafinance ; une unité estimée par ordre de grandeur
  est écartée, comme tout chiffre d'un document en écart et tout montant sous 1 million de FCFA ;
- une valeur par société, exercice, période et indicateur : la lecture concordante l'emporte, puis
  celle du document audité, puis la plus récente ; un chiffre dont les lectures divergent de plus de
  1 % est écarté. `lectures` compte les documents qui le donnent.

Les montants infra-annuels sont ceux publiés, en général cumulés depuis le début de l'exercice. Les
chiffres viennent d'une lecture automatique : `page` et `url` permettent de vérifier chacun d'eux dans
le PDF.

### Ce qu'il faut savoir sur la BRVM

- Un titre qui n'échange pas un jour n'a pas de ligne ce jour-là. `panneau()` met NaN.
- La variation d'un titre est limitée à ±7,5 % par séance.
- La dernière séance peut être provisoire si les cours ont été relevés avant la clôture :
  `brvm.infos()["derniere_seance_close"]`.

## API web (JSON statique)

Les mêmes données traitées sont publiées en JSON sur GitHub Pages, sans serveur ni clé :
`https://dylanetrader.github.io/brvm-py/`. Elles sont régénérées chaque jour de séance, après la
clôture, par le workflow `.github/workflows/api.yml`.

```js
fetch("https://dylanetrader.github.io/brvm-py/v1/cours/SNTS.sn.json")
  .then(r => r.json())
  .then(t => console.log(t.colonnes, t.lignes.at(-1)));
```

| Adresse | Contenu |
|---|---|
| `index.json` | liste des points d'accès, des codes et date de dernière séance |
| `v1/infos.json`, `v1/tickers.json`, `v1/seances.json` | description de l'export, codes des actions, calendrier |
| `v1/cours/{ticker}.json` | cours d'une action (ex. `SNTS.sn`) |
| `v1/indices.json`, `v1/indices/{code}.json` | liste des indices, valeurs d'un indice (ex. `BRVMC`) |
| `v1/dividendes.json`, `v1/dividendes/{ticker}.json` | dividendes, avec les montants nets des deux profils |
| `v1/societes.json`, `v1/societes/{ticker}.json` | fiches des sociétés |
| `v1/fondamentaux.json`, `v1/fondamentaux/{ticker}.json` | comptes par exercice |
| `v1/rapports.json`, `v1/rapports/{ticker}.json` | catalogue des rapports des sociétés, avec les liens |
| `v1/chiffres.json`, `v1/chiffres/{ticker}.json` | chiffres lus dans les rapports, en millions de FCFA |

Les tables ont la forme `{"colonnes": [...], "lignes": [[...], ...]}`, avec des dates ISO et `null`
pour les valeurs manquantes. Les adresses sont fixes : le filtrage par date se fait chez le client.
Les en-têtes CORS de GitHub Pages permettent l'appel depuis un navigateur.

Pour publier votre propre copie : activer GitHub Pages avec la source « GitHub Actions » dans les
réglages du dépôt, puis lancer le workflow. Pour générer les fichiers en local :
`python -m brvm.api --donnees chemin/vers/donnees --sortie site`.

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
[brvm.org](https://www.brvm.org) (avis de paiement des dividendes, rapports des sociétés), puis traitées par
l'application BRVM Analytics. Elles sont fournies telles quelles, sans garantie d'exactitude ni
d'exhaustivité, et ne constituent pas un conseil en investissement. Vérifiez auprès des
publications officielles de la BRVM avant toute décision.

Licence du code : MIT.
