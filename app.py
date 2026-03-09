import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random
import streamlit.components.v1 as components

# --- 1. ALERTA SONORO ---
def disparar_alerta_sonoro():
    components.html('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-3.mp3" type="audio/mpeg"></audio>', height=0)

# --- 2. MOTOR SNIPER (EAN + TERMO) ---
def buscar_preco_vtex(ean, termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    # Limpeza profunda do EAN (Trata 14 dígitos do Excel e remove .0)
    ean_limpo = str(ean).split('.')[0].strip()
    if len(ean_limpo) == 14 and ean_limpo.startswith('0'):
        ean_limpo = ean_limpo[1:]

    # TENTATIVA 1: Busca Sniper por EAN (fq)
    try:
        params_ean = {"fq": f"alternateIds_Ean:{ean_limpo}", "_from": 0, "_to": 0}
        r = requests.get(url, params=params_ean, headers=headers, timeout=6)
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return f"🎯 {nome}", float(preco)
    except:
        pass

    # TENTATIVA 2: Busca por Termo Curto (ft)
    try:
        termo_busca = " ".join(str(termo).strip().split()[:3])
        params_ft = {"ft": termo_busca, "_from": 0, "_to": 0}
        r = requests.get(url, params=params_ft, headers=headers, timeout=6)
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except:
        pass

    return "Não Localizado", None

# --- 3. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v9.1")
st.markdown("##### *Inteligência de Mercado Tome Leve*")

# --- 4. FLUXO DE DADOS ---
arquivo = st.file_uploader("📂 Carregar Planilha Comercial (.xlsx)", type=["xlsx"])

if arquivo:
    # A planilha só é carregada se o arquivo existir (Fix NameError)
    df_raw = pd.read_excel(arquivo).dropna(how='all').reset_index(drop=True)
    colunas = list(df_raw.columns)
    
    with st.sidebar:
        st.header("⚙️ Configuração")
        c_ean = st.selectbox("Coluna do EAN", colunas, index=0)
        c_desc = st.selectbox("Coluna da Descrição", colunas, index=1 if len(colunas)>1 else 0)
        c_busca = st.selectbox("Coluna de Busca", colunas, index=2 if len(colunas)>2 else 0)
        st.divider()
        st.caption("Verifique se cada campo aponta para a coluna correta.")

    # TRAVA DE SEGURANÇA
    if c_ean == c_busca or c_desc == c_busca:
        st.error("🚨 Erro de Mapeamento: Você selecionou a mesma coluna para funções diferentes.")
    else:
        if st.button("🚀 INICIAR AUDITORIA SNIPER"):
            resultados = []
            barra = st.progress(0)
            status_msg = st.empty()
            
            # Conexão Neon
            try: engine = create_engine(st.secrets["database"]["url"])
            except: engine = None

            for i, row in df_raw.iterrows():
                n_tl = str(row[c_desc])
                t_busca = str(row[c_busca])
                v_ean = str(row[c_ean])
                
                status_msg.info(f"🔍 Auditando ({i+1}/{len(df_raw)}): {n_tl}")
                
                # Executa busca sniper
                res_nome, res_preco = buscar_preco_vtex(v_ean, t_busca)
                
                # Busca Preço Anterior
                p_ant = None
                if engine and res_preco:
                    try:
                        query = text('SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = :ean ORDER BY "Data_Coleta" DESC LIMIT 1')
                        ean_sql = v_ean.split('.')[0].strip()
                        if len(ean_sql) == 14 and ean_sql.startswith('0'): ean_sql = ean_sql[1:]
                        
                        with engine.connect() as conn:
                            df_h = pd.read_sql(query, conn, params={"ean": ean_sql})
                            if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                    except: pass
                
                # Cálculo de Variação
                var = round(((res_preco - p_ant) / p_ant * 100), 2) if (res_preco and p_ant and p_ant > 0) else 0

                resultados.append({
                    "EAN": v_ean.split('.')[0],
                    "Descricao_Tome_Leve": n_tl,
                    "Descricao_Concorrente": res_nome,
                    "Preco_Atual": res_preco if res_preco else 0,
                    "Preco_Anterior": p_ant,
                    "Variacao_P": var,
                    "Data_Coleta": datetime.now()
                })
                
                barra.progress((i + 1) / len(df_raw))
                time.sleep(random.uniform(1.0, 2.0))

            if resultados:
                df_res = pd.DataFrame(resultados)
                status_msg.success("✨ Auditoria Concluída!")
                st.dataframe(df_res, use_container_width=True)

                # SINCRONIZAÇÃO NEON (Filtro de Colunas)
                colunas_db = ["EAN", "Descricao_Tome_Leve", "Descricao_Concorrente", "Preco_Atual", "Data_Coleta"]
                df_db = df_res[df_res["Preco_Atual"] > 0][colunas_db]

                if engine and not df_db.empty:
                    try:
                        df_db.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                        st.toast("Cofre Neon Sincronizado!", icon="🔐")
                    except Exception as e:
                        st.error(f"Erro de Banco: {e}")
                
                disparar_alerta_sonoro()
                st.balloons()
