import streamlit as st
import os
import datetime
import database
import pdf_engine

# Configuration de la page web
st.set_page_config(
    page_title="BPSG - Gestion & Facturation",
    page_icon="🏢",
    layout="wide"
)

# Initialisation de la base de données
database.init_db()

st.title("🏢 Building Pro Services Guinea (BPSG)")
st.caption("Plateforme web de gestion intégrée : Atelier, Négoce, Facturation & Caisse")

# Navigation par onglets (correspondant à vos anciennes fenêtres)
onglets = st.tabs([
    "📄 Facturation & Caisse", 
    "🛠️ Magasin A (Atelier)", 
    "📦 Magasin B (Négoce & CUMP)", 
    "👥 Clients", 
    "⚙️ Paramètres"
])

# ==========================================
# ONGLET 1 : FACTURATION & CAISSE
# ==========================================
with onglets[0]:
    st.header("Émission de Facture & Caisse")
    
    col1, col2 = st.columns(2)
    
    with col1:
        clients_noms = database.get_noms_clients()
        client_choisi = st.selectbox("Sélectionner ou saisir le client :", options=[""] + clients_noms, index=0)
        client_input = st.text_input("Ou nouveau client / Raison sociale :", value="")
        client_final = client_input.strip() if client_input.strip() else client_choisi

    with col2:
        origine_produit = st.selectbox("Origine du Produit :", ["Magasin A (Atelier)", "Magasin B (Négoce)"])

    st.markdown("---")
    
    # Chargement des articles selon le magasin
    articles_dict = {}
    if "Magasin A" in origine_produit:
        rows = database.get_articles_magasin_a()
        for r in rows:
            unite = r[3] if len(r) > 3 else "m²"
            libelle = f"{r[1]} - ({r[2]:,.0f} GNF/{unite})"
            articles_dict[libelle] = {'id': r[0], 'designation': f"{r[1]} ({unite})", 'pu': r[2], 'stock': 999999}
    else:
        rows = database.get_articles_magasin_b()
        for r in rows:
            libelle = f"[{r[1]}] {r[2]} (Dispo: {r[7]}) - ({r[8]:,.0f} GNF)"
            articles_dict[libelle] = {'id': r[0], 'designation': r[2], 'pu': r[8], 'stock': r[7]}

    col_art1, col_art2, col_art3 = st.columns([3, 1, 1])
    with col_art1:
        article_selectionne = st.selectbox("Choisir un article :", options=list(articles_dict.keys()))
    with col_art2:
        quantite = st.number_input("Qté / Surface :", min_value=0.1, value=1.0, step=1.0)
    with col_art3:
        st.text("")
        st.text("")
        ajouter_btn = st.button("➕ Ajouter au panier")

    # Gestion du panier en session Streamlit
    if 'panier' not in st.session_state:
        st.session_state.panier = []

    if ajouter_btn and article_selectionne:
        item_info = articles_dict[article_selectionne]
        if "Magasin B" in origine_produit and quantite > item_info['stock']:
            st.error(f"Stock insuffisant ! Disponible : {item_info['stock']}")
        else:
            tot = quantite * item_info['pu']
            st.session_state.panier.append({
                'id': item_info['id'],
                'designation': item_info['designation'],
                'quantite': quantite,
                'pu': item_info['pu'],
                'total': tot,
                'magasin': origine_produit
            })
            st.success("Article ajouté au panier !")

    # Affichage du panier
    if st.session_state.panier:
        st.subheader("Articles dans le Panier :")
        total_general = sum(i['total'] for i in st.session_state.panier)
        
        # Tableau récapitulatif
        st.table([{
            "Désignation": i['designation'],
            "Quantité": i['quantite'],
            "P.U (GNF)": f"{i['pu']:,.0f}",
            "Total (GNF)": f"{i['total']:,.0f}"
        } for i in st.session_state.panier])

        st.markdown(f"### **TOTAL GÉNÉRAL : {total_general:,.0f} GNF**")
        
        acompte = st.number_input("Acompte versé (GNF) :", min_value=0.0, value=0.0, step=50000.0)
        reste = total_general - acompte

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            if st.button("🖨️ Valider et Émettre la Facture PDF"):
                if not client_final:
                    st.warning("Veuillez renseigner un nom de client.")
                else:
                    num_fac = f"FAC-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    date_fac = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

                    database.ajouter_client(client_final, "", "")
                    database.enregistrer_facture(num_fac, client_final, date_fac, total_general, acompte, reste)

                    for item in st.session_state.panier:
                        if "Magasin B" in item['magasin']:
                            database.deduire_stock_magasin_b(item['id'], int(item['quantite']))

                    try:
                        pdf_path = pdf_engine.creer_facture(num_fac, client_final, st.session_state.panier, total_general, acompte, reste)
                        st.success(f"Facture {num_fac} générée avec succès dans le dossier 'Factures' !")
                        with open(pdf_path, "rb") as f:
                            st.download_button("📥 Télécharger la Facture PDF", f, file_name=os.path.basename(pdf_path), mime="application/pdf")
                    except Exception as e:
                        st.error(f"Erreur génération PDF : {e}")

                    st.session_state.panier = []
        with col_v2:
            if st.button("🗑️ Vider le panier"):
                st.session_state.panier = []
                st.rerun()

    if st.button("📊 Exporter le Rapport Global (Excel)"):
        database.exporter_vers_excel()
        st.success("Rapport Excel 'Rapport_BPSG.xlsx' généré !")


