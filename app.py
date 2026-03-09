import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v10.0")
st.markdown("##### *Precisão Humana, Velocidade de Máquina*")

# --- MOTOR DE BUSCA "HUMANO" (SIMULADOR DE NAVEGADOR) ---
def buscar_como_humano(ean, termo):
    # Usamos o termo de busca que o setor comercial já validou
    # Se o EAN estiver estranho, o termo salva a busca
    busca = str(termo).strip()
    url = f"https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.savegnago.com.br/"
    }

    try:
        # Simulamos a busca exatamente como o site faz quando você digita na barra
        params = {"ft": busca, "_from": 0, "_to": 2}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            if dados:
                # Pegamos o primeiro resultado da prateleira
                produto = dados[0]
                nome_site = produto.get("productName")
                preco = produto["items"][0]["sellers"][0]["commertialOffer"]["Price"]
                return nome_site, float(preco)
        
        return "Não Encontrado", None
    except:
        return "Erro de Conexão", None

# --- CARGA DE DADOS ---
arquivo = st.file_uploader("📂 Subir Planilha de Teste (.xlsx)", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo).dropna(how='all')
    
    with st.sidebar:
        st.header("⚙️ Mapeamento Simples")
        cols = list(df_raw.columns)
        # O Sauron agora tenta se auto-ajustar
        c_ean = st.selectbox("Coluna EAN", cols, index=0)
        c_desc = st.selectbox("Descrição Tome Leve", cols, index=1 if len(cols)>1 else 0)
        c_busca = st.selectbox("Termo para o Site", cols, index=2 if len(cols)>2 else 0)

    if st.button("🚀 INICIAR VARREDURA REAL"):
        resultados = []
        barra = st.progress(0)
        msg = st.empty()
        
        # Conexão com o Neon para o histórico
        try: engine = create_engine(st.secrets["database"]["url"])
        except: engine = None

        for i, row in df_raw.iterrows():
            ean = str(row[c_ean]).split('.')[0]
            nome_tl = str(row[c_desc])
            termo_site = str(row[c_busca])
            
            msg.info(f"🔎 Buscando no Savegnago: {nome_tl}")
            
            # O momento da verdade
            nome_conc, preco_atual = buscar_como_humano(ean, termo_site)
            
            # Busca histórico para mostrar evolução na planilha
            preco_ant = None
            if engine and preco_atual:
                try:
                    with engine.connect() as conn:
                        q = text('SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = :e ORDER BY "Data_Coleta" DESC LIMIT 1')
                        df_h = pd.read_sql(q, conn, params={"e": ean})
                        if not df_h.empty: preco_ant = float(df_h.iloc[0][0])
                except: pass

            var = round(((preco_atual - preco_ant) / preco_ant * 100), 2) if (preco_atual and preco_ant) else 0

            resultados.append({
                "EAN": ean,
                "Descricao_Tome_Leve": nome_tl,
                "Descricao_Concorrente": nome_conc,
                "Preco_Atual": preco_atual if preco_atual else 0,
                "Preco_Anterior": preco_ant,
                "Variacao_P": var,
                "Data_Coleta": datetime.now()
            })
            
            barra.progress((i + 1) / len(df_raw))
            # Pausa humana (essencial para o site não nos bloquear)
            time.sleep(random.uniform(2.0, 4.0))

        if resultados:
            df_final = pd.DataFrame(resultados)
            msg.success("✨ Planilha Estruturada com Sucesso!")
            st.dataframe(df_final, use_container_width=True)
            
            # Sincronização Neon (Apenas o necessário)
            if engine:
                try:
                    cols_db = ["EAN", "Descricao_Tome_Leve", "Descricao_Concorrente", "Preco_Atual", "Data_Coleta"]
                    df_final[df_final["Preco_Atual"] > 0][cols_db].to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Histórico salvo no Neon!", icon="🔐")
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")
