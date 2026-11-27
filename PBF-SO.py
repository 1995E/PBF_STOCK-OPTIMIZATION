import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import io
import re

st.set_page_config(
    page_title="PBF STOCK ANALYSE TOOL",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject CSS for column separators and general chart fitting
st.markdown("""
<style>
/* Add vertical dividers between the main layout columns */
div[data-testid="column"]:nth-of-type(1) {
    border-right: 1px solid #E5E7EB;
    padding-right: 20px;
}
div[data-testid="column"]:nth-of-type(2) {
    border-right: 1px solid #E5E7EB;
    padding-right: 20px;
    padding-left: 10px;
}
div[data-testid="column"]:nth-of-type(3) {
    padding-left: 10px;
}
</style>
""", unsafe_allow_html=True)

plant = st.segmented_control(
    "Select plant",
    ["All", 'GIRASSOL', 'DALIA', 'PAZFLOR', 'CLOV']
)

# 1. FILE UPLOADERS & SETTINGS IN SIDEBAR
with st.sidebar:
    st.header(
        "Data Source Configuration"
    )
    uploaded_materials = st.file_uploader("Material Overview per Plant (Excel)", type=["xlsx"])
    uploaded_prices = st.file_uploader("Material Overview per Price (Excel)", type=["xlsx"])
    st.markdown("---")


if uploaded_materials is not None and uploaded_prices is not None:
    # Read DataFrames
    removed_materials_df = pd.read_excel(uploaded_materials)
    unit_price_df = pd.read_excel(uploaded_prices)

    # 2. PROCESSING INFORMATION
    filtered_unit_prices = unit_price_df[unit_price_df['Valuation Type'] == 'BLOC-17']
    material_prices = filtered_unit_prices.groupby('Material n°')['Item Price'].mean()
    removed_materials_df['Unit price'] = removed_materials_df['Material n°'].map(material_prices)

    requested_columns = [
        'Material n°', 'Material description', 'Material discipline',
        'Plant code', 'Plant', 'Storage bin', 'FASD', 'Blocking status',
        'Gest', 'MRP Type', 'Stock qty', 'Blocked Stock Qty',
        'Safety', 'Min', 'Max', 'Unit price'
    ]
    existing_columns = [col for col in requested_columns if col in removed_materials_df.columns]
    df = removed_materials_df[existing_columns].copy()

    # Filter out "GENERAL DIVISION" from df
    if 'Plant' in df.columns:
        df = df[df['Plant'] != 'GENERAL DIVISION'].copy()

    # Add Gest_2L column directly to df
    if 'Gest' in df.columns:
        df['Gest_2L'] = df['Gest'].astype(str).str[:2]
    else:
        df['Gest_2L'] = ""

    # Filter data based on selected plant before calculations to make the flowchart dynamic
    if plant and plant != "All" and 'Plant' in df.columns:
        chart_df = df[df['Plant'] == plant].copy()
    else:
        chart_df = df.copy()

    # Perform calculations using filtered data for the flowchart
    Total_removed_materials = chart_df['Material n°'].nunique()
    pd_v1_df = chart_df[chart_df['MRP Type'].isin(['PD', 'V1'])].copy()

    # Calculate Stock Value for materials in the filtered dataset
    pd_v1_df['Stock Value'] = pd_v1_df['Stock qty'].fillna(0) * pd_v1_df['Unit price'].fillna(0)

    pd_v1_unique_materials = pd_v1_df.drop_duplicates(subset=['Material n°']).copy()

    # Number of materials that are not PD/V1 (ND)
    cnt_pd_v1 = pd_v1_unique_materials['Material n°'].nunique()
    cnt_nd = max(0, Total_removed_materials - cnt_pd_v1)

    # Count simplified Gest status (first two characters) from pd_v1_unique_materials
    gest_counts_series = pd_v1_unique_materials['Gest_2L'].value_counts() if 'Gest_2L' in pd_v1_unique_materials.columns else pd.Series(dtype=int)
    sum_se = int(gest_counts_series.get('SE', 0))
    sum_su = int(gest_counts_series.get('SU', 0))
    sum_mm = int(gest_counts_series.get('MM', 0))

    # Calculate the Total Stock Value for SE, SU, and MM groups in the current selection
    val_se = pd_v1_df[pd_v1_df['Gest_2L'] == 'SE']['Stock Value'].sum()
    val_su = pd_v1_df[pd_v1_df['Gest_2L'] == 'SU']['Stock Value'].sum()
    val_mm = pd_v1_df[pd_v1_df['Gest_2L'] == 'MM']['Stock Value'].sum()

    # Prepare stock overview data
    full_pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
    stock_greater_zero = full_pd_v1_df[full_pd_v1_df['Stock qty'] > 0].copy()
    stock_greater_zero['Stock Value'] = stock_greater_zero['Stock qty'] * stock_greater_zero['Unit price'].fillna(0)

    # Remap "Never been consumed" to "Dead" in FASD column
    if 'FASD' in stock_greater_zero.columns:
        stock_greater_zero['FASD'] = stock_greater_zero['FASD'].replace('Never been consumed', 'Dead')

    # Tab configuration
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Stock overview", "lorepsum 1", "lorepsum 2", "lorepsum 3", "lorepsum 4"])

    with tab1:
        # Ensure uniform control bar on top to align everything horizontally
        col_toggle1, col_toggle2, col_toggle3 = st.columns([1, 1, 1])
        with col_toggle1:
            chart_mode_plant = st.toggle("Show Donut Chart (Plant)", value=False, key="toggle_plant")
        with col_toggle2:
            chart_mode_fasd = st.toggle("Show Donut Chart (FASD)", value=False, key="toggle_fasd")
        with col_toggle3:
            show_discipline_chart = st.toggle("Show FASD Stock Value by Discipline", value=False, key="toggle_col3_view")

        st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;' />", unsafe_allow_html=True)

        # Use st.columns with gap for visual separation if needed, or manual vertical lines
        col1, col2, col3 = st.columns([1, 1, 1], gap="small")

        with col1:
            # Group by plant
            plant_stock_df = stock_greater_zero.groupby('Plant', as_index=False)['Stock Value'].sum()
            # Sort descending from highest to lowest stock value
            plant_stock_df = plant_stock_df.sort_values(by='Stock Value', ascending=False)
            total_plant_val = plant_stock_df['Stock Value'].sum()
            sorted_plants_list = plant_stock_df['Plant'].tolist()

            if chart_mode_plant:
                fig_plant = px.pie(
                    plant_stock_df,
                    values='Stock Value',
                    names='Plant',
                    hole=0.55,
                    color='Plant',
                    color_discrete_map={
                        'GIRASSOL': '#dbb127',
                        'DALIA': '#32a889',
                        'PAZFLOR': '#2769db',
                        'CLOV': '#a527db'
                    }
                )
                fig_plant.update_traces(
                    textposition='outside',
                    textinfo='percent',
                )
                fig_plant.update_layout(
                    title=dict(
                        text='<b>Stock Value distribution by Plant</b>',
                        font=dict(size=14, color='#1F2937'), 
                        automargin=True,
                        y=0.95
                    ),
                    annotations=[dict(
                        text=f"<b>Total</b><br><b>${total_plant_val/1e6:.1f}<b>M",
                        x=0.5, y=0.5, font_size=20, showarrow=False, font_color='#111827'
                    )],
                    showlegend=True,
                    legend=dict(orientation="h", y=-0.2, xanchor="center", x=0.5),
                    margin=dict(t=60, b=50, l=10, r=10),
                    height=450
                )
            else:
                fig_plant = px.bar(
                    plant_stock_df,
                    x='Plant',
                    y='Stock Value',
                    text='Stock Value',
                    orientation='v',
                )
                fig_plant.update_traces(
                    texttemplate='<b>$%{text:,.2s}<b>',
                    textposition='auto',
                    textfont=dict(
                        size=15,
                        color='#FFFFFF'
                    )
                )
                fig_plant.update_layout(
                    title=dict(
                        text='<b>Stock Value by Plant</b>',
                        font=dict(size=14, color='#1F2937'),
                        automargin=True,
                        y=0.95
                    ),
                    #xaxis_title="Plant",
                    #yaxis_title="Stock Value",
                    coloraxis_showscale=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=False,
                        gridcolor='rgba(235,235,235,1)',
                        tickformat="$.2s",
                        automargin=True,
                        categoryorder='array',
                        categoryarray=sorted_plants_list
                    ),
                    yaxis=dict(automargin=True),
                    margin=dict(t=60, b=50, l=10, r=10),
                    height=450
                )
            st.plotly_chart(fig_plant, use_container_width=True)

        with col2:
            # Apply plant filter if one is selected and not 'All'
            if plant and plant != 'All':
                filtered_stock_fasd = stock_greater_zero[stock_greater_zero['Plant'] == plant].copy()
            else:
                filtered_stock_fasd = stock_greater_zero.copy()

            # Drop null and empty FASD status values
            filtered_stock_fasd = filtered_stock_fasd.dropna(subset=['FASD'])
            filtered_stock_fasd = filtered_stock_fasd[filtered_stock_fasd['FASD'].astype(str).str.strip() != '']

            # Group by FASD status
            fasd_stock_df = filtered_stock_fasd.groupby('FASD', as_index=False)['Stock Value'].sum()

            # Define desired order: Fast, Active, Slow, Dead (from top to bottom)
            fasd_order = ['Dead', 'Slow', 'Active', 'Fast']
            fasd_stock_df['FASD'] = pd.Categorical(fasd_stock_df['FASD'], categories=fasd_order, ordered=True)
            fasd_stock_df = fasd_stock_df.sort_values('FASD', ascending=True)
            total_fasd_val = fasd_stock_df['Stock Value'].sum()

            if chart_mode_fasd:
                fig_fasd = px.pie(
                    fasd_stock_df,
                    values='Stock Value',
                    names='FASD',
                    hole=0.55,
                    color='FASD',
                    color_discrete_map={
                        'Fast': '#40a13f',
                        'Active': '#56a6f0',
                        'Slow': '#f0c818',
                        'Dead': '#f54f4c'
                   }
                )
                fig_fasd.update_traces(
                    textposition='inside',
                    textinfo='percent+label',
                )
                fig_fasd.update_layout(
                    title=dict(
                        text=f'<b>FASD Status Distribution ({plant if plant else "All"})</b>',
                        font=dict(size=14, color='#1F2937'),
                        automargin=True,
                        y=0.95
                    ),
                    annotations=[dict(
                        text=f"<b>Total</b><br><b>${total_fasd_val/1e6:.1f}M<b>",
                        x=0.5, y=0.5, font_size=20, showarrow=False, font_color='#111827'
                    )],
                    showlegend=True,
                    legend=dict(orientation="h", y=-0.2, xanchor="center", x=0.5),
                    margin=dict(t=60, b=50, l=10, r=10),
                    height=450
                )
            else:
                fig_fasd = px.bar(
                    fasd_stock_df,
                    x='Stock Value',
                    y='FASD',
                    text='Stock Value',
                    orientation='h',
                    color='FASD',
                    color_discrete_map={
                        'Fast': '#40a13f',
                        'Active': '#56a6f0',
                        'Slow': '#f0c818',
                        'Dead': '#f54f4c'
                   }
                )
                fig_fasd.update_traces(
                    texttemplate='$%{text:,.2s}',
                    textposition='auto',
                )
                fig_fasd.update_layout(
                    title=dict(
                        text=f'<b>FASD Status ({plant if plant else "All"})</b>',
                        font=dict(size=14, color='#1F2937'),
                        automargin=True,
                        y=0.95
                    ),
                    xaxis_title="Stock Value",
                    yaxis_title="FASD Status",
                    coloraxis_showscale=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(235,235,235,1)',
                        tickformat="$.2s",
                        automargin=True
                    ),
                    yaxis=dict(categoryorder='array', categoryarray=fasd_order, automargin=True),
                    margin=dict(t=60, b=50, l=10, r=10),
                    height=450
                )
            st.plotly_chart(fig_fasd, use_container_width=True)

        with col3:
            if show_discipline_chart:
                # Filter based on the selected plant if not 'All'
                if plant and plant != 'All':
                    col3_df = stock_greater_zero[stock_greater_zero['Plant'] == plant].copy()
                else:
                    col3_df = stock_greater_zero.copy()

                # Drop null and empty categories
                col3_df = col3_df.dropna(subset=['FASD', 'Material discipline'])
                col3_df = col3_df[col3_df['FASD'].astype(str).str.strip() != '']

                # Enforce desired order: Fast, Active, Slow, Dead
                fasd_v_order = ['Fast', 'Active', 'Slow', 'Dead']
                col3_df['FASD'] = pd.Categorical(col3_df['FASD'], categories=fasd_v_order, ordered=True)

                # Group by discipline to identify the descending sort order from highest total stock value to lowest
                discipline_totals = col3_df.groupby('Material discipline')['Stock Value'].sum().reset_index()
                discipline_totals = discipline_totals.sort_values(by='Stock Value', ascending=False)
                ordered_disciplines = discipline_totals['Material discipline'].tolist()

                # Group data to ensure individual stack labels display properly
                col3_grouped = col3_df.groupby(['Material discipline', 'FASD'], as_index=False)['Stock Value'].sum()
                col3_grouped = col3_grouped[col3_grouped['Stock Value'] > 0]

                # Create vertical stacked column chart with custom aesthetics and stack value labels
                fig_disp = px.bar(
                    col3_grouped,
                    x='Material discipline',
                    y='Stock Value',
                    color='FASD',
                    text='Stock Value',
                    category_orders={
                        "FASD": fasd_v_order,
                        "Material discipline": ordered_disciplines
                    },
                    title=f'FASD Stock Value per Discipline ({plant if plant else "All"})',
                    barmode='stack',
                    color_discrete_sequence=['#475569'],
                )
                fig_disp.update_traces(
                    texttemplate='$%{text:,.2s}',
                    textposition='inside',
                    insidetextanchor='middle'
                )
                fig_disp.update_layout(
                    xaxis_title="Material Discipline",
                    yaxis_title="Stock Value",
                    legend_title="FASD Status",
                    xaxis={'showgrid': False, 'tickangle': -45, 'automargin': True},
                    yaxis={'gridcolor': 'rgba(235,235,235,1)', 'automargin': True},
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                    height=450,
                    margin=dict(t=60, b=50, l=10, r=10),
                    title=dict(font=dict(size=14, color='#1F2937'), automargin=True, y=0.95)
                )
                st.plotly_chart(fig_disp, use_container_width=True)
            else:
                # Render the original Graphviz flowchart with top padding adjusted to match adjacent titles baseline
                st.markdown(
                    "<div style='padding-top: 13px; padding-bottom: 22px;'><span style='font-family: sans-serif; font-size: 15px; font-weight: bold; color: #1F2937;'>Material Breakdown Flow</span></div>",
                    unsafe_allow_html=True
                )

                st.markdown(
                    """
                    <style>
                    .centered-graphviz {
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        width: 100%;
                        margin: 0 auto;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

                dot_code = f"""
                digraph G {{
                    graph [rankdir=LR, size="8,5", bgcolor="transparent", splines=ortho, nodesep=0.4, ranksep=0.6];
                    node [
                        shape=box,
                        style="filled,rounded",
                        color="#D1D5DB",
                        fillcolor="#F9FAFB",
                        fontname="Segoe UI, Helvetica, Arial, sans-serif",
                        fontsize=11,
                        fontcolor="#1F2937",
                        penwidth=1.5,
                        margin="0.2,0.15"
                    ];
                    edge [
                        color="#9CA3AF",
                        penwidth=1.5,
                        arrowsize=0.8,
                        fontname="Segoe UI, Helvetica, Arial, sans-serif",
                        fontsize=9
                    ];

                    Total [
                        label="Materials in {plant if plant else 'All'} plant\n{Total_removed_materials}",
                        fillcolor="#EFF6FF",
                        color="#3B82F6",
                        fontcolor="#1E40AF",
                        fontname="Segoe UI Semibold, Segoe UI, Helvetica, Arial, sans-serif"
                    ];
                    PD_V1 [
                        label="Stock materials\n{cnt_pd_v1}",
                        fillcolor="#ECFDF5",
                        color="#10B981",
                        fontcolor="#065F46",
                        fontname="Segoe UI Semibold, Segoe UI, Helvetica, Arial, sans-serif"
                    ];
                    ND [
                        label="Non-stocked materials\n{cnt_nd}",
                        fillcolor="#FFFBEB",
                        color="#F59E0B",
                        fontcolor="#92400E",
                        fontname="Segoe UI Semibold, Segoe UI, Helvetica, Arial, sans-serif"
                    ];

                    SE [
                        label="SE: {sum_se}\nStock value: ${val_se:,.2f}",
                        fillcolor="#FDF2F8",
                        color="#EC4899",
                        fontcolor="#9D174D",
                        fontname="Segoe UI Semibold, Segoe UI, Helvetica, Arial, sans-serif"
                    ];
                    SU [
                        label="SU: {sum_su}\nStock value: ${val_su:,.2f}",
                        fillcolor="#F5F3FF",
                        color="#8B5CF6",
                        fontcolor="#5B21B6",
                        fontname="Segoe UI Semibold, Segoe UI, Helvetica, Arial, sans-serif"
                    ];
                    MM [
                        label="MM: {sum_mm}\nStock value: ${val_mm:,.2f}",
                        fillcolor="#EEF2FF",
                        color="#6366F1",
                        fontcolor="#3730A3",
                        fontname="Segoe UI Semibold, Segoe UI, Helvetica, Arial, sans-serif"
                    ];

                    Total -> PD_V1 [color="#3B82F6"];
                    Total -> ND [color="#F59E0B"];
                    PD_V1 -> SE [color="#10B981"];
                    PD_V1 -> SU [color="#10B981"];
                    PD_V1 -> MM [color="#10B981"];
                }}
                """

                st.markdown('<div class="centered-graphviz">', unsafe_allow_html=True)
                st.graphviz_chart(dot_code, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
