import sqlite3
import os
import sys
import datetime
import pandas as pd

# Détermination dynamique du dossier racine (compatible PyInstaller .exe & VS Code)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "bpsg_gestion.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    # Mode WAL pour éliminer les verrous SQLite ("database is locked")
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Table Clients
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT UNIQUE,
                telephone TEXT,
                adresse TEXT
            )
        ''')

        # Table Magasin A (Atelier / Prestations)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_a (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                designation TEXT UNIQUE,
                prix_unitaire REAL,
                unite TEXT DEFAULT 'm²'
            )
        ''')

        # Table Stock Magasin B (Négoce)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_b (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE,
                designation TEXT,
                stock_initial INTEGER DEFAULT 0,
                entrees INTEGER DEFAULT 0,
                sorties INTEGER DEFAULT 0,
                prix_unitaire REAL DEFAULT 0,
                date_dernier_achat TEXT
            )
        ''')

        # Table Historique des Arrivages Magasin B
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS arrivages_b (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT,
                designation TEXT,
                date_achat TEXT,
                quantite INTEGER,
                prix_achat REAL
            )
        ''')

        # Table Factures
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS factures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT,
                client TEXT,
                date TEXT,
                total REAL,
                acompte REAL,
                reste REAL
            )
        ''')

        # Table Paramètres Entreprise
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parametres (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                nom TEXT,
                slogan TEXT,
                tel TEXT,
                email TEXT,
                adresse TEXT,
                logo TEXT,
                pied_page TEXT
            )
        ''')

        # Migrations automatiques de structure
        try:
            cursor.execute("ALTER TABLE stock_a ADD COLUMN unite TEXT DEFAULT 'm²'")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE stock_b ADD COLUMN date_dernier_achat TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE parametres ADD COLUMN pied_page TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        # Valeurs par défaut des paramètres
        cursor.execute("SELECT COUNT(*) FROM parametres")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO parametres (id, nom, slogan, tel, email, adresse, logo, pied_page)
                VALUES (1, 'BUILDING PRO SERVICES GUINEA', 'BTP, Alu-Vitrerie & Négoce Pro', '+224 600 00 00 00', 'contact@bpsg.gn', 'Conakry, Guinée', '', 'Merci pour votre confiance !\nBuilding Pro Services Guinea - S.A.R.L - BTP, Alu-Vitrerie & Négoce Matériaux')
            ''')

        # Articles par défaut pour le Magasin A (Atelier)
        cursor.execute("SELECT COUNT(*) FROM stock_a")
        if cursor.fetchone()[0] == 0:
            articles_a = [
                ("Porte Aluminium Coulissante", 1500000, "m²"),
                ("Fenêtre Vitrée Standard", 850000, "m²"),
                ("Main Courante Inox", 350000, "ML"),
                ("Vitrage Clair 6mm", 220000, "m²")
            ]
            cursor.executemany("INSERT OR IGNORE INTO stock_a (designation, prix_unitaire, unite) VALUES (?, ?, ?)", articles_a)

        conn.commit()

# --- GESTION CLIENTS ---
def ajouter_client(nom, tel, adresse):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clients (nom, telephone, adresse)
            VALUES (?, ?, ?)
            ON CONFLICT(nom) DO UPDATE SET
            telephone=coalesce(NULLIF(excluded.telephone, ''), telephone),
            adresse=coalesce(NULLIF(excluded.adresse, ''), adresse)
        ''', (nom, tel, adresse))
        conn.commit()

def supprimer_client(client_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()

def get_noms_clients():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nom FROM clients ORDER BY nom ASC")
        return [row[0] for row in cursor.fetchall()]

def get_tous_clients():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom, telephone, adresse FROM clients ORDER BY nom ASC")
        return cursor.fetchall()

# --- MAGASIN A (ATELIER) ---
def ajouter_ou_modifier_article_a(desig, prix_unitaire, unite):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stock_a (designation, prix_unitaire, unite)
            VALUES (?, ?, ?)
            ON CONFLICT(designation) DO UPDATE SET
            prix_unitaire = excluded.prix_unitaire,
            unite = excluded.unite
        ''', (desig, prix_unitaire, unite))
        conn.commit()

def supprimer_article_magasin_a(article_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stock_a WHERE id = ?", (article_id,))
        conn.commit()

def get_articles_magasin_a():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, designation, prix_unitaire, unite FROM stock_a ORDER BY designation ASC")
        return cursor.fetchall()

# --- MAGASIN B (NÉGOCE - LOGIQUE CUMP) ---
def ajouter_ou_mettre_a_jour_article_b(ref, desig, qte_entree, prix_achat, date_achat=None):
    if not date_achat:
        date_achat = datetime.datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO arrivages_b (reference, designation, date_achat, quantite, prix_achat)
            VALUES (?, ?, ?, ?, ?)
        ''', (ref, desig, date_achat, qte_entree, prix_achat))

        cursor.execute("SELECT stock_initial, entrees, sorties, prix_unitaire FROM stock_b WHERE reference = ?", (ref,))
        row = cursor.fetchone()
        
        if row:
            stock_initial, entrees, sorties, ancien_cump = row
            stock_actuel = stock_initial + entrees - sorties
            nouveau_stock_total = stock_actuel + qte_entree
            
            # Calcul CUMP : [(Stock actuel * Ancien CUMP) + (Nouvel arrivage * Prix d'achat)] / Stock Total
            if nouveau_stock_total > 0:
                valeur_existante = stock_actuel * (ancien_cump if ancien_cump else 0)
                valeur_arrivage = qte_entree * prix_achat
                nouveau_cump = (valeur_existante + valeur_arrivage) / nouveau_stock_total
            else:
                nouveau_cump = ancien_cump if ancien_cump else prix_achat
            
            nouvelles_entrees = entrees + qte_entree
            
            cursor.execute('''
                UPDATE stock_b 
                SET designation = ?, entrees = ?, prix_unitaire = ?, date_dernier_achat = ?
                WHERE reference = ?
            ''', (desig, nouvelles_entrees, nouveau_cump, date_achat, ref))
        else:
            cursor.execute('''
                INSERT INTO stock_b (reference, designation, stock_initial, entrees, sorties, prix_unitaire, date_dernier_achat)
                VALUES (?, ?, 0, ?, 0, ?, ?)
            ''', (ref, desig, qte_entree, prix_achat, date_achat))
        conn.commit()

