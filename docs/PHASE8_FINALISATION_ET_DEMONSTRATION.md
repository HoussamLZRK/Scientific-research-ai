# Scientific Research AI — Finalisation (Phase 8)

## Ce qui est livré

- `app_final.py` : interface Streamlit finale. Le **menu Choisir une page de l’application est visible en haut du corps principal**, même si la barre latérale est fermée. Les cinq sections sont Vue d’ensemble, Assistant scientifique, Graph Analytics, Explorateur de corpus et Évaluation : protocole.
- `scripts/evaluation_phase8.py` : compare réellement la récupération BM25, hybride BM25+FAISS et GraphRAG Neo4j sur les mêmes questions, mêmes `top-k` et `candidates-k`. Ne crée ni embeddings, ni nouvelles arêtes dans Neo4j.
- `data/evaluation/questions_phase8.json` : six questions pilotes, dont trois références **provisoires tirées des extraits connus**, non validées par un annotateur humain. Trois questions exploratoires, aucune vérité de terrain inventée.
- `tests/test_evaluation_phase8.py` et `tests/test_app_final_navigation.py` : tests hors ligne.

**Ne pas écraser les anciens scripts** : cette mise à jour réutilise ceux déjà installés (`scripts/streamlit_phase7_backend.py`, `scripts/rag_classique_phase6.py`, `scripts/rag_hybride_phase6a2.py`, `scripts/rag_semantique_faiss_phase6a1.py`, `scripts/graphrag_phase6b.py`).

## Installation

1. Décompresser le ZIP dans `C:\Users\houss\Documents\Scientific-research-ai`. Fusionner `scripts`, `tests`, `docs`, `data` avec les dossiers existants.
2. Ouvrir PowerShell à la racine du projet et exécuter :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_evaluation_phase8.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_app_final_navigation.py" -v
```

3. Tester rapidement **une question, sans génération de texte** :

```powershell
.\.venv\Scripts\python.exe scripts/evaluation_phase8.py --max-questions 1 --top-k 3 --candidates-k 6
```

Le script te demandera le mot de passe Neo4j invisiblement ; ne le copie ni dans le code ni dans le compte rendu. La première question est celle sur BGM/GTR. Un fichier `data/reports/evaluation_phase8.json` sera créé.

4. Pour l'évaluation pilote complète sur 6 questions (avec services Ollama et Neo4j actifs) :

```powershell
.\.venv\Scripts\python.exe scripts/evaluation_phase8.py --top-k 3 --candidates-k 6
```

Alternative de dépannage si Neo4j est temporairement arrêté :

```powershell
.\.venv\Scripts\python.exe scripts/evaluation_phase8.py --skip-graph --max-questions 2
```

Cette dernière commande ne permet **pas** de conclure sur GraphRAG.

5. Démarrer l'interface finale (arrêter l'ancien Streamlit avec Ctrl+C auparavant) :

```powershell
.\.venv\Scripts\python.exe -m streamlit run app_final.py
```

Ouvrir l'URL locale que Streamlit affiche (habituellement http://localhost:8501). En haut de la page : **Choisir une page de l’application**. Sélectionner Assistant scientifique ou Évaluation : protocole. Pour GraphRAG, renseigner le secret Neo4j dans la barre latérale `Connexion Neo4j`.

6. Si l'écran affiche encore l'ancienne interface, vérifier l'URL et que la commande indique bien `app_final.py`, et utiliser `Ctrl+F5` dans le navigateur. Ne pas lancer simultanément `app.py`, `app_phase7.py` et `app_final.py` sur le même port.

## Choix méthodologiques

- Les **6 questions** sont un *benchmark pilote*, pas un benchmark validé.
- Les **3 références provisoires** proviennent de passages identifiés dans les précédents tests (ACL). Inspecter ces passages dans l'Explorateur de corpus et dans le PDF avant de changer `reference_status` de `provisional` à `human_verified`.
- Ne pas attribuer des références arbitraires aux questions HAL / PMLR / PLOS. Pour mesurer des performances, il faut d'abord déterminer les chunks pertinents à l'aide du texte original, éventuellement plusieurs références par question, et les ajouter dans `reference_chunk_ids`.
- `Precision@k`, `Recall@k`, `Hit@k` et `MRR@k` sont calculés uniquement pour les questions avec des références renseignées ; le rapport sépare `human_verified` et `provisional`.
- `Hit@3` ne dit rien sur la **fidélité d'une réponse générée**. Si tu exécutes `--generate`, les réponses et citations sont enregistrées mais **aucun score de fidélité n'est inventé**. Une grille d'annotation humaine doit être réalisée.
- Graph Analytics n'est pas une analyse de citations entre articles ni une preuve de collaboration scientifique. Les `SRAIAuthorMention` sont des occurrences d'auteur, pas des auteurs désambiguïsés ; les entités scientifiques de Neo4j portent la mention `LEXICAL_ONLY`.
- Neo4j ne contient actuellement que 9 chunks enrichis sur 263 (résultat d'exécution antérieur) ; le graphe peut donc avoir un effet réduit, voire nul, pour plusieurs questions.

## Rapport automatique

`data/reports/evaluation_phase8.json` contient :

- Pour chaque méthode, les réussites et erreurs, temps moyen, nombre de chunks et diversité de documents.
- Pour chaque question, les identifiants des chunks retrouvés et les métriques sur références provisoires/vérifiées, si disponibles.
- Pour GraphRAG, le nombre d'entités reconnues et de chunks apportés par Neo4j.
- Un contrôle **de cohérence** des rapports Graph Analytics existants : somme des nœuds, somme des relations, concordance `HAS_CHUNK`, etc.

Le programme sauvegarde aussi les erreurs par question : une panne Ollama/Neo4j ne sera jamais affichée comme succès.

## Démonstration conseillée en 3 minutes

1. **Vue d'ensemble** : expliquer 13 publications métadonnées crawlées, 4 PDF indépendants, 263 chunks. Ne pas inventer de liens entre les 13 publications et les 4 PDF.
2. **Explorateur de corpus** : consulter un passage ACL page 7, montrer l'origine PDF.
3. **Assistant scientifique** : question `How does BGM improve retrieval compared with GTR?`, choisir BM25 puis hybride puis GraphRAG, top-k=3, `reranking` désactivé d'abord. Activer `Générer une réponse` seulement si Ollama répond rapidement.
4. **Graph Analytics** : visualiser les vrais liens `HAS_CHUNK` et `MENTIONS_ENTITY`. Préciser que ce sont des mentions, pas des relations causales démontrées.
5. **Évaluation : protocole** : afficher **le rapport réellement exécuté**, les temps et indicateurs ; insister sur la faiblesse du benchmark et les références provisoires.

## Avant le dépôt GitHub

```powershell
git status
git add app_final.py scripts/evaluation_phase8.py tests/test_evaluation_phase8.py tests/test_app_final_navigation.py data/evaluation/questions_phase8.json docs/PHASE8_FINALISATION_ET_DEMONSTRATION.md
git commit -m "feat: final Streamlit navigation and transparent RAG evaluation"
git push origin main
```

Contrôler `git status` avant d'ajouter d'autres fichiers. **Ne jamais committer** de mot de passe Neo4j, de `.env` contenant des secrets, ou les poids Ollama. Le rapport d'évaluation peut être conservé comme artefact de soutenance après vérification, sans secrets.
