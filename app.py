import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
import time
import random

# ---------------------------------------------------
# CONFIGURAÇÃO DE SEGURANÇA (SECRETISMO)
# ---------------------------------------------------
st.set_page_config(page_title="Olho de Sauron", layout="wide")

# O código agora busca a senha diretamente dos Secrets do Streamlit
try:
    URL_DO_BANCO = st.secrets["database"]["url"]
except:
    URL_DO_BANCO = None

st.title("👁️ Olho de Sauron")
st.markdown("### Monitoramento de Preços em Tempo Real")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1067/1067555.png", width=80)
    st.header("Painel de Controle")
    concorrente = st.selectbox("Alvo", ["Savegnago"])
    if URL_DO_BANCO:
        st.success("🔐 Conexão com o Neon: Ativa")
    else:
        st.error("🚨 Cofre Neon não configurado!")

# ---------------------------------------------------
# MOTOR DE BUSCA (ESTABILIZADO)
# ---------------------------------------------------
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, params={"ft": termo}, headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except:
        return None
    return None

# ---------------------------------------------------
# LOGICA DE COMPARAÇÃO
# ---------------------------------------------------
def analisar_status(preco_novo, preco_antigo):
    if not preco_antigo: return "Novo", "Normal"
    variacao = round(((preco_novo - preco_antigo) / preco_antigo) * 100, 2)
    
    if variacao <= -8: return variacao, "🚨 Promoção Agressiva"
    if variacao <= -3: return variacao, "⚠️ Preço em Queda"
    if variacao >= 8: return variacao, "📈 Aumento de Preço"
    return variacao, "Normal"

# ---------------------------------------------------
# INTERFACE E EXECUÇÃO
# ---------------------------------------------------
arquivo = st.file_uploader("Carregar Planilha de Alvos (.xlsx)", type=["xlsx"])

if arquivo:
    df_alvos = pd.read_excel(arquivo)
    st.info(f"Carga pronta: {len(df_alvos)} itens identificados.")

    if st.button("🚀 INICIAR VARREDURA"):
        resultados = []
        barra = st.progress(0)
        info_status = st.empty()
        
        # Conexão única com o banco para evitar travamentos
        engine = create_engine(URL_DO_BANCO) if URL_DO_BANCO else None

        # Loop Sequencial Robusto (Evita bloqueios de IP e travamentos de UI)
        for i, row in df_alvos.iterrows():
            nome_tl = str(row["Descricao_Tome_Leve"])
            termo = str(row["Busca_Otimizada"])
            ean = str(row["EAN"])
            
            info_status.text(f"🔍 Analisando: {nome_tl}...")
            
            res = buscar_preco_vtex(termo)
            
            if res:
                nome_conc, preco_atual = res
                
                # Busca preço anterior se o banco estiver ativo
                preco_ant = None
                if engine:
                    try:
                        query = f"SELECT \"Preco_Atual\" FROM auditoria_precos_concorrencia WHERE \"EAN\" = '{ean}' ORDER BY \"Data_Coleta\" DESC LIMIT 1"
                        df_ant = pd.read_sql(query, engine)
                        if not df_ant.empty: preco_ant = float(df_ant.iloc[0][0])
                    except: pass
                
                var, status_msg = analisar_status(preco_atual, preco_ant)
                
                resultados.append({
                    "Concorrente": concorrente,
                    "EAN": ean,
                    "Produto Tome Leve": nome_tl,
                    "Produto Concorrente": nome_conc,
                    "Preço Atual": preco_atual,
                    "Preço Anterior": preco_ant,
                    "Variação %": var,
                    "Status": status_msg,
                    "Data_Coleta": datetime.now()
                })
            
            # Atualiza interface
            barra.progress((i + 1) / len(df_alvos))
            time.sleep(random.uniform(0.5, 1.5)) # Pausa humana para não ser bloqueado

        if resultados:
            df_final = pd.DataFrame(resultados)
            st.success("✅ Auditoria Concluída!")
            st.dataframe(df_final, use_container_width=True)

            # Gravação em lote (Muito mais rápido e seguro)
            if engine:
                try:
                    df_final.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Cofre Neon atualizado!", icon="🔐")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
