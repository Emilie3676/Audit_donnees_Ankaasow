import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

np.random.seed(42)
random.seed(42)

NB_USERS = 100
NB_DEMANDES = 250
SEC_PAR_JOUR = 86400

communes = ['Ouagadougou', 'Bobo-Dioulasso', 'Koudougou', 'Kaya', 'Ziniaré']
referentiel = {
    'Ouagadougou':    {'province': 'Kadiogo',    'region': 'Centre'},
    'Bobo-Dioulasso': {'province': 'Houet',      'region': 'Hauts-Bassins'},
    'Koudougou':      {'province': 'Boulkiemdé', 'region': 'Centre-Ouest'},
    'Kaya':           {'province': 'Sanmatenga', 'region': 'Centre-Nord'},
    'Ziniaré':        {'province': 'Oubritenga', 'region': 'Plateau-Central'},
}

statuts_pro = ['Fonctionnaire', 'Salarié(e)', 'Indépendant(e)', 'Chômeur/Chômeuse']
situations = ['Célibataire', 'Marié(e)', 'Divorcé(e)', 'Veuf/Veuve']

professions_libres = [
    'Instituteur / Enseignant', 'Secrétaire de direction', 'Commerçant',
    'Chauffeur', 'Infirmier / Agent de santé', 'Entrepreneur indépendant',
    'Agent de sécurité', 'Comptable', 'Artisan (Menuisier/Maçon)', "Fonctionnaire d'État"
]

TYPES_LOGEMENT_OFFICIELS = [
    'Sociale', 'Économique', "Appui à l'Autoconstruction", 'Coopérative de logement'
]

print("Génération du script de simulation affiné pour ANKAASOW...")

# 1. TABLE users
users = []
for user_id in range(1, NB_USERS + 1):
    users.append({
        'user_id': user_id,
        'uuid_hash': f'usr_{random.randint(100000, 999999)}',
        'profession': np.random.choice(professions_libres),
        'tranche_revenu': random.choice(['< 50k', '50k-150k', '150k-300k', '> 300k']),
        'commune': np.random.choice(communes, p=[0.45, 0.25, 0.15, 0.1, 0.05]),
        # vrai datetime, avec heure aléatoire (181 jours en secondes)
        'created_at': datetime(2025, 1, 1) + timedelta(seconds=random.randint(0, 181 * SEC_PAR_JOUR - 1)),
        # la date de naissance reste en texte (on y injecte des dates impossibles plus bas)
        'date_naissance': (datetime(1960, 1, 1) + timedelta(days=random.randint(0, 14000))).strftime('%Y-%m-%d'),
        'telephone': f'+226 {random.randint(50000000, 79999999)}',
    })
df_users = pd.DataFrame(users)

# 2. TABLE demande_logements
rng_ds07 = np.random.default_rng(7)
demandes = []
for demande_id in range(1, NB_DEMANDES + 1):
    user_associe = random.choice(users)
    date_soumission_base = datetime(2026, 1, 1) + timedelta(seconds=random.randint(0, 91 * SEC_PAR_JOUR - 1))
    type_log = np.random.choice(TYPES_LOGEMENT_OFFICIELS, p=[0.4, 0.3, 0.2, 0.1])
    statut_actuel_final = np.random.choice(
        ['validee', 'rejetee', 'active', 'attente', 'correction_demandee'],
        p=[0.4, 0.2, 0.2, 0.1, 0.1]
    )
    demandes.append({
        'demande_id': demande_id,
        'reference_dossier': f'ANK-2026-{demande_id:04d}',
        'user_id': user_associe['user_id'],
        'type_logement': type_log,
        'statut_actuel': statut_actuel_final,
        'date_soumission': date_soumission_base,      # plus de strftime
        'statut_professionnel': rng_ds07.choice(statuts_pro),
        'situation_matrimoniale': rng_ds07.choice(situations),
        'revenu_mensuel': int(rng_ds07.integers(20000, 600000))
    })
df_demandes = pd.DataFrame(demandes)
df_demandes = df_demandes.merge(df_users[['user_id', 'commune']], on='user_id', how='left')
df_demandes['province'] = df_demandes['commune'].map(lambda c: referentiel[c]['province'])
df_demandes['region']   = df_demandes['commune'].map(lambda c: referentiel[c]['region'])

