import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v8.5")
st.markdown("##### *Ajuste Final para Apresentação - Tome Leve*")

# --- MOTOR DE BUSCA SNIPER (TRIPLA TENTATIVA) ---
def buscar_preco_vtex(ean_cru, termo_completo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    # 1. LIMPEZA DO EAN (Remove .0 do Excel e zeros à esquerda de códigos de 14 dígitos)
    ean = str(ean_cru).replace('.0', '').strip()
    if len(ean) == 14 and ean.startswith('0'): ean = ean[1:]

    # TENTATIVA 1: Busca Direta por EAN (Filtro preciso da VTEX)
    try:
        r = requests.get(url, params={"fq": f"ean:{ean}"}, headers=headers, timeout=6)
        if r.status_code == 200 and r.json():
            prod = r.json()[0]
            nome = prod.get("productName")
            preco = prod["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return f"🎯 {nome}", float(preco)
    except: pass

    # TENTATIVA 2: Busca por Texto Curto (Primeiras 3 palavras)
    try:
        termo_curto = " ".join(str(termo_completo).strip().split()[:3])
        r = requests.get(url, params={"ft": termo_curto}, headers=headers, timeout=6)
        if r.status_code == 200 and r.json():
            prod = r.json()[0]
            nome = prod.get("productName")
            preco = prod["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except: pass

    return "Não Localizado", None

# --- INTERFACE ---
arquivo = st.file_uploader("📂 Carregar Planilha", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo).dropna(how='all').reset_index(drop=True)
    cols = list(df_raw.columns)

    with st.sidebar:
        st.header("⚙️ Mapeamento Comercial")
        c_ean = st.selectbox("Coluna EAN", cols, index=0)
        c_desc = st.selectbox("Descrição Interna", cols, index=1 if len(cols)>1 else 0)
        c_busca = st.selectbox("Termo de Busca", cols, index=2 if len(cols)>2 else 0)

    if st.button("🚀 INICIAR AUDITORIA INFALÍVEL"):
        resultados = []
        barra = st.progress(0)
        msg = st.empty()

        try: engine = create_engine(st.secrets["database"]["url"])
        except: engine = None

        for i, row in df_raw.iterrows():
            n_tl = str(row[c_desc])
            t_busca = str(row[c_busca])
            ean_raw = str(row[c_ean])

            msg.info(f"🔍 Auditando: {n_tl}")
            
            # Chamada ao motor com limpeza
            res_nome, res_preco = buscar_preco_vtex(ean_raw, t_busca)

            # Busca Histórico no Neon
            p_ant = None
            if engine and res_preco:
                try:
                    query = text('SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = :ean ORDER BY "Data_Coleta" DESC LIMIT 1')
                    ean_limpo = ean_raw.replace('.0', '').strip()
                    if len(ean_limpo) == 14 and ean_limpo.startswith('0'): ean_limpo = ean_limpo[1:]
                    with engine.connect() as conn:
                        df_h = pd.read_sql(query, conn, params={"ean": ean_limpo})
                        if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                except: pass

            var = round(((res_preco - p_ant) / p_ant * 100), 2) if (res_preco and p_ant) else 0

            resultados.append({
                "EAN": ean_raw.replace('.0', '').strip(),
                "Descricao_Tome_Leve": n_tl,
                "Descricao_Concorrente": res_nome,
                "Preco_Atual": res_preco if res_preco else 0,
                "Preco_Anterior": p_ant,
                "Variacao_P": var,
                "Data_Coleta": datetime.now()
            })

            barra.progress((i + 1) / len(df_raw))
            time.sleep(random.uniform(1.0, 1.8))

        if resultados:
            df_res = pd.DataFrame(resultados)
            msg.success("✨ Auditoria Concluída!")
            st.dataframe(df_res, use_container_width=True)

            # SINCRONIZAÇÃO (Filtro de colunas para o Banco)
            colunas_db = ["EAN", "Descricao_Tome_Leve", "Descricao_Concorrente", "Preco_Atual", "Data_Coleta"]
            df_banco = df_res[df_res["Preco_Atual"] > 0][colunas_db]

            if engine and not df_banco.empty:
                try:
                    df_banco.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Cofre Sincronizado!", icon="🔐")
                except Exception as e:
                    st.error(f"Erro de Banco: {e}")
