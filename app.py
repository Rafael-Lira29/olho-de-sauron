import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------
# CONFIGURAÇÃO DO APP
# ---------------------------------------------------

st.set_page_config(page_title="Olho de Sauron", layout="wide")

st.title("👁️ Olho de Sauron")
st.subheader("Radar de Inteligência Competitiva")

concorrente = st.sidebar.selectbox(
    "Concorrente",
    ["Savegnago"]
)

url_banco = st.sidebar.text_input(
    "URL Banco PostgreSQL",
    type="password"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ---------------------------------------------------
# FUNÇÃO BUSCA PREÇO NA API VTEX
# ---------------------------------------------------

def buscar_preco(termo):

    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"

    try:

        r = requests.get(
            url,
            params={"ft": termo},
            headers=HEADERS,
            timeout=8
        )

        if r.status_code != 200:
            return None

        data = r.json()

        if not data:
            return None

        for prod in data:

            try:

                nome = prod.get("productName")

                items = prod.get("items", [])

                if not items:
                    continue

                sellers = items[0].get("sellers", [])

                if not sellers:
                    continue

                preco = sellers[0]["commertialOffer"]["Price"]

                if preco:
                    return nome, float(preco)

            except Exception:
                continue

    except Exception:
        return None

    return None


# ---------------------------------------------------
# FUNÇÃO VARIAÇÃO DE PREÇO
# ---------------------------------------------------

def calcular_variacao(preco_antigo, preco_novo):

    if preco_antigo is None:
        return None

    variacao = ((preco_novo - preco_antigo) / preco_antigo) * 100

    return round(variacao, 2)


# ---------------------------------------------------
# DETECTOR DE PROMOÇÕES
# ---------------------------------------------------

def detectar_promocao(variacao):

    if variacao is None:
        return "Novo Produto"

    if variacao <= -8:
        return "🚨 Promoção Agressiva"

    elif variacao <= -3:
        return "⚠️ Preço em Queda"

    elif variacao >= 8:
        return "📈 Aumento de Preço"

    else:
        return "Normal"


# ---------------------------------------------------
# BUSCAR PREÇO ANTERIOR NO BANCO
# ---------------------------------------------------

def buscar_preco_anterior(engine, ean):

    try:

        query = f"""
        SELECT "Preco"
        FROM auditoria_precos
        WHERE "EAN" = '{ean}'
        ORDER BY "Data_Hora" DESC
        LIMIT 1
        """

        df = pd.read_sql(query, engine)

        if not df.empty:
            return float(df.iloc[0]["Preco"])

    except Exception:
        pass

    return None


# ---------------------------------------------------
# PROCESSAMENTO DE LINHA
# ---------------------------------------------------

def processar_linha(row):

    termo = str(row["Busca_Otimizada"])
    nome = str(row["Descricao_Tome_Leve"])
    ean = str(row["EAN"])

    res = buscar_preco(termo)

    if not res:
        return None

    nome_conc, preco = res

    preco_antigo = None
    variacao = None
    status = "Novo"

    if url_banco:

        try:

            engine = create_engine(url_banco)

            preco_antigo = buscar_preco_anterior(engine, ean)

            variacao = calcular_variacao(preco_antigo, preco)

            status = detectar_promocao(variacao)

        except Exception:
            pass

    return {
        "Concorrente": concorrente,
        "EAN": ean,
        "Produto_TL": nome,
        "Produto_Conc": nome_conc,
        "Preco_Atual": preco,
        "Preco_Anterior": preco_antigo,
        "Variacao_%": variacao,
        "Status": status,
        "Data_Hora": datetime.now()
    }


# ---------------------------------------------------
# INTERFACE STREAMLIT
# ---------------------------------------------------

arquivo = st.file_uploader(
    "Carregar planilha de produtos",
    type=["xlsx"]
)

if arquivo:

    df = pd.read_excel(arquivo)

    st.success(f"{len(df)} produtos carregados")

    st.dataframe(df.head())

    if st.button("🚀 Iniciar Varredura"):

        resultados = []

        progresso = st.progress(0)

        total = len(df)

        with ThreadPoolExecutor(max_workers=8) as executor:

            futures = [
                executor.submit(processar_linha, row)
                for _, row in df.iterrows()
            ]

            for i, future in enumerate(futures):

                res = future.result()

                if res:
                    resultados.append(res)

                progresso.progress((i + 1) / total)

        if resultados:

            df_final = pd.DataFrame(resultados)

            st.success(f"✔ {len(df_final)} produtos auditados")

            st.dataframe(df_final)

            # ---------------------------------------------------
            # ALERTAS
            # ---------------------------------------------------

            promocoes = df_final[df_final["Status"] == "🚨 Promoção Agressiva"]

            if not promocoes.empty:

                st.error("🚨 Promoções agressivas detectadas!")

                st.dataframe(promocoes)

            # ---------------------------------------------------
            # EXPORTAÇÃO CSV
            # ---------------------------------------------------

            csv = df_final.to_csv(index=False).encode()

            st.download_button(
                "📥 Baixar relatório CSV",
                csv,
                "auditoria_precos.csv"
            )

            # ---------------------------------------------------
            # SALVAR NO BANCO
            # ---------------------------------------------------

            if url_banco:

                try:

                    engine = create_engine(url_banco)

                    df_final.to_sql(
                        "auditoria_precos",
                        engine,
                        if_exists="append",
                        index=False
                    )

                    st.info("💾 Dados armazenados no banco.")

                except Exception as e:

                    st.error(f"Erro ao salvar no banco: {e}")
