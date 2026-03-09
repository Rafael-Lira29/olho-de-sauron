import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
import time
import random

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v8.0")

# --- MOTOR DE BUSCA (SIMPLIFICADO E RÍGIDO) ---
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        # Busca direta e rápida
        r = requests.get(url, params={"ft": termo.strip(), "_from": 0, "_to": 0}, headers=headers, timeout=5)
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except: pass
    return "Não Localizado", None

# --- CARGA E MAPEAMENTO ---
arquivo = st.file_uploader("📂 Carregar Planilha", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo).dropna(how='all')
    cols = list(df_raw.columns)
    
    with st.sidebar:
        st.header("⚙️ Ajuste de Colunas")
        # Prevenção de erro: Tenta selecionar colunas diferentes por padrão
        c_ean = st.selectbox("EAN (Coluna Numérica)", cols, index=0)
        c_desc = st.selectbox("Descrição Interna", cols, index=1 if len(cols)>1 else 0)
        c_busca = st.selectbox("Termo de Busca", cols, index=2 if len(cols)>2 else 0)

    # --- TRAVA DE SEGURANÇA CONTRA ERRO DE CONFIGURAÇÃO ---
    if c_ean == c_busca or c_desc == c_busca:
        st.warning("🚨 Erro de Configuração: As colunas mapeadas não podem ser iguais. Ajuste na barra lateral.")
    else:
        if st.button("🚀 INICIAR VARREDURA INFALÍVEL"):
            resultados = []
            barra = st.progress(0)
            msg = st.empty()
            
            # Conexão Neon (Opcional no Dashboard)
            try: engine = create_engine(st.secrets["database"]["url"])
            except: engine = None

            for i, row in df_raw.iterrows():
                nome_tl = str(row[c_desc])
                termo = str(row[c_busca])
                ean_val = str(row[c_ean])
                
                msg.info(f"🔍 Auditando: {nome_tl}")
                
                # BUSCA
                res_nome, res_preco = buscar_preco_vtex(termo)
                
                # COLETA DE HISTÓRICO (PROTEGIDA)
                p_ant = None
                if engine and res_preco:
                    try:
                        q = f"SELECT \"Preco_Atual\" FROM auditoria_precos_concorrencia WHERE \"EAN\" = '{ean_val}' ORDER BY \"Data_Coleta\" DESC LIMIT 1"
                        with engine.connect() as conn:
                            df_h = pd.read_sql(q, conn)
                            if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                    except: pass
                
                # ADICIONA AO RESULTADO (SEMPRE ADICIONA PARA NÃO TRAVAR)
                var = round(((res_preco - p_ant) / p_ant * 100), 2) if (res_preco and p_ant) else 0
                resultados.append({
                    "EAN": ean_val, "Produto": nome_tl, "Concorrente": res_nome,
                    "Preço Atual": res_preco if res_preco else 0,
                    "Preço Anterior": p_ant, "Variação %": var, "Data_Coleta": datetime.now()
                })
                
                barra.progress((i + 1) / len(df_raw))
                time.sleep(random.uniform(0.5, 1.2))

            # --- EXIBIÇÃO FORÇADA DOS RESULTADOS ---
            if resultados:
                msg.success("✨ Auditoria Concluída!")
                df_res = pd.DataFrame(resultados)
                
                # Dashboard Simples e Direto
                st.subheader("📊 Resultados Consolidados")
                st.dataframe(df_res, use_container_width=True)
                
                # Gravação no Banco por último (para não travar a visualização)
                if engine:
                    try:
                        df_res.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                        st.toast("Cofre Sincronizado!", icon="🔐")
                    except Exception as e:
                        st.error(f"Erro ao salvar histórico: {e}")
