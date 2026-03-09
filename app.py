import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine
import time
import random
import streamlit.components.v1 as components

# ---------------------------------------------------
# 1. PROTOCOLO SONORO (JAVASCRIPT)
# ---------------------------------------------------
def disparar_alerta_sonoro():
    """Injeta um pequeno script para tocar um som de notificação no navegador."""
    audio_html = """
        <audio autoplay>
            <source src="https://www.soundjay.com/buttons/sounds/button-3.mp3" type="audio/mpeg">
        </audio>
    """
    components.html(audio_html, height=0)

# ---------------------------------------------------
# 2. CONFIGURAÇÃO EXECUTIVA
# ---------------------------------------------------
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")

try:
    URL_DO_BANCO = st.secrets["database"]["url"]
except Exception:
    URL_DO_BANCO = None

st.title("👁️ Olho de Sauron v5.5")
st.markdown("##### *Sistema de Vigilância Competitiva - Inteligência Tome Leve*")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1067/1067555.png", width=80)
    st.header("Status de Operação")
    if URL_DO_BANCO:
        st.success("🔐 Conexão Neon: Ativa")
    else:
        st.error("🚨 Cofre Desconectado")
    
    concorrente_alvo = st.selectbox("Alvo da Auditoria", ["Savegnago"])
    st.divider()
    st.caption("Modo Sniper Híbrido com Rate Limiting Humano ativo.")

# ---------------------------------------------------
# 3. INTELIGÊNCIA DE MERCADO (API & ANÁLISE)
# ---------------------------------------------------
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
    try:
        r = requests.get(url, params={"ft": termo}, headers=headers, timeout=8)
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except: return None
    return None

def calcular_status(atual, anterior):
    if not anterior: return None, "Novo Produto"
    # Fórmula: $Variation = \frac{P_{new} - P_{old}}{P_{old}} \times 100$
    variacao = round(((atual - anterior) / anterior) * 100, 2)
    
    if variacao <= -8: return variacao, "🚨 Promoção Agressiva"
    if variacao <= -3: return variacao, "⚠️ Preço em Queda"
    if variacao >= 8: return variacao, "📈 Aumento de Preço"
    return variacao, "Normal"

# ---------------------------------------------------
# 4. EXECUÇÃO COM RATE LIMITING INTELIGENTE
# ---------------------------------------------------
arquivo = st.file_uploader("Carregar Alvos da Diretoria (.xlsx)", type=["xlsx"])

if arquivo:
    df_alvos = pd.read_excel(arquivo)
    st.info(f"📋 Carga de {len(df_alvos)} produtos identificada.")

    if st.button("🚀 INICIAR VARREDURA FURTIVA"):
        resultados = []
        alertas_promocao = []
        barra = st.progress(0)
        status_msg = st.empty()
        
        engine = create_engine(URL_DO_BANCO) if URL_DO_BANCO else None

        for i, row in df_alvos.iterrows():
            nome_tl = str(row["Descricao_Tome_Leve"])
            termo = str(row["Busca_Otimizada"])
            ean = str(row["EAN"])
            
            status_msg.text(f"🔍 Analisando item {i+1} de {len(df_alvos)}: {nome_tl}")
            
            # Captura de dados
            res = buscar_preco_vtex(termo)
            
            if res:
                nome_conc, preco_atual = res
                
                # Histórico no Neon
                preco_ant = None
                if engine:
                    try:
                        query = f'SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = \'{ean}\' ORDER BY "Data_Coleta" DESC LIMIT 1'
                        with engine.connect() as conn:
                            df_hist = pd.read_sql(query, conn)
                            if not df_hist.empty: preco_ant = float(df_hist.iloc[0][0])
                    except: pass
                
                var, msg = calcular_status(preco_atual, preco_ant)
                
                # Sistema de Notificações em Tempo Real
                if msg == "🚨 Promoção Agressiva":
                    st.toast(f"PROMOÇÃO DETECTADA: {nome_tl}", icon="🔥")
                    disparar_alerta_sonoro()
                    alertas_promocao.append(nome_tl)

                resultados.append({
                    "Concorrente": concorrente_alvo,
                    "EAN": ean,
                    "Produto Tome Leve": nome_tl,
                    "Produto Concorrente": nome_conc,
                    "Preço Atual": preco_atual,
                    "Preço Anterior": preco_ant,
                    "Variação %": var,
                    "Status": msg,
                    "Data_Coleta": datetime.now()
                })

            # --- RATE LIMITING INTELIGENTE (OSCILAÇÃO HUMANA) ---
            atraso = random.uniform(1.2, 3.5)
            if (i + 1) % 5 == 0: 
                atraso += random.uniform(3.0, 6.0) # Pausa de leitura
                st.toast("☕ O Olho está simulando uma leitura humana...", icon="👁️")
            
            barra.progress((i + 1) / len(df_alvos))
            time.sleep(atraso)

        # ---------------------------------------------------
        # 5. RELATÓRIO FINAL E EXPORTAÇÃO
        # ---------------------------------------------------
        if resultados:
            df_final = pd.DataFrame(resultados)
            st.success("✅ Auditoria Concluída com Sucesso!")
            disparar_alerta_sonoro() # Som de conclusão
            
            st.dataframe(df_final, use_container_width=True)

            if alertas_promocao:
                st.error(f"🛑 Atenção: {len(alertas_promocao)} promoções agressivas exigem revisão imediata!")

            # Gravação em lote no Neon
            if engine:
                try:
                    df_final.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                    st.toast("Histórico sincronizado!", icon="🔐")
                except Exception as e:
                    st.warning(f"Erro na sincronização: {e}")
            
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Relatório Executivo", csv, "relatorio_competitivo.csv")
