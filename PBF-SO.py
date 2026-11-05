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
    Bom_template = st.file_uploader("Bom template (Excel)", type=["xlsx"])
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
            index=0 if 'PAZFLOR' not in available_plants else available_plants.index('PAZFLOR'),
        )

    # Perform calculations based on selection
    Total_removed_materials = df['Material n°'].nunique()
    pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
    pd_v1_unique_materials = pd_v1_df.drop_duplicates(subset=['Material n°'])

    Interested_plant = pd_v1_df[pd_v1_df['Plant'] == plant].copy()
    Interested_plant_unique = Interested_plant.drop_duplicates(subset=['Material n°']).copy()

    Total_stock_value = (pd_v1_df['Stock qty'] *  pd_v1_df['Unit price']).sum()
    Interested_plant_stock_value = (Interested_plant['Stock qty'] * Interested_plant['Unit price']).sum()

    # 3. HIGHLY VISUAL KPI METRICS SECTION
    st.markdown("### MAIN HIGHLIGHT")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.markdown(f'<div class="metric-card"><h6>Total Removed Materials</h6><h3>{Total_removed_materials:,}</h3></div>', unsafe_allow_html=True)
    with kpi2:
        st.markdown(f'<div class="metric-card"><h6>Total Stock Materials</h6><h3>{len(pd_v1_unique_materials):,}</h3></div>', unsafe_allow_html=True)
    with kpi3:
        st.markdown(f'<div class="metric-card"><h6>Total Stock Value (USD)</h6><h3>${Total_stock_value:,.2f}</h3></div>', unsafe_allow_html=True)
    with kpi4:
        st.markdown(f'<div class="metric-card"><h6>Potential {plant} Dead Stock Value (USD)</h6><h3>${Interested_plant_stock_value:,.2f}</h3></div>', unsafe_allow_html=True)

    # 4. BOM ANALYSIS MAPPING
    if Bom_template is not None:
        try:
            # Load BOM & BOM Assignment sheets
            bom_sheet_df = pd.read_excel(Bom_template, sheet_name="BOM")
            bom_assignment_df = pd.read_excel(Bom_template, sheet_name="BOM Assignment")
            
            # Clean column names just in case
            bom_sheet_df.columns = bom_sheet_df.columns.str.strip()
            bom_assignment_df.columns = bom_assignment_df.columns.str.strip()

            # Rename assembly reference key in BOM sheet and join with plant unique list
            # Typically BOM sheet associates Material reference -> Assembly
            # Let's map Interested_plant_unique['Material n°'] to Assembly
            mapping_df = Interested_plant_unique[['Material n°']].copy()
            mapping_df['Material n°'] = mapping_df['Material n°'].astype(str).str.strip()
            
            bom_sheet_df['Material reference'] = bom_sheet_df['Material reference'].astype(str).str.strip()
            bom_sheet_df['Assembly'] = bom_sheet_df['Assembly'].astype(str).str.strip()
            
            # Merge to get the associated Assembly reference
            merged_bom = pd.merge(
                mapping_df, 
                bom_sheet_df[['Material reference', 'Assembly']], 
                left_on='Material n°', 
                right_on='Material reference', 
                how='left'
            )
            
            # Rename 'Assembly' to 'Sub-assembly'
            merged_bom.rename(columns={'Assembly': 'Sub-assembly'}, inplace=True)
            
            # Use Assembly reference value to go to BOM Assignment sheet and get associated FL
            bom_assignment_df['Assembly'] = bom_assignment_df['Assembly'].astype(str).str.strip()
            bom_assignment_df['FL'] = bom_assignment_df['FL'].astype(str).str.strip()
            
            final_bom_df = pd.merge(
                merged_bom, 
                bom_assignment_df[['Assembly', 'FL']], 
                left_on='Sub-assembly', 
                right_on='Assembly', 
                how='left'
            )
            
            # Rename FL to Functional Locations
            final_bom_df.rename(columns={'FL': 'Functional Locations'}, inplace=True)
            
            # Structure final dataframe columns
            final_display_df = final_bom_df[['Material n°', 'Sub-assembly', 'Functional Locations']].drop_duplicates()
            
            st.markdown("### 📋 BOM Assignment Overview")
            st.dataframe(final_display_df, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error processing BOM template sheets: {e}")
    else:
        st.warning("Please upload the BOM template to view Assembly and Functional Locations mappings.")
