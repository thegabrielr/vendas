import streamlit as st
from datetime import date
from fpdf import FPDF

st.set_page_config(page_title="Devoluções", layout="wide")
st.title("📦 Sistema de Devoluções")

# ==================== ESTADO ====================
if "motivos" not in st.session_state:
    st.session_state.motivos = [
        "Recusado",
        "Danificado",
        "Endereço incompleto",
        "Fora de rota",
        "Desconhecido"
        "Outro"
    ]

if "itens" not in st.session_state:
    st.session_state.itens = []

# ==================== ABAS ====================
tab1, tab2 = st.tabs(["📋 Operação", "⚙️ Motivos"])

# ==================== ABA 1 ====================
with tab1:

    col1, col2 = st.columns([2, 1])
    with col1:
        data_relatorio = st.date_input("Data", value=date.today())
    with col2:
        transportadora = st.text_input("Entregador", value="Honorio/Gabriel - Parque mambucaba")

    st.subheader("Adicionar item")

    with st.form("form_add", clear_on_submit=True):

        c1, c2, c3 = st.columns([1, 2, 3])

        with c1:
            awb = st.text_input("AWB")

        with c2:
            cliente = st.text_input("Cliente")

        with c3:
            endereco = st.text_input("Endereço")

        motivo = st.selectbox("Motivo (opcional)", [""] + st.session_state.motivos)

        submit = st.form_submit_button("➕ Adicionar")

        if submit and awb.strip():
            st.session_state.itens.append({
                "AWB": awb.strip(),
                "Nome do Cliente": cliente.strip(),
                "Endereço": endereco.strip(),
                "Motivo": motivo.strip()
            })
            st.rerun()

    st.subheader(f"Itens ({len(st.session_state.itens)})")

    if not st.session_state.itens:
        st.info("Nenhum item")
    else:
        for i, item in enumerate(st.session_state.itens):
            with st.expander(f"{item['AWB']} - {item.get('Nome do Cliente','')}"):

                item["Nome do Cliente"] = st.text_input(
                    "Cliente", value=item.get("Nome do Cliente",""), key=f"cli_{i}"
                )

                item["Endereço"] = st.text_area(
                    "Endereço", value=item.get("Endereço",""), key=f"end_{i}"
                )

                item["Motivo"] = st.selectbox(
                    "Motivo",
                    [""] + st.session_state.motivos,
                    index=(st.session_state.motivos.index(item["Motivo"]) + 1)
                    if item["Motivo"] in st.session_state.motivos else 0,
                    key=f"mot_{i}"
                )

                if st.button("Remover", key=f"del_{i}"):
                    st.session_state.itens.pop(i)
                    st.rerun()

    if st.button("Limpar lista"):
        st.session_state.itens = []
        st.rerun()

    # ==================== PDF ====================
    if st.session_state.itens:

        if st.button("Gerar PDF"):

            pdf = FPDF("P", "mm", "A4")
            pdf.add_page()

            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 8, "RELATÓRIO DE DEVOLUÇÕES", ln=True, align="C")

            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, f"{transportadora} | {data_relatorio.strftime('%d/%m/%Y')}", ln=True, align="C")
            pdf.ln(5)

            page_width = pdf.w - 2 * pdf.l_margin

            col_awb = page_width * 0.18
            col_cliente = page_width * 0.27
            col_endereco = page_width * 0.35
            col_motivo = page_width * 0.20

            pdf.set_font("Arial", "B", 9)
            pdf.set_fill_color(220, 220, 220)

            pdf.cell(col_awb, 7, "AWB", 1, 0, "C", True)
            pdf.cell(col_cliente, 7, "CLIENTE", 1, 0, "C", True)
            pdf.cell(col_endereco, 7, "ENDEREÇO", 1, 0, "C", True)
            pdf.cell(col_motivo, 7, "MOTIVO", 1, 1, "C", True)

            pdf.set_font("Arial", "", 9)
            line_h = 5

            for row in st.session_state.itens:
                awb = str(row.get("AWB",""))
                cliente = str(row.get("Nome do Cliente",""))
                endereco = str(row.get("Endereço",""))
                motivo = str(row.get("Motivo",""))

                max_lines = max(
                    len(pdf.multi_cell(col_awb, line_h, awb, split_only=True)),
                    len(pdf.multi_cell(col_cliente, line_h, cliente, split_only=True)),
                    len(pdf.multi_cell(col_endereco, line_h, endereco, split_only=True)),
                    len(pdf.multi_cell(col_motivo, line_h, motivo, split_only=True)),
                )

                row_h = line_h * max_lines

                x = pdf.get_x()
                y = pdf.get_y()

                pdf.multi_cell(col_awb, line_h, awb, border=1)
                pdf.set_xy(x + col_awb, y)

                pdf.multi_cell(col_cliente, line_h, cliente, border=1)
                pdf.set_xy(x + col_awb + col_cliente, y)

                pdf.multi_cell(col_endereco, line_h, endereco, border=1)
                pdf.set_xy(x + col_awb + col_cliente + col_endereco, y)

                pdf.multi_cell(col_motivo, line_h, motivo, border=1)

                pdf.ln(row_h)

            pdf_bytes = pdf.output(dest="S").encode("latin1")

            st.download_button(
                "Baixar PDF",
                pdf_bytes,
                file_name="relatorio.pdf",
                mime="application/pdf"
            )

# ==================== ABA 2 ====================
with tab2:

    st.subheader("Gerenciar Motivos")

    novo = st.text_input("Novo motivo")

    if st.button("Adicionar motivo"):
        if novo.strip() and novo not in st.session_state.motivos:
            st.session_state.motivos.append(novo.strip())
            st.rerun()

    for i, m in enumerate(st.session_state.motivos):
        col1, col2 = st.columns([5,1])
        col1.write(m)
        if col2.button("X", key=f"del_m_{i}"):
            st.session_state.motivos.pop(i)
            st.rerun()
