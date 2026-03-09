import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
import time
import random
import streamlit.components.v1 as components

# --- 1. ALERTA SONORO ---
def disparar_alerta_sonoro():
    components.html('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-3.mp3" type="audio/mpeg"></audio>', height=0)

# --- 2. MOTOR SNIPER COM BUSCA RECURSIVA (O SEGREDO DA VITÓRIA) ---
def buscar_preco_vtex_robusto(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    
    # Lista de tentativas: Nome Completo -> Nome Curto -> Marca + Peso
    palavras = termo.split()
    tentativas = [
        termo,                                 # 1. Termo integral
        " ".join(palavras[:3]),                # 2. Primeiras 3 palavras (ex: Leite Condensado Moça)
        f"{palavras[0]} {palavras[-1]}"        # 3. Primeira e última palavra (ex: Leite 395g)
    ]

    for tentativa in tentativas:
        try:
            r = requests.get(url, params={"ft": tentativa, "_from": 0, "_to": 0}, headers=headers, timeout=6)
            if r.status_code == 200:
                dados = r.json()
                if dados:
                    item = dados[0]
                    nome = item.get("productName")
                    preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
                    return nome, float(preco)
        except:
            continue # Se der timeout, tenta a próxima simplificação
    
    return "Não Localizado", None

# --- 3. INTERFACE E VALIDAÇÃO ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")

try: URL_DO_BANCO = st.secrets["database"]["url"]
except: URL_DO_BANCO = None

st.title("👁️ Olho de Sauron v7.3")
st.markdown("##### *Sistema Inabalável de Auditoria - Tome Leve*")

arquivo = st.file_uploader("📂 Carregar Planilha Comercial", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo)
    
    # Sidebar Inteligente
    with st.sidebar:
        st.header("⚙️ Ajuste de Colunas")
        cols = list(df_raw.columns)
        c_ean = st.selectbox("EAN", cols, index=cols.index("EAN") if "EAN" in cols else 0)
        c_desc = st.selectbox("Descrição", cols, index=0)
        c_busca = st.selectbox("Busca", cols, index=0)

    # VALIDAÇÃO
    if df_raw[c_ean].duplicated().any():
        st.error("🚨 Erro: Planilha contém EANs duplicados. Corrija antes de prosseguir.")
    else:
        if st.button("🚀 INICIAR VARREDURA INFALÍVEL"):
            resultados = []
            barra = st.progress(0)
            msg = st.empty()
            engine = create_engine(URL_DO_BANCO) if URL_DO_BANCO else None

            for i, row in df_raw.iterrows():
                nome_tl = str(row[c_desc])
                termo = str(row[c_busca])
                ean = str(row[c_ean])
                
                msg.info(f"🔍 Auditando ({i+1}/{len(df_raw)}): {nome_tl}")
                
                # Executa a busca com o novo motor recursivo
                res_nome, res_preco = buscar_preco_vtex_robusto(termo)
                
                if res_preco:
                    # Busca Histórico
                    p_ant = None
                    if engine:
                        try:
                            q = f'SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = \'{ean}\' ORDER BY "Data_Coleta" DESC LIMIT 1'
                            with engine.connect() as conn:
                                df_h = pd.read_sql(q, conn)
                                if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                        except: pass
                    
                    # Cálculo de Variação LaTeX: $V = \frac{P_{n} - P_{a}}{P_{a}} \times 100$
                    var = round(((res_preco - p_ant) / p_ant * 100), 2) if p_ant else None
                    
                    resultados.append({
                        "EAN": ean, "Produto": nome_tl, "Concorrente": res_nome,
                        "Preço Atual": res_preco, "Preço Anterior": p_ant,
                        "Variação %": var, "Data_Coleta": datetime.now()
                    })
                
                barra.progress((i + 1) / len(df_raw))
                time.sleep(random.uniform(1.0, 2.0))

            if resultados:
                df_res = pd.DataFrame(resultados)
                st.success("✅ Missão Cumprida!")
                st.dataframe(df_res, use_container_width=True)
                
                # Sincronização Neon
                if engine:
                    df_res.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Dados protegidos no Neon!")
                
                disparar_alerta_sonoro()
                st.balloons()