def supprimer_article_magasin_b(article_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stock_b WHERE id = ?", (article_id,))
        conn.commit()

def get_articles_magasin_b():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, reference, designation, date_dernier_achat, stock_initial, entrees, sorties, 
                   (stock_initial + entrees - sorties) as stock_final, prix_unitaire
            FROM stock_b
            ORDER BY designation ASC
        ''')
        return cursor.fetchall()

def get_historique_arrivages_b():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, reference, designation, date_achat, quantite, prix_achat
            FROM arrivages_b
            ORDER BY date_achat DESC, id DESC
        ''')
        return cursor.fetchall()

def deduire_stock_magasin_b(article_id, quantite_vendue):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE stock_b 
            SET sorties = sorties + ?
            WHERE id = ?
        ''', (quantite_vendue, article_id))
        conn.commit()

# --- FACTURES ---
def enregistrer_facture(numero, client, date, total, acompte, reste):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO factures (numero, client, date, total, acompte, reste)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (numero, client, date, total, acompte, reste))
        conn.commit()

# --- PARAMÈTRES ---
def get_parametres():
    with get_connection() as conn:
        cursor = conn.cursor()
        # On sélectionne explicitement les 7 colonnes
        cursor.execute("SELECT nom, slogan, tel, email, adresse, logo, pied_page FROM parametres WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return {
                "nom": row[0] or "BUILDING PRO SERVICES GUINEA",
                "slogan": row[1] or "",
                "tel": row[2] or "",
                "email": row[3] or "",
                "adresse": row[4] or "",
                "logo": row[5] or "",
                "pied_page": row[6] if row[6] is not None else "Merci pour votre confiance !\nBuilding Pro Services Guinea - S.A.R.L - BTP, Alu-Vitrerie & Négoce Matériaux"
            }
        return {
            "nom": "BUILDING PRO SERVICES GUINEA",
            "slogan": "",
            "tel": "",
            "email": "",
            "adresse": "",
            "logo": "",
            "pied_page": "Merci pour votre confiance !\nBuilding Pro Services Guinea - S.A.R.L - BTP, Alu-Vitrerie & Négoce Matériaux"
        }

def sauvegarder_parametres(nom, slogan, tel, email, adresse, logo, pied_page):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE parametres 
            SET nom = ?, slogan = ?, tel = ?, email = ?, adresse = ?, logo = ?, pied_page = ?
            WHERE id = 1
        ''', (nom, slogan, tel, email, adresse, logo, pied_page))
        conn.commit()

# --- EXPORT EXCEL GLOBAL ---
def exporter_vers_excel():
    with get_connection() as conn:
        df_stock_a = pd.read_sql_query("SELECT designation, prix_unitaire, unite FROM stock_a", conn)
        df_stock_b = pd.read_sql_query("SELECT reference, designation, date_dernier_achat, stock_initial, entrees, sorties, (stock_initial + entrees - sorties) AS stock_actuel, prix_unitaire AS CUMP_GNF FROM stock_b", conn)
        df_arrivages_b = pd.read_sql_query("SELECT reference, designation, date_achat, quantite, prix_achat FROM arrivages_b ORDER BY date_achat DESC", conn)
        df_clients = pd.read_sql_query("SELECT nom, telephone, adresse FROM clients", conn)
        df_factures = pd.read_sql_query("SELECT numero, client, date, total, acompte, reste FROM factures", conn)

    fichier_sortie = os.path.join(BASE_DIR, "Rapport_BPSG.xlsx")
    with pd.ExcelWriter(fichier_sortie, engine='openpyxl') as writer:
        df_stock_a.to_excel(writer, sheet_name="Atelier (Magasin A)", index=False)
        df_stock_b.to_excel(writer, sheet_name="Stock Négoce (Mag B)", index=False)
        df_arrivages_b.to_excel(writer, sheet_name="Historique Arrivages", index=False)
        df_clients.to_excel(writer, sheet_name="Clients", index=False)
        df_factures.to_excel(writer, sheet_name="Factures", index=False)

    os.startfile(fichier_sortie)