import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import io

st.set_page_config(
    page_title="PBF STOCK ANALYSE TOOL",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Custom CSS Styling
st.markdown("""
    <style> 
        .main-header {
            font-size: 2.2rem;
            color: #1E3A8A;
            font-weight: 700;
            margin-bottom: 2.5rem;
        }
        .sub-header {
            font-size: 1.1rem;
            color: #4B5563;
            margin-bottom: 1.5rem;
        }
        .metric-card {
            background-color: #F9FAFB;
            padding: 1.2rem;
            border-radius: 10px;
            border-left: 5px solid #3B82F6;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 1rem;
            min-height: 125px;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #6B7280;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .metric-value {
            font-size: 1.6rem;
            color: #111827;
            font-weight: 700;
            margin-top: 0.2rem;
        }
        .metric-subvalue {
            font-size: 0.95rem;
            color: #4B5563;
            margin-top: 0.1rem;
        }
    </style>
""", unsafe_allow_html=True)

# Modern Title
st.markdown("<div class=\"main-header\"> PBF STOCK ANALYSE TOOL</div>", unsafe_allow_html=True)

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

            # Clean mapping IDs
            material_list_df['Material n°'] = material_list_df['Material n°'].astype(str).str.strip()
            Interested_plant['Material n°'] = Interested_plant['Material n°'].astype(str).str.strip()
            Others_plant['Material n°'] = Others_plant['Material n°'].astype(str).str.strip()

            # Group by material number if there are duplicates
            action_mapping = material_list_df.set_index('Material n°')['Results'].to_dict()
            Interested_plant['Action'] = Interested_plant['Material n°'].map(action_mapping)

            # Create default status column
            Interested_plant['Optimization Status'] = 'Standard'

            # Rule: Action update
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

    # 3. EXECUTIVE KPI CARDS
    kpi_cols = st.columns(5)

    # Card 1: Total material removed in one card
    with kpi_cols[0]:
        st.markdown(f"""
            <div class=\"metric-card\" style=\"border-left-color: #1E3A8A;\">
                <div class=\"metric-label\">Total Material Assessed</div>
                <div class=\"metric-value\">{Total_removed_materials:,}</div>
            </div>
        """, unsafe_allow_html=True)

    # Card 2: Show active stock item and total portfolio stock in the same card
    with kpi_cols[1]:
        st.markdown(f"""
            <div class=\"metric-card\" style=\"border-left-color: #10B981;\">
                <div class=\"metric-label\">Total Stock Value</div> 
                <div class=\"metric-value\">${Total_stock_value:,.0f}</div>
                <div class=\"metric-subvalue\"><b>{len(pd_v1_unique_materials):,}</b> Stock materials</div>
            </div>
        """, unsafe_allow_html=True)
        
    # Card 3: Selected plant stock value (e.g. DALIA / GIRASSOL)
    with kpi_cols[2]:
        st.markdown(f"""
            <div class=\"metric-card\" style=\"border-left-color: #F59E0B;\">
                <div class=\"metric-label\">{plant} Stock Value</div>
                <div class=\"metric-value\">${Interested_plant_stock_value:,.0f}</div>
                <div class=\"metric-subvalue\"> Reduction after BOM analyse</div>
            </div>
        """, unsafe_allow_html=True)

    # Card 4: Sum of (scrap proposal value + potential transfer saving) and potential transfer saving in the same card
    with kpi_cols[3]:
        #total_savings = scrap_value + transfer_value if bom_loaded else 0.0
        scrap_val_str = f"${ scrap_value:,.0f}" if bom_loaded else "N/A (Load BOM)"
        sub_str = f"<b>${transfer_value:,.0f}</b> Stock value to be transferred" if bom_loaded else "N/A (Load BOM)"
        st.markdown(f"""
            <div class=\"metric-card\" style=\"border-left-color: #8B5CF6;\">
                <div class=\"metric-label\">{plant} Potential Value for Scrapping</div>
                <div class=\"metric-value\">{scrap_val_str</div>
                <div class=\"metric-subvalue\">{sub_str}</div>
            </div>
        """, unsafe_allow_html=True)


    # 4. EXECUTIVE TABS FOR HIGH LEVEL MANAGEMENT
    tab1, tab2 = st.tabs(["📈 Executive Visualizations", "📋 Detailed Datasets & Actions"])


    with tab2:
        if bom_loaded:
            st.markdown(f"### 📋 Interested Plant Materials for {plant} (with Actions & Optimization Rules)")
            display_columns = [
                'Material n°', 'Material description', 'Material discipline',
                'Plant code', 'Plant', 'Storage bin', 'FASD', 'Blocking status',
                'MRP Type', 'Stock qty', 'Blocked Stock Qty', 'Safety', 'Min',
                'Max', 'Unit price', 'Action', 'Optimization Status'
            ]
            existing_display_cols = [col for col in display_columns if col in Interested_plant.columns]
            Interested_plant_display = Interested_plant[existing_display_cols]
            st.dataframe(Interested_plant_display, use_container_width=True)

            # Export Option
            buffer_interested = io.BytesIO()
            with pd.ExcelWriter(buffer_interested, engine='openpyxl') as writer:
                Interested_plant_display.to_excel(writer, index=False, sheet_name='Interested Plant')
            st.download_button(
                label="📥 Download Interested Plant Excel",
                data=buffer_interested.getvalue(),
                file_name=f"Interested_Plant_{plant}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.markdown("### 🔄 Materials to be Transferred (Active in other plants, FASD != 'Dead')")
            if not materials_to_transfer.empty:
                st.dataframe(materials_to_transfer, use_container_width=True)

                # Export Option
                buffer_transfer = io.BytesIO()
                with pd.ExcelWriter(buffer_transfer, engine='openpyxl') as writer:
                    materials_to_transfer.to_excel(writer, index=False, sheet_name='Materials to Transfer')
                st.download_button(
                    label="📥 Download Materials to Transfer Excel",
                    data=buffer_transfer.getvalue(),
                    file_name=f"Materials_to_Transfer_{plant}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No matching materials to transfer.")
        else:
            st.markdown(f"### 📋 Interested Plant Materials for {plant}")
            st.dataframe(pd_v1_df, use_container_width=True)
else:
    st.info("💡 Please upload both 'Material Overview per Plant' and 'Material Overview per Price' Excel files in the sidebar to get started!")
