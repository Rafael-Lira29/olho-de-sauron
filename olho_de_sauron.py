import os
import streamlit as st

#A VACINA (INSTALAÇÃO AUTOMÁTICA NA NUVEM) ---
@st.cache_resource
def instalar_navegador():
    # Este comando baixa os binários do Chromium para o servidor Linux do Streamlit
    os.system("playwright install chromium")

instalar_navegador()
# ---------------------------------------------------------

import pandas as pd
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime
import time
import random
from sqlalchemy import create_engine
import urllib.parse

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Olho de Sauron - Tome Leve", layout="wide")
st.title("👁️ O Olho de Sauron")
st.markdown("### Inteligência Competitiva Tome Leve")

# SEGURANÇA: URL DO BANCO (Vinda dos Secrets do Streamlit)
try:
    URL_DO_BANCO = st.secrets["database"]["url"]
except:
    URL_DO_BANCO = None
    st.sidebar.warning("⚠️ Configuração de banco de dados não encontrada.")

# MOTOR DE BUSCA (API)
def buscar_vtex_api(termo):
    try:
        url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
        headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params={"ft": termo}, headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            prod = r.json()[0]
            return prod["productName"], float(prod["items"][0]["sellers"][0]["commertialOffer"]["Price"])
    except: return None
    return None

# INTERFACE
arquivo_upload = st.file_uploader("Carregar Planilha de Alvos (.xlsx)", type=["xlsx"])

if arquivo_upload:
    df_alvos = pd.read_excel(arquivo_upload)
    st.write(f"📊 {len(df_alvos)} produtos prontos para auditoria.")

    if st.button("🚀 INICIAR VARREDURA"):
        barra = st.progress(0)
        status = st.empty()
        resultados = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            for i, row in df_alvos.iterrows():
                nome_int = str(row["Descricao_Tome_Leve"])
                termo = str(row["Busca_Otimizada"])
                ean = str(row["EAN"])
                
                status.text(f"🔍 Auditando: {nome_int}")
                
                # Tenta API primeiro
                res = buscar_vtex_api(termo)
                
                if res:
                    nome_conc, preco = res
                    resultados.append({
                        "Concorrente": "Savegnago",
                        "EAN": ean,
                        "Produto Tome Leve": nome_int,
                        "Produto Concorrente": nome_conc,
                        "Preço Atual": preco,
                        "Data_Hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    })
                
                barra.progress((i + 1) / len(df_alvos))
                time.sleep(random.uniform(1, 2))
            
            browser.close()

        if resultados:
            df_final = pd.DataFrame(resultados)
            st.success("✅ Auditoria finalizada!")
            st.dataframe(df_final)

            # Gravação no Neon
            if URL_DO_BANCO:
                try:
                    engine = create_engine(URL_DO_BANCO)
                    df_final.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Dados sincronizados com o Neon!", icon="🔐")
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")
