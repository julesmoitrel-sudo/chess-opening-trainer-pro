# Chess Opening Trainer Pro

Un logiciel de bureau moderne pour **travailler vos ouvertures d'échecs** et
analyser vos parties **après coup**. Base d'ouvertures riche, reconnaissance
des transpositions par position FEN, et **Stockfish en filet de sécurité**
quand la théorie s'arrête.

> ⚠️ **Avertissement fair-play**
> Cette application est un outil d'**entraînement personnel** et d'**analyse
> hors-ligne**. Elle **ne doit pas être utilisée pendant une partie** sur
> Chess.com, Lichess ou toute autre plateforme. Utilisez-la pour préparer vos
> ouvertures, comprendre les idées stratégiques et revoir vos parties.

---

## Fonctionnalités

- Choix Blancs / Noirs et choix de l'ouverture à travailler.
- Saisie des coups en **SAN** (`e4`, `Nf3`, `O-O`) ou **UCI** (`e2e4`).
- **Drag & drop** : déplacez vous-même les pièces de votre adversaire à la souris.
- Reconnaissance des **transpositions** par position FEN.
- Affichage du **coup recommandé**, des **alternatives** théoriques et de
  l'**idée stratégique** de chaque variante.
- Bascule automatique sur **Stockfish** dès la sortie de théorie.
- **Surlignages** dernier coup / coup recommandé / échec / coups légaux.
- Retournement de l'échiquier, retour en arrière, nouvelle partie.
- **Export PGN** automatique d'une partie.
- Détection de fin de partie : échec et mat, pat, nulle.
- Détection automatique de Stockfish + fenêtre **Paramètres** complète.
- Interface **sombre, moderne et premium** en PySide6.

---

## Installation

### Pré-requis
- Python **3.10+**
- (Optionnel mais recommandé) **Stockfish** installé sur votre machine

### Dépendances Python

```bash
pip install -r requirements.txt
```

### Lancer l'application

```bash
python main.py
```

---

## Stockfish

Stockfish est **détecté automatiquement** au lancement. L'application teste
dans cet ordre :

1. la commande `stockfish` dans le `PATH`
2. `stockfish.exe` dans le `PATH`
3. les emplacements classiques :
   - `C:\Stockfish\stockfish.exe`
   - `C:\Program Files\Stockfish\stockfish.exe`
   - `C:\Program Files (x86)\Stockfish\stockfish.exe`
   - `/usr/local/bin/stockfish`
   - `/opt/homebrew/bin/stockfish`
   - `/usr/bin/stockfish`

Pour **vérifier votre installation** depuis un terminal :

```bash
stockfish
```

(tapez `quit` pour sortir).

### Configurer manuellement le chemin

Si Stockfish n'est pas trouvé, ouvrez l'écran **Paramètres** :
- bouton **Parcourir…** pour choisir l'exécutable
- bouton **Tester Stockfish** pour valider la connexion
- le chemin est sauvegardé dans `config.json`

---

## Base d'ouvertures (`openings.json`)

Le fichier `openings.json` contient **19 ouvertures** et **74 variantes**
développées jusqu'aux coups 8 à 16. Vous pouvez l'éditer librement.

Structure d'une ouverture :

```json
{
  "name": "Défense Française",
  "color": "black",
  "eco": "C00-C19",
  "idea": "Construire une chaîne e6-d5 et contre-attaquer avec c5.",
  "variations": [
    {
      "name": "Variante d'avance",
      "moves": ["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6"],
      "idea": "Attaquer la chaîne d4 avec c5 et Qb6.",
      "alternatives": ["Bd7", "f6 Milner-Barry"]
    }
  ]
}
```

### Ajouter une ouverture

1. Ouvrez `openings.json`.
2. Ajoutez un objet dans le tableau `"openings"` avec :
   - `name`, `color` (`"white"` ou `"black"`), `eco`, `idea`,
   - une liste `variations` contenant chacune `name`, `moves` (SAN),
     `idea`, `alternatives`.
