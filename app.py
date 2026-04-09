import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

# --- CONFIGURAÇÃO DO CAMINHO DO BANCO ---
# Garante que o banco fique sempre na mesma pasta do arquivo .py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_BANCO = os.path.join(BASE_DIR, 'dados_loja.db')

def conectar():
    """Conecta ao banco de dados no mesmo diretório do script"""
    return sqlite3.connect(CAMINHO_BANCO, check_same_thread=False)

# --- RESTO DO CÓDIGO (criar_tabelas, etc.) permanece igual ---

def criar_tabelas():
    conn = conectar()
    c = conn.cursor()
    
    # TABELA PRODUTOS
    c.execute('CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, preco REAL)')
    
    # TABELA TAXAS - Apenas Dinheiro como padrão
    c.execute('''CREATE TABLE IF NOT EXISTS taxas (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 metodo TEXT UNIQUE, 
                 valor_taxa REAL,
                 assume_vendedor INTEGER DEFAULT 1,
                 descricao TEXT)''')
    
    # TABELA VENDAS
    c.execute('''CREATE TABLE IF NOT EXISTS vendas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, produto TEXT, valor_bruto REAL, 
                  desconto REAL, metodo_pgto TEXT, taxa_momento REAL, data TEXT, mes_ano TEXT, obs TEXT)''')
    
    # TABELA DESPESAS
    c.execute('''CREATE TABLE IF NOT EXISTS despesas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT, valor REAL, 
                  categoria TEXT, data TEXT, mes_ano TEXT)''')
    
    # TABELA CATEGORIAS DE DESPESA
    c.execute('CREATE TABLE IF NOT EXISTS categorias_desp (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)')
    
    # TABELA ANOTAÇÕES (Lembretes)
    c.execute('''CREATE TABLE IF NOT EXISTS anotacoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, conteudo TEXT, 
                  data TEXT, prioridade TEXT DEFAULT "Média", concluido INTEGER DEFAULT 0)''')
    
    # TABELA CARRINHO TEMPORÁRIO
    c.execute('''CREATE TABLE IF NOT EXISTS carrinho_temp 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, produto TEXT, 
                  valor_bruto REAL, desconto REAL DEFAULT 0, valor REAL, obs TEXT)''')

    # ==================== DADOS INICIAIS ====================
    
    # Taxas - Apenas Dinheiro
    if c.execute("SELECT COUNT(*) FROM taxas").fetchone()[0] == 0:
        c.execute("""INSERT INTO taxas (metodo, valor_taxa, assume_vendedor, descricao) 
                     VALUES (?,?,?,?)""", 
                  ('Dinheiro', 0.0, 1, 'Pagamento em espécie - sem taxa'))
    
    # Categorias de Despesa padrão
    if c.execute("SELECT COUNT(*) FROM categorias_desp").fetchone()[0] == 0:
        c.executemany("INSERT INTO categorias_desp (nome) VALUES (?)", 
                     [('Insumos',), ('Fixo',), ('Marketing',), ('Outros',), ('Aluguel',), ('Energia',)])

    conn.commit()
    conn.close()

def migrar_banco():
    """Migração robusta - adiciona colunas faltantes"""
    conn = conectar()
    c = conn.cursor()
    
    try:
        # Adiciona colunas na tabela anotacoes
        c.execute("ALTER TABLE anotacoes ADD COLUMN prioridade TEXT DEFAULT 'Média'")
        print("✅ Coluna 'prioridade' adicionada.")
    except sqlite3.OperationalError:
        pass  # coluna já existe
    
    try:
        c.execute("ALTER TABLE anotacoes ADD COLUMN concluido INTEGER DEFAULT 0")
        print("✅ Coluna 'concluido' adicionada.")
    except sqlite3.OperationalError:
        pass  # coluna já existe

    conn.commit()
    conn.close()

# Executa criação e migração
criar_tabelas()
migrar_banco()

# --- MENU LATERAL ---
st.sidebar.title("📸 Foto Amancio")
menu = st.sidebar.radio("Navegação:", 
    ["🛒 PDV", "📊 Dashboard", "📜 Histórico", "💰 Despesas", "📦 Cadastros", 
     "📝 Notas", "💳 Taxas", "🔄 Backup OneDrive"])

