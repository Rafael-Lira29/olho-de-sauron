import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
from datetime import datetime
import time
import random
from sqlalchemy import create_engine
import urllib.parse
import requests

# -----------------------------
# CONFIGURAÇÃO DA PÁGINA
# -----------------------------
st.set_page_config(page_title="Olho de Sauron - Inteligência Tome Leve", layout="wide")

st.title("👁️ O Olho de Sauron")
st.subheader("Módulo de Auditoria de Preços - Tome Leve vs Concorrentes")

# Barra Lateral
st.sidebar.header("Configurações da Missão")
concorrente_selecionado = st.sidebar.selectbox("Selecionar Concorrente", ["Savegnago", "Pão de Açúcar (Em breve)", "Carrefour (Em breve)"])
url_banco = st.sidebar.text_input("Link do Cofre Neon", type="password")

# -----------------------------
# MOTOR DE BUSCA (A LÓGICA QUE CRIAMOS)
# -----------------------------
def buscar_vtex_v4(termo):
    try:
        url = f"https://www.savegnago.com.br/api/catalog_system/pub/products/search"
        r = requests.get(url, params={"ft": termo}, timeout=10)
        if r.status_code == 200 and r.json():
            prod = r.json()[0]
            return prod["productName"], float(prod["items"][0]["sellers"][0]["commertialOffer"]["Price"])
    except: return None
    return None

# -----------------------------
# INTERFACE DE USUÁRIO
# -----------------------------
arquivo_upload = st.file_uploader("Carregar Planilha de Alvos (Excel)", type=["xlsx"])

if arquivo_upload:
    df_alvos = pd.read_excel(arquivo_upload)
    st.write("📋 Lista de produtos carregada:")
    st.dataframe(df_alvos.head())

    if st.button("🚀 INICIAR VARREDURA AGORA"):
        progresso = st.progress(0)
        status_text = st.empty()
        resultados = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            total = len(df_alvos)
            for i, row in df_alvos.iterrows():
                nome_interno = str(row["Descricao_Tome_Leve"])
                termo = str(row["Busca_Otimizada"])
                ean = str(row["EAN"])
                
                status_text.text(f"🎯 Caçando: {nome_interno}...")
                
                # A INTELIGÊNCIA HÍBRIDA
                res = buscar_vtex_v4(termo)
                
                if res:
                    nome_conc, preco = res
                    resultados.append({
                        "Concorrente": concorrente_selecionado, # A IDENTIDADE QUE FALTAVA
                        "EAN": ean,
                        "Produto Tome Leve": nome_interno,
                        "Produto Concorrente": nome_conc,
                        "Preço Atual": preco,
                        "Data_Hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    })
                
                # Atualiza Barra de Progresso
                progresso.progress((i + 1) / total)
                time.sleep(random.uniform(1, 3))
            
            browser.close()

        # -----------------------------
        # EXIBIÇÃO DOS RESULTADOS
        # -----------------------------
        if resultados:
            df_final = pd.DataFrame(resultados)
            st.success(f"✅ Missão cumprida! {len(df_final)} produtos auditados no {concorrente_selecionado}.")
            st.table(df_final)

            # Botão para Download
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Relatório Completo (CSV)", data=csv, file_name=f"Auditoria_{concorrente_selecionado}.csv")

            # Envio Automático para o Banco se a URL existir
            if url_banco:
                try:
                    engine = create_engine(url_banco)
                    df_final.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.info("🔐 Dados guardados automaticamente no cofre Neon.")
                except Exception as e:
                    st.error(f"🚨 Falha ao aceder ao cofre: {e}")