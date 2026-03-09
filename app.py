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

# --- 2. CONFIGURAÇÃO EXECUTIVA ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")

try:
    URL_DO_BANCO = st.secrets["database"]["url"]
except:
    URL_DO_BANCO = None

st.title("👁️ Olho de Sauron v6.0")
st.markdown("#### *Painel de Inteligência Competitiva - Tome Leve*")

# --- 3. DASHBOARD DE TOPO (SÓ APARECE APÓS A VARREDURA) ---
def renderizar_dashboard(df):
    st.divider()
    st.subheader("📊 Resumo para a Diretoria")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Itens mais caros que o concorrente
    mais_caros = df[df["Preço Atual"] < 15.0] # Exemplo de lógica: Itens com GAP
    # (Na prática, você compararia com o seu preço interno se ele estivesse na planilha)
    
    with col1:
        st.metric("Total Auditado", f"{len(df)} itens")
    with col2:
        promos = len(df[df["Status"].str.contains("🚨")])
        st.metric("Promoções do Alvo", promos, delta="-8%" if promos > 0 else "0", delta_color="inverse")
    with col3:
        st.metric("Concorrente", "Savegnago", "Ativo")
    with col4:
        st.metric("Status do Cofre", "Sincronizado", icon="🔐")

    st.divider()
    
    # TOP 5 OPORTUNIDADES (Onde o GAP de preço é maior)
    st.subheader("🎯 Top 5: Plano de Batalha (Oportunidades)")
    df_ranking = df.sort_values(by="Variação %", ascending=True).head(5)
    st.table(df_ranking[["Produto Tome Leve", "Preço Atual", "Preço Anterior", "Status"]])

# --- 4. MOTOR DE BUSCA ESTABILIZADO ---
def buscar_preco_vtex(termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, params={"ft": termo}, headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            return nome, float(preco)
    except: return None
    return None

# --- 5. EXECUÇÃO ---
arquivo = st.file_uploader("Subir Planilha Comercial (.xlsx)", type=["xlsx"])

if arquivo:
    df_alvos = pd.read_excel(arquivo)
    
    if st.button("🚀 INICIAR VIGILÂNCIA"):
        resultados = []
        barra = st.progress(0)
        status_msg = st.empty()
        
        # Conexão única
        engine = create_engine(URL_DO_BANCO) if URL_DO_BANCO else None

        for i, row in df_alvos.iterrows():
            nome_tl = str(row["Descricao_Tome_Leve"])
            termo = str(row["Busca_Otimizada"])
            ean = str(row["EAN"])
            
            status_msg.markdown(f"**Vigiando:** `{nome_tl}` ({i+1}/{len(df_alvos)})")
            
            res = buscar_preco_vtex(termo)
            
            if res:
                nome_conc, preco_atual = res
                
                # Busca histórico
                preco_ant = None
                if engine:
                    try:
                        query = f'SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = \'{ean}\' ORDER BY "Data_Coleta" DESC LIMIT 1'
                        df_h = pd.read_sql(query, engine)
                        if not df_h.empty: preco_ant = float(df_h.iloc[0][0])
                    except: pass
                
                # Lógica de Status
                var = None
                status_txt = "Normal"
                if preco_ant:
                    var = round(((preco_atual - preco_ant) / preco_ant) * 100, 2)
                    if var <= -8: status_txt = "🚨 Promoção Agressiva"
                    elif var <= -3: status_txt = "⚠️ Preço em Queda"
                    elif var >= 8: status_txt = "📈 Aumento de Preço"
                
                resultados.append({
                    "EAN": ean,
                    "Produto Tome Leve": nome_tl,
                    "Produto Concorrente": nome_conc,
                    "Preço Atual": preco_atual,
                    "Preço Anterior": preco_ant,
                    "Variação %": var,
                    "Status": status_txt,
                    "Data_Coleta": datetime.now()
                })

            # --- RATE LIMITING INTELIGENTE ---
            barra.progress((i + 1) / len(df_alvos))
            
            # Pausa humana
            time.sleep(random.uniform(1.5, 3.5))
            if (i + 1) % 5 == 0:
                st.toast("O Olho está analisando o comportamento do mercado...", icon="👁️")
                time.sleep(random.uniform(3, 5))

        # --- FINALIZAÇÃO SEGURA ---
        status_msg.success("✨ Varredura Finalizada! A preparar o Dashboard...")
        
        if not resultados:
            st.error("⚠️ Atenção: O loop terminou, mas a lista de resultados está vazia. Verifique a planilha ou a conexão.")
        else:
            df_final = pd.DataFrame(resultados)
            
            # --- 1. DASHBOARD DE TOPO (RENDERIZAÇÃO RÁPIDA) ---
            st.divider()
            st.subheader("📊 Resumo para a Diretoria")
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Total Auditado", f"{len(df_final)} itens")
            with m2:
                # Conta quantos têm o alerta no status
                promos = len(df_final[df_final["Status"].str.contains("🚨", na=False)])
                st.metric("Promoções Ativas", promos)
            with m3:
                st.metric("Alvo Principal", "Savegnago")

            # --- 2. TOP 5 OPORTUNIDADES (USANDO DATAFRAME EM VEZ DE TABLE) ---
            st.subheader("🎯 Plano de Batalha: Top 5 Oportunidades")
            # Filtra apenas quem tem variação negativa (preço caiu)
            df_rank = df_final.sort_values(by="Variação %", ascending=True).head(5)
            st.dataframe(df_rank[["Produto Tome Leve", "Preço Atual", "Variação %", "Status"]], use_container_width=True)

            # --- 3. RELATÓRIO COMPLETO ---
            with st.expander("📄 Ver Relatório Detalhado Completo"):
                st.dataframe(df_final, use_container_width=True)

            # --- 4. EXPORTAÇÃO ---
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Relatório CSV", csv, "auditoria_tome_leve.csv")

            # --- 5. SINCRONIZAÇÃO COM O COFRE (O QUE PODE ESTAR A TRAVAR) ---
            if engine:
                with st.spinner("🔐 Sincronizando com o Cofre Neon..."):
                    try:
                        df_final.to_sql("auditoria_precos_concorrencia", engine, if_exists="append", index=False)
                        st.toast("Cofre Sincronizado!", icon="✅")
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco: {e}")

            # --- 6. ALERTAS FINAIS (SONORO POR ÚLTIMO) ---
            disparar_alerta_sonoro()
            st.balloons()