# 3. TABLE demande_statut_histories
historique = []

def avancer(date, jmin, jmax):
    """Ajoute jmin à jmax jours + une heure aléatoire dans la journée."""
    return date + timedelta(days=random.randint(jmin, jmax),
                            seconds=random.randint(0, SEC_PAR_JOUR - 1))

def ajouter(demande_id, precedent, nouveau, date, agent):
    historique.append({
        'id': len(historique) + 1,
        'demande_id': demande_id,
        'statut_precedent': precedent,
        'nouveau_statut': nouveau,
        'created_at': date,
        'agent_id': agent
    })

for _, demande in df_demandes.iterrows():
    d_id = demande['demande_id']
    date_courante = demande['date_soumission']     
    type_logement = demande['type_logement']
    statut_cible = demande['statut_actuel']

    ajouter(d_id, 'brouillon', 'soumise', date_courante, None)

    date_courante = avancer(date_courante, 1, 2)
    ajouter(d_id, 'soumise', 'attente', date_courante, None)

    # Le dossier reste en attente : l'historique s'arrête ici
    if statut_cible == 'attente':
        continue

    risque_correction = 0.35 if type_logement in ["Coopérative de logement", "Appui à l'Autoconstruction"] else 0.15

    if statut_cible == 'correction_demandee' or random.random() < risque_correction:
        date_courante = avancer(date_courante, 2, 5)
        ajouter(d_id, 'attente', 'non_conforme', date_courante, random.randint(10, 15))

        date_courante = avancer(date_courante, 5, 15)
        ajouter(d_id, 'non_conforme', 'correction_demandee', date_courante, None)

        # Le dossier finit ici si c'est son statut actuel
        if statut_cible == 'correction_demandee':
            continue

        # Sinon l'usager corrige, et le dossier repart en attente
        date_courante = avancer(date_courante, 2, 6)
        ajouter(d_id, 'correction_demandee', 'attente', date_courante, None)

    # Dossier conforme
    date_courante = avancer(date_courante, 2, 4)
    ajouter(d_id, 'attente', 'conforme', date_courante, random.randint(10, 15))

    facteur_geo = 1.8 if demande['commune'] == 'Ouagadougou' else 1.0
    facteur_type = 1.5 if type_logement == 'Coopérative de logement' else 1.0
    delai_instruction = int(np.random.gamma(shape=3, scale=3) * facteur_geo * facteur_type) + 3

    date_courante = avancer(date_courante, delai_instruction, delai_instruction)
    dernier_statut = 'rejetee' if statut_cible == 'rejetee' else 'validee'
    ajouter(d_id, 'conforme', dernier_statut, date_courante, random.randint(10, 15))

    if statut_cible == 'active':
        date_courante = avancer(date_courante, 5, 12)
        ajouter(d_id, 'validee', 'active', date_courante, random.randint(10, 15))

df_historique = pd.DataFrame(historique)

# On garde les données propres intactes, et on abîme des COPIES
dem = df_demandes.copy()
usr = df_users.copy()

# --- injection d'anomalies ---
lignes = dem.sample(n=20).index
dem.loc[lignes, 'commune'] = np.nan

lignes = dem.sample(n=15).index
dem.loc[lignes, ['region', 'province', 'commune']] = 'undefined'

ouaga = dem[dem['commune'] == 'Ouagadougou'].sample(n=10).index
dem.loc[ouaga, 'province'] = 'Houet'

lignes = usr.sample(n=4).index
usr.loc[lignes, 'date_naissance'] = '2090-05-12'

lignes = usr.sample(n=2).index
usr.loc[lignes, 'date_naissance'] = '1850-01-01'

# doublons de demandeurs
doublons = usr.sample(n=5).copy()
doublons['user_id'] = range(NB_USERS + 1, NB_USERS + 6)
doublons['uuid_hash'] = [f'usr_{random.randint(100000, 999999)}' for _ in range(5)]
usr = pd.concat([usr, doublons], ignore_index=True)

variantes_prof = {
    'Instituteur / Enseignant': ['Enseignant', 'instituteur', 'Prof'],
    'Commerçant': ['commercant', 'COMMERÇANT', 'Commerce'],
    'Chauffeur': ['chauffeur ', 'Chauffeur routier'],
}
for i in usr.index:
    profession = usr.loc[i, 'profession']
    if profession in variantes_prof and rng_ds07.random() < 0.5:
        usr.loc[i, 'profession'] = rng_ds07.choice(variantes_prof[profession])

