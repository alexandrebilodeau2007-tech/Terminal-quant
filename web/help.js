/* Aide « Comment l'utiliser » : une fiche par onglet (touches, effet, usage dans une thèse). */
const TAB_NAMES = {accueil:"ACCUEIL",semaine:"SEMAINE",calendrier:"CALENDRIER",fiches:"FICHES",nouvelles:"NOUVELLES",macro:"MACRO",
  devises:"DEVISES",graphiques:"GRAPHIQUES",force:"FORCE FX",taux:"TAUX BC",positions:"POSITIONS",saison:"SAISONNALITÉ",alertes:"ALERTES"};

const HELP = {
  accueil: {
    but: "Le résumé du marché en un coup d'œil : la semaine, les prochaines annonces, les derniers chiffres, le ton des banques centrales, le positionnement et les nouvelles. Mis à jour toutes les 20 secondes.",
    touches: [
      ["ANALYSE →", "Ouvre l'onglet SEMAINE (analyse complète de la semaine)."],
      ["CALENDRIER →", "Ouvre le calendrier économique complet."],
      ["Badge BON / MAUVAIS", "Dans « Derniers chiffres » : le chiffre réel comparé au consensus est bon ou mauvais pour la devise."],
      ["Carte d'une banque centrale", "Ouvre la fiche de la devise dans DEVISES (taux, inflation, ton, données clés)."],
      ["MACRO →", "Ouvre le tableau macro comparatif de tous les pays."],
      ["DÉTAIL → (sentiment, divergences, positionnement)", "Ouvre la bonne section de l'onglet POSITIONS : retail, comparatif ou institutionnel."],
      ["TOUT →", "Ouvre le fil de nouvelles complet."],
      ["Une nouvelle", "Ouvre l'article dans un nouvel onglet."],
    ],
    these: ["Point de départ chaque matin : quel est le régime (risk-on ou risk-off), quel catalyseur arrive, quelle surprise vient de sortir.",
      "Les divergences retail vs institutionnels donnent des idées de paires à creuser, pas des entrées."],
  },
  semaine: {
    but: "L'analyse de la semaine, limitée aux annonces 🔴 et 🟠. Générée automatiquement le dimanche à 17 h.",
    touches: [
      ["↻ RÉGÉNÉRER", "Recalcule l'analyse avec le calendrier à jour (utile après un ajout d'annonce)."],
      ["Rouges / Orange", "Nombre d'annonces à impact élevé et moyen dans la semaine."],
      ["Cartes par devise", "Triées par charge de la semaine (rouge compte triple). Le badge montre le ton de la banque centrale ; la liste donne chaque annonce avec consensus et précédent."],
      ["Liste de la semaine", "Toutes les annonces. Touche une ligne pour le détail : spécifications, historique en graphique, et 📘 ta fiche si elle existe."],
    ],
    these: ["Repère les catalyseurs de chaque devise de ta paire et note leur date dans ton plan.",
      "Évite d'ouvrir une position juste avant une annonce 🔴 sur une des deux devises, sauf si c'est le pari."],
  },
  calendrier: {
    but: "Le calendrier économique façon Forex Factory, à l'heure de l'Est, avec le chiffre réel en direct.",
    touches: [
      ["Hier · Aujourd'hui · Demain · Cette semaine · Sem. prochaine · Sem. passée · Ce mois", "Choisit la période affichée."],
      ["Recherche", "Filtre par nom d'événement, devise ou catégorie (ex. « CPI », « JPY »)."],
      ["FILTRES ▴ / ▾", "Montre ou cache les filtres."],
      ["MASQUER PASSÉS", "Cache les annonces déjà publiées."],
      ["RÉINIT.", "Remet tous les filtres par défaut (cette semaine, impact élevé et moyen, toutes les devises)."],
      ["↻", "Force une mise à jour depuis les sources."],
      ["IMPACT", "🔴 élevé, 🟠 moyen, 🟡 faible, ⚪ jour férié. Touche pour ajouter ou retirer."],
      ["TYPE D'ÉVÉNEMENT", "Croissance, inflation, emploi, banque centrale, etc. TOUS coche ou décoche tout."],
      ["DEVISE", "Garde seulement les devises choisies. TOUTES coche ou décoche tout."],
      ["Une ligne", "Ouvre le détail : source, ce que l'indicateur mesure, effet habituel, prochaine publication, historique."],
      ["Colonnes", "Réel (vert = bon pour la devise, rouge = mauvais) · Prév. = consensus · Préc. = chiffre précédent · TE = prévision Trading Economics (si configurée) · Écart = réel − consensus."],
      ["Ligne en surbrillance", "La prochaine annonce, avec le compte à rebours."],
    ],
    these: ["Le prix réagit à la surprise par rapport au consensus, pas au chiffre seul (Niveau 2, Calendrier économique avancé).",
      "Regarde aussi le précédent : une révision peut annuler une bonne surprise."],
  },
  fiches: {
    but: "Tes fiches de triche sur les indicateurs économiques, classées en indicateurs avancés et retardés.",
    touches: [
      ["Recherche", "Cherche dans tout le contenu des fiches (ex. « inflation », « logement », « BLS »)."],
      ["Une carte", "Ouvre la fiche : pays, temporalité, croissance ou inflation, publication, fréquence, importance, explication, fonctionnement, quoi regarder."],
      ["📆 sur une carte", "L'indicateur sort cette semaine, avec la date et l'heure."],
      ["🔥", "Importance pour le marché."],
      ["VOIR LA FICHE ORIGINALE", "Affiche l'image de la fiche d'origine."],
    ],
    these: ["Avant une annonce, relis « Ce qu'il faut regarder » : la composition compte souvent plus que le titre."],
  },
  nouvelles: {
    but: "Le fil de nouvelles en direct de FinancialJuice, InvestingLive et Investing.com. Mis à jour toutes les 20 secondes.",
    touches: [
      ["TOUT / une devise", "Garde les nouvelles qui mentionnent cette devise ou son pays (recherche par mots-clés)."],
      ["Sources", "Toutes ou une seule source."],
      ["HAWK / DOVE", "Étiquette automatique sur les titres liés aux banques centrales ou à l'inflation. Elle repose sur des mots-clés : vérifie toujours le titre."],
      ["Trait orange à gauche", "Nouvelle de moins de 15 minutes."],
      ["Un titre", "Ouvre l'article."],
    ],
    these: ["Cherche ce qui peut changer le pricé d'une banque centrale : discours, fuites, données surprises."],
  },
  macro: {
    but: "Le tableau macro comparatif : une ligne par devise, le dernier chiffre de chaque grand indicateur. Le positionnement est maintenant dans l'onglet POSITIONS.",
    touches: [
      ["En-tête de colonne", "Trie par cet indicateur. Touche encore pour inverser (▲ / ▼)."],
      ["Case verte / rouge", "Le dernier chiffre a battu ou raté le consensus, du point de vue de la devise."],
      ["Garder le doigt sur une case", "Affiche la période et le chiffre précédent."],
      ["+25pb dans Taux directeur", "Dernier mouvement de la banque centrale."],
      ["Ton BC", "Hawkish (vers des hausses), neutre ou dovish (vers des baisses), calculé automatiquement."],
      ["« t/t »", "Inflation trimestrielle, affichée quand le pays ne publie pas de chiffre annuel mensuel (Nouvelle-Zélande)."],
      ["Une ligne", "Ouvre la fiche de la devise."],
      ["OUVRIR POSITIONS →", "Ouvre l'onglet POSITIONS."],
    ],
    these: ["Classe chaque pays selon la croissance et l'inflation, puis cherche la paire où une banque est hawkish et l'autre dovish (Niveau 2, divergences de politique monétaire)."],
  },
  devises: {
    but: "Une carte par devise, puis une fiche détaillée : ton de la banque centrale, taux, inflation, données clés, graphique et nouvelles.",
    touches: [
      ["Une carte", "Ouvre la fiche de la devise."],
      ["Jauge DOVISH → HAWKISH", "Score du ton, calculé avec les décisions de taux, l'inflation par rapport à la cible et le ton des nouvelles récentes. Chaque composante est détaillée sous la jauge."],
      ["Données clés", "Derniers chiffres publiés (réel, consensus, précédent)."],
      ["À venir", "Annonces 🔴 / 🟠 de la semaine. Touche une ligne pour le détail."],
      ["Signaux de ton", "Nouvelles des 14 derniers jours étiquetées hawkish ou dovish."],
      ["← TOUTES LES DEVISES", "Revient à la grille."],
    ],
    these: ["Le score est automatique : il donne une direction, mais lis le dernier communiqué de la banque centrale avant de conclure."],
  },
  graphiques: {
    but: "Des graphiques en direct, de 1 à 8 à la fois, avec les moyennes mobiles lissées 50 et 200.",
    touches: [
      ["Modèle", "Choisit un jeu de symboles prédéfini (Devises, Croisées, Taux et pétrole, Macro) ou un de tes modèles."],
      ["Disposition", "1, 2, 4, 6 ou 8 graphiques."],
      ["Unité de temps", "5 min à semaine, pour tous les graphiques."],
      ["💾", "Enregistre la disposition et les symboles actuels comme modèle perso."],
      ["⛶", "Plein écran. ✕ ou Échap pour sortir."],
      ["Case du symbole", "Tape un symbole (ex. CADJPY) pour changer ce graphique."],
      ["⤢", "Agrandit ce graphique."],
      ["Couleurs", "Chandelles grises = hausse, orange = baisse. Pastille verte = données en direct."],
    ],
    these: ["Sers-t'en pour le timing seulement : la direction vient de la macro (Niveau 1, analyse multi-timeframe)."],
  },
  force: {
    but: "La force relative des 8 devises majeures, en direct, et leur performance sur différentes périodes.",
    touches: [
      ["TD · TW · 8H · 1D · 5D · 7D · 1M", "Fenêtre de la courbe de force : depuis l'ouverture du jour (TD), de la semaine (TW), ou sur 8 heures à 1 mois."],
      ["Courbe de force", "En points de base ; 0 = moyenne du panier. Une devise au-dessus monte contre les autres. Mise à jour toutes les 10 s."],
      ["Périodes (performance)", "Change la période du tableau et de la matrice."],
      ["Paires majeures", "Variation de chaque paire sur la période."],
      ["Matrice", "Ligne = devise de base, colonne = devise cotée : la case donne la variation de la paire."],
    ],
    these: ["Une thèse est plus solide quand la devise que tu achètes est déjà parmi les plus fortes et celle que tu vends parmi les plus faibles."],
  },
  taux: {
    but: "Ce que le marché pricé pour chaque banque centrale : probabilité de hausse, de statu quo ou de baisse à chaque réunion, déduite des contrats à terme sur taux.",
    touches: [
      ["Une devise", "Choisit la banque centrale."],
      ["Cartes du haut", "Prochain mouvement le plus probable, sa probabilité, la variation attendue en points de base, le taux actuel et la date de la réunion."],
      ["Distribution des scénarios", "Hausse, statu quo, baisse pour la prochaine réunion."],
      ["Tableau Réunions", "Taux implicite et probabilités à chaque réunion à venir."],
      ["Courbe à terme", "Trajectoire de taux attendue (vert) comparée à celle d'il y a une semaine (rouge pointillé)."],
      ["RBA, RBNZ, BoJ", "Pas de contrats à terme accessibles gratuitement : seules les dates de réunion s'affichent."],
    ],
    these: ["C'est « le pricé » du Niveau 2. Une donnée fait bouger la devise seulement si elle change ces probabilités.",
      "Une courbe qui monte par rapport à la semaine dernière = le marché devient plus hawkish."],
  },
  positions: {
    but: "Qui est acheteur et qui est vendeur, en trois sections : RETAIL (traders particuliers), INSTITUTIONNEL (banques, fonds, hedge funds, flux de capitaux) et COMPARATIF.",
    touches: [
      ["👥 RETAIL", "% long / short des traders particuliers par paire (Myfxbook), nombre de positions, prix moyen d'entrée, et lecture contrarienne quand 65 % ou plus sont du même côté."],
      ["🏦 INSTITUTIONNEL", "Trois tableaux : flux quotidiens (prix + intérêts ouverts), positionnement COT par catégorie, et flux de capitaux officiels (section Devises)."],
      ["Devises · Indices · Taux · Matières premières", "Dans INSTITUTIONNEL : choisit la classe d'actifs."],
      ["Flux quotidiens", "Prix ↑ + OI ↑ = nouveaux acheteurs ; prix ↓ + OI ↑ = nouveaux vendeurs ; prix ↑ + OI ↓ = rachat de shorts ; prix ↓ + OI ↓ = liquidation de longs."],
      ["COT par catégorie", "Pour chaque groupe : barre % long / short, position nette, variation sur la semaine. Indice 6 m / 1 an : 0 = position la plus courte de la période, 100 = la plus longue ; au-delà de 90 ou sous 10 = extrême."],
      ["Flux de capitaux officiels", "Achats de titres par les investisseurs étrangers et nationaux (Japon hebdo, États-Unis TIC, Canada, Suisse). Soutien = entrée de capitaux pour la devise ; pression = sortie."],
      ["⚖ COMPARATIF", "Retail, hedge funds et asset managers côte à côte, dans le sens de la paire. Une divergence (retail ≥ 60 % d'un côté, hedge funds de l'autre) donne un biais contrarien."],
    ],
    these: ["Le positionnement est une confluence, pas une entrée (Niveau 2, chapitre VI).",
      "Hedge funds dans ton sens sans extrême = confirmation. Hedge funds à un extrême dans ton sens = risque de rachat.",
      "Le COT date du mardi et sort le vendredi 15 h 30 : vérifie la date affichée."],
  },
  saison: {
    but: "La saisonnalité d'un actif, façon Seasonax : son parcours moyen dans l'année et le rendement d'une fenêtre de dates, année par année.",
    touches: [
      ["Actif", "Choisit le symbole."],
      ["Années", "Nombre d'années d'historique (5 à 25)."],
      ["MM-JJ → MM-JJ", "Fenêtre à tester (ex. 11-21 → 12-21)."],
      ["ANALYSER", "Lance le calcul."],
      ["Cartes de la fenêtre", "Rendement moyen, médian, % d'années gagnantes, meilleure et pire année."],
      ["Graphiques", "Courbe saisonnière moyenne vs année en cours, rendement moyen par mois, rendement de la fenêtre par année."],
    ],
    these: ["Une confluence de plus, jamais une raison seule de prendre un trade (Niveau 2, Saisonnalité)."],
  },
  alertes: {
    but: "Les notifications sur ton téléphone et l'état du serveur.",
    touches: [
      ["Sur iPhone", "Les notifications fonctionnent seulement si le site est installé : Partager → Sur l'écran d'accueil, puis ouvre l'app depuis l'écran d'accueil."],
      ["ACTIVER LES NOTIFICATIONS", "Demande la permission et abonne cet appareil."],
      ["ENVOYER UN TEST", "Envoie une notification de test."],
      ["DEVISES / IMPACT", "Choisit les devises et les impacts (🔴, 🟠) qui déclenchent une alerte."],
      ["TYPES", "Rappel avant l'annonce, chiffre réel dès sa sortie, banquiers centraux en direct, analyse du dimanche."],
      ["NOUVELLES", "Une notification par nouvelle, par source. FinancialJuice publie beaucoup."],
      ["ENREGISTRER", "Sauvegarde tes préférences sur le serveur."],
      ["Sentiment retail", "Connexion Myfxbook de secours, si la page publique est bloquée."],
      ["État du serveur", "Dernière mise à jour, sources en erreur, options activées."],
    ],
    these: ["Active au minimum le rappel avant et le chiffre réel pour les devises de tes trades ouverts."],
  },
};

