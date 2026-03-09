import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Olho de Sauron", page_icon="👁️", layout="wide")
st.title("👁️ Olho de Sauron v10.0")
st.markdown("##### *Precisão Tradicional - A Solução para o Escritório*")

# --- MOTOR DE BUSCA "HUMANO" (VIA SESSÃO E FRONT-END) ---
def buscar_na_prateleira(ean, termo):
    # Criamos uma sessão para "parecer" uma pessoa navegando
    session = requests.Session()
    
    # Cabeçalhos que simulam um navegador Chrome real
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.savegnago.com.br/"
    }

    try:
        # Primeiro, damos um "olá" na página inicial para ganhar cookies de sessão
        session.get("https://www.savegnago.com.br/", headers=headers, timeout=10)
        
        # Agora, fazemos a busca usando o EAN (que é infalível)
        # Se o EAN falhar, usamos o termo de busca
        ean_limpo = str(ean).split('.')[0].strip()
        busca_final = ean_limpo if len(ean_limpo) > 10 else str(termo).strip()
        
        url_busca = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
        params = {"ft": busca_final, "_from": 0, "_to": 1}
        
        response = session.get(url_busca, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            dados = response.json()
            if dados:
                produto = dados[0]
                nome_conc = produto.get("productName")
                # Caminho direto para o preço comercial
                preco = produto["items"][0]["sellers"][0]["commertialOffer"]["Price"]
                return f"🎯 {nome_conc}", float(preco)
        
        return "Não Localizado", None
    except Exception as e:
        return f"Erro: {str(e)[:20]}", None

# --- CARGA E INTERFACE ---
arquivo = st.file_uploader("📂 Carregar Planilha de Alvos (.xlsx)", type=["xlsx"])

if arquivo:
    df_raw = pd.read_excel(arquivo).dropna(how='all').reset_index(drop=True)
    cols = list(df_raw.columns)
    
    with st.sidebar:
        st.header("⚙️ Mapeamento Comercial")
        c_ean = st.selectbox("Coluna do EAN", cols, index=0)
        c_desc = st.selectbox("Descrição Tome Leve", cols, index=1 if len(cols)>1 else 0)
        c_busca = st.selectbox("Termo de Busca", cols, index=2 if len(cols)>2 else 0)
        st.divider()
        st.caption("Dica: Use a coluna de busca com termos curtos (ex: 'Coca 2L')")

    if st.button("🚀 INICIAR VARREDURA LEGACY"):
        resultados = []
        barra = st.progress(0)
        status_msg = st.empty()
        
        # Conexão Neon (Opcional para a apresentação)
        try: engine = create_engine(st.secrets["database"]["url"])
        except: engine = None

        for i, row in df_raw.iterrows():
            ean_val = str(row[c_ean])
            nome_tl = str(row[c_desc])
            termo = str(row[c_busca])
            
            status_msg.info(f"🔎 Analisando Prateleira: {nome_tl}")
            
            # Busca com "alma" humana
            nome_conc, preco_atual = buscar_na_prateleira(ean_val, termo)
            
            # Histórico no Neon
            p_ant = None
            if engine and preco_atual:
                try:
                    with engine.connect() as conn:
                        ean_sql = ean_val.split('.')[0]
                        q = text('SELECT "Preco_Atual" FROM auditoria_precos_concorrencia WHERE "EAN" = :e ORDER BY "Data_Coleta" DESC LIMIT 1')
                        df_h = pd.read_sql(q, conn, params={"e": ean_sql})
                        if not df_h.empty: p_ant = float(df_h.iloc[0][0])
                except: pass

            var = round(((preco_atual - p_ant) / p_ant * 100), 2) if (preco_atual and p_ant) else 0

            resultados.append({
                "EAN": ean_val.split('.')[0],
                "Produto": nome_tl,
                "Concorrente": nome_conc,
                "Preço Atual": preco_atual if preco_atual else 0,
                "Variação %": var,
                "Data_Coleta": datetime.now()
            })
            
            barra.progress((i + 1) / len(df_raw))
            # O SEGREDO: Pausa real. Se for rápido demais, o Savegnago bloqueia.
            time.sleep(random.uniform(3.0, 5.0))

        if resultados:
            df_final = pd.DataFrame(resultados)
            status_msg.success("✅ Auditoria Finalizada com Precisão!")
            st.dataframe(df_final, use_container_width=True)
            
            # Exportação para o seu relatório comercial
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Relatório para a Diretoria", csv, "auditoria_final.csv")
