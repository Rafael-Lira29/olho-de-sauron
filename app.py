import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# --- CONFIGURAÇÃO DE ELITE ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v11.0")
st.markdown("#### *Relatório de Inteligência Competitiva - Tome Leve*")

# --- MOTOR DE CAPTURA PROFISSIONAL ---
def capturar_preco_savegnago(ean, termo):
    # Lista de identidades para enganar o firewall
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ]
    
    session = requests.Session()
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer": "https://www.savegnago.com.br/",
        "Origin": "https://www.savegnago.com.br"
    }

    # Limpeza de EAN (Remove o .0 que o Excel insere)
    ean_limpo = str(ean).split('.')[0].strip()
    
    # ESTRATÉGIA DE BUSCA EM 3 NÍVEIS
    # 1. Busca por EAN (O mais preciso)
    # 2. Busca por Termo Exato
    # 3. Busca por Termo Reduzido
    
    tentativas = [
        {"fq": f"alternateIds_Ean:{ean_limpo}"},
        {"ft": str(termo).strip()},
        {"ft": " ".join(str(termo).split()[:2])}
    ]

    for p in tentativas:
        try:
            url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
            # Adicionamos um delay aleatório antes de cada tentativa para parecer humano
            time.sleep(random.uniform(1.0, 2.5))
            
            r = session.get(url, params=p, headers=headers, timeout=12)
            
            if r.status_code == 200 and r.json():
                item = r.json()[0]
                nome_site = item.get("productName")
                # Extração segura do preço
                oferta = item["items"][0]["sellers"][0]["commertialOffer"]
                preco = oferta.get("Price") or oferta.get("ListPrice")
                
                if preco and preco > 0:
                    return f"✅ {nome_site}", float(preco)
        except:
            continue
            
    return "❌ Bloqueio/Não Encontrado", 0.0

# --- INTERFACE EXECUTIVA ---
arquivo = st.file_uploader("📂 Carregar Planilha de Auditoria (.xlsx)", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo).dropna(how='all')
    
    with st.sidebar:
        st.header("⚙️ Sincronização")
        cols = list(df_raw.columns)
        c_ean = st.selectbox("Coluna EAN", cols, index=0)
        c_desc = st.selectbox("Descrição Tome Leve", cols, index=1 if len(cols)>1 else 0)
        c_busca = st.selectbox("Termo de Busca", cols, index=2 if len(cols)>2 else 0)

    if st.button("🚀 EXECUTAR VARREDURA DE MERCADO"):
        resultados = []
        barra = st.progress(0)
        status = st.empty()
        
        try: engine = create_engine(st.secrets["database"]["url"])
        except: engine = None

        for i, row in df_raw.iterrows():
            ean = str(row[c_ean])
            nome_tl = str(row[c_desc])
            termo = str(row[c_busca])
            
            status.info(f"🛰️ Rastreando item {i+1}: {nome_tl}")
            
            nome_conc, preco_atual = capturar_preco_savegnago(ean, termo)
            
            # Histórico Neon
            p_ant = None
            if engine and preco_atual > 0:
                try:
                    with engine.connect() as conn:
                        q = text('SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = :e ORDER BY "Data_Coleta" DESC LIMIT 1')
                        df_h = pd.read_sql(q, conn, params={"e": ean.split('.')[0]})
                        if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                except: pass

            var = round(((preco_atual - p_ant) / p_ant * 100), 2) if (preco_atual > 0 and p_ant) else 0

            resultados.append({
                "EAN": ean.split('.')[0],
                "Produto_TL": nome_tl,
                "Concorrente": nome_conc,
                "Preco_Atual": preco_atual,
                "Preco_Anterior": p_ant,
                "Variacao_%": var,
                "Data_Coleta": datetime.now()
            })
            barra.progress((i + 1) / len(df_raw))

        if resultados:
            df_final = pd.DataFrame(resultados)
            status.success("🏁 Auditoria Finalizada!")
            
            # Dashboard de impacto para a diretoria
            st.subheader("📊 Resultados da Auditoria Comercial")
            st.dataframe(df_final.style.highlight_min(axis=0, subset=['Preco_Atual'], color='lightgreen'), use_container_width=True)
            
            # Sincronização Neon
            if engine:
                try:
                    cols_db = ["EAN", "Descricao_Tome_Leve", "Descricao_Concorrente", "Preco_Atual", "Data_Coleta"]
                    # Mapeamos as colunas do DF para o banco
                    df_db = df_final[df_final["Preco_Atual"] > 0].copy()
                    df_db.columns = ["EAN", "Descricao_Tome_Leve", "Descricao_Concorrente", "Preco_Atual", "Preco_Anterior", "Variacao_P", "Data_Coleta"]
                    df_db[cols_db].to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Cofre Neon Sincronizado!", icon="🔐")
                except Exception as e:
                    st.error(f"Erro de Banco: {e}")
