import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import time
import random

# --- MOTOR DE BUSCA HÍBRIDO (EAN + TERMO) ---
def buscar_preco_vtex(ean, termo):
    url = "https://www.savegnago.com.br/api/catalog_system/pub/products/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Connection": "keep-alive"
    }
    
    # 1. Limpeza do EAN (Garante que seja apenas os números, sem .0 do Excel)
    ean_limpo = str(ean).split('.')[0].strip()
    
    # TENTATIVA 1: Busca Sniper por EAN (Precisão de 100%)
    try:
        # Nota: Algumas lojas usam 'ean' outras 'alternateIds_Ean'
        params_ean = {"fq": f"alternateIds_Ean:{ean_limpo}", "_from": 0, "_to": 0}
        r = requests.get(url, params=params_ean, headers=headers, timeout=5)
        
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            if preco: return f"🎯 {nome}", float(preco)
    except:
        pass

    # TENTATIVA 2: Busca por Termo (Fallback caso o EAN não esteja indexado)
    try:
        termo_busca = " ".join(str(termo).strip().split()[:3]) # Pega apenas as 3 primeiras palavras
        params_ft = {"ft": termo_busca, "_from": 0, "_to": 1}
        r = requests.get(url, params=params_ft, headers=headers, timeout=5)
        
        if r.status_code == 200 and r.json():
            item = r.json()[0]
            nome = item.get("productName")
            preco = item["items"][0]["sellers"][0]["commertialOffer"].get("Price") or \
                    item["items"][0]["sellers"][0]["commertialOffer"].get("ListPrice")
            if preco: return nome, float(preco)
    except:
        pass

    return "Não Localizado", None

# --- ESTRUTURA PRINCIPAL (LOOP) ---
# Substitua o bloco de busca dentro do botão 'Iniciar Varredura' por este:
if st.button("🚀 INICIAR AUDITORIA"):
    resultados = []
    barra = st.progress(0)
    
    # Mapeamento dinâmico conforme sua última versão
    for i, row in df_raw.iterrows():
        v_ean = row[c_ean]
        v_desc = row[c_desc]
        v_busca = row[c_busca]
        
        st.write(f"🔍 Analisando: {v_desc}")
        
        # Chama o motor híbrido
        res_nome, res_preco = buscar_preco_vtex(v_ean, v_busca)
        
        # ... (Logica de busca de preço anterior no banco e cálculo de variação) ...
        
        resultados.append({
            "EAN": v_ean,
            "Produto_TL": v_desc,
            "Concorrente": res_nome,
            "Preco_Atual": res_preco if res_preco else 0,
            "Data_Coleta": datetime.now()
        })
        
        barra.progress((i + 1) / len(df_raw))
        time.sleep(random.uniform(1.2, 2.5))