# ==========================================
# ONGLET 2 : MAGASIN A (ATELIER)
# ==========================================
with onglets[1]:
    st.header("Gestion de l'Atelier (Magasin A)")
    
    with st.form("form_mag_a"):
        col_a1, col_a2, col_a3 = st.columns(3)
        with col_a1:
            desig_a = st.text_input("Désignation de la prestation / article :")
        with col_a2:
            pu_a = st.number_input("Prix unitaire (GNF) :", min_value=0.0, value=0.0)
        with col_a3:
            unite_a = st.selectbox("Unité de calcul :", ["m²", "ML", "Unité"])
        
        submit_a = st.form_submit_button("➕ Enregistrer Article Atelier")
        if submit_a:
            if desig_a.strip():
                database.ajouter_ou_modifier_article_a(desig_a.strip(), pu_a, unite_a)
                st.success(f"Article '{desig_a}' enregistré !")
                st.rerun()
            else:
                st.warning("La désignation est obligatoire.")

    st.subheader("Articles actuels de l'Atelier")
    articles_a = database.get_articles_magasin_a()
    if articles_a:
        for row in articles_a:
            col_t1, col_t2, col_t3, col_t4 = st.columns([3, 2, 1, 1])
            col_t1.text(row[1])
            col_t2.text(f"{row[2]:,.0f} GNF / {row[3]}")
            if col_t4.button("🗑️ Supprimer", key=f"del_a_{row[0]}"):
                database.supprimer_article_magasin_a(row[0])
                st.success("Supprimé !")
                st.rerun()
    else:
        st.info("Aucun article dans l'atelier.")


# ==========================================
# ONGLET 3 : MAGASIN B (NÉGOCE & CUMP)
# ==========================================
with onglets[2]:
    st.header("Gestion du Négoce & Arrivages (Méthode CUMP)")

    with st.form("form_mag_b"):
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            ref_b = st.text_input("Référence article :")
        with col_b2:
            desig_b = st.text_input("Désignation :")
        with col_b3:
            date_b = st.date_input("Date d'achat / Arrivage :")

        col_b4, col_b5 = st.columns(2)
        with col_b4:
            qte_b = st.number_input("Quantité reçue :", min_value=1, value=1)
        with col_b5:
            pu_achat_b = st.number_input("Prix d'achat unitaire (GNF) :", min_value=0.0, value=0.0)

        submit_b = st.form_submit_button("➕ Enregistrer l'Arrivage (Calculer CUMP)")
        if submit_b:
            if ref_b.strip() and desig_b.strip():
                database.ajouter_ou_mettre_a_jour_article_b(
                    ref_b.strip(), desig_b.strip(), qte_b, pu_achat_b, date_b.strftime("%Y-%m-%d")
                )
                st.success("Arrivage enregistré et CUMP recalculé avec succès !")
                st.rerun()
            else:
                st.warning("Référence et désignation obligatoires.")

    st.subheader("État actuel du stock négoce")
    stock_b = database.get_articles_magasin_b()
    if stock_b:
        for row in stock_b:
            col_sb1, col_sb2, col_sb3, col_sb4 = st.columns([2, 2, 2, 1])
            col_sb1.text(f"[{row[1]}] {row[2]}")
            col_sb2.text(f"Stock Actuel : {row[7]} | CUMP : {row[8]:,.0f} GNF")
            if col_sb4.button("🗑️ Supprimer", key=f"del_b_{row[0]}"):
                database.supprimer_article_magasin_b(row[0])
                st.success("Article supprimé !")
                st.rerun()
    else:
        st.info("Aucun stock en négoce.")


# ==========================================
# ONGLET 4 : GESTION DES CLIENTS
# ==========================================
with onglets[3]:
    st.header("Gestion des Clients")

    with st.form("form_client"):
        c_nom = st.text_input("Nom complet / Raison sociale :")
        c_tel = st.text_input("Téléphone :")
        c_adr = st.text_input("Adresse / Ville :")
        
        if st.form_submit_button("➕ Enregistrer Client"):
            if c_nom.strip():
                database.ajouter_client(c_nom.strip(), c_tel.strip(), c_adr.strip())
                st.success(f"Client '{c_nom}' enregistré !")
                st.rerun()
            else:
                st.warning("Le nom du client est obligatoire.")

    st.subheader("Liste des Clients")
    clients = database.get_tous_clients()
    if clients:
        for cli in clients:
            col_c1, col_c2, col_c3 = st.columns([3, 3, 1])
            col_c1.text(f"{cli[1]} - {cli[2]}")
            col_c2.text(cli[3])
            if col_c3.button("🗑️ Suppr.", key=f"del_cli_{cli[0]}"):
                database.supprimer_client(cli[0])
                st.success("Client supprimé !")
                st.rerun()
    else:
        st.info("Aucun client enregistré.")


# ==========================================
# ONGLET 5 : PARAMÈTRES ENTREPRISE
# ==========================================
with onglets[4]:
    st.header("Paramètres de l'Entreprise & Pied de Page")
    
    p = database.get_parametres()
    
    with st.form("form_param"):
        p_nom = st.text_input("Nom de la Société :", value=p["nom"])
        p_slogan = st.text_input("Slogan / Activité :", value=p["slogan"])
        p_tel = st.text_input("Téléphone :", value=p["tel"])
        p_email = st.text_input("Email :", value=p["email"])
        p_adr = st.text_input("Adresse :", value=p["adresse"])
        p_logo = st.text_input("Chemin du logo (image) :", value=p["logo"])
        p_footer = st.text_area("Pied de page des factures :", value=p["pied_page"])

        if st.form_submit_button("💾 Enregistrer les Modifications"):
            database.sauvegarder_parametres(p_nom, p_slogan, p_tel, p_email, p_adr, p_logo, p_footer)
            st.success("Paramètres mis à jour avec succès !")
            st.rerun()