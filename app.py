import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import shutil
from pathlib import Path

# ===================================================================
# CONFIGURAÇÃO E SETUP
# ===================================================================

# Configuração de caminhos - compatível com Windows, Mac e Linux
BASE_DIR = Path(__file__).parent.absolute()
CAMINHO_BANCO = BASE_DIR / 'dados_loja.db'

# BACKUP FOLDER - pode ser configurado via variável de ambiente
BACKUP_FOLDER = Path(os.getenv('FOTO_AMANCIO_BACKUP', BASE_DIR / 'backups'))
BACKUP_FOLDER.mkdir(exist_ok=True, parents=True)

# ===================================================================
# FUNÇÕES DE BANCO DE DADOS
# ===================================================================

def limpar_todos_os_dados():
    """Limpa todos os dados das tabelas (exceto estrutura) - protegido por senha"""
    st.subheader("🗑️ Limpeza Total do Banco de Dados")
    st.warning("⚠️ Esta ação é irreversível! Todos os dados serão apagados.")

    senha = st.text_input("Digite a senha para confirmar a limpeza total:", 
                         type="password", 
                         placeholder="Digite a senha")

    if st.button("🗑️ APAGAR TODOS OS DADOS", type="primary"):
        if not senha:
            st.error("❌ Você deve digitar a senha.")
            return
        
        # ==================== SENHA DEFINIDA AQUI ====================
        SENHA_CORRETA = "limpar123"   # ← MUDE ESTA SENHA PARA ALGO SEGURO!

        if senha == SENHA_CORRETA:
            try:
                conn = conectar()
                c = conn.cursor()
                
                with st.spinner("Apagando todos os dados..."):
                    # Limpa os dados (mantém a estrutura das tabelas)
                    c.execute("DELETE FROM vendas")
                    c.execute("DELETE FROM despesas")
                    c.execute("DELETE FROM carrinho_temp")
                    c.execute("DELETE FROM anotacoes")
                    c.execute("DELETE FROM produtos")
                    c.execute("DELETE FROM categorias_desp")
                    
                    # Opcional: também limpar a flag de categorias iniciais
                    c.execute("DELETE FROM system_flags WHERE flag_name = 'initial_categories_created'")
                    
                    conn.commit()
                    conn.close()
                
                st.success("✅ Todos os dados foram apagados com sucesso!")
                st.info("O app será reiniciado em 2 segundos...")
                import time
                time.sleep(2)
                st.rerun()
                
            except Exception as e:
                st.error(f"Erro durante a limpeza: {e}")
        else:
            st.error("❌ Senha incorreta! Operação cancelada.")


def conectar():
    """Conecta ao banco de dados SQLite com settings seguros"""
    conn = sqlite3.connect(str(CAMINHO_BANCO), check_same_thread=False)
    return conn

def cleanup_old_backups(folder=None, max_backups=15):
    """Mantém apenas os últimos X backups - versão segura"""
    if folder is None:
        folder = BACKUP_FOLDER
    try:
        folder = Path(folder)
        files = sorted(
            [f for f in folder.glob('dados_loja_*.db')],
            reverse=True
        )
        for old_file in files[max_backups:]:
            old_file.unlink()
    except Exception as e:
        st.warning(f"Erro ao limpar backups: {e}")

def fazer_backup_automatico(tipo=""):
    """Faz backup automático após alterações importantes"""
    try:
        BACKUP_FOLDER.mkdir(exist_ok=True, parents=True)
        timestamp = datetime.now().strftime("%d_%m_%Y_%H%M%S")
        
        if tipo:
            backup_name = f"dados_loja_{tipo}_{timestamp}.db"
        else:
            backup_name = f"dados_loja_backup_{timestamp}.db"
        
        destino = BACKUP_FOLDER / backup_name
        shutil.copy2(str(CAMINHO_BANCO), str(destino))
        cleanup_old_backups(BACKUP_FOLDER, max_backups=15)
        return True
    except Exception as e:
        st.error(f"Erro no backup automático: {e}")
        return False

# ===================================================================
# CRIAÇÃO DE TABELAS E MIGRATIONS
# ===================================================================

