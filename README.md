# Pont vocal

Parler avec une session Claude Code depuis son téléphone, comme au téléphone, sans regarder l'écran. Tout tourne en local, sauf le modèle Claude lui-même : le serveur Mumble sur le homelab, le reste sur le PC.

## Comment ça marche

```
Mumla (téléphone) ⇄ WireGuard via le Pi ⇄ serveur Mumble (Pi) ⇄ pont vocal ⇄ session Claude Code
```

1. **Mumla** envoie l'audio du téléphone au serveur Mumble, le service `mumble` du homelab.
2. **Le pont** écoute uniquement l'utilisateur `marc` et attend environ 0,8 seconde de silence pour considérer qu'une phrase est finie.
3. **Whisper** transcrit la phrase en français, sur la carte graphique.
4. **Un canal Claude Code** injecte le texte dans la session.
5. **Claude** répond avec l'outil `reply`. **Voxtral** lit la réponse phrase par phrase dans le casque.

Parler pendant que Claude parle coupe sa voix. Son travail en cours continue, et il sait qu'il a été interrompu.

## Lancer une session

### 1. Le serveur Mumble

Rien à lancer : il tourne sur le homelab et redémarre avec lui. Voir `docs/05-services/mumble.md` dans le dépôt home-lab.

### 2. Lancer Claude depuis le dossier de travail

Dans un vrai terminal, sur le PC :

```bash
cd ~/notes
~/path/to/voice-bridge/claude-vocal.sh
```

Pour reprendre une session existante, depuis son dossier d'origine :

```bash
~/path/to/voice-bridge/claude-vocal.sh --resume <id-de-session>
```

Le script démarre Voxtral s'il ne tourne pas. Son démarrage prend de 1 min 30 à 2 min 30.

Une seule session vocale à la fois : deux sessions prendraient le même nom `claude` dans Mumble et s'éjecteraient mutuellement.

### 3. Accepter l'avertissement

Un écran d'avertissement s'affiche à chaque lancement : choisir **I am using this for local development**.

Il apparaît parce que ce canal est fait maison. Pendant la préversion, Claude Code n'accepte d'office que les canaux de sa liste officielle. L'option lève seulement cette liste : les permissions habituelles restent actives.

Sous la bannière, cette ligne doit s'afficher :

```
Channels (experimental) messages from server:voix
```

### 4. Activer Remote Control, si besoin

Dans la session, taper :

```
/remote-control
```

La voix n'en a pas besoin. Il sert à voir la session sur le téléphone et à valider les permissions depuis l'app Claude. Sans lui, si Claude demande une permission alors que tu es loin du PC, il reste bloqué, et tu n'entends rien.

### 5. Se connecter dans Mumla

Installer Mumla depuis F-Droid, puis ajouter ce serveur :

| Champ | Valeur |
|---|---|
| Adresse | `voice.example.org` |
| Port | `64738` |
| Nom d'utilisateur | `marc` |
| Mot de passe | `MUMBLE_PASSWORD` dans le fichier `.env` |

- **À la maison :** le Wi-Fi suffit.
- **Dehors :** activer WireGuard, qui passe par le Pi.

Une fois Whisper chargé (jusqu'à 40 secondes), on entend **« Je t'écoute »** et l'utilisateur `claude` apparaît.

Pour parler sans être entendu, mettre Mumla en sourdine.

## Pendant que ça tourne

- Utiliser un casque : sinon, le micro capte le haut-parleur et la voix de Claude se coupe toute seule.
- Le PC doit rester branché, capot ouvert : fermer le capot le met en veille.
- Un silence prolongé veut souvent dire que Claude attend une permission : regarder l'app.

## Arrêter

- Quitter la session avec `/exit`.
- Libérer la carte graphique, car Voxtral occupe 12,6 Go de mémoire vidéo tant qu'il tourne :

```bash
~/path/to/voice-bridge/voxtral.sh stop
```

Voxtral et Whisper utilisent ensemble environ 13,9 Go sur 16.

## Commandes utiles

```bash
./voxtral.sh start|stop|status|logs
tail -f logs/voix.log
./run.sh -m pont_vocal.recorder
uv run pytest
```

`logs/voix.log` contient les transcriptions et les messages échangés avec Claude Code, chaque ligne précédée de sa date et de son heure à la milliseconde : il reste sur le PC et n'est pas versionné.

L'enregistreur de diagnostic se connecte au serveur Mumble comme un second auditeur et enregistre ce que le serveur renvoie de la voix de Claude : un fichier `logs/enregistreur/AAAA-MM-JJ/HHMMSS.wav` par réponse, et une ligne par réponse dans `logs/enregistreur/journal.log` (durée, paquets reçus et perdus, plus long trou entre deux paquets). En comparant avec `voix.log`, on sait si un son coupé s'est perdu avant le serveur, côté PC, ou après, entre le serveur et le téléphone. Le lancer pendant les essais, l'arrêter avec Ctrl+C.

## Dépannage

| Symptôme | Piste |
|---|---|
| Pas de « Je t'écoute » | `./voxtral.sh status`, puis `logs/voix.log` |
| Mot de passe refusé dans Mumla | Vérifier les majuscules et les espaces ajoutés par le clavier |
| Claude dit ne pas avoir d'outil vocal | La session n'a pas été lancée avec `claude-vocal.sh` |
| Sa voix se coupe toute seule | Bruit ou écho pris pour de la parole : `interruption` en série dans le journal. Vérifier le casque, ou relever `VOICE_THRESHOLD` dans `.env` |
| Sa voix arrive hachée, sans `interruption` dans le journal | Comparer avec l'enregistreur : si son fichier est complet, le son se perd entre le serveur et le téléphone (réseau mobile, Mumla) |
| Mumla ne se connecte pas | Voir le dépannage de `docs/05-services/mumble.md` dans le dépôt home-lab |

## Installation sur une nouvelle machine

```bash
cp .env.example .env
uv sync
```

Renseigner ensuite `MUMBLE_PASSWORD` dans `.env` : c'est le mot de passe du serveur Mumble du homelab. `mcp.json` contient un chemin absolu vers ce dossier, à adapter si le projet change de place.

## Limites actuelles

- Les permissions ne passent pas par la voix.
- Interrompre Claude coupe sa voix, pas sa tâche.
- La détection de la voix repose sur le volume, donc le vent ou le bruit peuvent la déclencher. L'usage en course n'a pas encore été testé.
- La licence de Voxtral (CC BY-NC 4.0) n'autorise pas un usage commercial.