variantes_statut = {
    'Fonctionnaire':    ['fonctionnaire', "Fonctionnaire d'État", "Agent de l'État"],
    'Salarié(e)':       ['Salarié', 'Salariée', 'salarie'],
    'Indépendant(e)':   ['Indépendant', 'Indépendante', 'independant'],
    'Chômeur/Chômeuse': ['Chômeur', 'Chômeuse', 'chomeur'],
}
variantes_situation = {
    'Célibataire': ['celibataire', 'Célibataire '],
    'Marié(e)':    ['marie', 'Marié', 'Mariée'],
    'Divorcé(e)':  ['divorce', 'Divorcé', 'Divorcée'],
    'Veuf/Veuve':  ['veuf', 'Veuve'],
}
for i in dem.index:
    s = dem.loc[i, 'statut_professionnel']
    if s in variantes_statut and rng_ds07.random() < 0.5:
        dem.loc[i, 'statut_professionnel'] = rng_ds07.choice(variantes_statut[s])

    m = dem.loc[i, 'situation_matrimoniale']
    if m in variantes_situation and rng_ds07.random() < 0.5:
        dem.loc[i, 'situation_matrimoniale'] = rng_ds07.choice(variantes_situation[m])

print("Professions différentes (users) :", usr['profession'].nunique())
print("Statuts différents (demandes) :", dem['statut_professionnel'].nunique())
print("Situations différentes (demandes) :", dem['situation_matrimoniale'].nunique())

# --- export ---
usr.to_csv('users_simules.csv', index=False, encoding='utf-8')
dem.to_csv('demande_logements_simulees.csv', index=False, encoding='utf-8')
df_historique.to_csv('demande_statut_histories_simulees.csv', index=False, encoding='utf-8')

df_users.to_csv('ref_users_propres.csv', index=False, encoding='utf-8')
df_demandes.to_csv('ref_demandes_propres.csv', index=False, encoding='utf-8')

print("Colonnes dem :", len(dem.columns), "| Colonnes usr :", len(usr.columns))
print("Fichiers CSV écrits.")

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

np.random.seed(42)
random.seed(42)

NB_USERS = 100
NB_DEMANDES = 250
SEC_PAR_JOUR = 86400

communes = ['Ouagadougou', 'Bobo-Dioulasso', 'Koudougou', 'Kaya', 'Ziniaré']
referentiel = {
    'Ouagadougou':    {'province': 'Kadiogo',    'region': 'Centre'},
    'Bobo-Dioulasso': {'province': 'Houet',      'region': 'Hauts-Bassins'},
    'Koudougou':      {'province': 'Boulkiemdé', 'region': 'Centre-Ouest'},
    'Kaya':           {'province': 'Sanmatenga', 'region': 'Centre-Nord'},
    'Ziniaré':        {'province': 'Oubritenga', 'region': 'Plateau-Central'},
}

statuts_pro = ['Fonctionnaire', 'Salarié(e)', 'Indépendant(e)', 'Chômeur/Chômeuse']
situations = ['Célibataire', 'Marié(e)', 'Divorcé(e)', 'Veuf/Veuve']

professions_libres = [
    'Instituteur / Enseignant', 'Secrétaire de direction', 'Commerçant',
    'Chauffeur', 'Infirmier / Agent de santé', 'Entrepreneur indépendant',
    'Agent de sécurité', 'Comptable', 'Artisan (Menuisier/Maçon)', "Fonctionnaire d'État"
]

TYPES_LOGEMENT_OFFICIELS = [
    'Sociale', 'Économique', "Appui à l'Autoconstruction", 'Coopérative de logement'
]

print("Génération du script de simulation affiné pour ANKAASOW...")

# 1. TABLE users
users = []
for user_id in range(1, NB_USERS + 1):
    users.append({
        'user_id': user_id,
        'uuid_hash': f'usr_{random.randint(100000, 999999)}',
        'profession': np.random.choice(professions_libres),
        'tranche_revenu': random.choice(['< 50k', '50k-150k', '150k-300k', '> 300k']),
        'commune': np.random.choice(communes, p=[0.45, 0.25, 0.15, 0.1, 0.05]),
        # vrai datetime, avec heure aléatoire (181 jours en secondes)
        'created_at': datetime(2025, 1, 1) + timedelta(seconds=random.randint(0, 181 * SEC_PAR_JOUR - 1)),
        # la date de naissance reste en texte (on y injecte des dates impossibles plus bas)
        'date_naissance': (datetime(1960, 1, 1) + timedelta(days=random.randint(0, 14000))).strftime('%Y-%m-%d'),
        'telephone': f'+226 {random.randint(50000000, 79999999)}',
    })
