import os
# Força o servidor do Streamlit a instalar o navegador Chrome invisível no arranque
os.system("playwright install chromium")
import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random
import json

# IMPORTAÇÃO DO NAVEGADOR REAL (A CHAVE PARA O SUCESSO)
from playwright.sync_api import sync_playwright

# -----------------------------
# CONFIGURAÇÃO
# -----------------------------
st.set_page_config(page_title="Sauron v12", page_icon="👁️", layout="wide")
st.title("👁️ Sauron v12 — O Navegador Fantasma")
st.markdown("##### *Bypass de Firewall e Captura com Playwright*")

# -----------------------------
# CONCORRENTES SUPORTADOS
# -----------------------------
CONCORRENTES = {
    "Savegnago": "https://www.savegnago.com.br",
}

with st.sidebar:
    st.header("⚙️ Operação")
    concorrente = st.selectbox("Concorrente Alvo", list(CONCORRENTES.keys()))
    BASE_URL = CONCORRENTES[concorrente]

# -----------------------------
# EXTRATOR SEGURO DE PREÇO
# -----------------------------
def extrair_preco(item):
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
# MOTORES DE BUSCA VIA NAVEGADOR INVISÍVEL
# -----------------------------
def buscar_preco_com_navegador(ean_bruto, termo):
    ean_str = str(ean_bruto).split('.')[0].strip()
    if len(ean_str) == 14 and ean_str.startswith('0'):
        ean_str = ean_str[1:]
        
    termo_limpo = " ".join(str(termo).strip().split()[:3])

    # Abrimos o navegador real invisível para furar o bloqueio
    with sync_playwright() as p:
        # headless=True: o navegador roda em background. Se quiser VER a magia, mude para False
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # TENTATIVA 1: Busca Sniper por EAN através do navegador
            url_ean = f"{BASE_URL}/api/catalog_system/pub/products/search?fq=alternateIds_Ean:{ean_str}"
            page.goto(url_ean, wait_until="networkidle")
            time.sleep(1.5) # Simula o tempo de leitura humana
            
            conteudo = page.inner_text("body")
            dados = json.loads(conteudo)
            
            if dados and isinstance(dados, list):
                nome, preco = extrair_preco(dados[0])
                if preco:
                    browser.close()
                    return f"🎯 {nome}", preco, ean_str

        except Exception as e:
            pass # Se o EAN falhar, segue para a próxima tentativa

        try:
            # TENTATIVA 2: Busca por Texto através do navegador
            url_texto = f"{BASE_URL}/api/catalog_system/pub/products/search?ft={termo_limpo}&_from=0&_to=2"
            page.goto(url_texto, wait_until="networkidle")
            time.sleep(1.5)
            
            conteudo = page.inner_text("body")
            dados = json.loads(conteudo)
            
            if dados and isinstance(dados, list):
                nome, preco = extrair_preco(dados[0])
                if preco:
                    browser.close()
                    return nome, preco, ean_str

        except Exception:
            pass

        browser.close()
    
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

    if st.button("🚀 Iniciar Invasão Silenciosa"):
        resultados = []
        barra = st.progress(0)
        msg = st.empty()

        try: engine = create_engine(st.secrets["database"]["url"])
        except: engine = None

        for i, row in df_raw.iterrows():
            ean_cru = row[c_ean]
            nome_tl = str(row[c_desc])
            termo = str(row[c_busca])

            msg.info(f"🕵️‍♂️ Navegador rastreando: {nome_tl}...")

            res_nome, res_preco, ean_proc = buscar_preco_com_navegador(ean_cru, termo)

            preco_anterior = None
            if engine and res_preco:
                try:
                    query = text('SELECT "Preco" FROM precos WHERE "EAN" = :ean ORDER BY "Data_Coleta" DESC LIMIT 1')
                    with engine.connect() as conn:
                        df_h = pd.read_sql(query, conn, params={"ean": ean_proc})
                        if not df_h.empty:
                            preco_anterior = float(df_h.iloc[0][0])
                except:
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

        if resultados:
            df_res = pd.DataFrame(resultados)
            msg.success("✨ Bloqueios contornados. Auditoria concluída!")
            st.dataframe(df_res, use_container_width=True)

            promocoes = df_res[df_res["Promocao"] == True]
            if not promocoes.empty:
                st.warning(f"⚠️ {len(promocoes)} Promoções detectadas!")
                st.dataframe(promocoes[["Produto_TL", "Preco", "Variacao_%"]])

            csv = df_res.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Baixar Relatório Dourado", csv, "sauron_relatorio_final.csv", "text/csv")

            if engine:
                try:
                    df_res_db = df_res[df_res["Preco"] > 0][[
                        "EAN", "Produto_TL", "Produto_Concorrente", 
                        "Concorrente", "Preco", "Data_Coleta"
                    ]]
                    if not df_res_db.empty:
                        df_res_db.to_sql("precos", engine, if_exists="append", index=False)
                        st.toast("🔐 Banco de dados atualizado")
                except Exception as e:
                    st.error(f"Erro de sincronização: {e}")
