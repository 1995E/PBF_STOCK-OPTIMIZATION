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

# CHOOSE THE IMPACTED PLANT IN SIDEBAR
with st.sidebar:
    st.markdown("### 🚢 Plant Selection")
    plant = st.selectbox(
        "Select the impacted Plant:",
        ['GIRASSOL', 'DALIA', 'PAZFLOR', 'CLOV', 'GENERAL DIVISION'],
    )

# 1. FILE UPLOADERS IN SIDEBAR
with st.sidebar:
    st.header("📂 Data Source Configuration")
    uploaded_materials = st.file_uploader("Material Overview per Plant (Excel)", type=["xlsx"])
    uploaded_prices = st.file_uploader("Material Overview per Price (Excel)", type=["xlsx"])
    st.markdown("---")
    Bom_template = st.file_uploader("Impacted Bom (Excel)", type=["xlsx"])
    st.markdown("---")

st.markdown(f"""
    <style>
        .main-header {{
            font-size: 2.0rem;
            color: #303947;
            font-weight: 800;
            margin-bottom: 1rem;
        }}
        .section-gap {{
            margin-top: 15px;
            margin-bottom: 15px;
        }}
        .kpi-gap {{ 
            margin-top: 10px;
            margin-bottom: 10px;
        }}
        .kpi-title {{
            font-size: 1.3rem !important;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: #1E3A8A;
        }}
        .metric-card {{
            background-color: #F8FAFC;
            padding: 1.0rem;
            border-radius: 10px;
            border-left: 6px solid #3B82F6;
            border-top: 1px solid #E2E8F0;
            border-right: 1px solid #E2E8F0;
            border-bottom: 1px solid #E2E8F0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
            margin-bottom: 0.5rem;
            min-height: 110px;
        }}
        .metric-label {{
            font-size: 0.8rem;
            color: #64748B;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .metric-value {{
            font-size: 1.45rem;
            color: #0F172A;
            font-weight: 800;
            margin-top: 0.15rem;
        }}
        .metric-subvalue {{
            font-size: 0.8rem;
            color: #475569;
            margin-top: 0.1rem;
        }}
        .chart-card {{
            background-color: #FFFFFF;
            padding: 1.0rem;
            border-radius: 10px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
            margin-bottom: 0.75rem;
        }}
        .stProgress > div > div > div {{
            height: 20px !important;
            border-radius: 6px;
        }}
        .stProgress > div > div > div > div {{
            background-color: #EF4444 !important;
        }}
    </style>
""", unsafe_allow_html=True)

