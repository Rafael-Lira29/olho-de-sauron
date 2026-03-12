import os
# Força instalação do Chromium no arranque (necessário para Streamlit Cloud)
os.system("playwright install chromium")

import streamlit as st
import pandas as pd
import re
import io
import time
import random
import json
import logging
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from sqlalchemy import create_engine, text
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment

from playwright.sync_api import sync_playwright, Page

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

# ==========================================
# CONFIGURAÇÃO GERAL
# ==========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sauron")

CONCORRENTES = {
    "Savegnago": "https://www.savegnago.com.br"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# ==========================================
# MOTOR 1: O TRATOR (Limpeza e Extração)
# ==========================================
MARCAS_BEBIDAS = sorted([
    "51", "SMIRNOFF", "SKOL", "BRAHMA", "HEINEKEN", "AMSTEL", "CORONA",
    "SPATEN", "PERGOLA", "ABSOLUT", "JACK DANIELS", "RED LABEL", "BLACK LABEL",
    "CHIVAS", "BEEFEATER", "GORDON", "TANQUERAY", "KAISER", "ITAIPAVA",
    "PETRA", "COLORADO", "BUDWEISER", "STELLA ARTOIS", "BECKS", "PASSPORT",
    "CAMPARI", "APEROL", "JURUPINGA", "COROTE", "ASKOV", "NATU NOBILIS",
    "VELHO BARREIRO", "YPIOCA", "PITU", "SALTON", "AURORA", "GALLO", "CHANDON"
], key=len, reverse=True)

def extrair_volume(descricao):
    match = re.search(r'(\d+(?:[.,]\d+)?\s*(?:ML|L|KG|G|CC|M|LT))', str(descricao).upper())
    return match.group(1).replace(' ', '') if match else ''

def extrair_marca(descricao, marcas_conhecidas):
    desc_upper = str(descricao).upper()
    for marca in marcas_conhecidas:
        if re.search(rf'\b{marca}\b', desc_upper): return marca
    return 'SEM_MARCA'

def processar_planilha_bruta(arquivo_bruto, nome_setor):
    df_bruto = pd.read_excel(arquivo_bruto, header=1)
    col_desc = 'DESCRIÇÃO' if 'DESCRIÇÃO' in df_bruto.columns else 'DESCRICAO'
    col_cod = 'CÓDIGO' if 'CÓDIGO' in df_bruto.columns else 'CODIGO'

    if col_desc not in df_bruto.columns: raise ValueError("Coluna de descrição não encontrada.")

    # Extermínio de Nulos
    df_bruto = df_bruto.dropna(subset=[col_desc])
    df_bruto = df_bruto[df_bruto[col_desc].astype(str).str.strip() != '']
    df_bruto = df_bruto[~df_bruto[col_desc].astype(str).str.contains('Produto Sem Nome', case=False, na=False)]

    df_padrao = pd.DataFrame()
    df_padrao['EAN_CODIGO_BARRAS'] = df_bruto['EAN'] if 'EAN' in df_bruto.columns else ''
    df_padrao['CODIGO_INTERNO'] = df_bruto[col_cod] if col_cod in df_bruto.columns else ''
    df_padrao['DESCRICAO_SISTEMA'] = df_bruto[col_desc].astype(str).str.strip()
    df_padrao = df_padrao[df_padrao['CODIGO_INTERNO'].astype(str).str.strip() != '']

    # Extração de Travas
    df_padrao['MARCA_EXTRAIDA'] = df_padrao['DESCRICAO_SISTEMA'].apply(lambda x: extrair_marca(x, MARCAS_BEBIDAS))
    df_padrao['VOLUME_EXTRAIDO'] = df_padrao['DESCRICAO_SISTEMA'].apply(extrair_volume)
    df_padrao['TERMO_DE_BUSCA'] = df_padrao['DESCRICAO_SISTEMA'].str.title()
    df_padrao['SETOR_CURVA'] = nome_setor
    return df_padrao

def gerar_excel_base_ouro(df_padrao, nome_setor):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_padrao.to_excel(writer, index=False, sheet_name='Base_Sauron')
        workbook = writer.book
        worksheet = writer.sheets['Base_Sauron']
        fmt_cabecalho = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#1E3A8A', 'border': 1, 'align': 'center'})
        for col_num, value in enumerate(df_padrao.columns.values): worksheet.write(0, col_num, value, fmt_cabecalho)
        worksheet.set_column('A:B', 15); worksheet.set_column('C:D', 40)
        worksheet.set_column('E:F', 18); worksheet.set_column('G:G', 20)
        worksheet.autofilter(0, 0, len(df_padrao), len(df_padrao.columns) - 1)
    output.seek(0)
    return output

# ==========================================
# MOTOR 2: O SAURON (Playwright + VTEX)
# ==========================================
def validar_match_rigoroso(marca_tl, volume_tl, desc_concorrente):
    """Trava matemática. Se a marca ou volume divergirem, bloqueia o falso positivo."""
    desc_conc_upper = str(desc_concorrente).upper()
    if marca_tl != 'SEM_MARCA' and marca_tl not in desc_conc_upper: return False
    if volume_tl:
        vol_conc = extrair_volume(desc_concorrente)
        if volume_tl != vol_conc: return False
    return True

class ConcorrenteScraper:
    def __init__(self, base_url: str, user_agent: str, page: Page):
        self.base_url = base_url
        self.page = page

    def buscar_por_ean(self, ean: str) -> Optional[Dict]:
        url = f"{self.base_url}/api/catalog_system/pub/products/search?fq=alternateIds_Ean:{ean}"
        return self._fetch_json(url)

    def buscar_por_termo(self, termo: str) -> Optional[Dict]:
        termo_limpo = " ".join(termo.strip().split()[:3])
        url = f"{self.base_url}/api/catalog_system/pub/products/search?ft={termo_limpo}&_from=0&_to=2"
        return self._fetch_json(url)

    def _fetch_json(self, url: str) -> Optional[Dict]:
        try:
            time.sleep(random.uniform(0.5, 1.5))
            resp = self.page.goto(url, wait_until="networkidle", timeout=30000)
            if resp and resp.status in [403, 429, 503]: return None
            time.sleep(random.uniform(0.8, 1.5))
            
            # Movimento humano simulado
            viewport = self.page.viewport_size
            if viewport: self.page.mouse.move(random.randint(0, viewport['width']), random.randint(0, viewport['height']), steps=10)
            
            content = self.page.inner_text("body")
            return json.loads(content) if content else None
        except Exception: return None

    @staticmethod
    def extrair_preco(item: Dict) -> Tuple[Optional[str], Optional[float]]:
        try:
            nome = item.get("productName", "").strip()
            sellers = item.get("items", [])[0].get("sellers", [])
            offer = sellers[0].get("commertialOffer", {}) if sellers else {}
            preco = offer.get("Price") or offer.get("ListPrice") or offer.get("spotPrice")
            if nome and preco and preco > 0: return nome, float(preco)
        except Exception: pass
        return None, None

def buscar_precos(df_produtos: pd.DataFrame, base_url: str, limiar: int, progress_callback: callable) -> List[Dict]:
    resultados = []
    total = len(df_produtos)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])
        context = browser.new_context(user_agent=random.choice(USER_AGENTS), locale='pt-BR')
        page = context.new_page()
        page.set_default_timeout(45000)
        scraper = ConcorrenteScraper(base_url, "", page)

        for idx, row in df_produtos.iterrows():
            ean_raw = str(row.get('EAN_CODIGO_BARRAS', '')).strip()
            ean = ean_raw.split('.')[0] if ean_raw else ""
            if len(ean) == 14 and ean.startswith('0'): ean = ean[1:]

            nome_tl = str(row.get('DESCRICAO_SISTEMA', '')).strip()
            termo = str(row.get('TERMO_DE_BUSCA', '')).strip()
            marca_tl = row.get('MARCA_EXTRAIDA', 'SEM_MARCA')
            volume_tl = row.get('VOLUME_EXTRAIDO', '')

            produto_info, origem = None, None

            # 1. Busca por EAN
            if ean:
                dados = scraper.buscar_por_ean(ean)
                if dados and isinstance(dados, list):
                    for item in dados:
                        nome_cand, preco_cand = scraper.extrair_preco(item)
                        if nome_cand:
                            # A BARREIRA DE BLINDAGEM DO TRATOR (Marca e Volume)
                            if validar_match_rigoroso(marca_tl, volume_tl, nome_cand):
                                produto_info = (nome_cand, preco_cand)
                                origem = "EAN (Blindado)"
                                break

            # 2. Busca por Termo (Se EAN falhar)
            if not produto_info and termo:
                dados = scraper.buscar_por_termo(termo)
                if dados and isinstance(dados, list):
                    for item in dados:
                        nome_cand, preco_cand = scraper.extrair_preco(item)
                        if nome_cand:
                            # Barreira Trator + Fuzzy
                            if validar_match_rigoroso(marca_tl, volume_tl, nome_cand):
                                if fuzz is None or fuzz.token_sort_ratio(nome_tl, nome_cand) >= limiar:
                                    produto_info = (nome_cand, preco_cand)
                                    origem = "Termo (Blindado)"
                                    break

            nome_enc, preco_enc = produto_info if produto_info else ("❌ Não Localizado / Divergente", None)
            resultados.append({"EAN": ean, "Produto_TL": nome_tl, "Produto_Concorrente": nome_enc, "Preco": preco_enc, "Origem": origem if origem else "Falha"})
            progress_callback(idx, total, nome_tl, preco_enc)

        browser.close()
    return resultados