3. Sauvegardez et relancez l'application.

### Ajouter une variante à une ouverture existante

Ajoutez un nouvel objet dans le tableau `variations` de l'ouverture concernée.
Les coups sont en notation **SAN**.

---

## Exporter une partie en PGN

- Bouton **Exporter PGN** dans l'écran principal.
- Le fichier est nommé `partie-YYYYMMDD-HHMMSS.pgn`.
- Le dossier de destination est configurable dans **Paramètres** (par défaut :
  votre dossier personnel).

---

## Générer le `.exe` Windows

L'application est prévue pour être empaquetée avec **PyInstaller**.

### Méthode rapide (Windows)

Double-cliquez sur `build_exe.bat`.

### Méthode manuelle

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed ^
    --name chess_opening_trainer_pro ^
    --add-data "openings.json;." ^
    --add-data "config.json;." ^
    --add-data "assets;assets" ^
    main.py
```

L'exécutable est généré dans `dist/chess_opening_trainer_pro/`.

> Sous Linux/macOS, remplacez le séparateur `;` par `:` dans `--add-data`.

---

## Comment utiliser l'application

1. Au lancement, choisissez **Blancs** ou **Noirs** et l'ouverture à travailler.
2. Cliquez sur **Commencer**.
3. Sur l'écran principal :
   - Si c'est à vous : l'application affiche le **coup recommandé** + idée + alternatives.
   - Si c'est à l'adversaire : entrez son coup (champ texte) **ou**
     déplacez la pièce à la souris.
4. À chaque demi-coup :
   - **Dans la théorie** → coup principal + alternatives + idée stratégique.
   - **Sortie de théorie** → bascule sur Stockfish (évaluation + profondeur).
5. Boutons disponibles : **Valider**, **Meilleur coup**, **Retour**,
   **Nouvelle partie**, **Retourner l'échiquier**, **Exporter PGN**,
   **Paramètres**.

---

## Erreurs fréquentes

| Symptôme                                 | Solution                                                                 |
|------------------------------------------|--------------------------------------------------------------------------|
| `ModuleNotFoundError: PySide6`           | `pip install -r requirements.txt`                                        |
| `Stockfish : non configuré`              | Paramètres → Parcourir → choisissez votre binaire `stockfish`            |
| `Coup illégal ou notation invalide`      | Vérifiez la notation (`Nf3`, `O-O`, `e2e4`)                              |
| `openings.json` mal formé                | Validez votre JSON ; l'application reviendra à une base vide sinon       |
| `.exe` qui ne se lance pas               | Lancez-le depuis un terminal pour voir les messages, vérifiez antivirus  |
| `libEGL` manquant sous Linux             | `sudo apt install libegl1 libgl1`                                        |

---

## Structure du projet

```
chess_opening_trainer/
├── main.py                # entrypoint
├── requirements.txt
├── README.md
├── config.json            # paramètres (auto-créé/maj)
├── openings.json          # base d'ouvertures éditable
├── build_exe.bat          # build Windows
├── app/
│   ├── __init__.py
│   ├── ui.py              # fenêtre, écrans, dialogues, style
│   ├── board_widget.py    # échiquier custom + drag & drop
│   ├── engine.py          # détection + wrapper Stockfish (UCI)
│   ├── opening_book.py    # parsing + indexation FEN des ouvertures
│   ├── game_manager.py    # logique de partie + recommandations
│   ├── settings.py        # config.json
│   └── utils.py
└── assets/
    ├── icons/
    ├── pieces/
    └── styles/
```

---

## Fair-play (rappel)

Cet outil est conçu pour **apprendre, comprendre, progresser**. Toute
utilisation pendant une partie en ligne enfreint les conditions d'utilisation
des plateformes (Chess.com, Lichess…) et peut conduire à la fermeture de votre
compte.

Bon entraînement, et bonne route vers de meilleures ouvertures.
