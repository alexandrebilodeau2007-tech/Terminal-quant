"""Configuration centrale du Macro Terminal.

Toutes les valeurs peuvent être surchargées dans le fichier .env à la racine.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # dotenv optionnel
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
WEB_DIR = ROOT / "web"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(os.getenv("PORT", "8787"))
TIMEZONE = os.getenv("TIMEZONE", "America/Toronto")

# Mot de passe optionnel pour protéger le site (recommandé si exposé sur Internet)
APP_TOKEN = os.getenv("APP_TOKEN", "").strip()

# Web Push (notifications iPhone / navigateur)
VAPID_SUB = os.getenv("VAPID_SUB", "mailto:changeme@example.com")

# Alertes
REMINDER_MINUTES = int(os.getenv("REMINDER_MINUTES", "15"))
FAST_POLL_SECONDS = int(os.getenv("FAST_POLL_SECONDS", "5"))
RELEASE_TIMEOUT_MINUTES = int(os.getenv("RELEASE_TIMEOUT_MINUTES", "20"))
WEEK_REFRESH_MINUTES = int(os.getenv("WEEK_REFRESH_MINUTES", "10"))
FF_REFRESH_MINUTES = int(os.getenv("FF_REFRESH_MINUTES", "30"))  # Forex Factory limite les requêtes
NEWS_REFRESH_MINUTES = int(os.getenv("NEWS_REFRESH_MINUTES", "10"))

# Analyse hebdomadaire (dimanche, heure de l'Est)
WEEKLY_DAY = 6          # 0=lundi ... 6=dimanche
WEEKLY_HOUR = int(os.getenv("WEEKLY_HOUR", "17"))

# Sources optionnelles
TE_API_KEY = os.getenv("TE_API_KEY", "").strip()          # Trading Economics (payant) — optionnel
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()  # IA pour l'analyse du dimanche — optionnel
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")

INVESTINGLIVE_FEEDS = [u.strip() for u in os.getenv(
    "INVESTINGLIVE_FEEDS",
    "https://investinglive.com/feed/,https://investinglive.com/feed,https://investinglive.com/rss",
).split(",") if u.strip()]
INVESTINGLIVE_HOME = os.getenv("INVESTINGLIVE_HOME", "https://investinglive.com/")
FINANCIALJUICE_FEED = os.getenv("FINANCIALJUICE_FEED", "https://www.financialjuice.com/feed.ashx?xy=rss")
FJ_REFRESH_SECONDS = int(os.getenv("FJ_REFRESH_SECONDS", "60"))
EXTRA_NEWS_FEEDS = [u.strip() for u in os.getenv(
    "EXTRA_NEWS_FEEDS",
    "https://www.investing.com/rss/news_1.rss,https://www.investing.com/rss/news_95.rss",
).split(",") if u.strip()]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
