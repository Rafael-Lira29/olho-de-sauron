import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
from concurrent.futures import ThreadPoolExecutor
import time

# ---------------------------------------------------
# CONFIGURAÇÃO DO APP
# ---------------------------------------------------
st.set_page_config(page_title="Olho de Sauron", layout="wide")

st.title("👁️ Olho de Sauron")
st.subheader("Radar de Inteligência Competitiva - Tome Leve")

# Tenta carregar a URL dos Secrets por segurança, mas mantém o input manual como fallback
try:
    url_padrao = st.secrets["database"]["url"]
except:
    url_padrao = ""

with st.sidebar:
    st.header("Configurações")
    concorrente = st.selectbox("Concorrente Alvo", ["Savegnago"])
    url_banco = st.text_input("URL Banco PostgreSQL", value=url_padrao, type="password")
    max_threads = st.slider("Velocidade (Threads)", 1, 10, 5)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ---------------------------------------------------
# FUNÇÕES DE APOIO
# ---------------------------------------------------
def buscar_preco(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    try:
        r = requests.get(url, params={"ft": termo}, headers=HEADERS, timeout=10)
        if r.status_code == 200 and r.json():
            prod = r.json()[0]
            nome = prod.get("productName")
            preco = prod["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except:
        return None
    return None

def detectar_promocao(v):
    if v is None: return "Novo Produto"
    if v <= -8: return "🚨 Promoção Agressiva"
    if v <= -3: return "⚠️ Preço em Queda"
    if v >= 8: return "📈 Aumento de Preço"
    return "Normal"

def buscar_preco_anterior(engine, ean):
    if not engine: return None
    try:
        # Nota: Ajustei o nome da tabela para o que usamos anteriormente
        query = f"SELECT \"Preco_Atual\" FROM auditoria_precos_concorrencia WHERE \"EAN\" = '{ean}' ORDER BY \"Data_Coleta\" DESC LIMIT 1"
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            return float(df.iloc[0]["Preco_Atual"]) if not df.empty else None
    except:
        return None

# ---------------------------------------------------
# PROCESSAMENTO OTIMIZADO
# ---------------------------------------------------
def processar_linha(row, engine):
    termo = str(row["Busca_Otimizada"])
    ean = str(row["EAN"])
    nome_tl = str(row["Descricao_Tome_Leve"])

    res = buscar_preco(termo)
    if not res: return None

    nome_conc, preco_atual = res
    preco_antigo = buscar_preco_anterior(engine, ean)
    
    variacao = None
    if preco_antigo:
        variacao = round(((preco_atual - preco_antigo) / preco_antigo) * 100, 2)

    return {
        "Concorrente": concorrente,
        "EAN": ean,
        "Produto_TL": nome_tl,
        "Produto_Conc": nome_conc,
        "Preco_Atual": preco_atual,
        "Preco_Anterior": preco_antigo,
        "Variacao_%": variacao,
        "Status": detectar_promocao(variacao),
        "Data_Coleta": datetime.now()
    }

# ---------------------------------------------------
# INTERFACE PRINCIPAL
# ---------------------------------------------------
arquivo = st.file_uploader("Carregar planilha de produtos (.xlsx)", type=["xlsx"])

if arquivo:
    df_alvos = pd.read_excel(arquivo)
    st.success(f"{len(df_alvos)} produtos prontos para análise.")

    if st.button("🚀 Iniciar Varredura de Mercado"):
        resultados = []
        progresso = st.progress(0)
        
        # Criamos o engine UMA VEZ fora da thread para eficiência
        engine = None
        if url_banco:
            try: engine = create_engine(url_banco)
            except: st.error("Erro ao conectar ao Banco de Dados.")

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            # Passamos o engine para as threads usarem a mesma base de conexão
            futures = [executor.submit(processar_linha, row, engine) for _, row in df_alvos.iterrows()]
            
            for i, future in enumerate(futures):
                res = future.result()
                if res: resultados.append(res)
                progresso.progress((i + 1) / len(df_alvos))

        if resultados:
            df_final = pd.DataFrame(resultados)
            st.divider()
            st.subheader("📊 Resultados da Auditoria")
            st.dataframe(df_final, use_container_width=True)

            # Dashboard Rápido
            col1, col2 = st.columns(2)
            with col1:
                promos = df_final[df_final["Status"] == "🚨 Promoção Agressiva"]
                if not promos.empty:
                    st.error(f"⚠️ Detectamos {len(promos)} promoções agressivas!")
                    st.dataframe(promos[["Produto_TL", "Preco_Atual", "Variacao_%"]])
            
            # Exportação e Gravação
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Relatório CSV", csv, "auditoria.csv")

            if engine:
                try:
                    df_final.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.info("💾 Histórico sincronizado com o cofre Neon.")
                except Exception as e:
                    st.warning(f"Os dados não puderam ser salvos: {e}")
