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

# --- 2. MOTOR DE BUSCA (COM DIAGNÓSTICO DE ERRO) ---
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
    try:
        r = requests.get(url, params={"ft": termo}, headers=headers, timeout=10)
        if r.status_code == 200:
            dados = r.json()
            if dados:
                item = dados[0]
                nome = item.get("productName")
                preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
                return nome, float(preco)
            return "Vazio", None # API respondeu mas não achou o produto
        return f"Erro {r.status_code}", None # Bloqueio de IP ou Erro de Servidor
    except Exception as e:
        return f"Falha: {str(e)}", None

# --- 3. INTERFACE E LOGICA ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")

try: URL_DO_BANCO = st.secrets["database"]["url"]
except: URL_DO_BANCO = None

st.title("👁️ Olho de Sauron v6.2")

arquivo = st.file_uploader("Subir Planilha (.xlsx)", type=["xlsx"])

if arquivo:
    df_alvos = pd.read_excel(arquivo)
    
    # INSPEÇÃO DE COLUNAS (Onde o erro costuma estar)
    colunas_encontradas = [str(c).strip() for c in df_alvos.columns]
    st.sidebar.write("### 🔍 Inspetor de Planilha")
    st.sidebar.write(f"Colunas lidas: {colunas_encontradas}")
    
    # Mapeamento Automático (Caso o senhor tenha usado espaços em vez de _)
    col_nome = "Descricao_Tome_Leve" if "Descricao_Tome_Leve" in colunas_encontradas else "Descricao Tome Leve"
    col_busca = "Busca_Otimizada" if "Busca_Otimizada" in colunas_encontradas else "Busca Otimizada"
    col_ean = "EAN" if "EAN" in colunas_encontradas else "ean"

    if st.button("🚀 INICIAR VARREDURA"):
        resultados = []
        falhas = 0
        barra = st.progress(0)
        status_msg = st.empty()
        
        engine = create_engine(URL_DO_BANCO) if URL_DO_BANCO else None

        for i, row in df_alvos.iterrows():
            try:
                # Lendo as colunas de forma segura
                n_tl = str(row[col_nome])
                t_busca = str(row[col_busca])
                v_ean = str(row[col_ean])
                
                status_msg.markdown(f"**Vigiando:** `{n_tl}`")
                
                res_nome, res_preco = buscar_preco_vtex(t_busca)
                
                if res_preco is not None:
                    # Lógica de Preço Anterior
                    p_ant = None
                    if engine:
                        try:
                            q = f'SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = \'{v_ean}\' ORDER BY "Data_Coleta" DESC LIMIT 1'
                            df_h = pd.read_sql(q, engine)
                            if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                        except: pass
                    
                    var = round(((res_preco - p_ant) / p_ant * 100), 2) if p_ant else None
                    status_txt = "🚨 Promoção" if (var and var <= -8) else "Normal"

                    resultados.append({
                        "EAN": v_ean,
                        "Produto Tome Leve": n_tl,
                        "Produto Concorrente": res_nome,
                        "Preço Atual": res_preco,
                        "Preço Anterior": p_ant,
                        "Variação %": var,
                        "Status": status_txt,
                        "Data_Coleta": datetime.now()
                    })
                else:
                    falhas += 1
                    st.sidebar.warning(f"⚠️ Falha no item {n_tl}: {res_nome}")

            except KeyError as e:
                st.error(f"❌ Erro crítico: A coluna {e} não foi encontrada na sua planilha!")
                break
            
            barra.progress((i + 1) / len(df_alvos))
            time.sleep(random.uniform(1.5, 3.0))

        # --- FINALIZAÇÃO ---
        status_msg.success(f"✨ Varredura concluída. Capturados: {len(resultados)} | Falhas: {falhas}")
        
        if resultados:
            df_res = pd.DataFrame(resultados)
            st.subheader("📊 Dashboard Executivo")
            
            c1, c2 = st.columns(2)
            c1.metric("Total de Itens", len(df_res))
            c2.metric("Sucesso de Captura", f"{(len(df_res)/(len(df_res)+falhas))*100:.1f}%")
            
            st.dataframe(df_res, use_container_width=True)
            
            if engine:
                df_res.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                st.toast("Cofre Sincronizado!")
            
            disparar_alerta_sonoro()