function openHelp(v){
  const h=HELP[v]; if(!h) return;
  const d=document.createElement("div"); d.className="modal";
  d.innerHTML=`<div class="panel mbox"><div class="ph"><b>❓ Comment utiliser ${esc(TAB_NAMES[v]||v)}</b><div class="r"><button class="chip" data-x>✕</button></div></div>
    <div class="pb help"><h4>À QUOI ÇA SERT</h4><p>${esc(h.but)}</p>
    <h4>CHAQUE TOUCHE</h4><table class="spec">${h.touches.map(([k,t])=>`<tr><th>${esc(k)}</th><td>${esc(t)}</td></tr>`).join("")}</table>
    <h4>POUR TA THÈSE</h4><ul>${h.these.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div></div>`;
  d.onclick=e=>{ if(e.target===d||e.target.closest("[data-x]")) d.remove(); };
  document.body.appendChild(d);
}
function currentView(){ return (document.querySelector(".view.on")?.id||"v-accueil").slice(2); }
function syncHelp(){ const v=currentView(); const t=document.getElementById("helpTab"); if(t) t.textContent=TAB_NAMES[v]||v.toUpperCase(); }
document.getElementById("helpBtn").addEventListener("click",()=>openHelp(currentView()));
document.getElementById("tabs").addEventListener("click",()=>setTimeout(syncHelp,0));
window.addEventListener("hashchange",()=>setTimeout(syncHelp,0));
syncHelp();
window.openHelp=openHelp; window.syncHelp=syncHelp;
