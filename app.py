import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
import time
import random
import streamlit.components.v1 as components

# --- 1. PROTOCOLO SONORO ---
def disparar_alerta_sonoro():
    audio_html = """<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-3.mp3" type="audio/mpeg"></audio>"""
    components.html(audio_html, height=0)

# --- 2. MOTOR DE BUSCA VTEX ---
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"
    }
    try:
        termo_limpo = str(termo).strip()
        r = requests.get(url, params={"ft": termo_limpo}, headers=headers, timeout=12)
        if r.status_code == 200:
            dados = r.json()
            if dados:
                item = dados[0]
                nome = item.get("productName")
                preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
                return nome, float(preco)
            return "Não Localizado", None
        return f"Erro {r.status_code}", None
    except Exception as e:
        return f"Falha: {str(e)}", None

# --- 3. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")

try: URL_DO_BANCO = st.secrets["database"]["url"]
except: URL_DO_BANCO = None

st.title("👁️ Olho de Sauron v6.4")
st.markdown("##### *Painel Estratégico de Preços - Tome Leve*")

# --- 4. EXECUÇÃO E INTERFACE ---
arquivo = st.file_uploader("Subir Planilha (.xlsx)", type=["xlsx"])

if arquivo:
    df_alvos = pd.read_excel(arquivo)
    
    # Sidebar de Inspeção
    colunas = [str(c).strip() for c in df_alvos.columns]
    with st.sidebar:
        st.write("### 🔍 Inspeção de Dados")
        st.write(f"Itens na Planilha: **{len(df_alvos)}**")
        col_nome = "Descricao_Tome_Leve" if "Descricao_Tome_Leve" in colunas else "Descricao Tome Leve"
        col_busca = "Busca_Otimizada" if "Busca_Otimizada" in colunas else "Busca Otimizada"
        col_ean = "EAN" if "EAN" in colunas else "ean"

    if st.button("🚀 INICIAR VARREDURA ESTRATÉGICA"):
        resultados = []
        barra = st.progress(0)
        status_msg = st.empty()
        
        engine = create_engine(URL_DO_BANCO) if URL_DO_BANCO else None

        for i, row in df_alvos.iterrows():
            n_tl = str(row[col_nome])
            t_busca = str(row[col_busca])
            v_ean = str(row[col_ean])
            
            status_msg.markdown(f"**Vigiando:** `{n_tl}` ({i+1}/{len(df_alvos)})")
            
            res_nome, res_preco = buscar_preco_vtex(t_busca)
            
            if res_preco is not None:
                p_ant = None
                if engine:
                    try:
                        q = f'SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = \'{v_ean}\' ORDER BY "Data_Coleta" DESC LIMIT 1'
                        with engine.connect() as conn:
                            df_h = pd.read_sql(q, conn)
                            if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                    except: pass
                
                var = round(((res_preco - p_ant) / p_ant * 100), 2) if p_ant else None
                status_txt = "🚨 Promoção" if (var and var <= -8) else "Normal"

                resultados.append({
                    "EAN": v_ean,
                    "Produto": n_tl,
                    "Concorrente": res_nome,
                    "Preço Atual": res_preco,
                    "Preço Anterior": p_ant,
                    "Variação %": var,
                    "Status": status_txt,
                    "Data_Coleta": datetime.now()
                })
            
            barra.progress((i + 1) / len(df_alvos))
            # Rate Limiting Estocástico
            time.sleep(random.uniform(1.2, 3.2))

        # --- EXIBIÇÃO DO DASHBOARD ---
        if resultados:
            df_res = pd.DataFrame(resultados)
            st.success("✅ Varredura Finalizada!")
            
            # --- DASHBOARD VISUAL ---
            st.divider()
            st.subheader("📊 Análise de Oportunidades")
            
            # Gráfico de Barras: Top 10 Maiores Descontos
            df_descontos = df_res[df_res["Variação %"] < 0].sort_values(by="Variação %", ascending=True).head(10)
            
            if not df_descontos.empty:
                st.write("**📉 Top 10 Maiores Descontos do Concorrente (%)**")
                # Invertemos o valor para o gráfico de barras ficar visualmente intuitivo (queda para baixo)
                st.bar_chart(df_descontos.set_index("Produto")["Variação %"])
            else:
                st.info("Nenhuma queda de preço detectada nesta rodada.")

            # Tabela Completa
            st.divider()
            st.subheader("📋 Relatório Completo")
            st.dataframe(df_res, use_container_width=True)
            
            # Sincronização e Alertas
            if engine:
                df_res.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                st.toast("Cofre Sincronizado!", icon="🔐")
            
            disparar_alerta_sonoro()
            st.balloons()
