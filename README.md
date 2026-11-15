# Macro Terminal

Ton terminal macro personnel : il tourne sur ta tour et tu l'ouvres sur ton iPhone comme une app, avec des notifications push.

## Ce qu'il fait

| Section | Contenu |
|---|---|
| **Semaine** | Chaque dimanche à 17 h (heure de l'Est), l'analyse de la semaine à venir, **orange et rouge seulement**. Tu y trouves les catalyseurs majeurs, un résumé par devise et la liste complète des annonces. Une notification t'avertit quand elle est prête. |
| **Calendrier** | Les annonces 🔴/🟠 des 9 devises, en heure de l'Est : **réel, consensus, précédent**, TE Forecast si configuré, et l'écart coloré selon l'effet sur la devise. |
| **Nouvelles** | Le fil **FinancialJuice** (mis à jour chaque minute), avec InvestingLive et Investing.com. Tu peux filtrer par devise et par source. Les titres hawkish/dovish sont marqués et ceux de moins de 15 min sont surlignés. |
| **Devises** | Une fiche par devise (USD, EUR, GBP, JPY, CAD, AUD, NZD, CHF, CNY). Elle montre le **ton de la banque centrale (Hawkish / Neutre / Dovish)** avec le détail du calcul, le taux directeur et les mouvements sur 12 mois, l'inflation et la core par rapport à la cible, les données clés, les annonces à venir, les nouvelles et un graphique. |
| **Graphiques** | **4 graphiques par page**, sur 6 pages : DXY et chaque devise contre le USD, croisées, taux 10 ans (US, Allemagne, R.-U.) et pétrole, et une page macro (or, argent, S&P 500, VIX). |
| **Saisonnalité** | Le même principe que Seasonax : la courbe saisonnière moyenne comparée à l'année en cours, les stats par mois (moyenne, médiane, % d'années positives) et l'analyse d'une **fenêtre de dates** (ex. 03-01 → 04-15) année par année. |
| **Alertes** | Tu choisis les devises, l'impact (rouge/orange) et le type de notification : rappel X min avant, chiffre réel à la sortie, analyse du dimanche. |

**Exemple de notification à la sortie d'un chiffre :**
```
🔴 🇺🇸 USD Non Farm Payrolls : 165K ▲
Réel 165K · Consensus 65K · Préc. 60K
Au-dessus du consensus (+100K) → lecture brute positif pour le USD
```

## Sources de données

- **TradingView (calendrier)** : c'est la base pour les heures, le consensus, le précédent et surtout le **chiffre réel**. C'est gratuit et sans clé. Le serveur interroge la source toutes les 5 secondes à l'heure de la publication.
- **Forex Factory** : fournit la couleur des dossiers (rouge/orange) et ajoute les annonces absentes de TradingView, comme les discours.
- **Trading Economics** : optionnel, il faut une clé API payante (`TE_API_KEY`). Il ajoute le *TE Forecast*.
- **FinancialJuice** : les manchettes, mises à jour chaque minute. C'est le flux RSS public, qui n'est pas une API officielle, donc il peut changer. Le squawk audio n'est pas inclus.
- **InvestingLive** (et Investing.com en complément) : les nouvelles par devise et le ton hawkish/dovish.

> ⚠️ **Fourchette min/max du consensus :** aucune de ces sources ne la publie de façon structurée (elle vient des sondages Bloomberg/Reuters, payants). Le terminal affiche donc consensus, précédent, réel et TE Forecast.
>
> Le **ton hawkish/dovish** est un indicateur calculé : dernière décision, mouvements sur 12 mois, inflation vs cible et ton des titres récents. Chaque composante est affichée pour que tu juges toi-même.

---

## Installation sur ta tour (Windows)

1. Installe **Python 3.11 ou plus récent** depuis python.org (coche « Add Python to PATH »).
2. Décompresse le dossier `macro-terminal`, par exemple dans `C:\macro-terminal`.
3. Double-clique sur **`START_TERMINAL.bat`**. La première fois, il installe tout (2-3 min). Ensuite il redémarre tout seul s'il plante.
4. Ouvre **http://localhost:8787** sur la tour pour vérifier que tout s'affiche.
5. Ouvre le fichier `.env`, qui a été créé automatiquement, et remplis au minimum :
   - `VAPID_SUB=mailto:ton.courriel@gmail.com` (Apple l'exige pour les notifications)
   - `APP_TOKEN=un-mot-de-passe` (le site sera accessible sur Internet)

   Puis ferme et relance `START_TERMINAL.bat`.

**Démarrage automatique avec Windows :** appuie sur `Win + R`, tape `shell:startup`, puis place un raccourci de `START_TERMINAL.bat` dans ce dossier. Tu peux aussi l'ajouter à ton `START_ALL.bat`.

## Rendre le site accessible à ton iPhone (HTTPS obligatoire)

Les notifications iPhone exigent une adresse **https** qui **ne change pas**. La solution gratuite la plus simple est **Tailscale Funnel** :

1. Installe **Tailscale** sur la tour (tailscale.com) et connecte-toi.
2. Dans la console d'administration Tailscale, active **HTTPS** (DNS → HTTPS Certificates) et autorise **Funnel**.
3. Dans un terminal sur la tour :
   ```
   tailscale funnel --bg 8787
   ```
4. Il t'affiche une adresse du genre `https://ta-tour.tailxxxx.ts.net`. C'est l'adresse de ton terminal, et elle ne changera pas.

> Évite les liens temporaires `trycloudflare.com` : l'adresse change à chaque redémarrage et tes notifications cesseraient de fonctionner. Si tu as un nom de domaine, un *Cloudflare Tunnel nommé* fonctionne aussi.

## Installer l'app sur l'iPhone (iOS 16.4 ou plus)

1. Ouvre l'adresse `https://…ts.net` dans **Safari**.
2. Touche **Partager** (carré avec une flèche), puis **Sur l'écran d'accueil**.
3. Ouvre l'app **Macro** depuis l'écran d'accueil. Entre ton mot de passe si demandé.
4. Va dans **Alertes**, puis **Activer les notifications**, puis **Autoriser**.
5. Touche **Envoyer un test** : tu devrais recevoir la notification.

Ça fonctionne aussi sur Android, et sur un ordinateur avec Chrome, Edge ou Safari.

## Options

| Variable `.env` | Effet |
|---|---|
| `REMINDER_MINUTES=15` | Délai du rappel avant chaque annonce |
| `WEEKLY_HOUR=17` | Heure de l'analyse du dimanche |
| `ANTHROPIC_API_KEY` | Ajoute une analyse rédigée par IA le dimanche (1 appel par semaine, quelques cents). Sans clé, l'analyse automatique (sans IA) est utilisée. |
| `TE_API_KEY` | Ajoute le TE Forecast de Trading Economics |

## Structure

```
server/   API + moteur d'alertes (Python / FastAPI)
web/      Site PWA (HTML/CSS/JS) + service worker pour les notifications
data/     Cache, abonnements, analyses hebdo (créé automatiquement)
tests/    Tests hors ligne : python tests/test_core.py
```

## Dépannage

- **Pas de notification sur iPhone** : vérifie que l'app est ouverte depuis l'écran d'accueil (pas dans Safari), que `VAPID_SUB` contient un vrai courriel, et que l'adresse https n'a pas changé.
- **« Sources en erreur »** dans l'onglet Alertes : un site est temporairement inaccessible. Le cache est utilisé en attendant.
- **Saisonnalité vide** : Yahoo Finance limite parfois les requêtes. Réessaie plus tard (le serveur bascule sur Stooq en secours).
