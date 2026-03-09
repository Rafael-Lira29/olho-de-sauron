import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v8.3.2")
st.markdown("##### *Monitoramento de Preços Tome Leve*")

# --- MOTOR DE BUSCA VTEX (REFINADO) ---
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    # User-Agent mais robusto para evitar bloqueios
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        # Pega as 3 primeiras palavras para aumentar a chance de acerto na API
        termo_curto = " ".join(str(termo).strip().split()[:3])
        params = {"ft": termo_curto, "_from": 0, "_to": 1}
        
        r = requests.get(url, params=params, headers=headers, timeout=8)
        
        if r.status_code != 200:
            return f"Erro HTTP {r.status_code}", None
        
        data = r.json()
        if not data:
            return "Não Localizado", None

        item = data[0]
        nome = item.get("productName", "Sem Nome")
        
        # Navegação segura no JSON para evitar erros de 'None'
        try:
            items = item.get("items", [])
            if items:
                sellers = items[0].get("sellers", [])
                if sellers:
                    offer = sellers[0].get("commertialOffer", {})
                    preco = offer.get("Price")
                    if preco is not None:
                        return nome, float(preco)
        except (KeyError, IndexError):
            pass

    except Exception as e:
        return f"Falha Técnica", None

    return "Preço não disponível", None

# --- INTERFACE ---
arquivo = st.file_uploader("📂 Carregar Planilha Comercial (.xlsx)", type=["xlsx"])

if arquivo:
    # Lemos a planilha e garantimos que os índices estejam limpos
    df_raw = pd.read_excel(arquivo).dropna(how='all').reset_index(drop=True)
    cols = list(df_raw.columns)

    with st.sidebar:
        st.header("⚙️ Configuração de Colunas")
        c_ean = st.selectbox("Identificador (EAN)", cols, index=0)
        c_desc = st.selectbox("Descrição Tome Leve", cols, index=1 if len(cols) > 1 else 0)
        c_busca = st.selectbox("Termo de Busca", cols, index=2 if len(cols) > 2 else 0)

    if st.button("🚀 INICIAR VARREDURA ESTRATÉGICA"):
        resultados = []
        barra = st.progress(0)
        msg = st.empty()

        # Conexão com o banco Neon via Secrets
        try:
            engine = create_engine(st.secrets["database"]["url"])
        except Exception as e:
            engine = None
            st.sidebar.error("⚠️ Cofre Neon não conectado.")

        for i, row in df_raw.iterrows():
            nome_tl = str(row[c_desc])
            termo = str(row[c_busca])
            ean_val = str(row[c_ean])

            msg.info(f"🔍 Analisando: {nome_tl}")
            res_nome, res_preco = buscar_preco_vtex(termo)

            preco_anterior = None
            # Só buscamos histórico se a captura atual foi bem-sucedida
            if engine and res_preco:
                try:
                    query = text("""
                        SELECT "Preco_Atual"
                        FROM auditoria_precos_concorrencia
                        WHERE "EAN" = :ean
                        ORDER BY "Data_Coleta" DESC
                        LIMIT 1
                    """)
                    with engine.connect() as conn:
                        df_h = pd.read_sql(query, conn, params={"ean": ean_val})
                        if not df_h.empty:
                            preco_anterior = float(df_h.iloc[0][0])
                except:
                    pass

            # Cálculo de variação (apenas se houver histórico)
            variacao = None
            if res_preco and preco_anterior and preco_anterior > 0:
                variacao = round(((res_preco - preco_anterior) / preco_anterior) * 100, 2)

            resultados.append({
                "EAN": ean_val,
                "Descricao_Tome_Leve": nome_tl,
                "Descricao_Concorrente": res_nome,
                "Preco_Atual": res_preco if res_preco else 0,
                "Preco_Anterior": preco_anterior,
                "Variacao_P": variacao,
                "Data_Coleta": datetime.now()
            })

            barra.progress((i + 1) / len(df_raw))
            # Rate Limiting Humano
            time.sleep(random.uniform(1.2, 2.2))

        if resultados:
            df_res = pd.DataFrame(resultados)
            msg.success("✨ Auditoria Concluída com Sucesso!")
            
            # Exibição no Streamlit
            st.dataframe(df_res, use_container_width=True)

            # --- PREPARAÇÃO E SINCRONIZAÇÃO COM O BANCO ---
            # Filtramos rigorosamente as colunas que existem no PostgreSQL
            colunas_db = [
                "EAN", "Descricao_Tome_Leve", "Descricao_Concorrente", 
                "Preco_Atual", "Data_Coleta"
            ]
            
            # Filtramos apenas as capturas bem-sucedidas para não sujar o histórico com zeros
            df_para_banco = df_res[df_res["Preco_Atual"] > 0][colunas_db]

            if engine and not df_para_banco.empty:
                try:
                    df_para_banco.to_sql(
                        "auditoria_precos_concorrencia",
                        engine,
                        if_exists="append",
                        index=False
                    )
                    st.toast("🔐 Cofre Neon Sincronizado!", icon="🔐")
                except Exception as e:
                    st.error(f"Erro de Sincronização: {e}")
            
            # Exportação para uso imediato no escritório
            csv = df_res.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Baixar Relatório (CSV)", csv, "auditoria_sauron.csv", "text/csv")
