# Phase 1 — HDFS (Scientific Research AI)

## Objectif
Deployer un NameNode et un DataNode en local avec Docker Compose,
conserver leurs donnees dans des volumes Docker et transferer 3 fichiers
JSONL (ACL, PMLR et dataset fusionne) ainsi que 4 PDF scientifiques.

## Prerequis
- Windows 11 avec Docker Desktop (moteur WSL2 Linux demarre)
- Deposer les fichiers deja valides sous `data/`
- Surveiller les ports : l'interface locale utilise **19870** par defaut
- Verifier la RAM : d'autres conteneurs Docker peuvent deja tourner

## Lancement (racine du depot, PowerShell)

```powershell
docker ps --format "table {{.Names}}\t{{.Ports}}"
docker compose -f docker/hdfs/compose.yaml config
docker compose -f docker/hdfs/compose.yaml up -d
docker compose -f docker/hdfs/compose.yaml ps
```

Premiere execution : telechargement d'image Hadoop Apache (plusieurs centaines de Mo)
et formatage initial du NameNode ; le volume de donnees evite un formatage
aux demarrages suivants. Le DataNode peut prendre quelques instants pour s'enregistrer.

Verification :

```powershell
docker compose -f docker/hdfs/compose.yaml exec -T namenode hdfs dfsadmin -report
```

Verifier une ligne `Live datanodes (1)` avant l'import. En cas de soucis :

```powershell
docker compose -f docker/hdfs/compose.yaml logs --tail 80 namenode
docker compose -f docker/hdfs/compose.yaml logs --tail 80 datanode
```

## Import des donnees

```powershell
powershell -ExecutionPolicy Bypass -File scripts/upload_to_hdfs.ps1
```

Le script controle les fichiers locaux, puis les copie via le montage **en lecture seule**
`data/` du projet vers `/project-data` dans le conteneur NameNode. Il ne
supprime aucun PDF ni JSONL local. En sortie, il liste les objets dans HDFS.

## Interface web HDFS

Dans le navigateur : `http://localhost:19870` ; consulter `Datanodes`, puis
`Utilities > Browse the file system` selon la version de l'interface.

## Arret et persistance

```powershell
docker compose -f docker/hdfs/compose.yaml down
```

Les volumes nommes conservent les blocs et les metadonnees HDFS. **Ne pas utiliser
`down -v`**, qui effacerait ces volumes. Le NameNode n'est formaté qu'au premier
lancement avec un volume vide.

## Port deja utilise

Pour changer l'interface HDFS locale (sans changer le conteneur) :

```powershell
$env:HDFS_UI_PORT = '19871'
docker compose -f docker/hdfs/compose.yaml up -d
```

Ne pas exposer cette configuration de laboratoire sur un reseau public :
permissions HDFS desactivees, pas d'authentification. L'interface est liee a
`127.0.0.1` pour rester accessible uniquement sur la machine locale.

## Limites de demonstration

Deux conteneurs sur le meme PC montrent les mecanismes HDFS mais pas
la resistance aux pannes de plusieurs machines physiques. Le facteur de
replication `1` est adapte au laboratoire avec un DataNode, mais n'offre
aucune redondance. La partie Spark viendra ensuite.