# Modern Title
st.markdown("<div class=\"main-header\"> STOCK ANALYSE TOOL</div>", unsafe_allow_html=True)

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
        'MRP Type', 'Stock qty', 'Blocked Stock Qty', 'Safety', 'Min',
        'Max', 'Unit price'
    ]
    existing_columns = [col for col in requested_columns if col in removed_materials_df.columns]
    df = removed_materials_df[existing_columns].copy()

    # Perform calculations based on selection
    Total_removed_materials = df['Material n°'].nunique()
    pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
    pd_v1_unique_materials = pd_v1_df.drop_duplicates(subset=['Material n°'])
    stock_greater_zero = pd_v1_df[pd_v1_df['Stock qty'] > 0]

    Interested_plant = stock_greater_zero[stock_greater_zero['Plant'] == plant].copy()
    Interested_plant_unique = Interested_plant.drop_duplicates(subset=['Material n°']).copy()

    Others_plant = pd_v1_df[pd_v1_df['Plant'] != plant].copy()
    Others_plant_unique = Others_plant.drop_duplicates(subset=['Material n°']).copy()

    Total_stock_value = (stock_greater_zero['Stock qty'] *  stock_greater_zero['Unit price']).sum()
    Interested_plant_stock_value = (Interested_plant['Stock qty'] * Interested_plant['Unit price']).sum()
    Others_plant_stock_value = Total_stock_value - Interested_plant_stock_value

    # INTELLIGENT DESCRIPTION CHARACTERISTIC GROUPING
    if not Interested_plant.empty:
        # Parse base keywords for each row
        parsed_records = []
        for idx, row in Interested_plant.iterrows():
            desc = row['Material description']
            if pd.isna(desc):
                parsed_records.append({'idx': idx, 'first': 'UNKNOWN', 'second': ''})
                continue
            desc_str = str(desc).upper()
            parts = desc_str.split(',')
            
            first_part = parts[0]
            first_tokens = [t.strip() for t in re.sub(r'[^A-Z0-9\s-]', ' ', first_part).split() if len(t.strip()) > 2]
            first_key = first_tokens[0] if len(first_tokens) > 0 else 'OTHER'
            
            second_key = ''
            if len(parts) > 1:
                second_part = parts[1]
                second_tokens = [t.strip() for t in re.sub(r'[^A-Z0-9\s-]', ' ', second_part).split() if len(t.strip()) > 2]
                second_key = second_tokens[0] if len(second_tokens) > 0 else ''
            
            parsed_records.append({'idx': idx, 'first': first_key, 'second': second_key})
        
        parsed_df = pd.DataFrame(parsed_records)
        
        # Group analysis implementation:
        # For each first keyword, determine if all entries have the same second keyword.
        # If yes, we use 'FIRST SECOND'. If different, we group them only by 'FIRST'.
        char_mapping = {}
        for first_val, group in parsed_df.groupby('first'):
            unique_seconds = group['second'].unique()
            unique_seconds = [s for s in unique_seconds if s != '']
            
            if len(unique_seconds) == 1:
                second_val = unique_seconds[0]
                mapped_name = f"{first_val} {second_val}"
            else:
                mapped_name = first_val
            
            for row_idx in group['idx']:
                char_mapping[row_idx] = mapped_name
        
        Interested_plant['Description Characteristic'] = Interested_plant.index.map(char_mapping).fillna('OTHER')
    else:
        Interested_plant['Description Characteristic'] = pd.Series(dtype='str')
        
    Interested_plant['Stock Value'] = Interested_plant['Stock qty'] * Interested_plant['Unit price'].fillna(0)

    # UPDATE INTERESTED PLANT DATAFRAME WITH ACTION COLUMN FROM IMPACTED BOM BEFORE DISPLAYING KPIs
    scrap_value = 0.0
    transfer_value = 0.0
    bom_loaded = False
    materials_to_transfer = pd.DataFrame()
    scrap_df = pd.DataFrame()

    if Bom_template is not None:
        try:
            material_list_df = pd.read_excel(Bom_template, sheet_name="Material_List")
            material_list_df.columns = material_list_df.columns.str.strip()

            material_list_df['Material n°'] = material_list_df['Material n°'].astype(str).str.strip()
            Interested_plant['Material n°'] = Interested_plant['Material n°'].astype(str).str.strip()
            Others_plant['Material n°'] = Others_plant['Material n°'].astype(str).str.strip()

            action_mapping = material_list_df.set_index('Material n°')['Results'].to_dict()
            Interested_plant['Action'] = Interested_plant['Material n°'].map(action_mapping)
            Interested_plant['Optimization Status'] = 'Standard'

            mask = (Interested_plant['Action'] == 'FASD analyse') & (Interested_plant['FASD'] == 'Dead')
            Interested_plant.loc[mask, 'Action'] = 'Scrap analyse'
            Interested_plant.loc[mask, 'Optimization Status'] = 'Optimized'

            scrap_analyse_materials = Interested_plant[Interested_plant['Action'] == 'Scrap analyse']['Material n°'].unique()
            active_others_df = Others_plant[(Others_plant['Material n°'].isin(scrap_analyse_materials)) & (Others_plant['FASD'] != 'Dead')].copy()

            priority_map = {'FAST': 1, 'Active': 2, 'Slow': 3}
            active_others_df['Priority'] = active_others_df['FASD'].map(priority_map).fillna(4)
            active_others_df = active_others_df.sort_values(by=['Material n°', 'Priority'])
            best_receiving_plants = active_others_df.drop_duplicates(subset=['Material n°']).set_index('Material n°')

            transfer_material_ids = best_receiving_plants.index.unique()

            raw_transfer_df = Interested_plant[Interested_plant['Material n°'].isin(transfer_material_ids)].copy()
            Interested_plant = Interested_plant[~Interested_plant['Material n°'].isin(transfer_material_ids)].copy()

            if not raw_transfer_df.empty:
                raw_transfer_df['Receiving plant'] = raw_transfer_df['Material n°'].map(best_receiving_plants['Plant'])
                raw_transfer_df['Receiving quantity'] = raw_transfer_df['Stock qty']

                target_cols = [
                    'Material n°', 'Material description', 'Material discipline',
                    'Plant code', 'Plant', 'Storage bin', 'FASD', 'Stock qty',
                    'Receiving plant', 'Receiving quantity', 'Unit price',
                ]
                existing_target_cols = [c for c in target_cols if c in raw_transfer_df.columns]
                materials_to_transfer = raw_transfer_df[existing_target_cols].copy()
                transfer_value = (materials_to_transfer['Stock qty'] * materials_to_transfer['Unit price']).sum()
            else:
                materials_to_transfer = pd.DataFrame()
                transfer_value = 0.0

            scrap_df = Interested_plant[Interested_plant['Action'] == 'Scrap analyse'].copy()
            scrap_value = (scrap_df['Stock qty'] * scrap_df['Unit price']).sum()

            bom_loaded = True
        except Exception as e:
            st.error(f"Error reading Material_List from Impacted Bom: {e}")

    # Calculate values if not yet set
    if 'Calculated Value' not in Interested_plant.columns and not Interested_plant.empty:
        Interested_plant['Calculated Value'] = Interested_plant['Stock qty'] * Interested_plant['Unit price'].fillna(0)

    # Calculate Potential Scrap Ratio
    scrap_ratio = 0.0
    if Interested_plant_stock_value > 0:
        scrap_ratio = (scrap_value / Interested_plant_stock_value) * 100
        remaining_crap = 100-scrap_ratio

    # 3. EXECUTIVE KPI CARDS
    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        st.markdown(f"""
            <div class="metric-card" style="border-left-color: #1E3A8A">
                <div class="metric-label">Total Material Assessed</div>
                <div class="metric-value">{Total_removed_materials:,}</div>
                <div class="metric-subvalue">stock and non-stocked materials</div>
            </div>
        """, unsafe_allow_html=True)
    with kpi_cols[1]:
        st.markdown(f"""
            <div class="metric-card" style=
