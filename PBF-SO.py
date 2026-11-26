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
    
    # Calculate stock value for stock_greater_zero
    stock_greater_zero['Stock Value'] = stock_greater_zero['Stock qty'] * stock_greater_zero['Unit price'].fillna(0)

    # Tab configuration
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Stock overview", "lorepsum 1", "lorepsum 2", "lorepsum 3", "lorepsum 4"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            # Toggle option on top
            chart_mode_plant = st.toggle("Show Pie Chart (Plant)", value=False, key="toggle_plant")
            
            # Group by plant
            plant_stock_df = stock_greater_zero.groupby('Plant', as_index=False)['Stock Value'].sum()
            
            if chart_mode_plant:
                fig_plant = px.pie(
                    plant_stock_df,
                    values='Stock Value',
                    names='Plant',
                    title='Stock Value by Plant'
                )
            else:
                fig_plant = px.bar(
                    plant_stock_df,
                    x='Stock Value',
                    y='Plant',
                    orientation='h',
                    title='Stock Value by Plant'
                )
                fig_plant.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_plant, use_container_width=True)

        with col2:
            # Toggle option on top
            chart_mode_fasd = st.toggle("Show Pie Chart (FASD)", value=False, key="toggle_fasd")
            
            # Group by FASD status
            fasd_stock_df = stock_greater_zero.groupby('FASD', as_index=False)['Stock Value'].sum()
            
            # Define desired order: Fast, Active, Slow, Dead (from top to bottom in horizontal bar chart means last in categorical lists)
            # We sort descending based on this categorical order index so 'Fast' sits on top
            fasd_order = ['Dead', 'Slow', 'Active', 'Fast']
            fasd_stock_df['FASD'] = pd.Categorical(fasd_stock_df['FASD'], categories=fasd_order, ordered=True)
            fasd_stock_df = fasd_stock_df.sort_values('FASD', ascending=True)
            
            if chart_mode_fasd:
                fig_fasd = px.pie(
                    fasd_stock_df,
                    values='Stock Value',
                    names='FASD',
                    title='Stock Value by FASD Status'
                )
            else:
                fig_fasd = px.bar(
                    fasd_stock_df,
                    x='Stock Value',
                    y='FASD',
                    orientation='h',
                    title='Stock Value by FASD Status'
                )
                # Update y-axis to follow categorical order perfectly
                fig_fasd.update_layout(yaxis={'categoryorder': 'array', 'categoryarray': fasd_order})
            st.plotly_chart(fig_fasd, use_container_width=True)