# ==========================================
# INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="Sauron Enterprise", page_icon="👁️", layout="wide")
st.markdown("""<style>div.stButton > button:first-child { background-color: #1E3A8A; color: white; height: 3em; font-weight: bold; width: 100%; border-radius: 8px; }</style>""", unsafe_allow_html=True)
st.title("👁️ Sauron Enterprise — Olho que Tudo Vê")

aba_trator, aba_sauron = st.tabs(["🚜 1. Trator (Limpar Base)", "👁️ 2. Sauron (Pesquisa Furtiva API)"])

with aba_trator:
    st.header("🚜 Refinaria de Dados (Trator)")
    arquivo_bruto = st.file_uploader("Carregar Planilha Bruta (.xlsx) Exportada do Sistema", type=['xlsx'], key="up_trator")
    setor_alvo = st.selectbox("Setor Mapeado", ["Bebidas", "Açougue", "Mercearia"])
    
    if st.button("Refinar e Blindar Base"):
        if arquivo_bruto:
            with st.spinner("A exterminar nulos e extrair Marcas/Volumes..."):
                df_limpo = processar_planilha_bruta(arquivo_bruto, setor_alvo)
                st.success(f"✅ Base Ouro gerada! Sobreviveram {len(df_limpo)} produtos.")
                st.download_button("📥 Baixar Base Ouro (Para o Sauron)", gerar_excel_base_ouro(df_limpo, setor_alvo), f"Sauron_Padrao_{setor_alvo}.xlsx")