def criar_tabelas():
    conn = conectar()
    c = conn.cursor()
    
    # ==================== NOVA TABELA DE USUÁRIOS ====================
    # perfil: 'dono' ou 'operador'
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT UNIQUE,
                 senha TEXT,
                 perfil TEXT)''')

    # ==================== CRIAÇÃO DAS TABELAS ORIGINAIS ====================
    c.execute('CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, preco REAL)')
    
    c.execute('''CREATE TABLE IF NOT EXISTS taxas (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 metodo TEXT UNIQUE,
                 valor_taxa REAL,
                 assume_vendedor INTEGER DEFAULT 1,
                 descricao TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS vendas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, produto TEXT, valor_bruto REAL,
                  desconto REAL, metodo_pgto TEXT, taxa_momento REAL, data TEXT, mes_ano TEXT, obs TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS despesas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT, valor REAL,
                  categoria TEXT, data TEXT, mes_ano TEXT)''')
    
    c.execute('CREATE TABLE IF NOT EXISTS categorias_desp (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)')
    
    c.execute('''CREATE TABLE IF NOT EXISTS anotacoes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, conteudo TEXT,
                  data TEXT, prioridade TEXT DEFAULT "Média", concluido INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS carrinho_temp
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, produto TEXT,
                  valor_bruto REAL, desconto REAL DEFAULT 0, valor REAL, obs TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS fluxo_caixa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_abertura TEXT,
                data_fechamento TEXT,
                valor_inicial REAL,
                valor_final_informado REAL,
                valor_esperado REAL,
                status TEXT)''') # status: 'Aberto' ou 'Fechado'
    

# ==================== DADOS INICIAIS (SEGURANÇA) ====================
    
    # Verifica se o admin já existe
    admin_existe = c.execute("SELECT id FROM usuarios WHERE username = 'admin'").fetchone()
    
    if admin_existe:
        # Se existe, apenas garante que a senha e perfil estão corretos (conforme sua escolha)
        c.execute("UPDATE usuarios SET senha = ?, perfil = ? WHERE username = ?", 
                  ('batatinhafrita', 'dono', 'admin'))
    else:
        # Se não existe, cria do zero
        c.execute("INSERT INTO usuarios (username, senha, perfil) VALUES (?,?,?)", 
                  ('admin', 'batatinhafrita', 'dono'))

    # Método "Dinheiro"
    if c.execute("SELECT COUNT(*) FROM taxas WHERE metodo = 'Dinheiro'").fetchone()[0] == 0:
        c.execute("""INSERT INTO taxas (metodo, valor_taxa, assume_vendedor, descricao)
                     VALUES (?,?,?,?)""", 
                  ('Dinheiro', 0.0, 1, 'Pagamento em espécie - sem taxa'))

    conn.commit()
    conn.close()

def migrar_banco():
    """Executa migrações de banco de dados"""
    conn = conectar()
    c = conn.cursor()
    
    try:
        c.execute("ALTER TABLE anotacoes ADD COLUMN prioridade TEXT DEFAULT 'Média'")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE anotacoes ADD COLUMN concluido INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

# Executa criação e migração na inicialização
criar_tabelas()
migrar_banco()

# ===================================================================
# FUNÇÕES AUXILIARES DE VALIDAÇÃO
# ===================================================================

def validar_texto(texto, min_length=1, max_length=500):
    """Valida entrada de texto"""
    if not texto or not texto.strip():
        return False
    if len(texto.strip()) < min_length or len(texto.strip()) > max_length:
        return False
    return True

def validar_valor(valor, min_val=0.0):
    """Valida entrada de valores monetários"""
    try:
        v = float(valor)
        return v >= min_val
    except (ValueError, TypeError):
        return False

def formatar_moeda(valor):
    """Formata valor em reais"""
    return f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

# ===================================================================
# CONFIGURAÇÃO STREAMLIT
# ===================================================================

st.set_page_config(
    page_title="Foto Amancio - PDV",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar variáveis de sessão
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.perfil = None

def tela_login():
    st.title("📸 Sistema Foto Amancio")
    with st.form("login"):
        user = st.text_input("Usuário")
        pw = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            conn = conectar()
            res = conn.execute("SELECT perfil FROM usuarios WHERE username=? AND senha=?", 
                             (user, pw)).fetchone()
            conn.close()
            
            if res:
                st.session_state.autenticado = True
                st.session_state.perfil = res[0]
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos")

if not st.session_state.autenticado:
    tela_login()
    st.stop() # Interrompe a execução aqui se não estiver logado


# ===================================================================
# MENU LATERAL (Filtrado por Perfil)
# ===================================================================

st.sidebar.title("📸 Foto Amancio")
st.sidebar.caption(f"Logado como: **{st.session_state.perfil.upper()}**")
st.sidebar.divider()

# 1. Definir as opções permitidas para cada nível
opcoes_dono = ["🛒 PDV", "💰 Caixa", "📊 Dashboard", "👥 Gestão de Usuários", ...]
opcoes_operador = ["🛒 PDV", "💰 Caixa", "📝 Notas"]

# 2. Escolher a lista baseada no perfil
if st.session_state.perfil == "dono":
    opcoes_finais = opcoes_dono
else:
    opcoes_finais = opcoes_operador

# 3. Renderizar o rádio
menu = st.sidebar.radio("Navegação:", opcoes_finais)


st.sidebar.divider()

# 4. Botão de Logout (Sair)
if st.sidebar.button("🚪 Sair do Sistema"):
    st.session_state.autenticado = False
    st.session_state.perfil = None
    st.rerun()

st.sidebar.divider()
st.sidebar.caption(f"📁 Banco: {CAMINHO_BANCO.name}")
st.sidebar.caption(f"💾 Backups: {BACKUP_FOLDER.name}")

# ... (Aqui termina o seu código do Sidebar que você postou por último)
st.sidebar.caption(f"💾 Backups: {BACKUP_FOLDER.name}")

# ===================================================================
# COLOQUE O CÓDIGO NOVO AQUI (LOGICA DE EXIBIÇÃO)
# ===================================================================

# ===================================================================
# LÓGICA DE EXIBIÇÃO DAS PÁGINAS
# ===================================================================

if menu == "👥 Gestão de Usuários":
    st.header("👥 Gestão de Usuários e Acessos")
    
    # --- 1. FORMULÁRIO PARA NOVO USUÁRIO ---
    with st.expander("➕ Cadastrar Novo Usuário/Funcionário"):
        with st.form("novo_usuario"):
            u_nome = st.text_input("Login do Usuário")
            u_senha = st.text_input("Senha", type="password")
            u_perfil = st.selectbox("Nível de Acesso", ["operador", "dono"])
            
            if st.form_submit_button("Salvar Usuário"):
                if u_nome and u_senha:
                    try:
                        conn = conectar()
                        conn.execute("INSERT INTO usuarios (username, senha, perfil) VALUES (?,?,?)",
                                     (u_nome, u_senha, u_perfil))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Usuário '{u_nome}' criado com sucesso!")
                        st.rerun()
                    except:
                        st.error("❌ Erro: Este usuário já existe.")
                else:
                    st.warning("Preencha todos os campos.")

    st.divider()

    # --- 2. LISTAGEM E EDIÇÃO DE SENHA ---
    st.subheader("Usuários Cadastrados")
    conn = conectar()
    df_users = pd.read_sql("SELECT id, username, perfil FROM usuarios", conn)
    conn.close()

    for i, row in df_users.iterrows():
        with st.container(border=True):
            col_info, col_edit, col_del = st.columns([2, 3, 1])
            
            col_info.write(f"👤 **{row['username']}**")
            col_info.caption(f"Nível: `{row['perfil']}`")
            
            nova_senha = col_edit.text_input(
                "Alterar senha", 
                type="password", 
                key=f"input_pw_{row['id']}", 
                placeholder="Nova senha..."
            )
            
            if col_edit.button("Atualizar Senha", key=f"btn_pw_{row['id']}", use_container_width=True):
                if nova_senha:
                    conn = conectar()
                    conn.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (nova_senha, row['id']))
                    conn.commit()
                    conn.close()
                    st.success(f"Senha de {row['username']} atualizada!")
                else:
                    st.warning("Digite a nova senha primeiro.")

            if row['username'] != 'admin':
                if col_del.button("🗑️", key=f"del_{row['id']}", help="Excluir usuário"):
                    conn = conectar()
                    conn.execute("DELETE FROM usuarios WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
            else:
                col_del.info("Mestre")

# ===================================================================
# 3. NOVA PÁGINA: CONTROLE DE CAIXA
# ===================================================================
elif menu == "💰 Caixa":
    st.header("💰 Controle de Caixa")
    
    conn = conectar()
    caixa_atual = pd.read_sql("SELECT * FROM fluxo_caixa WHERE status = 'Aberto' ORDER BY id DESC LIMIT 1", conn)
    conn.close()

    if caixa_atual.empty:
        st.info("🏪 O caixa está fechado. Abra o caixa para registrar vendas em dinheiro.")
        with st.form("abrir_caixa"):
            valor_ini = st.number_input("Valor Inicial (Troco):", min_value=0.0, step=1.0)
            if st.form_submit_button("🔓 Abrir Caixa"):
                conn = conectar()
                data_abr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("INSERT INTO fluxo_caixa (data_abertura, valor_inicial, status) VALUES (?,?,?)",
                             (data_abr, valor_ini, 'Aberto'))
                conn.commit()
                conn.close()
                st.success("Caixa aberto!")
                st.rerun()
    else:
        dados = caixa_atual.iloc[0]
        st.warning(f"🟢 Caixa Aberto em: {dados['data_abertura']}")
        
        # Lógica de cálculo
        conn = conectar()
        vendas_dinheiro = pd.read_sql(f"""SELECT SUM(valor_bruto - desconto) as total FROM vendas 
                                         WHERE metodo_pgto = 'Dinheiro' 
                                         AND data >= '{dados['data_abertura']}'""", conn)['total'].iloc[0] or 0.0
        conn.close()
        
        valor_esperado = dados['valor_inicial'] + vendas_dinheiro
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Troco Inicial", f"R$ {dados['valor_inicial']:.2f}")
        c2.metric("Vendas (Dinheiro)", f"R$ {vendas_dinheiro:.2f}")
        c3.metric("Total Esperado", f"R$ {valor_esperado:.2f}")

        st.divider()

        with st.expander("🔒 Fechar Caixa"):
            valor_final_real = st.number_input("Valor total contado na gaveta:", min_value=0.0, step=1.0)
            if st.button("Finalizar Fechamento"):
                quebra = valor_final_real - valor_esperado
                data_fec = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                conn = conectar()
                conn.execute("""UPDATE fluxo_caixa SET 
                                data_fechamento = ?, 
                                valor_final_informado = ?, 
                                valor_esperado = ?, 
                                status = 'Fechado' 
                                WHERE id = ?""", 
                             (data_fec, valor_final_real, valor_esperado, dados['id']))
                conn.commit()
                conn.close()
                st.rerun()

# ===================================================================
# 4. PDV (AGORA COMO ELIF)
# ===================================================================
elif menu == "🛒 PDV":
    st.header("🛒 Frente de Caixa")    
    conn = conectar()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY nome", conn)
    txs = pd.read_sql("SELECT * FROM taxas ORDER BY metodo", conn)
    carr = pd.read_sql("SELECT * FROM carrinho_temp", conn)
    conn.close()
    
    col1, col2 = st.columns([1, 1.2])
    
    # ======================= COLUNA 1: ADICIONAR ITENS =======================
    with col1:
        st.subheader("Adicionar Item")
        
        lista_produtos = ["Personalizado"] + prods['nome'].tolist()
        p_sel = st.selectbox("Produto", lista_produtos)
        
        # Preço sugerido baseado no produto selecionado
        if p_sel == "Personalizado":
            p_unit_sugerido = 0.0
        else:
            p_unit_sugerido = float(prods[prods['nome'] == p_sel]['preco'].values[0])
        
        c_v1, c_v2 = st.columns([2, 1])
        v_unit = c_v1.number_input("Preço Unitário R$", min_value=0.0, value=p_unit_sugerido, step=0.01)
        qtd = c_v2.number_input("Qtd", min_value=1, value=1, step=1)
        
        com_desconto = st.checkbox("Aplicar desconto neste item?")
        valor_bruto_item = v_unit * qtd
        desconto_aplicado = 0.0
        v_final_item = valor_bruto_item

        if com_desconto:
            v_com_desconto = st.number_input(
                "Preço Final com Desconto R$", 
                min_value=0.0, 
                max_value=valor_bruto_item, 
                value=valor_bruto_item, 
                step=0.01
            )
            desconto_aplicado = valor_bruto_item - v_com_desconto
            v_final_item = v_com_desconto
            st.warning(f"Desconto de {formatar_moeda(desconto_aplicado)} aplicado.")
        
        v_obs = st.text_input("Observação do Item")
        
        if v_unit > 0:
            st.info(f"Subtotal: {qtd}x {p_sel} = {formatar_moeda(v_final_item)}")

        if st.button("➕ Adicionar ao Carrinho", use_container_width=True, type="primary"):
            if v_unit > 0:
                conn = conectar()
                obs_detalhada = f"Qtd: {qtd} | {v_obs}" if v_obs else f"Qtd: {qtd}"
                conn.execute(
                    """INSERT INTO carrinho_temp
                       (produto, valor_bruto, desconto, valor, obs)
                       VALUES (?,?,?,?,?)""", 
                    (p_sel, valor_bruto_item, desconto_aplicado, v_final_item, obs_detalhada)
                )
                conn.commit()
                conn.close()
                st.success("✅ Item adicionado!")
                st.rerun()
            else:
                st.error("O preço do item deve ser maior que zero.")
    
    # ======================= COLUNA 2: CARRINHO =======================
    with col2:
        st.subheader("🛒 Itens no Carrinho")
        
        if not carr.empty:
            # Exibir itens
            df_display = carr[['produto', 'valor_bruto', 'desconto', 'valor', 'obs']].copy()
            df_display.columns = ['Produto', 'Bruto (R$)', 'Desc (R$)', 'Final (R$)', 'Obs']
            st.dataframe(df_display, hide_index=True, use_container_width=True)
            
            # Total
            total_carrinho = carr['valor'].sum()
            st.divider()
            st.metric("Total do Pedido", formatar_moeda(total_carrinho))
            
            # Forma de pagamento
            if not txs.empty:
                met_p = st.selectbox("Forma de Pagamento", txs['metodo'].tolist())
                tx_v = txs[txs['metodo'] == met_p]['valor_taxa'].values[0]
                
                c_f1, c_f2, c_f3 = st.columns(3)
                
                # Botão finalizar venda
                if c_f1.button("✅ FINALIZAR VENDA", type="primary", use_container_width=True):
                    agora = datetime.now()
                    conn = conectar()
                    c = conn.cursor()
                    
                    try:
                        # Inserir as vendas - usando parametrized query
                        for _, item in carr.iterrows():
                            c.execute(
                                """INSERT INTO vendas
                                   (produto, valor_bruto, desconto, metodo_pgto, taxa_momento, data, mes_ano, obs)
                                   VALUES (?,?,?,?,?,?,?,?)""",
                                (item['produto'], item['valor_bruto'], item['desconto'], 
                                 met_p, tx_v, agora.strftime("%d/%m/%Y %H:%M"), 
                                 agora.strftime("%m/%Y"), item['obs'])
                            )
                        
                        # Limpar carrinho
                        c.execute("DELETE FROM carrinho_temp")
                        conn.commit()
                        
                        st.success("✅ Venda finalizada com sucesso!")
                        
                        # Backup automático
                        if fazer_backup_automatico("venda"):
                            st.success("💾 Backup realizado!")
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao finalizar venda: {e}")
                        conn.rollback()
                    finally:
                        conn.close()
                
                # Botão esvaziar carrinho
                if c_f2.button("🗑️ Esvaziar", use_container_width=True):
                    conn = conectar()
                    conn.execute("DELETE FROM carrinho_temp")
                    conn.commit()
                    conn.close()
                    st.rerun()
            else:
                st.warning("Nenhuma forma de pagamento cadastrada!")
        else:
            st.info("O carrinho está vazio.")

# ===================================================================
# 2. DASHBOARD
# ===================================================================

elif menu == "📊 Dashboard":
    st.header("📊 Resumo Financeiro Real")
    
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

    def filtrar_por_data(df, coluna_data):
        """Filtra dataframe por intervalo de datas - SEGURO"""
        if df.empty:
            return df
        try:
            df = df.copy()
            df['data_obj'] = pd.to_datetime(df[coluna_data], format="%d/%m/%Y %H:%M", errors='coerce')
        except Exception:
            try:
                df['data_obj'] = pd.to_datetime(df[coluna_data], errors='coerce')
            except Exception:
                return df
        
        df = df.dropna(subset=['data_obj'])
        df = df[(df['data_obj'].dt.date >= data_inicio) & (df['data_obj'].dt.date <= data_fim)]
        return df

    df_v_filtrado = filtrar_por_data(df_v, 'data')
    df_d_filtrado = filtrar_por_data(df_d, 'data')

    # Cálculos
    faturamento_bruto = df_v_filtrado['valor_bruto'].sum() if not df_v_filtrado.empty else 0.0
    total_descontos = df_v_filtrado['desconto'].sum() if not df_v_filtrado.empty else 0.0
    total_taxas_cartao = (
        (df_v_filtrado['valor_bruto'] - df_v_filtrado['desconto']) * 
        (df_v_filtrado['taxa_momento'] / 100)
    ).sum() if not df_v_filtrado.empty else 0.0
    total_despesas = df_d_filtrado['valor'].sum() if not df_d_filtrado.empty else 0.0
    lucro_final = faturamento_bruto - total_descontos - total_taxas_cartao - total_despesas

    # Métricas
    m1, m2 = st.columns(2)
    m3, m4 = st.columns(2)
    m5 = st.container()

    with m1:
        st.metric("Faturamento Bruto", formatar_moeda(faturamento_bruto))
    with m2:
        st.metric("Descontos", f"- {formatar_moeda(total_descontos)}", delta_color="inverse")
    with m3:
        st.metric("Taxas Cartão", f"- {formatar_moeda(total_taxas_cartao)}", delta_color="inverse")
    with m4:
        st.metric("Despesas", f"- {formatar_moeda(total_despesas)}", delta_color="inverse")
    with m5:
        st.metric("**LUCRO REAL**", formatar_moeda(lucro_final))

    st.divider()
    st.caption(f"📅 Período: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")
    st.info(f"**Vendas:** {len(df_v_filtrado)}   |   **Despesas:** {len(df_d_filtrado)}")

    # Gráficos
    st.divider()
    st.subheader("📈 Gráficos")
    
    if not df_v_filtrado.empty:
        # Gráfico de vendas por método de pagamento
        vendas_por_metodo = df_v_filtrado.groupby('metodo_pgto')['valor_bruto'].sum()
        st.bar_chart(vendas_por_metodo)
    
    if not df_d_filtrado.empty:
        # Gráfico de despesas por categoria
        despesas_por_cat = df_d_filtrado.groupby('categoria')['valor'].sum()
        st.bar_chart(despesas_por_cat)

    # Botão para baixar relatório
    st.divider()
    if st.button("📄 Gerar Relatório PDF", use_container_width=True):
        try:
            from fpdf import FPDF
            
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, "Relatório Financeiro - Foto Amancio", ln=True, align='C')
            pdf.cell(200, 10, f"Período: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}", ln=True, align='C')
            pdf.ln(15)
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, f"Faturamento Bruto: {formatar_moeda(faturamento_bruto)}", ln=True)
            pdf.cell(200, 10, f"Descontos: {formatar_moeda(total_descontos)}", ln=True)
            pdf.cell(200, 10, f"Taxas de Cartão: {formatar_moeda(total_taxas_cartao)}", ln=True)
            pdf.cell(200, 10, f"Despesas: {formatar_moeda(total_despesas)}", ln=True)
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 15, f"LUCRO LÍQUIDO REAL: {formatar_moeda(lucro_final)}", ln=True, align='C')
            
            pdf_output = pdf.output(dest='S').encode('latin-1')
            st.download_button(
                label="📥 Baixar Relatório",
                data=pdf_output,
                file_name=f"Relatorio_{data_inicio.strftime('%d%m%Y')}_a_{data_fim.strftime('%d%m%Y')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except ImportError:
            st.error("Instale fpdf2: pip install fpdf2")

# ===================================================================
# 3. HISTÓRICO
# ===================================================================

elif menu == "📜 Histórico":
    st.header("📜 Histórico Recente")
    
    if 'edit_id' not in st.session_state:
        st.session_state.edit_id = None
        st.session_state.edit_tipo = None

    sub = st.selectbox("Tipo:", ["Vendas", "Despesas"])
    conn = conectar()
    
    if sub == "Vendas":
        df = pd.read_sql("SELECT * FROM vendas ORDER BY id DESC LIMIT 30", conn)
        
        if df.empty:
            st.info("Nenhuma venda registrada.")
        else:
            for _, r in df.iterrows():
                with st.container(border=True):
                    col_a, col_b, col_c, col_d = st.columns([3, 1.3, 0.8, 0.8])
                    col_a.write(f"**{r['produto']}** | {r['data']}")
                    col_a.caption(f"{r['metodo_pgto']} | {r['obs']}")
                    col_b.write(formatar_moeda(r['valor_bruto']))
                    if r['desconto'] > 0:
                        col_b.caption(f"Desc: {formatar_moeda(r['desconto'])}")
                    
                    if col_c.button("✏️", key=f"edit_v_{r['id']}"):
                        st.session_state.edit_id = r['id']
                        st.session_state.edit_tipo = "vendas"
                    
                    if col_d.button("🗑️", key=f"del_v_{r['id']}"):
                        conn.execute("DELETE FROM vendas WHERE id=?", (r['id'],))
                        conn.commit()
                        st.rerun()
    else:
        df = pd.read_sql("SELECT * FROM despesas ORDER BY id DESC LIMIT 30", conn)
        
        if df.empty:
            st.info("Nenhuma despesa registrada.")
        else:
            for _, r in df.iterrows():
                with st.container(border=True):
                    col_a, col_b, col_c, col_d = st.columns([3, 1.2, 0.8, 0.8])
                    col_a.write(f"**{r['descricao']}** | {r['data']}")
                    col_a.caption(f"Cat: {r['categoria']}")
                    col_b.write(formatar_moeda(r['valor']))
                    
                    if col_c.button("✏️", key=f"edit_d_{r['id']}"):
                        st.session_state.edit_id = r['id']
                        st.session_state.edit_tipo = "despesas"
                    
                    if col_d.button("🗑️", key=f"del_d_{r['id']}"):
                        conn.execute("DELETE FROM despesas WHERE id=?", (r['id'],))
                        conn.commit()
                        st.rerun()
    
    conn.close()

    # ======================= FORMULÁRIO DE EDIÇÃO =======================
    if st.session_state.edit_id is not None and st.session_state.edit_tipo is not None:
        st.divider()
        st.subheader("✏️ Editando Registro")

        conn = conectar()

        if st.session_state.edit_tipo == "vendas":
            df_edit = pd.read_sql(
                "SELECT * FROM vendas WHERE id = ?",
                conn,
                params=(st.session_state.edit_id,)
            )

            if not df_edit.empty:
                item = df_edit.iloc[0]
                
                with st.form("edit_venda_form"):
                    novo_produto = st.text_input("Produto", value=item['produto'])
                    novo_valor_bruto = st.number_input("Valor Bruto R$", value=float(item['valor_bruto']), step=0.01)
                    novo_desconto = st.number_input("Desconto R$", value=float(item['desconto']), step=0.01, min_value=0.0)
                    novo_metodo = st.text_input("Método de Pagamento", value=item['metodo_pgto'])
                    nova_taxa = st.number_input("Taxa (%)", value=float(item['taxa_momento']), step=0.01)
                    nova_obs = st.text_input("Observação", value=item['obs'])
                    
                    col_save, col_cancel = st.columns(2)
                    
                    if col_save.form_submit_button("💾 Salvar", type="primary"):
                        if novo_valor_bruto > 0:
                            conn.execute(
                                """UPDATE vendas SET 
                                   produto=?, valor_bruto=?, desconto=?, 
                                   metodo_pgto=?, taxa_momento=?, obs=? 
                                   WHERE id=?""",
                                (novo_produto, novo_valor_bruto, novo_desconto,
                                 novo_metodo, nova_taxa, nova_obs, st.session_state.edit_id)
                            )
                            conn.commit()
                            st.success("✅ Venda atualizada com sucesso!")
                            st.session_state.edit_id = None
                            st.session_state.edit_tipo = None
                            st.rerun()
                        else:
                            st.error("Valor deve ser maior que zero!")
                    
                    if col_cancel.form_submit_button("❌ Cancelar"):
                        st.session_state.edit_id = None
                        st.session_state.edit_tipo = None
                        st.rerun()
            else:
                st.error("Venda não encontrada!")

        elif st.session_state.edit_tipo == "despesas":
            df_edit = pd.read_sql(
                "SELECT * FROM despesas WHERE id = ?",
                conn,
                params=(st.session_state.edit_id,)
            )

            if not df_edit.empty:
                item = df_edit.iloc[0]
                
                with st.form("edit_despesa_hist_form"):
                    novo_desc = st.text_input("Descrição", value=item['descricao'])
                    novo_valor = st.number_input("Valor R$", value=float(item['valor']), step=0.01)
                    novo_cat = st.text_input("Categoria", value=item['categoria'])
                    nova_data = st.text_input("Data (DD/MM/YYYY HH:MM)", value=item['data'])
                    
                    col_save, col_cancel = st.columns(2)
                    
                    if col_save.form_submit_button("💾 Salvar", type="primary"):
                        if novo_valor > 0:
                            conn.execute(
                                """UPDATE despesas SET 
                                   descricao=?, valor=?, categoria=?, data=? 
                                   WHERE id=?""",
                                (novo_desc, novo_valor, novo_cat, nova_data, st.session_state.edit_id)
                            )
                            conn.commit()
                            st.success("✅ Despesa atualizada com sucesso!")
                            st.session_state.edit_id = None
                            st.session_state.edit_tipo = None
                            st.rerun()
                        else:
                            st.error("Valor deve ser maior que zero!")
                    
                    if col_cancel.form_submit_button("❌ Cancelar"):
                        st.session_state.edit_id = None
                        st.session_state.edit_tipo = None
                        st.rerun()
            else:
                st.error("Despesa não encontrada!")

        conn.close()

# ===================================================================
# 4. CADASTROS
# ===================================================================

elif menu == "📦 Cadastros":
    st.header("📦 Gestão de Itens")
    tab1, tab2 = st.tabs(["🛍️ Produtos", "📂 Categorias"])

    if 'edit_item' not in st.session_state:
        st.session_state.edit_item = None
        st.session_state.edit_tipo = None

    # ======================= PRODUTOS =======================
    with tab1:
        st.subheader("🛍️ Cadastro de Produtos")
        
        with st.form("novo_produto", clear_on_submit=True):
            col_nome, col_preco = st.columns([3, 1])
            nome_prod = col_nome.text_input("Nome do Produto", placeholder="Ex: Pacote 20 fotos 15x21")
            preco_prod = col_preco.number_input("Preço de Venda R$", min_value=0.0, value=0.0, step=0.01)
            
            if st.form_submit_button("➕ Cadastrar Produto", use_container_width=True, type="primary"):
                if validar_texto(nome_prod, min_length=3, max_length=200):
                    if validar_valor(preco_prod, min_val=0.0):
                        conn = conectar()
                        try:
                            conn.execute(
                                "INSERT INTO produtos (nome, preco) VALUES (?,?)", 
                                (nome_prod.strip(), float(preco_prod))
                            )
                            conn.commit()
                            st.success("✅ Produto cadastrado com sucesso!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("❌ Produto com este nome já existe!")
                        finally:
                            conn.close()
                    else:
                        st.error("Preço inválido!")
                else:
                    st.error("❌ Nome do produto é obrigatório (3-200 caracteres).")

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
                    col2.metric("Preço", formatar_moeda(row['preco']))
                    
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

    # ======================= CATEGORIAS =======================
    # ======================= 2. CATEGORIAS =======================
    with tab2:
        st.subheader("📂 Categorias de Despesa")
        
        with st.form("nova_categoria", clear_on_submit=True):
            nova_cat = st.text_input("Nome da Categoria", placeholder="Ex: Aluguel, Energia, Marketing...")
            
            if st.form_submit_button("➕ Adicionar Categoria", use_container_width=True, type="primary"):
                # Validação: deve ter pelo menos uma letra (não pode ser vazio ou só espaços)
                if not nova_cat or not nova_cat.strip():
                    st.error("❌ O nome da categoria não pode estar vazio.")
                elif len(nova_cat.strip()) < 1:
                    st.error("❌ A categoria deve ter pelo menos uma letra.")
                else:
                    nome_limpo = nova_cat.strip()
                    conn = conectar()
                    # Verifica se a categoria já existe (evita duplicatas)
                    existe = conn.execute("SELECT COUNT(*) FROM categorias_desp WHERE nome = ?", 
                                        (nome_limpo,)).fetchone()[0]
                    
                    if existe > 0:
                        st.error(f"❌ A categoria '{nome_limpo}' já existe.")
                    else:
                        conn.execute("INSERT INTO categorias_desp (nome) VALUES (?)", (nome_limpo,))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Categoria '{nome_limpo}' adicionada com sucesso!")
                        st.rerun()

        st.divider()
        st.subheader("📋 Categorias Cadastradas")
        
        conn = conectar()
        df_cat = pd.read_sql("SELECT id, nome FROM categorias_desp ORDER BY nome", conn)
        conn.close()

        if df_cat.empty:
            st.info("Nenhuma categoria cadastrada ainda.")
        else:
            for _, row in df_cat.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([5, 1, 1])
                    col1.write(f"**{row['nome']}**")
                    
                    if col2.button("✏️ Editar", key=f"ec_{row['id']}"):
                        st.session_state.edit_item = row['id']
                        st.session_state.edit_tipo = "categoria"
                        st.rerun()
                    
                    if col3.button("🗑️ Excluir", key=f"dc_{row['id']}"):
                        conn = conectar()
                        uso = conn.execute("SELECT COUNT(*) FROM despesas WHERE categoria=?", 
                                         (row['nome'],)).fetchone()[0]
                        if uso > 0:
                            st.error(f"Não é possível excluir. Usada em {uso} despesa(s).")
                        else:
                            conn.execute("DELETE FROM categorias_desp WHERE id=?", (row['id'],))
                            conn.commit()
                            st.success("Categoria excluída!")
                        conn.close()
                        st.rerun()
# ===================================================================
# 5. DESPESAS
# ===================================================================

elif menu == "💰 Despesas":
    st.header("💰 Lançamento de Despesas")

    if 'edit_despesa_id' not in st.session_state:
        st.session_state.edit_despesa_id = None

    conn = conectar()
    categorias = pd.read_sql("SELECT nome FROM categorias_desp ORDER BY nome", conn)['nome'].tolist()
    conn.close()

    # ======================= NOVA DESPESA =======================
    with st.form("nova_despesa", clear_on_submit=True):
        st.subheader("Nova Despesa")
        
        col1, col2 = st.columns([2, 1])
        descricao = col1.text_input("Descrição (opcional)", placeholder="Ex: Conta de internet")
        valor = col2.number_input("Valor R$", min_value=0.01, step=0.01)
        
        categoria = st.selectbox("Categoria *", categorias if categorias else ["Outros"])
        data_selecionada = st.date_input("Data da Despesa", value=datetime.now().date())
        
        if st.form_submit_button("💾 Lançar Despesa", type="primary", use_container_width=True):
            if validar_valor(valor, min_val=0.01):
                desc_final = descricao.strip() if descricao and descricao.strip() else categoria
                
                conn = conectar()
                try:
                    mes_ano = data_selecionada.strftime("%m/%Y")
                    data_desp = data_selecionada.strftime("%d/%m/%Y %H:%M")
                    
                    conn.execute(
                        """INSERT INTO despesas
                           (descricao, valor, categoria, data, mes_ano)
                           VALUES (?,?,?,?,?)""", 
                        (desc_final, float(valor), categoria, data_desp, mes_ano)
                    )
                    conn.commit()
                    st.success("✅ Despesa lançada com sucesso!")
                    
                    # Backup automático
                    fazer_backup_automatico("despesa")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao lançar despesa: {e}")
                finally:
                    conn.close()
            else:
                st.error("Valor inválido!")

    st.divider()

    # ======================= LISTA DE DESPESAS =======================
    st.subheader("Despesas Lançadas")
    conn = conectar()
    df_desp = pd.read_sql("SELECT * FROM despesas ORDER BY id DESC LIMIT 50", conn)
    conn.close()

    if df_desp.empty:
        st.info("Nenhuma despesa lançada.")
    else:
        for _, r in df_desp.iterrows():
            with st.container(border=True):
                col_a, col_b, col_c, col_d = st.columns([3.5, 1.5, 0.8, 0.8])
                
                col_a.write(f"**{r['descricao']}**")
                col_a.caption(f"{r['data']} | {r['categoria']}")
                col_b.metric("Valor", formatar_moeda(r['valor']))
                
                if col_c.button("✏️", key=f"edit_desp_{r['id']}"):
                    st.session_state.edit_despesa_id = r['id']
                    st.rerun()
                
                if col_d.button("🗑️", key=f"del_desp_{r['id']}"):
                    conn = conectar()
                    conn.execute("DELETE FROM despesas WHERE id=?", (r['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

    # ======================= EDIÇÃO DE DESPESA =======================
    if st.session_state.edit_despesa_id is not None:
        st.divider()
        st.subheader("✏️ Editando Despesa")

        conn = conectar()
        df_edit = pd.read_sql(
            "SELECT * FROM despesas WHERE id = ?", 
            conn, 
            params=(st.session_state.edit_despesa_id,)
        )
        
        if df_edit.empty:
            st.error("Registro não encontrado.")
            st.session_state.edit_despesa_id = None
            st.rerun()
        else:
            item = df_edit.iloc[0]
            
            with st.form("edit_despesa_form"):
                novo_desc = st.text_input("Descrição", value=item['descricao'])
                novo_valor = st.number_input("Valor R$", value=float(item['valor']), step=0.01)
                
                categorias = pd.read_sql("SELECT nome FROM categorias_desp ORDER BY nome", conn)['nome'].tolist()
                idx = categorias.index(item['categoria']) if item['categoria'] in categorias else 0
                novo_cat = st.selectbox("Categoria", categorias, index=idx)
                
                novo_data = st.text_input("Data (DD/MM/YYYY HH:MM)", value=item['data'])
                
                col_save, col_cancel = st.columns(2)
                if col_save.form_submit_button("💾 Salvar", type="primary"):
                    if validar_valor(novo_valor):
                        conn.execute(
                            """UPDATE despesas SET 
                               descricao=?, valor=?, categoria=?, data=? 
                               WHERE id=?""",
                            (novo_desc, novo_valor, novo_cat, novo_data, st.session_state.edit_despesa_id)
                        )
                        conn.commit()
                        st.success("✅ Despesa atualizada!")
                        st.session_state.edit_despesa_id = None
                        st.rerun()
                    else:
                        st.error("Valor inválido!")
                
                if col_cancel.form_submit_button("❌ Cancelar"):
                    st.session_state.edit_despesa_id = None
                    st.rerun()

        conn.close()

# ===================================================================
# 6. NOTAS E TAREFAS
# ===================================================================

elif menu == "📝 Notas":
    st.header("📌 Lembretes e Tarefas")

    filtro = st.selectbox("Mostrar:", ["Pendentes", "Concluídos", "Todos"], index=0)

    conn = conectar()
    
    # ======================= NOVA TAREFA =======================
    with st.form("nova_tarefa"):
        st.subheader("Nova Tarefa / Lembrete")
        col1, col2 = st.columns([3, 1])
        titulo = col1.text_input("Título", placeholder="Ex: Ligar para cliente João")
        prioridade = col2.selectbox("Prioridade", ["Alta", "Média", "Baixa"], index=1)
        
        conteudo = st.text_area("Descrição / Detalhes", placeholder="Telefone, observações...")
        data_prazo = st.date_input("Prazo (opcional)", value=None)
        
        if st.form_submit_button("💾 Salvar Tarefa", type="primary", use_container_width=True):
            if validar_texto(titulo, min_length=3, max_length=200):
                data_str = data_prazo.strftime("%d/%m/%Y") if data_prazo else "Sem prazo"
                
                conn.execute(
                    """INSERT INTO anotacoes 
                       (titulo, conteudo, data, prioridade, concluido) 
                       VALUES (?,?,?,?,0)""", 
                    (titulo.strip(), conteudo, data_str, prioridade)
                )
                conn.commit()
                st.success("✅ Tarefa salva!")
                st.rerun()
            else:
                st.error("Título inválido!")

    st.divider()

    # ======================= LISTA DE TAREFAS =======================
    if filtro == "Pendentes":
        query = "SELECT * FROM anotacoes WHERE concluido = 0 ORDER BY prioridade DESC, id DESC"
    elif filtro == "Concluídos":
        query = "SELECT * FROM anotacoes WHERE concluido = 1 ORDER BY id DESC"
    else:
        query = "SELECT * FROM anotacoes ORDER BY prioridade DESC, id DESC"
    
    df_notas = pd.read_sql(query, conn)

    if df_notas.empty:
        st.info(f"Nenhuma tarefa encontrada.")
    else:
        for _, r in df_notas.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([0.5, 5, 1.5])
                
                # Checkbox
                concluido = col1.checkbox("", value=bool(r['concluido']), key=f"check_{r['id']}")
                
                # Título com prioridade
                prio_color = {"Alta": "🔴", "Média": "🟡", "Baixa": "🟢"}
                titulo_display = f"{prio_color.get(r.get('prioridade', 'Média'), '⚪')} **{r['titulo']}**"
                if r['concluido']:
                    titulo_display = f"~~{titulo_display}~~"
                
                col2.write(titulo_display)
                col2.caption(f"{r['data']} | {r.get('conteudo', '')[:100]}...")
                
                # Botão excluir
                if col3.button("🗑️", key=f"del_n_{r['id']}"):
                    conn.execute("DELETE FROM anotacoes WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
                
                # Atualizar status
                if concluido != bool(r['concluido']):
                    conn.execute("UPDATE anotacoes SET concluido=? WHERE id=?", 
                                (1 if concluido else 0, r['id']))
                    conn.commit()
                    st.rerun()

    conn.close()

# ===================================================================
# 7. TAXAS/MÉTODOS DE PAGAMENTO
# ===================================================================

elif menu == "💳 Taxas":
    st.header("💳 Métodos de Pagamento")
    
    conn = conectar()
    txs_data = pd.read_sql("SELECT * FROM taxas ORDER BY metodo", conn)
    conn.close()

    with st.form("novo_metodo"):
        st.subheader("Novo Método de Pagamento")
        col1, col2 = st.columns([2, 1])
        nome_metodo = col1.text_input("Nome", placeholder="Ex: Pix, Crédito 3x...")
        taxa = col2.number_input("Taxa (%)", min_value=0.0, value=3.99, step=0.01, max_value=100.0)
        assume = st.checkbox("Vendedor assume a taxa", value=True)
        descricao = st.text_input("Descrição")
        
        if st.form_submit_button("💾 Cadastrar Método", type="primary"):
            if validar_texto(nome_metodo, min_length=3):
                conn = conectar()
                try:
                    conn.execute(
                        """INSERT INTO taxas (metodo, valor_taxa, assume_vendedor, descricao)
                           VALUES (?,?,?,?)""",
                        (nome_metodo.strip(), float(taxa), 1 if assume else 0, descricao)
                    )
                    conn.commit()
                    st.success(f"✅ Método '{nome_metodo}' cadastrado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("❌ Este método já existe!")
                finally:
                    conn.close()
            else:
                st.error("Nome inválido!")

    st.divider()
    st.subheader("📋 Métodos Cadastrados")
    
    if txs_data.empty:
        st.info("Nenhum método cadastrado.")
    else:
        for _, r in txs_data.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.write(f"**{r['metodo']}**")
                col1.caption(r['descricao'] if r['descricao'] else "Sem descrição")
                col2.metric("Taxa", f"{r['valor_taxa']:.2f}%")
                
                if col3.button("🗑️", key=f"del_taxa_{r['id']}"):
                    if r['metodo'] != 'Dinheiro':
                        conn = conectar()
                        conn.execute("DELETE FROM taxas WHERE id=?", (r['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Método deletado!")
                        st.rerun()
                    else:
                        st.error("❌ Não é possível deletar 'Dinheiro'!")

# ===================================================================
# 8. BACKUP
# ===================================================================

elif menu == "🔄 Backup":
    st.header("🔄 Gerenciador de Backup")

    st.success("✅ Backup Automático está ativado!")
    st.info(f"""
    **Informações:**
    - Backups são criados automaticamente ao finalizar vendas e despesas
    - Pasta de backups: `{BACKUP_FOLDER}`
    - São mantidos os últimos 15 backups automaticamente
    - Você pode também criar um backup manual abaixo
    """)

    # Criar backup manual
    if st.button("💾 Criar Backup Manual", type="primary", use_container_width=True):
        if fazer_backup_automatico("manual"):
            st.success("✅ Backup manual criado com sucesso!")
            st.rerun()

    st.divider()

    # Listar backups
    st.subheader("📁 Backups Existentes")
    if BACKUP_FOLDER.exists():
        backups = sorted(
            [f for f in BACKUP_FOLDER.glob('dados_loja_*.db')],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if backups:
            st.info(f"Total de {len(backups)} backup(s) encontrado(s)")
            
            for i, backup in enumerate(backups[:20], 1):
                col1, col2, col3 = st.columns([3, 2, 1])
                
                # Info do arquivo
                size_mb = backup.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                
                col1.write(f"**{i}. {backup.name}**")
                col1.caption(f"Criado em: {mtime.strftime('%d/%m/%Y %H:%M:%S')}")
                col2.metric("Tamanho", f"{size_mb:.2f} MB")
                
                # Botão download
                with open(backup, 'rb') as f:
                    col3.download_button(
                        label="📥",
                        data=f,
                        file_name=backup.name,
                        mime="application/x-sqlite3",
                        key=f"download_{i}"
                    )
        else:
            st.info("Nenhum backup encontrado ainda.")
    else:
        st.warning(f"Pasta de backup não encontrada: {BACKUP_FOLDER}")
# ===================================================================
# LIMPEZA TOTAL (Protegida por senha)
# ===================================================================
elif menu == "🗑️ Limpeza Total":
    limpar_todos_os_dados()
