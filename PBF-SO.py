import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import io

st.set_page_config(
    page_title="Material Analysis Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Material Overview & Stock Analysis")
st.markdown("Retrieve structured insights, classify inventory status, and assess material for scrapping or to be transferred.")

# 1. FILE UPLOADERS IN SIDEBAR
with st.sidebar:
    st.header("📂 Data Source Configuration")
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
        'Plant code', 'Plant', 'storage bin', 'FASD', 'Blocking status',
        'MRP Type', 'Stock qty', 'Blocked Stock Qty', 'Safety', 'Min',
        'Max', 'Unit price'
    ]
    existing_columns = [col for col in requested_columns if col in removed_materials_df.columns]
    df = removed_materials_df[existing_columns].copy()

    # DYNAMIC PLANT SELECTOR IN SIDEBAR
    with st.sidebar:
        available_plants = sorted(df['Plant'].dropna().unique())
        plant = st.selectbox(
            "Select Plant of Interest:",
            available_plants,
            index=0 if 'PAZFLOR' not in available_plants else available_plants.index('PAZFLOR')
        )

    # Perform calculations based on selection
    Total_removed_materials = df['Material n°'].nunique()
    pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
    pd_v1_unique_materials = pd_v1_df.drop_duplicates(subset=['Material n°'])

    stock_greater_zero = pd_v1_df[pd_v1_df['Stock qty'] > 0]
    stock_greater_zero_unique = pd_v1_df[pd_v1_df['Stock qty'] > 0].drop_duplicates(subset=['Material n°']).copy()

    Interested_plant = stock_greater_zero[stock_greater_zero['Plant'] == plant].copy()
    Interested_plant_unique = Interested_plant.drop_duplicates(subset=['Material n°']).copy()

    Total_stock_value = (stock_greater_zero['Stock qty'] * stock_greater_zero['Unit price']).sum()
    Interested_plant_stock_value = (Interested_plant['Stock qty'] * Interested_plant['Unit price']).sum()

    # Categorization logic
    other_active_materials = pd_v1_df [
        (pd_v1_df['Plant'] != plant) &
        (pd_v1_df['FASD'].str.upper() != 'DEAD')
    ]['Material n°'].unique()

    def categorize_material(row):
        mat_no = row['Material n°']
        if mat_no in other_active_materials:
            return 'TO BE TRANSFERRED'
        else:
            return 'TO BE SCRAPPED'

    if not Interested_plant.empty:
        Interested_plant['Category'] = Interested_plant.apply(categorize_material, axis=1)
    else:
        Interested_plant['Category'] = pd.Series(dtype='object')

    # 3. HIGHLY VISUAL KPI METRICS SECTION
    st.markdown("### MAIN HIGHLIGHT")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.markdown(f'<div class="metric-card"><h6>Total Removed Materials</h6><h3>{Total_removed_materials:,}</h3></div>', unsafe_allow_html=True)
    with kpi2:
        st.markdown(f'<div class="metric-card"><h6>TOTAL STOCK MATERIALS</h6><h3>{len(pd_v1_unique_materials):,}</h3></div>', unsafe_allow_html=True)
    with kpi3:
        st.markdown(f'<div class="metric-card"><h6>TOTAL STOCK VALUE (USD)</h6><h3>${Total_stock_value:,.2f}</h3></div>', unsafe_allow_html=True)
    with kpi4:
        st.markdown(f'<div class="metric-card"><h6>POTENTIAL {plant} DEAD STOCK VALUE(USD)</h6><h3>${Interested_plant_stock_value:,.2f}</h3></div>', unsafe_allow_html=True)

    # Separator after KPIs
    st.markdown("<div class='custom-divider'></div>", unsafe_allow_html=True)

    # 4. INTERACTIVE CHARTS (HEATMAP & PIE)
    st.markdown("### Distribution and Visual Categorization Insights")

    if not Interested_plant.empty:
        col_left, col_right = st.columns(2)

        with col_left:
            cross_tab = pd.crosstab(Interested_plant['FASD'], Interested_plant['Category'])
            # IMPROVED COLOR: 'Ice' or 'deep' offers exceptionally clear, professional stakeholder visualization
            fig_heat = px.imshow(
                cross_tab,
                text_auto=True,
                aspect="auto",
                color_continuous_scale="ice",
                labels=dict(x="Category", y="FASD Status", color="Material Quantity"),
                title="Distribution per FASD Status"
            )
            fig_heat.update_layout(
                margin=dict(l=40, r=40, t=60, b=40),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", size=12)
            )
            st.plotly_chart(fig_heat, use_container_width=True)

        with col_right:
            category_counts = Interested_plant['Category'].value_counts().reset_index()
            category_counts.columns = ['Category', 'Count']

            # IMPROVED COLORS: Muted Slate Gray for Scrapped, Executive Cyan/Blue for Transferred
            color_map = {"TO BE SCRAPPED": "#334155", "TO BE TRANSFERRED": "#0284c7"}
            fig_pie = px.pie(
                category_counts,
                values='Count',
                names='Category',
                hole=0.45,
                color='Category',
                color_discrete_map=color_map,
                title="General Classification Distribution"
        
            )
            fig_pie.update_traces(textinfo='percent+label', pull=[0.02] * len(category_counts))
            fig_pie.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(l=40, r=40, t=60, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", size=12)
            
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.warning(f"No stock records found for plant: {plant}")

    # 6. EXPORT ACTION IN SIDEBAR
    with st.sidebar:
        st.markdown("--- ")
        st.header("📦 Download the Results")
        if not Interested_plant.empty:
            buffer = io.BytesIO()
            export_df = Interested_plant.drop(columns=['Total Value'], errors='ignore')
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name=f'{plant}_Materials')
            buffer.seek(0)

            st.download_button(
                label=f"📥 {plant} Materials for Scrap (Excel)",
                data=buffer,
                file_name=f"{plant}_potential_materials_for_scrap.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No data available to export.")
else:
    st.info("Please upload both Excel files in the sidebar to activate the dashboard.")
