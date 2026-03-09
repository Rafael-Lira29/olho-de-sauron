import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
import time
import random
import streamlit.components.v1 as components

# --- 1. PROTOCOLO DE ALERTAS ---
def disparar_alerta_sonoro():
    components.html('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-3.mp3" type="audio/mpeg"></audio>', height=0)

# --- 2. MOTOR DE BUSCA ULTRA-LEVE (FIX: LEITE CONDENSADO) ---
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        termo_limpo = str(termo).strip()
        # O SEGREDO: _from=0&_to=0 pede apenas o primeiro item, evitando JSONs gigantes
        params = {"ft": termo_limpo, "_from": 0, "_to": 0}
        r = requests.get(url, params=params, headers=headers, timeout=5)
        
        if r.status_code == 200:
            dados = r.json()
            if dados and len(dados) > 0:
                item = dados[0]
                nome = item.get("productName")
                preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
                return nome, float(preco)
            return "Não Localizado", None
        return f"Erro {r.status_code}", None
    except:
        return "Timeout/Falha", None

# --- 3. CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")

try: URL_DO_BANCO = st.secrets["database"]["url"]
except: URL_DO_BANCO = None

st.title("👁️ Olho de Sauron v7.1")
st.markdown("##### *Inteligência de Mercado de Alta Performance*")

arquivo = st.file_uploader("📂 Subir Planilha (.xlsx)", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo)
    colunas = list(df_raw.columns)
    
    with st.sidebar:
        st.header("⚙️ Configuração")
        col_ean = st.selectbox("Coluna EAN", colunas, index=colunas.index("EAN") if "EAN" in colunas else 0)
        col_desc = st.selectbox("Descrição Interna", colunas, index=0)
        col_busca = st.selectbox("Termo de Busca", colunas, index=0)

    # --- TRAVA DE SEGURANÇA (MELHORIA SOLICITADA) ---
    st.subheader("🛡️ Validação de Integridade")
    erros = []
    if df_raw[col_ean].isnull().any(): erros.append("Existem linhas com EAN vazio.")
    if df_raw.duplicated(subset=[col_ean]).any(): erros.append("Existem EANs duplicados na planilha.")
    
    if erros:
        for erro in erros: st.error(erro)
        st.warning("Corrija a planilha para habilitar a varredura.")
    else:
        st.success("✅ Planilha validada e pronta para o escritório.")
        
        if st.button("🚀 INICIAR VARREDURA BLINDADA"):
            resultados = []
            barra = st.progress(0)
            status_msg = st.empty()
            engine = create_engine(URL_DO_BANCO) if URL_DO_BANCO else None

            for i, row in df_raw.iterrows():
                n_tl = str(row[col_desc])
                t_busca = str(row[col_busca])
                v_ean = str(row[col_ean])
                
                status_msg.info(f"🔍 Analisando: {n_tl}")
                
                res_nome, res_preco = buscar_preco_vtex(t_busca)
                
                if res_preco:
                    # Lógica de Preço Anterior
                    p_ant = None
                    if engine:
                        try:
                            q = f'SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = \'{v_ean}\' ORDER BY "Data_Coleta" DESC LIMIT 1'
                            with engine.connect() as conn:
                                df_h = pd.read_sql(q, conn)
                                if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                        except: pass
                    
                    var = round(((res_preco - p_ant) / p_ant * 100), 2) if p_ant else None
                    resultados.append({
                        "EAN": v_ean, "Produto": n_tl, "Concorrente": res_nome,
                        "Preço Atual": res_preco, "Preço Anterior": p_ant,
                        "Variação %": var, "Data_Coleta": datetime.now()
                    })
                
                barra.progress((i + 1) / len(df_raw))
                time.sleep(random.uniform(1.0, 2.5))

            if resultados:
                df_res = pd.DataFrame(resultados)
                
                # DASHBOARD DE DESCONTOS
                st.divider()
                st.subheader("📊 Top 10 Maiores Oportunidades")
                df_desc = df_res[df_res["Variação %"] < 0].sort_values(by="Variação %").head(10)
                if not df_desc.empty:
                    st.bar_chart(df_desc.set_index("Produto")["Variação %"])
                
                st.dataframe(df_res, use_container_width=True)
                
                if engine:
                    df_res.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Cofre Sincronizado!")
                
                disparar_alerta_sonoro()
                st.balloons()