# ===================================================================
# 1. PDV (FRENTE DE CAIXA) - COM CORREÇÃO DE DESCONTO
# ===================================================================
if menu == "🛒 PDV":
    st.header("🛒 Frente de Caixa")
    
    conn = conectar()
    prods = pd.read_sql("SELECT * FROM produtos", conn)
    txs = pd.read_sql("SELECT * FROM taxas", conn)
    carr = pd.read_sql("SELECT * FROM carrinho_temp", conn)
    conn.close()
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.subheader("Adicionar Item")
        
        p_sel = st.selectbox("Produto", ["Personalizado"] + prods['nome'].tolist())
        
        if p_sel == "Personalizado":
            p_unit_sugerido = 0.0
        else:
            p_unit_sugerido = float(prods[prods['nome'] == p_sel]['preco'].values[0])
        
        c_v1, c_v2 = st.columns([2, 1])
        v_unit = c_v1.number_input("Preço Unitário R$", min_value=0.0, value=p_unit_sugerido, step=0.01)
        qtd = c_v2.number_input("Qtd", min_value=1, value=1, step=1)
        
        # --- LÓGICA DE DESCONTO CORRIGIDA ---
        com_desconto = st.checkbox("Aplicar desconto neste item?")
        valor_bruto_item = v_unit * qtd
        desconto_aplicado = 0.0
        v_final_item = valor_bruto_item

        if com_desconto:
            v_com_desconto = st.number_input("Preço Final com Desconto R$", 
                                           min_value=0.0, max_value=valor_bruto_item, 
                                           value=valor_bruto_item, step=0.01)
            desconto_aplicado = valor_bruto_item - v_com_desconto
            v_final_item = v_com_desconto
            st.warning(f"Desconto de R$ {desconto_aplicado:.2f} aplicado.")
        
        v_obs = st.text_input("Observação do Item")
        
        if v_unit > 0:
            st.info(f"Subtotal: {qtd}x {p_sel} = R$ {v_final_item:.2f}")

        if st.button("➕ Adicionar ao Carrinho", use_container_width=True, type="primary"):
            if v_final_item >= 0:          # ← Mudado de > 0 para >= 0
                conn = conectar()
                obs_detalhada = f"Qtd: {qtd} | {v_obs}"
                conn.execute("""INSERT INTO carrinho_temp
                                (produto, valor_bruto, desconto, valor, obs)
                                VALUES (?,?,?,?,?)""", 
                             (p_sel, valor_bruto_item, desconto_aplicado, v_final_item, obs_detalhada))
                conn.commit()
                conn.close()
                st.success("Item adicionado!")
                st.rerun()
            else:
                st.error("O valor do item não pode ser negativo.")
    
    with col2:
        st.subheader("🛒 Itens no Carrinho")
        if not carr.empty:
            # Mostra colunas claras (bruto, desconto e valor final)
            df_display = carr[['produto', 'valor_bruto', 'desconto', 'valor', 'obs']].copy()
            df_display = df_display.rename(columns={
                'valor_bruto': 'Bruto (R$)',
                'desconto': 'Desconto (R$)',
                'valor': 'Final (R$)'
            })
            st.dataframe(df_display, hide_index=True, use_container_width=True)
            
            total_carrinho = carr['valor'].sum()
            st.divider()
            st.metric("Total do Pedido (valor pago pelo cliente)", f"R$ {total_carrinho:.2f}")
            
            met_p = st.selectbox("Forma de Pagamento", txs['metodo'].tolist())
            tx_v = txs[txs['metodo'] == met_p]['valor_taxa'].values[0]
            
            c_f1, c_f2 = st.columns(2)
            if c_f1.button("✅ FINALIZAR VENDA", type="primary", use_container_width=True):
                agora = datetime.now()
                conn = conectar()
                for _, i in carr.iterrows():
                    conn.execute("""INSERT INTO vendas 
                        (produto, valor_bruto, desconto, metodo_pgto, taxa_momento, data, mes_ano, obs) 
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (i['produto'], i['valor_bruto'], i['desconto'], met_p, tx_v, 
                         agora.strftime("%d/%m/%Y %H:%M"), agora.strftime("%m/%Y"), i['obs']))
                conn.execute("DELETE FROM carrinho_temp")
                conn.commit()
                conn.close()
                st.success("✅ Venda finalizada com sucesso!")
                st.rerun()
                
            if c_f2.button("🗑️ Esvaziar Carrinho", use_container_width=True):
                conn = conectar()
                conn.execute("DELETE FROM carrinho_temp")
                conn.commit()
                conn.close()
                st.rerun()
        else:
            st.info("O carrinho está vazio.")

# ===================================================================
# 2. DASHBOARD - VERSÃO RESPONSIVA (Melhor para Celular)
# ===================================================================
elif menu == "📊 Dashboard":
    st.header("📊 Resumo Financeiro Real")

    # ======================= FILTRO DE DATA =======================
    st.subheader("📅 Período do Relatório")
    
    col_data1, col_data2, col_data3 = st.columns([2, 2, 1])
    data_inicio = col_data1.date_input("Data Inicial", value=datetime.now().replace(day=1))
    data_fim = col_data2.date_input("Data Final", value=datetime.now())
    
    if col_data3.button("🔄 Todo Período", use_container_width=True):
        data_inicio = datetime(2020, 1, 1).date()
        data_fim = datetime.now().date()

    conn = conectar()
    df_v = pd.read_sql("SELECT * FROM vendas", conn)
    df_d = pd.read_sql("SELECT * FROM despesas", conn)
    conn.close()

    # Filtragem (mantida igual)
    def filtrar_por_data(df, coluna_data):
        if df.empty:
            return df
        try:
            df['data_obj'] = pd.to_datetime(df[coluna_data], format="%d/%m/%Y %H:%M", errors='coerce')
        except:
            df['data_obj'] = pd.to_datetime(df[coluna_data], errors='coerce')
        df = df.dropna(subset=['data_obj'])
        df = df[(df['data_obj'].dt.date >= data_inicio) & 
                (df['data_obj'].dt.date <= data_fim)]
        return df

    df_v = filtrar_por_data(df_v, 'data')
    df_d = filtrar_por_data(df_d, 'data')

    # ======================= CÁLCULOS =======================
    faturamento_bruto = df_v['valor_bruto'].sum() if not df_v.empty else 0.0
    total_descontos   = df_v['desconto'].sum() if not df_v.empty else 0.0
    total_taxas_cartao = ((df_v['valor_bruto'] - df_v['desconto']) * 
                          (df_v['taxa_momento'] / 100)).sum() if not df_v.empty else 0.0
    total_despesas = df_d['valor'].sum() if not df_d.empty else 0.0
    lucro_final = (faturamento_bruto - total_descontos - total_taxas_cartao - total_despesas)

    # ======================= MÉTRICAS VERTICAIS (Melhor para Celular) =======================
    st.subheader("Resumo Financeiro")

    # Usamos colunas simples, mas com layout mais vertical em telas pequenas
    m1, m2 = st.columns(2)
    m3, m4 = st.columns(2)
    m5 = st.container()

    with m1:
        st.metric("Faturamento Bruto", f"R$ {faturamento_bruto:,.2f}")
    with m2:
        st.metric("Descontos", f"- R$ {total_descontos:,.2f}", delta_color="inverse")

    with m3:
        st.metric("Taxas Cartão", f"- R$ {total_taxas_cartao:,.2f}", delta_color="inverse")
    with m4:
        st.metric("Despesas", f"- R$ {total_despesas:,.2f}", delta_color="inverse")

    with m5:
        st.metric("**LUCRO REAL**", f"R$ {lucro_final:,.2f}", delta_color="normal")

    st.divider()

    # Informações do período
    st.caption(f"📅 Período: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")
    st.info(f"**Vendas:** {len(df_v)}   |   **Despesas:** {len(df_d)}")

    st.divider()

    # ======================= PDF =======================
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "Relatório Financeiro - Foto Amancio", ln=True, align='C')
        pdf.cell(200, 10, f"Período: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}", 
                ln=True, align='C')
        pdf.ln(15)
        
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, f"Faturamento Bruto: R$ {faturamento_bruto:,.2f}", ln=True)
        pdf.cell(200, 10, f"Descontos: R$ {total_descontos:,.2f}", ln=True)
        pdf.cell(200, 10, f"Taxas de Cartão: R$ {total_taxas_cartao:,.2f}", ln=True)
        pdf.cell(200, 10, f"Despesas: R$ {total_despesas:,.2f}", ln=True)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 15, f"LUCRO LÍQUIDO REAL: R$ {lucro_final:,.2f}", ln=True, align='C')
        
        pdf_output = pdf.output(dest='S').encode('latin-1')

        st.download_button(
            label="📄 Baixar Relatório PDF",
            data=pdf_output,
            file_name=f"Relatorio_{data_inicio.strftime('%d%m%Y')}_a_{data_fim.strftime('%d%m%Y')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except:
        st.error("Instale fpdf: pip install fpdf")

# ===================================================================
# 3. HISTÓRICO - COM EDIÇÃO DE QUANTIDADE (Corrigido)
# ===================================================================
elif menu == "📜 Histórico":
    st.header("📜 Histórico Recente (Últimos 15)")
    
    if 'edit_id' not in st.session_state:
        st.session_state.edit_id = None
        st.session_state.edit_tipo = None

    sub = st.selectbox("Tipo:", ["Vendas", "Despesas"])
    conn = conectar()
    
    if sub == "Vendas":
        df = pd.read_sql("SELECT * FROM vendas ORDER BY id DESC LIMIT 15", conn)
        
        for _, r in df.iterrows():
            with st.container(border=True):
                col_a, col_b, col_c, col_d = st.columns([3, 1.3, 0.8, 0.8])
                
                col_a.write(f"**{r['produto']}** | {r['data']}")
                col_a.caption(f"{r['metodo_pgto']} | {r['obs']}")
                col_b.write(f"R$ {r['valor_bruto']:.2f}")
                if r['desconto'] > 0:
                    col_b.caption(f"Desc: -R$ {r['desconto']:.2f}")
                
                if col_c.button("✏️ Editar", key=f"edit_v_{r['id']}"):
                    st.session_state.edit_id = r['id']
                    st.session_state.edit_tipo = "vendas"
                    st.rerun()
                
                if col_d.button("🗑️", key=f"del_v_{r['id']}"):
                    conn.execute("DELETE FROM vendas WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
    
    else:  # Despesas
        df = pd.read_sql("SELECT * FROM despesas ORDER BY id DESC LIMIT 15", conn)
        for _, r in df.iterrows():
            with st.container(border=True):
                col_a, col_b, col_c, col_d = st.columns([3, 1.2, 0.8, 0.8])
                col_a.write(f"**{r['descricao']}** | {r['data']}")
                col_a.caption(f"Cat: {r['categoria']}")
                col_b.write(f"R$ {r['valor']:.2f}")
                
                if col_c.button("✏️ Editar", key=f"edit_d_{r['id']}"):
                    st.session_state.edit_id = r['id']
                    st.session_state.edit_tipo = "despesas"
                    st.rerun()
                
                if col_d.button("🗑️", key=f"del_d_{r['id']}"):
                    conn.execute("DELETE FROM despesas WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
    
    conn.close()

    # ======================= FORMULÁRIO DE EDIÇÃO =======================
    if st.session_state.edit_id is not None:
        st.divider()
        st.subheader("✏️ Editando Registro")

        conn = conectar()

        if st.session_state.edit_tipo == "vendas":
            # Busca segura com verificação
            df_edit_query = pd.read_sql(f"SELECT * FROM vendas WHERE id = {st.session_state.edit_id}", conn)
            
            if df_edit_query.empty:
                st.error("❌ Registro não encontrado. Pode ter sido excluído.")
                if st.button("Fechar"):
                    st.session_state.edit_id = None
                    st.session_state.edit_tipo = None
                    st.rerun()
                conn.close()
            else:
                df_edit = df_edit_query.iloc[0]
                
                with st.form("edit_venda"):
                    novo_produto = st.text_input("Produto", value=df_edit['produto'])
                    
                    # Extrai quantidade atual da observação
                    qtd_atual = 1
                    if "Qtd:" in str(df_edit['obs']):
                        try:
                            qtd_atual = int(df_edit['obs'].split("Qtd:")[1].split("|")[0].strip())
                        except:
                            qtd_atual = 1
                    
                    nova_qtd = st.number_input("Quantidade", min_value=1, value=qtd_atual, step=1)
                    
                    novo_valor_bruto = st.number_input("Valor Bruto Total R$", 
                                                     value=float(df_edit['valor_bruto']), step=0.01)
                    novo_desconto = st.number_input("Desconto R$", 
                                                  value=float(df_edit['desconto']), step=0.01)
                    
                    metodos = pd.read_sql("SELECT metodo FROM taxas", conn)['metodo'].tolist()
                    idx = metodos.index(df_edit['metodo_pgto']) if df_edit['metodo_pgto'] in metodos else 0
                    novo_metodo = st.selectbox("Forma de Pagamento", metodos, index=idx)
                    
                    novo_obs = st.text_area("Observação", value=df_edit['obs'])
                    
                    col_save, col_cancel = st.columns(2)
                    if col_save.form_submit_button("💾 Salvar Alterações", type="primary"):
                        taxa_nova = pd.read_sql("SELECT valor_taxa FROM taxas WHERE metodo = ?", 
                                              conn, params=(novo_metodo,)).iloc[0]['valor_taxa']
                        
                        obs_final = novo_obs
                        if "Qtd:" in novo_obs:
                            obs_final = novo_obs.replace(f"Qtd: {qtd_atual}", f"Qtd: {nova_qtd}")
                        else:
                            obs_final = f"Qtd: {nova_qtd} | {novo_obs}"
                        
                        conn.execute("""UPDATE vendas SET 
                                        produto=?, valor_bruto=?, desconto=?, 
                                        metodo_pgto=?, taxa_momento=?, obs=? 
                                        WHERE id=?""",
                                     (novo_produto, novo_valor_bruto, novo_desconto,
                                      novo_metodo, taxa_nova, obs_final, st.session_state.edit_id))
                        conn.commit()
                        st.success("✅ Venda atualizada com sucesso!")
                        st.session_state.edit_id = None
                        st.session_state.edit_tipo = None
                        st.rerun()
                    
                    if col_cancel.form_submit_button("❌ Cancelar"):
                        st.session_state.edit_id = None
                        st.session_state.edit_tipo = None
                        st.rerun()

        else:  # === EDIÇÃO DE DESPESA ===
            df_edit_query = pd.read_sql(f"SELECT * FROM despesas WHERE id = {st.session_state.edit_id}", conn)
            
            if df_edit_query.empty:
                st.error("❌ Registro não encontrado.")
                if st.button("Fechar"):
                    st.session_state.edit_id = None
                    st.session_state.edit_tipo = None
                    st.rerun()
            else:
                df_edit = df_edit_query.iloc[0]
                
                with st.form("edit_despesa"):
                    novo_desc = st.text_input("Descrição", value=df_edit['descricao'])
                    novo_valor = st.number_input("Valor R$", value=float(df_edit['valor']), step=0.01)
                    
                    categorias = pd.read_sql("SELECT nome FROM categorias_desp", conn)['nome'].tolist()
                    idx_cat = categorias.index(df_edit['categoria']) if df_edit['categoria'] in categorias else 0
                    novo_cat = st.selectbox("Categoria", categorias, index=idx_cat)
                    
                    novo_data = st.text_input("Data", value=df_edit['data'])
                    
                    col_save, col_cancel = st.columns(2)
                    if col_save.form_submit_button("💾 Salvar Alterações", type="primary"):
                        conn.execute("""UPDATE despesas SET 
                                        descricao=?, valor=?, categoria=?, data=? 
                                        WHERE id=?""",
                                     (novo_desc, novo_valor, novo_cat, novo_data, st.session_state.edit_id))
                        conn.commit()
                        st.success("✅ Despesa atualizada com sucesso!")
                        st.session_state.edit_id = None
                        st.session_state.edit_tipo = None
                        st.rerun()
                    
                    if col_cancel.form_submit_button("❌ Cancelar"):
                        st.session_state.edit_id = None
                        st.session_state.edit_tipo = None
                        st.rerun()

        conn.close()

# ===================================================================
# 4. CADASTROS - COM EDIÇÃO DE CATEGORIAS FUNCIONANDO
# ===================================================================
elif menu == "📦 Cadastros":
    st.header("📦 Gestão de Itens")
    tab1, tab2 = st.tabs(["🛍️ Produtos", "📂 Categorias de Despesa"])

    if 'edit_item' not in st.session_state:
        st.session_state.edit_item = None
        st.session_state.edit_tipo = None

        # ======================= 1. PRODUTOS =======================
    with tab1:
        st.subheader("🛍️ Cadastro de Produtos")
        
        with st.form("novo_produto", clear_on_submit=True):
            col_nome, col_preco = st.columns([3, 1])
            nome_prod = col_nome.text_input("Nome do Produto", placeholder="Ex: Pacote 20 fotos 15x21")
            preco_prod = col_preco.number_input("Preço de Venda R$", 
                                              min_value=0.0, 
                                              value=0.0, 
                                              step=0.01)
            
            if st.form_submit_button("➕ Cadastrar Produto", use_container_width=True, type="primary"):
                if not nome_prod.strip():
                    st.error("❌ Nome do produto é obrigatório.")
                else:
                    conn = conectar()
                    conn.execute("INSERT INTO produtos (nome, preco) VALUES (?,?)", 
                                (nome_prod.strip(), preco_prod))
                    conn.commit()
                    conn.close()
                    st.success("✅ Produto cadastrado com sucesso!")
                    st.rerun()

        st.divider()
        st.subheader("📋 Produtos Cadastrados")
        
        conn = conectar()
        df_prod = pd.read_sql("SELECT id, nome, preco FROM produtos ORDER BY nome", conn)
        conn.close()

        if df_prod.empty:
            st.info("Nenhum produto cadastrado ainda.")
        else:
            for _, row in df_prod.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
                    col1.write(f"**{row['nome']}**")
                    col2.metric("Preço", f"R$ {row['preco']:.2f}")
                    if col3.button("✏️", key=f"ep_{row['id']}"):
                        st.session_state.edit_item = row['id']
                        st.session_state.edit_tipo = "produto"
                        st.rerun()
                    if col4.button("🗑️", key=f"dp_{row['id']}"):
                        conn = conectar()
                        conn.execute("DELETE FROM produtos WHERE id=?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Produto excluído!")
                        st.rerun()

    # ======================= 2. CATEGORIAS =======================
    with tab2:
        st.subheader("📂 Categorias de Despesa")
        
        with st.form("nova_categoria", clear_on_submit=True):
            nova_cat = st.text_input("Nome da Categoria", placeholder="Ex: Aluguel, Energia, Insumos...")
            if st.form_submit_button("➕ Adicionar Categoria", use_container_width=True, type="primary"):
                if nova_cat.strip():
                    conn = conectar()
                    conn.execute("INSERT INTO categorias_desp (nome) VALUES (?)", (nova_cat.strip(),))
                    conn.commit()
                    conn.close()
                    st.success("✅ Categoria adicionada!")
                    st.rerun()
                else:
                    st.error("Nome da categoria é obrigatório.")

        st.divider()
        st.subheader("📋 Categorias Cadastradas")
        
        conn = conectar()
        df_cat = pd.read_sql("SELECT id, nome FROM categorias_desp ORDER BY nome", conn)
        conn.close()

        if df_cat.empty:
            st.info("Nenhuma categoria cadastrada.")
        else:
            for _, row in df_cat.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([5, 1, 1])
                    col1.write(f"**{row['nome']}**")
                    if col2.button("✏️ Editar", key=f"ec_{row['id']}"):
                        st.session_state.edit_item = row['id']
                        st.session_state.edit_tipo = "categoria"
                        st.rerun()
                    if col3.button("🗑️", key=f"dc_{row['id']}"):
                        conn = conectar()
                        uso = conn.execute("SELECT COUNT(*) FROM despesas WHERE categoria=?", (row['nome'],)).fetchone()[0]
                        if uso > 0:
                            st.error(f"Não é possível excluir. Usada em {uso} despesa(s).")
                        else:
                            conn.execute("DELETE FROM categorias_desp WHERE id=?", (row['id'],))
                            conn.commit()
                            st.success("Categoria excluída!")
                        conn.close()
                        st.rerun()

    # ======================= FORMULÁRIO DE EDIÇÃO =======================
    if st.session_state.edit_item is not None:
        st.divider()
        st.subheader("✏️ Editando Item")

        conn = conectar()

        if st.session_state.edit_tipo == "categoria":
            item = pd.read_sql(f"SELECT * FROM categorias_desp WHERE id = {st.session_state.edit_item}", conn).iloc[0]
            
            with st.form("edit_categoria_form"):
                novo_nome = st.text_input("Nome da Categoria", value=item['nome'])
                
                col_salvar, col_cancelar = st.columns(2)
                if col_salvar.form_submit_button("💾 Salvar Alteração", type="primary"):
                    if novo_nome.strip():
                        conn.execute("UPDATE categorias_desp SET nome=? WHERE id=?", 
                                    (novo_nome.strip(), st.session_state.edit_item))
                        conn.commit()
                        st.success("✅ Categoria atualizada com sucesso!")
                        st.session_state.edit_item = None
                        st.session_state.edit_tipo = None
                        st.rerun()
                    else:
                        st.error("Nome não pode estar vazio.")
                
                if col_cancelar.form_submit_button("❌ Cancelar"):
                    st.session_state.edit_item = None
                    st.session_state.edit_tipo = None
                    st.rerun()

        conn.close()
    


# ===================================================================
# NOVA ABA: DESPESAS (Adicionar + Histórico)
# ===================================================================
elif menu == "💰 Despesas":
    st.header("💰 Lançamento de Despesas")

    conn = conectar()
    categorias = pd.read_sql("SELECT nome FROM categorias_desp", conn)['nome'].tolist()
    conn.close()

    # ======================= FORMULÁRIO DE NOVA DESPESA =======================
    with st.form("nova_despesa"):
        st.subheader("Nova Despesa")
        
        col1, col2 = st.columns([2, 1])
        descricao = col1.text_input("Descrição da Despesa", placeholder="Ex: Aluguel da loja, Conta de luz...")
        valor = col2.number_input("Valor R$", min_value=0.0, value=None, placeholder="0,00", step=0.01)
        
        categoria = st.selectbox("Categoria", categorias if categorias else ["Outros"])
        
        data_desp = st.text_input("Data", value=datetime.now().strftime("%d/%m/%Y %H:%M"))
        
        if st.form_submit_button("💾 Lançar Despesa", type="primary", use_container_width=True):
            if not descricao.strip():
                st.error("❌ Descrição é obrigatória.")
            elif valor is None or valor <= 0:
                st.error("❌ Valor deve ser maior que zero.")
            else:
                conn = conectar()
                mes_ano = datetime.now().strftime("%m/%Y")
                conn.execute("""INSERT INTO despesas 
                                (descricao, valor, categoria, data, mes_ano) 
                                VALUES (?,?,?,?,?)""", 
                             (descricao.strip(), valor, categoria, data_desp, mes_ano))
                conn.commit()
                conn.close()
                st.success("✅ Despesa lançada com sucesso!")
                st.rerun()

    st.divider()

    # ======================= ÚLTIMAS DESPESAS =======================
    st.subheader("Últimas Despesas Lançadas")
    conn = conectar()
    df_desp = pd.read_sql("SELECT * FROM despesas ORDER BY id DESC LIMIT 20", conn)
    conn.close()

    if df_desp.empty:
        st.info("Nenhuma despesa lançada ainda.")
    else:
        for _, r in df_desp.iterrows():
            with st.container(border=True):
                col_a, col_b, col_c = st.columns([3.5, 1.5, 1])
                col_a.write(f"**{r['descricao']}**")
                col_a.caption(f"{r['data']} | {r['categoria']}")
                col_b.metric("Valor", f"R$ {r['valor']:.2f}")
                
                if col_c.button("🗑️", key=f"del_desp_{r['id']}"):
                    conn = conectar()
                    conn.execute("DELETE FROM despesas WHERE id=?", (r['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

# ===================================================================
# 5. LEMBRETES E TAREFAS (substituindo o bloco de notas antigo)
# ===================================================================
elif menu == "📝 Notas":
    st.header("📌 Lembretes e Tarefas")

    # Controle de filtro
    filtro = st.selectbox("Mostrar:", ["Pendentes", "Concluídos", "Todos"], index=0)

    conn = conectar()
    
    # ======================= NOVA TAREFA =======================
    with st.form("nova_tarefa"):
        st.subheader("Nova Tarefa / Lembrete")
        col1, col2 = st.columns([3, 1])
        titulo = col1.text_input("Título da tarefa", placeholder="Ex: Ligar para cliente João")
        prioridade = col2.selectbox("Prioridade", ["Alta", "Média", "Baixa"], index=1)
        
        conteudo = st.text_area("Descrição / Detalhes", placeholder="Detalhes, telefone, observações...")
        data_prazo = st.date_input("Prazo (opcional)", value=None)
        
        if st.form_submit_button("💾 Salvar Tarefa", type="primary", use_container_width=True):
            if not titulo.strip():
                st.error("Título é obrigatório.")
            else:
                data_str = data_prazo.strftime("%d/%m/%Y") if data_prazo else "Sem prazo"
                conn.execute("""INSERT INTO anotacoes 
                                (titulo, conteudo, data, prioridade, concluido) 
                                VALUES (?,?,?,?,0)""", 
                             (titulo.strip(), conteudo, data_str, prioridade))
                conn.commit()
                st.success("✅ Tarefa salva!")
                st.rerun()

    st.divider()

    # ======================= LISTA DE TAREFAS =======================
    query = "SELECT * FROM anotacoes"
    if filtro == "Pendentes":
        query += " WHERE concluido = 0"
    elif filtro == "Concluídos":
        query += " WHERE concluido = 1"
    query += " ORDER BY prioridade DESC, id DESC"
    
    df_notas = pd.read_sql(query, conn)

    if df_notas.empty:
        st.info("Nenhuma tarefa encontrada.")
    else:
        for _, r in df_notas.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([0.5, 5, 1.5])
                
                # Checkbox de concluído
                concluido = col1.checkbox("", value=bool(r['concluido']), key=f"check_{r['id']}")
                
                # Título e prioridade
                prio_color = {"Alta": "🔴", "Média": "🟡", "Baixa": "🟢"}
                titulo_display = f"{prio_color.get(r['prioridade'], '⚪')} **{r['titulo']}**"
                if r['concluido']:
                    titulo_display = f"~~{titulo_display}~~"
                
                col2.write(titulo_display)
                col2.caption(f"{r['data']} | {r.get('conteudo', '')[:80]}...")
                
                # Botão excluir
                if col3.button("🗑️", key=f"del_n_{r['id']}"):
                    conn.execute("DELETE FROM anotacoes WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
                
                # Atualiza status de concluído
                if concluido != bool(r['concluido']):
                    conn.execute("UPDATE anotacoes SET concluido=? WHERE id=?", 
                                (1 if concluido else 0, r['id']))
                    conn.commit()
                    st.rerun()

    conn.close()

# ===================================================================
# 6. TAXAS - SIMPLIFICADO (Apenas Dinheiro como padrão)
# ===================================================================
elif menu == "💳 Taxas":
    st.header("💳 Métodos de Pagamento")

    conn = conectar()
    txs_data = pd.read_sql("SELECT * FROM taxas", conn)
    conn.close()

    # --- CADASTRAR NOVO MÉTODO ---
    st.subheader("➕ Novo Método de Pagamento")
    with st.form("novo_metodo"):
        col1, col2 = st.columns([2, 1])
        nome_metodo = col1.text_input("Nome do Método", placeholder="ex: Pix, Crédito 3x, PicPay...")
        taxa = col2.number_input("Taxa (%)", min_value=0.0, value=3.99, step=0.01)

        assume = st.checkbox("Vendedor assume a taxa", value=True)
        descricao = st.text_input("Descrição", placeholder="Ex: Parcelamento em 3x sem juros...")

        if st.form_submit_button("💾 Cadastrar Método", use_container_width=True, type="primary"):
            if nome_metodo.strip():
                conn = conectar()
                conn.execute("""INSERT INTO taxas (metodo, valor_taxa, assume_vendedor, descricao)
                                VALUES (?,?,?,?)""",
                             (nome_metodo.strip(), taxa, 1 if assume else 0, descricao))
                conn.commit()
                conn.close()
                st.success(f"✅ Método **{nome_metodo}** cadastrado!")
                st.rerun()
            else:
                st.error("Nome do método é obrigatório.")

    st.divider()

    # --- LISTA DE MÉTODOS ---
    st.subheader("📋 Métodos Cadastrados")
    
    if txs_data.empty:
        st.info("Nenhum método cadastrado.")
    else:
        for _, r in txs_data.iterrows():
            with st.expander(f"💳 {r['metodo']} — {r['valor_taxa']:.2f}%"):
                c1, c2 = st.columns([3, 1])
                
                nv_taxa = c1.number_input("Taxa (%)", value=float(r['valor_taxa']), step=0.01, key=f"taxa_{r['id']}")
                nv_assume = c2.checkbox("Vendedor assume", value=bool(r['assume_vendedor']), key=f"assume_{r['id']}")
                
                nv_desc = st.text_input("Descrição", value=r.get('descricao', ''), key=f"desc_{r['id']}")

                col_salvar, col_excluir = st.columns(2)
                
                if col_salvar.button("💾 Salvar", key=f"salvar_{r['id']}"):
                    conn = conectar()
                    conn.execute("""UPDATE taxas 
                                    SET valor_taxa=?, assume_vendedor=?, descricao=? 
                                    WHERE id=?""",
                                 (nv_taxa, 1 if nv_assume else 0, nv_desc, r['id']))
                    conn.commit()
                    conn.close()
                    st.success("Alterações salvas!")
                    st.rerun()

                # Só permite excluir se NÃO for Dinheiro
                if r['metodo'] != "Dinheiro":
                    if col_excluir.button("🗑️ Excluir Método", key=f"excluir_{r['id']}"):
                        conn = conectar()
                        conn.execute("DELETE FROM taxas WHERE id=?", (r['id'],))
                        conn.commit()
                        conn.close()
                        st.success(f"Método {r['metodo']} excluído!")
                        st.rerun()
                else:
                    col_excluir.button("🔒 Padrão", disabled=True)

# ===================================================================
# 7. BACKUP COM ONEDRIVE
# ===================================================================
elif menu == "🔄 Backup OneDrive":
    st.header("🔄 Backup e Restauração - OneDrive")

    # Defina aqui o caminho da pasta sincronizada do OneDrive
    ONEDRIVE_PATH = os.path.join(os.path.expanduser("~"), "OneDrive", "PhotoGestao_Backups")
    os.makedirs(ONEDRIVE_PATH, exist_ok=True)

    st.info(f"Pasta do OneDrive configurada em:\n`{ONEDRIVE_PATH}`")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📤 Fazer Backup (Enviar para OneDrive)")
        backup_name = f"dados_loja_backup_{datetime.now().strftime('%d_%m_%Y_%H%M')}.db"
        
        if st.button("💾 Criar Backup no OneDrive", type="primary", use_container_width=True):
            try:
                import shutil
                destino = os.path.join(ONEDRIVE_PATH, backup_name)
                shutil.copy2(CAMINHO_BANCO, destino)
                st.success(f"✅ Backup criado com sucesso!\nArquivo: **{backup_name}**")
                st.info("O OneDrive vai sincronizar automaticamente.")
            except Exception as e:
                st.error(f"Erro ao criar backup: {e}")

    with col2:
        st.subheader("📥 Restaurar Backup Antigo")
        st.warning("⚠️ Cuidado: Isso vai substituir o banco atual!")

        # Lista os backups disponíveis na pasta do OneDrive
        if os.path.exists(ONEDRIVE_PATH):
            backups = [f for f in os.listdir(ONEDRIVE_PATH) if f.endswith('.db')]
            backups.sort(reverse=True)
            
            if backups:
                arquivo_selecionado = st.selectbox("Escolha o backup para restaurar:", backups)
                
                if st.button("🔄 Restaurar este Backup", type="primary", use_container_width=True):
                    try:
                        # Faz backup de segurança do atual
                        shutil.copy2(CAMINHO_BANCO, CAMINHO_BANCO + ".backup")
                        
                        origem = os.path.join(ONEDRIVE_PATH, arquivo_selecionado)
                        shutil.copy2(origem, CAMINHO_BANCO)
                        
                        st.success("✅ Banco restaurado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro na restauração: {e}")
            else:
                st.info("Nenhum backup encontrado na pasta do OneDrive.")
        else:
            st.error("Pasta do OneDrive não encontrada. Verifique o caminho.")

    st.divider()
    st.caption("Dica: Mantenha a pasta 'PhotoGestao_Backups' sincronizada no OneDrive.")