df_users = pd.DataFrame(users)

# 2. TABLE demande_logements
rng_ds07 = np.random.default_rng(7)
demandes = []
for demande_id in range(1, NB_DEMANDES + 1):
    user_associe = random.choice(users)
    date_soumission_base = datetime(2026, 1, 1) + timedelta(seconds=random.randint(0, 91 * SEC_PAR_JOUR - 1))
    type_log = np.random.choice(TYPES_LOGEMENT_OFFICIELS, p=[0.4, 0.3, 0.2, 0.1])
    statut_actuel_final = np.random.choice(
        ['validee', 'rejetee', 'active', 'attente', 'correction_demandee'],
        p=[0.4, 0.2, 0.2, 0.1, 0.1]
    )
    demandes.append({
        'demande_id': demande_id,
        'reference_dossier': f'ANK-2026-{demande_id:04d}',
        'user_id': user_associe['user_id'],
        'type_logement': type_log,
        'statut_actuel': statut_actuel_final,
        'date_soumission': date_soumission_base,      # plus de strftime
        'statut_professionnel': rng_ds07.choice(statuts_pro),
        'situation_matrimoniale': rng_ds07.choice(situations),
        'revenu_mensuel': int(rng_ds07.integers(20000, 600000))
    })
df_demandes = pd.DataFrame(demandes)
df_demandes = df_demandes.merge(df_users[['user_id', 'commune']], on='user_id', how='left')
df_demandes['province'] = df_demandes['commune'].map(lambda c: referentiel[c]['province'])
df_demandes['region']   = df_demandes['commune'].map(lambda c: referentiel[c]['region'])

# 3. TABLE demande_statut_histories
historique = []

def avancer(date, jmin, jmax):
    """Ajoute jmin à jmax jours + une heure aléatoire dans la journée."""
    return date + timedelta(days=random.randint(jmin, jmax),
                            seconds=random.randint(0, SEC_PAR_JOUR - 1))

def ajouter(demande_id, precedent, nouveau, date, agent):
    historique.append({
        'id': len(historique) + 1,
        'demande_id': demande_id,
        'statut_precedent': precedent,
        'nouveau_statut': nouveau,
        'created_at': date,
        'agent_id': agent
    })

for _, demande in df_demandes.iterrows():
    d_id = demande['demande_id']
    date_courante = demande['date_soumission']     
    type_logement = demande['type_logement']
    statut_cible = demande['statut_actuel']

    ajouter(d_id, 'brouillon', 'soumise', date_courante, None)

    date_courante = avancer(date_courante, 1, 2)
    ajouter(d_id, 'soumise', 'attente', date_courante, None)

    # Le dossier reste en attente : l'historique s'arrête ici
    if statut_cible == 'attente':
        continue

    risque_correction = 0.35 if type_logement in ["Coopérative de logement", "Appui à l'Autoconstruction"] else 0.15

    if statut_cible == 'correction_demandee' or random.random() < risque_correction:
        date_courante = avancer(date_courante, 2, 5)
        ajouter(d_id, 'attente', 'non_conforme', date_courante, random.randint(10, 15))

        date_courante = avancer(date_courante, 5, 15)
        ajouter(d_id, 'non_conforme', 'correction_demandee', date_courante, None)

        # Le dossier finit ici si c'est son statut actuel
        if statut_cible == 'correction_demandee':
            continue

        # Sinon l'usager corrige, et le dossier repart en attente
        date_courante = avancer(date_courante, 2, 6)
        ajouter(d_id, 'correction_demandee', 'attente', date_courante, None)

    # Dossier conforme
    date_courante = avancer(date_courante, 2, 4)
    ajouter(d_id, 'attente', 'conforme', date_courante, random.randint(10, 15))

    facteur_geo = 1.8 if demande['commune'] == 'Ouagadougou' else 1.0
    facteur_type = 1.5 if type_logement == 'Coopérative de logement' else 1.0
    delai_instruction = int(np.random.gamma(shape=3, scale=3) * facteur_geo * facteur_type) + 3

    date_courante = avancer(date_courante, delai_instruction, delai_instruction)
    dernier_statut = 'rejetee' if statut_cible == 'rejetee' else 'validee'
    ajouter(d_id, 'conforme', dernier_statut, date_courante, random.randint(10, 15))

    if statut_cible == 'active':
        date_courante = avancer(date_courante, 5, 12)
        ajouter(d_id, 'validee', 'active', date_courante, random.randint(10, 15))