with aba_sauron:
    st.header("👁️ Varredura VTEX (Concorrente)")
    with st.sidebar:
        st.header("⚙️ Configurações do Sauron")
        concorrente = st.selectbox("Alvo", list(CONCORRENTES.keys()))
        limiar = st.slider("Aperto do Fuzzy (%)", 60, 100, 75, 5, help="Atua em conjunto com a trava de Marca/Litragem.")
        
    arquivo_ouro = st.file_uploader("📂 Carregar Base Ouro (Sauron_Padrao.xlsx)", type=["xlsx"])
    
    if st.button("🚀 Iniciar Infiltração API"):
        if arquivo_ouro:
            df_ouro = pd.read_excel(arquivo_ouro)
            if 'MARCA_EXTRAIDA' not in df_ouro.columns:
                st.error("❌ Arquivo inválido! Você precisa passar a planilha pelo TRATOR (Aba 1) primeiro.")
            else:
                status = st.empty()
                progress_bar = st.progress(0)
                
                def update_ui(idx, total, nome, preco):
                    progress_bar.progress((idx + 1) / total)
                    status.info(f"🕵️‍♂️ {idx+1}/{total} | {nome[:40]}... Preço: {preco if preco else '❌ Rejeitado/Falta'}")

                try: engine = create_engine(st.secrets["database"]["url"])
                except: engine = None

                resultados = buscar_precos(df_ouro, CONCORRENTES[concorrente], limiar, update_ui)
                
                if resultados:
                    df_res = pd.DataFrame(resultados)
                    df_res["Concorrente"] = concorrente
                    df_res["Data_Coleta"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    st.success("✨ Varredura furtiva concluída com barreiras de blindagem ativas!")
                    st.dataframe(df_res, use_container_width=True)
                    
                    out_excel = io.BytesIO()
                    df_res.to_excel(out_excel, index=False)
                    st.download_button("⬇️ Baixar Relatório Final (Excel)", out_excel.getvalue(), f"Precos_Sauron_{datetime.now().strftime('%d_%m')}.xlsx")
                    
                    if engine:
                        try:
                            # Lógica para salvar no banco de dados mantida
                            df_res[df_res["Preco"].notna()].to_sql("precos", engine, if_exists="append", index=False)
                            st.toast("🔐 Dados salvos no banco PostgreSQL com sucesso.")
                        except Exception as e: st.warning(f"Aviso BD: {e}")
