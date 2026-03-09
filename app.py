import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# -----------------------------
# CONFIGURAÇÃO
# -----------------------------
st.set_page_config(page_title="Sauron v10", page_icon="👁️", layout="wide")
st.title("👁️ Sauron v10 — Inteligência de Preços Nacional")

# Sessão persistente: O segredo para não ser bloqueado em múltiplas buscas
session = requests.Session()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Connection": "keep-alive"
}

# -----------------------------
# CONCORRENTES SUPORTADOS
# -----------------------------
CONCORRENTES = {
    "Savegnago": "https://www.savegnago.com.br",
    "Pao de Acucar": "https://www.paodeacucar.com",
}

with st.sidebar:
    st.header("⚙️ Operação")
    concorrente = st.selectbox("Concorrente Alvo", list(CONCORRENTES.keys()))
    BASE_URL = CONCORRENTES[concorrente]

# -----------------------------
# EXTRATOR SEGURO (MÓDULO INTERNO)
# -----------------------------
def extrair_preco(item):
    """Garante que a navegação no JSON não quebre o app"""
    try:
        nome = item.get("productName", "Sem Nome")
        sellers = item.get("items", [])[0].get("sellers", [])
        offer = sellers[0].get("commertialOffer", {})
        preco = offer.get("Price") or offer.get("ListPrice")
        if preco and preco > 0:
            return nome, float(preco)
    except Exception:
        pass
    return None, None

# -----------------------------
# MOTORES DE BUSCA
# -----------------------------
def buscar_por_ean(ean_limpo):
    url = f"{BASE_URL}/api/catalog_system/pub/products/search"
    params = {"fq": f"alternateIds_Ean:{ean_limpo}"}
    try:
        r = session.get(url, params=params, headers=HEADERS, timeout=8)
        if r.status_code == 200 and r.json():
            return extrair_preco(r.json()[0])
    except: pass
    return None, None

def buscar_por_nome(termo):
    url = f"{BASE_URL}/api/catalog_system/pub/products/search"
    # Foca nas palavras principais para evitar Erro 400 em textos longos
    termo_limpo = " ".join(str(termo).strip().split()[:3])
    params = {"ft": termo_limpo, "_from": 0, "_to": 2}
    try:
        r = session.get(url, params=params, headers=HEADERS, timeout=8)
        if r.status_code == 200 and r.json():
            return extrair_preco(r.json()[0])
    except: pass
    return None, None

def buscar_preco(ean_bruto, termo):
    # O Fator de Cura do EAN (Excel -> EAN Puro)
    ean_str = str(ean_bruto).split('.')[0].strip()
    if len(ean_str) == 14 and ean_str.startswith('0'):
        ean_str = ean_str[1:]

    nome, preco = buscar_por_ean(ean_str)
    if preco:
        return f"🎯 {nome}", preco, ean_str

    nome, preco = buscar_por_nome(termo)
    if preco:
        return nome, preco, ean_str

    return "Não Localizado", None, ean_str

# -----------------------------
# INTERFACE
# -----------------------------
arquivo = st.file_uploader("📂 Carregar Planilha de Produtos (.xlsx)", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo).dropna(how="all").reset_index(drop=True)
    cols = list(df_raw.columns)

    with st.sidebar:
        st.divider()
        st.header("⚙️ Colunas")
        c_ean = st.selectbox("EAN", cols, index=0)
        c_desc = st.selectbox("Descrição", cols, index=1 if len(cols)>1 else 0)
        c_busca = st.selectbox("Busca Otimizada", cols, index=2 if len(cols)>2 else 0)

    if st.button("🚀 Iniciar Varredura Nacional"):
        resultados = []
        barra = st.progress(0)
        msg = st.empty()

        try: engine = create_engine(st.secrets["database"]["url"])
        except: engine = None

        for i, row in df_raw.iterrows():
            ean_cru = row[c_ean]
            nome_tl = str(row[c_desc])
            termo = str(row[c_busca])

            msg.info(f"🔍 Auditando: {nome_tl}")

            res_nome, res_preco, ean_proc = buscar_preco(ean_cru, termo)

            # Histórico Blindado contra Erros de Sintaxe SQL
            preco_anterior = None
            if engine and res_preco:
                try:
                    query = text('SELECT "Preco" FROM precos WHERE "EAN" = :ean ORDER BY "Data_Coleta" DESC LIMIT 1')
                    with engine.connect() as conn:
                        df_h = pd.read_sql(query, conn, params={"ean": ean_proc})
                        if not df_h.empty:
                            preco_anterior = float(df_h.iloc[0][0])
                except Exception:
                    pass

            variacao = None
            promocao = False
            if res_preco and preco_anterior and preco_anterior > 0:
                variacao = round(((res_preco - preco_anterior) / preco_anterior) * 100, 2)
                if variacao <= -8:
                    promocao = True

            resultados.append({
                "EAN": ean_proc,
                "Produto_TL": nome_tl,
                "Produto_Concorrente": res_nome,
                "Concorrente": concorrente,
                "Preco": res_preco if res_preco else 0.0,
                "Preco_Anterior": preco_anterior,
                "Variacao_%": variacao,
                "Promocao": promocao,
                "Data_Coleta": datetime.now()
            })

            barra.progress((i + 1) / len(df_raw))
            time.sleep(random.uniform(1.2, 2.5))

        # -----------------------------
        # DASHBOARD & BANCO DE DADOS
        # -----------------------------
        if resultados:
            df_res = pd.DataFrame(resultados)
            msg.success("✨ Auditoria concluída com precisão cirúrgica!")
            st.dataframe(df_res, use_container_width=True)

            promocoes = df_res[df_res["Promocao"] == True]
            if not promocoes.empty:
                st.warning(f"⚠️ {len(promocoes)} Promoções detectadas na rede {concorrente}")
                st.dataframe(promocoes[["Produto_TL", "Preco", "Variacao_%"]])

            csv = df_res.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Baixar Relatório", csv, "sauron_relatorio.csv", "text/csv")

            if engine:
                try:
                    # Impede que produtos "Não Localizados" sujem o histórico da Diretoria
                    df_res_db = df_res[df_res["Preco"] > 0][[
                        "EAN", "Produto_TL", "Produto_Concorrente", 
                        "Concorrente", "Preco", "Data_Coleta"
                    ]]
                    if not df_res_db.empty:
                        df_res_db.to_sql("precos", engine, if_exists="append", index=False)
                        st.toast("🔐 Banco de dados atualizado em segurança")
                except Exception as e:
                    st.error(f"Erro de sincronização: {e}")
