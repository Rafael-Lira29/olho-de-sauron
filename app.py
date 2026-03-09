import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v8.4")
st.markdown("##### *Auditoria de Precisão Tome Leve*")

# --- MOTOR SNIPER (BUSCA POR EAN + FALLBACK) ---
def buscar_preco_vtex(ean, termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # TENTATIVA 1: Busca Direta por EAN (Muito mais precisa)
    try:
        # O parâmetro fq=alternateIds_Ean: é o 'pulo do gato' da VTEX
        params_ean = {"fq": f"alternateIds_Ean:{ean}"}
        r = requests.get(url, params=params_ean, headers=headers, timeout=7)
        
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return f"🎯 {nome}", float(preco)
    except:
        pass

    # TENTATIVA 2: Busca por Termo (Se o EAN falhar)
    try:
        termo_limpo = " ".join(str(termo).strip().split()[:3])
        params_ft = {"ft": termo_limpo}
        r = requests.get(url, params=params_ft, headers=headers, timeout=7)
        
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except:
        pass

    return "Não Localizado", None

# --- INTERFACE ---
arquivo = st.file_uploader("📂 Carregar Planilha Comercial", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo).dropna(how='all').reset_index(drop=True)
    cols = list(df_raw.columns)

    with st.sidebar:
        st.header("⚙️ Configuração")
        c_ean = st.selectbox("Coluna EAN", cols, index=0)
        c_desc = st.selectbox("Descrição Tome Leve", cols, index=1 if len(cols) > 1 else 0)
        c_busca = st.selectbox("Busca Otimizada", cols, index=2 if len(cols) > 2 else 0)

    if st.button("🚀 INICIAR AUDITORIA"):
        resultados = []
        barra = st.progress(0)
        msg = st.empty()

        try: engine = create_engine(st.secrets["database"]["url"])
        except: engine = None

        for i, row in df_raw.iterrows():
            nome_tl = str(row[c_desc])
            termo = str(row[c_busca])
            ean_val = str(row[c_ean]).split('.')[0] # Limpa EANs que venham como float

            msg.info(f"🔍 Auditando: {nome_tl}")
            
            # Chama o novo motor Sniper
            res_nome, res_preco = buscar_preco_vtex(ean_val, termo)

            # Busca Histórico
            preco_anterior = None
            if engine and res_preco:
                try:
                    query = text('SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = :ean ORDER BY "Data_Coleta" DESC LIMIT 1')
                    with engine.connect() as conn:
                        df_h = pd.read_sql(query, conn, params={"ean": ean_val})
                        if not df_h.empty: preco_anterior = float(df_h.iloc[0][0])
                except: pass

            var = round(((res_preco - preco_anterior) / preco_anterior * 100), 2) if (res_preco and preco_anterior) else 0

            resultados.append({
                "EAN": ean_val,
                "Descricao_Tome_Leve": nome_tl,
                "Descricao_Concorrente": res_nome,
                "Preco_Atual": res_preco if res_preco else 0,
                "Preco_Anterior": preco_anterior,
                "Variacao_P": var,
                "Data_Coleta": datetime.now()
            })

            barra.progress((i + 1) / len(df_raw))
            time.sleep(random.uniform(1.2, 2.0))

        if resultados:
            df_res = pd.DataFrame(resultados)
            msg.success("✨ Auditoria Concluída!")
            st.dataframe(df_res, use_container_width=True)

            # --- SINCRONIZAÇÃO SEGURA ---
            colunas_db = ["EAN", "Descricao_Tome_Leve", "Descricao_Concorrente", "Preco_Atual", "Data_Coleta"]
            df_para_banco = df_res[df_res["Preco_Atual"] > 0][colunas_db]

            if engine and not df_para_banco.empty:
                try:
                    df_para_banco.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Cofre Sincronizado!", icon="🔐")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
