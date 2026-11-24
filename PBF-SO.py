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

critical_only = st.toggle("Show Critical Materials Only")

if critical_only:
    st.write("Displaying only critical materials")

selected = st.pills(
    "Material Type",
    ["Stock", "Non-Stock", "Critical"]
)

selected = st.pills(
    "GEST",
    ["SE", "SU", "MM"],
    selection_mode="multi"
)

stock_status = st.segmented_control(
    "Stock Status",
    ["All", "Stock", "Non-Stock"]
)

stock_status = st.radio(
    "Stock Status",
    ["All", "Stock", "Non-Stock"]
)

st.write("Selected:", stock_status)

# 1. FILE UPLOADERS IN SIDEBAR
with st.sidebar:
    st.header("Data Source Configuration")
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

    # Perform calculations
    Total_removed_materials = df['Material n°'].nunique()
    pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
    pd_v1_unique_materials = pd_v1_df.drop_duplicates(subset=['Material n°']).copy()

    # Number of materials that are not PD/V1 (ND)
    cnt_pd_v1 = pd_v1_unique_materials['Material n°'].nunique()
    cnt_nd = max(0, Total_removed_materials - cnt_pd_v1)

    # Count simplified Gest status (first two characters) from pd_v1_unique_materials
    gest_counts = pd.DataFrame(columns=['Gest Status', 'Count'])
    if 'Gest' in pd_v1_unique_materials.columns:
        pd_v1_unique_materials['Gest_2L'] = pd_v1_unique_materials['Gest'].astype(str).str[:2]
        gest_counts = pd_v1_unique_materials['Gest_2L'].value_counts().reset_index()
        gest_counts.columns = ['Gest Status', 'Count']

    stock_greater_zero = pd_v1_df[pd_v1_df['Stock qty'] > 0].copy()

    Interested_plant = stock_greater_zero[stock_greater_zero['Plant'] == plant].copy()
    Interested_plant_unique = Interested_plant.drop_duplicates(subset=['Material n°']).copy()

    Others_plant = pd_v1_df[pd_v1_df['Plant'] != plant].copy()
    Others_plant_unique = Others_plant.drop_duplicates(subset=['Material n°']).copy()

    Total_stock_value = (stock_greater_zero['Stock qty'] *  stock_greater_zero['Unit price']).sum()
    Interested_plant_stock_value = (Interested_plant['Stock qty'] * Interested_plant['Unit price']).sum()
    Others_plant_stock_value = Total_stock_value - Interested_plant_stock_value
    Interested_plant['Stock Value'] = Interested_plant['Stock qty'] * Interested_plant['Unit price'].fillna(0)

    # Modern Title
    st.markdown("---")

