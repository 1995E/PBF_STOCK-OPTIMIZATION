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

plant = st.segmented_control(
    "Select plant",
    ["All", 'GIRASSOL', 'DALIA', 'PAZFLOR', 'CLOV']
)

# 1. FILE UPLOADERS IN SIDEBAR
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

    # Prepare stock overview data (always based on entire dataset and conditionally filtered in layout)
    full_pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
    stock_greater_zero = full_pd_v1_df[full_pd_v1_df['Stock qty'] > 0].copy()
    stock_greater_zero['Stock Value'] = stock_greater_zero['Stock qty'] * stock_greater_zero['Unit price'].fillna(0)

    # Remap "Never been consumed" to "Dead" in FASD column
    if 'FASD' in stock_greater_zero.columns:
        stock_greater_zero['FASD'] = stock_greater_zero['FASD'].replace('Never been consumed', 'Dead')

    # Tab configuration
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Stock overview", "lorepsum 1", "lorepsum 2", "lorepsum 3", "lorepsum 4"])

    with tab1:
        col1, col2, col3 = st.columns([0.8,0.8,0.9])

        with col1:
            # Toggle option on top
            chart_mode_plant = st.toggle("Show Donut Chart (Plant)", value=False, key="toggle_plant")

            # Group by plant
            plant_stock_df = stock_greater_zero.groupby('Plant', as_index=False)['Stock Value'].sum()

            if chart_mode_plant:
                fig_plant = px.pie(
                    plant_stock_df,
                    values='Stock Value',
                    names='Plant',
                    hole=0.4,
                    title='Stock Value by Plant'
                )
            else:
                fig_plant = px.bar(
                    plant_stock_df,
                    x='Stock Value',
                    y='Plant',
                    text='Stock Value',
                    orientation='h',
                    title='Stock Value by Plant'
                )
                fig_plant.update_traces(
                    texttemplate='$%{text:,.2s}',
                    textposition='inside'
                )
                fig_plant.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_plant, use_container_width=True)

        with col2:
            # Toggle option on top
            chart_mode_fasd = st.toggle("Show Donut Chart (FASD)", value=False, key="toggle_fasd")

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

            if chart_mode_fasd:
                fig_fasd = px.pie(
                    fasd_stock_df,
                    values='Stock Value',
                    names='FASD',
                    hole=0.4,
                    title=f'Stock Value by FASD Status ({plant if plant else "All"})'
                )
            else:
                fig_fasd = px.bar(
                    fasd_stock_df,
                    x='Stock Value',
                    y='FASD',
                    text='Stock Value',
                    orientation='h',
                    title=f'Stock Value by FASD Status ({plant if plant else "All"})'
                )
                fig_fasd.update_traces(
                    texttemplate='$%{text:,.2s}',
                    textposition='inside'
                )
                fig_fasd.update_layout(yaxis={'categoryorder': 'array', 'categoryarray': fasd_order})
            st.plotly_chart(fig_fasd, use_container_width=True)

        with col3:
            # Toggle to switch between flowchart and FASD bar chart
            show_discipline_chart = st.toggle("Show FASD Stock Value by Discipline", value=False, key="toggle_col3_view")

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

                # CSS overrides are omitted here to ensure the standard Streamlit value label is completely visible

                # Split Column 3 into sub-columns: left for slider, right for chart
                sub_col_left, sub_col_right = st.columns([0.11, 0.89])

                with sub_col_left:
                    # Convert the maximum value to millions to present a clean scale on the slider
                    max_possible_y_raw = float(discipline_totals['Stock Value'].max()) if not discipline_totals.empty else 1000000.0
                    max_possible_y_m = max_possible_y_raw / 1_000_000.0
                    
                    # Display current value explicitly formatted in Millions (e.g., 2.5M)
                    y_limit_m = st.slider(
                        "Zoom",
                        min_value=0.0,
                        max_value=max_possible_y_m,
                        value=max_possible_y_m,
                        step=max(0.1, max_possible_y_m / 20.0),
                        format="%.1fM",
                        key="y_axis_slider_m"
                    )
                    # Convert selected million value back to raw units for plot range control
                    y_limit = y_limit_m * 1_000_000.0

                with sub_col_right:
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
                        color_discrete_sequence=px.colors.qualitative.Antique
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
                        xaxis={'showgrid': False},
                        yaxis={'gridcolor': 'rgba(235,235,235,1)', 'range': [0, y_limit]},
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_disp, use_container_width=True)
            else:
                # Render the original Graphviz flowchart
                st.markdown(
                    "<div style='padding-top: 30px; padding-bottom: 1px;'><span style='font-family: sans-serif; font-size: 17px; font-weight: bold; color: rgb(49, 51, 63);'>Material Breakdown Flow</span></div>",
                    unsafe_allow_html=True
                )

                # Use a wrapper with CSS flex centering to horizontally align the Graphviz chart
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

                # Embed the graph within a centered container block
                st.markdown('<div class="centered-graphviz">', unsafe_allow_html=True)
                st.graphviz_chart(dot_code, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