df_historique = pd.DataFrame(historique)

# On garde les données propres intactes, et on abîme des COPIES
dem = df_demandes.copy()
usr = df_users.copy()

# --- injection d'anomalies ---
lignes = dem.sample(n=20).index
dem.loc[lignes, 'commune'] = np.nan

lignes = dem.sample(n=15).index
dem.loc[lignes, ['region', 'province', 'commune']] = 'undefined'

ouaga = dem[dem['commune'] == 'Ouagadougou'].sample(n=10).index
dem.loc[ouaga, 'province'] = 'Houet'

lignes = usr.sample(n=4).index
usr.loc[lignes, 'date_naissance'] = '2090-05-12'

lignes = usr.sample(n=2).index
usr.loc[lignes, 'date_naissance'] = '1850-01-01'

# doublons de demandeurs
doublons = usr.sample(n=5).copy()
doublons['user_id'] = range(NB_USERS + 1, NB_USERS + 6)
doublons['uuid_hash'] = [f'usr_{random.randint(100000, 999999)}' for _ in range(5)]
usr = pd.concat([usr, doublons], ignore_index=True)

variantes_prof = {
    'Instituteur / Enseignant': ['Enseignant', 'instituteur', 'Prof'],
    'Commerçant': ['commercant', 'COMMERÇANT', 'Commerce'],
    'Chauffeur': ['chauffeur ', 'Chauffeur routier'],
}
for i in usr.index:
    profession = usr.loc[i, 'profession']
    if profession in variantes_prof and rng_ds07.random() < 0.5:
        usr.loc[i, 'profession'] = rng_ds07.choice(variantes_prof[profession])

variantes_statut = {
    'Fonctionnaire':    ['fonctionnaire', "Fonctionnaire d'État", "Agent de l'État"],
    'Salarié(e)':       ['Salarié', 'Salariée', 'salarie'],
    'Indépendant(e)':   ['Indépendant', 'Indépendante', 'independant'],
    'Chômeur/Chômeuse': ['Chômeur', 'Chômeuse', 'chomeur'],
}
variantes_situation = {
    'Célibataire': ['celibataire', 'Célibataire '],
    'Marié(e)':    ['marie', 'Marié', 'Mariée'],
    'Divorcé(e)':  ['divorce', 'Divorcé', 'Divorcée'],
    'Veuf/Veuve':  ['veuf', 'Veuve'],
}
for i in dem.index:
    s = dem.loc[i, 'statut_professionnel']
    if s in variantes_statut and rng_ds07.random() < 0.5:
        dem.loc[i, 'statut_professionnel'] = rng_ds07.choice(variantes_statut[s])

    m = dem.loc[i, 'situation_matrimoniale']
    if m in variantes_situation and rng_ds07.random() < 0.5:
        dem.loc[i, 'situation_matrimoniale'] = rng_ds07.choice(variantes_situation[m])

print("Professions différentes (users) :", usr['profession'].nunique())
print("Statuts différents (demandes) :", dem['statut_professionnel'].nunique())
print("Situations différentes (demandes) :", dem['situation_matrimoniale'].nunique())

# --- export ---
usr.to_csv('users_simules.csv', index=False, encoding='utf-8')
dem.to_csv('demande_logements_simulees.csv', index=False, encoding='utf-8')
df_historique.to_csv('demande_statut_histories_simulees.csv', index=False, encoding='utf-8')

df_users.to_csv('ref_users_propres.csv', index=False, encoding='utf-8')
df_demandes.to_csv('ref_demandes_propres.csv', index=False, encoding='utf-8')

print("Colonnes dem :", len(dem.columns), "| Colonnes usr :", len(usr.columns))
print("Fichiers CSV écrits.")

