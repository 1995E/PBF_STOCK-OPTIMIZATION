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
            <div class="metric-card" style="border-left-color: #10B981">
                <div class="metric-label">Total Stock Value</div>
                <div class="metric-value">${Total_stock_value:,.0f}</div>
                <div class="metric-subvalue"><b>{len(pd_v1_unique_materials):,}</b> stock materials</div>
            </div>
        """, unsafe_allow_html=True)
    with kpi_cols[2]:
        st.markdown(f"""
            <div class="metric-card" style="border-left-color: #F59E0B">
                <div class="metric-label">{plant} Stock Value</div>
                <div class="metric-value">${Interested_plant_stock_value:,.0f}</div>
                <div class="metric-subvalue"><b>{len(Interested_plant_unique):,}</b> stock materials</div>
            </div>
        """, unsafe_allow_html=True)
    with kpi_cols[3]:
        scrap_val_str = f"${scrap_value:,.0f}" if bom_loaded else "N/A (Load BOM)"
        sub_str = f"<b>${transfer_value:,.0f}</b> to be transferred" if bom_loaded else "N/A (Load BOM)"
        st.markdown(f"""
            <div class="metric-card" style="border-left-color: #EF4444">
                <div class="metric-label">{plant} Potential Scrap</div>
                <div class="metric-value">{scrap_val_str}</div>
                <div class="metric-subvalue">-{sub_str}</div>
            </div>
        """, unsafe_allow_html=True)
    with kpi_cols[4]:
        scrap_pct_str = f"{scrap_ratio:.0f}%" if bom_loaded else "N/A (Load BOM)"
        st.markdown(f"""
            <div class="metric-card" style="border-left-color: #7C3AED; background-color: #FAF5FF;">
                <div class="metric-label">Potential Scrap Ratio</div>
                <div class="metric-value" style="color: #EF4444;">{scrap_pct_str}</div>
                <div class="metric-subvalue">{remaining_crap:.0f}% to be kept in {plant}</div>
            </div>
        """, unsafe_allow_html=True)

    # 4. EXECUTIVE TABS FOR HIGH LEVEL MANAGEMENT
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📊 DISPLAY CHART", "📋 DETAILED DATASET"])

    with tab1:
        if bom_loaded:
            st.markdown('<div class="kpi-gap"></div>', unsafe_allow_html=True)

            # --------------------------- KPI PROGRESS BAR ---------------------------
            if Interested_plant_stock_value > 0:
                st.progress(scrap_ratio / 100.0)
                st.markdown(f"**{scrap_ratio:.0f}%** of {plant} STOCK VALUE IDENTIFIED FOR POTENTIAL SCRAPPING")
            else:
                st.info("No stock value for selected plant to calculate scrapping progress.")

            st.markdown('<hr style="border: 1px solid #E2E8F0; margin-top: 15px; margin-bottom: 15px;">', unsafe_allow_html=True)

            # --------------------------- ROW 1: INTERACTIVE SELECTED CHARACTERISTIC ANALYSIS ---------------------------
            if not Interested_plant.empty:
                col_sel_left, col_sel_right = st.columns([1.0, 2.0])

                with col_sel_left:
                    st.markdown('<div class="chart-card" style="min-height: 290px;">', unsafe_allow_html=True)
                    st.markdown("##### 🔍 FILTER BY CHARACTERISTIC")
                    unique_characteristics = sorted(list(Interested_plant['Description Characteristic'].dropna().unique()))
                    selected_char = st.selectbox(
                        "Choose a Description Characteristic:",
                        options=unique_characteristics,
                        index=0,
                        key="char_select_dashboard"
                    )
                    filtered_by_char = Interested_plant[Interested_plant['Description Characteristic'] == selected_char].copy()

                    if not filtered_by_char.empty:
                        grp_stock_val = filtered_by_char['Stock Value'].sum()
                        pred_fasd = filtered_by_char.groupby('FASD')['Stock qty'].sum().idxmax() if not filtered_by_char.dropna(subset=['FASD']).empty else 'N/A'
                        st.markdown(f"""
                            <div style="margin-top: 15px;">
                                <p style="margin-bottom:2px; font-weight:bold; color:#64748B; font-size:0.85rem;">TOTAL GROUP STOCK VALUE</p>
                                <h3 style="margin-top:0px; color:#1E3A8A; font-size:1.3rem;">${grp_stock_val:,.2f}</h3>
                                <p style="margin-bottom:2px; font-weight:bold; color:#64748B; font-size:0.85rem;">PREDOMINANT FASD STATUS</p>
                                <h4 style="margin-top:0px; color:#EF4444; font-size:1.15rem;">{pred_fasd}</h4>
                            </div>
                        """, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                with col_sel_right:
                    st.markdown('<div class="chart-card" style="min-height: 290px;">', unsafe_allow_html=True)
                    if not filtered_by_char.empty:
                        st.markdown(f"##### BAR CHART: STOCK VALUE FOR {selected_char}")
                        char_fasd_data = filtered_by_char.groupby('FASD')['Stock Value'].sum().reset_index()

                        bar_grp_fig = px.bar(
                            char_fasd_data,
                            x='FASD',
                            y='Stock Value',
                            labels={'Stock Value': 'Total Stock Value ($)'},
                            color='FASD',
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        bar_grp_fig.update_layout(height=200, margin=dict(t=10, b=10, l=10, r=10))
                        st.plotly_chart(bar_grp_fig, use_container_width=True)
                    else:
                        st.info("No data available for the chosen group.")
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("No data to display group analysis.")
                selected_char = None
                filtered_by_char = pd.DataFrame()

            st.markdown('<hr style="border: 1px solid #E2E8F0; margin-top: 15px; margin-bottom: 15px;">', unsafe_allow_html=True)

            # --------------------------- ROW 2: GENERAL EXECUTIVE DASHBOARD OVERVIEW ---------------------------
            col_left, col_right = st.columns([1.0, 1.0])

            with col_left:
                st.markdown('<div class="chart-card" style="min-height: 310px;">', unsafe_allow_html=True)
                st.markdown("##### STOCK DISTRIBUTION OVERVIEW")

                bar_data = [
                    {"Category": "Total Stock Value", "Type": "All plant", "Value": Total_stock_value},
                    {"Category": "Stock Distribution", "Type": f"{plant}", "Value": Interested_plant_stock_value},
                    {"Category": "Stock Distribution", "Type": "Others plant", "Value": Others_plant_stock_value},
                    {"Category": f"{plant} Scrap Result", "Type": f"{plant} Potential value for scrapping", "Value": scrap_value},
                    {"Category": f"{plant} Scrap Result", "Type": "Transferred value", "Value": transfer_value}
                ]
                bar_df = pd.DataFrame(bar_data)
                sorted_cats = ["Total Stock Value", "Stock Distribution", f"{plant} Scrap Result"]

                bar_fig = px.bar(
                    bar_df,
                    y="Category",
                    x="Value",
                    color="Type",
                    orientation='h',
                    category_orders={"Category": sorted_cats},
                    color_discrete_map={
                        "All plant": "#1E3A5F",
                        f"{plant}": "#2563EB",
                        "Others plant": "#94A3B8",
                        f"{plant} Potential value for scrapping": "#D97706",
                        "Transferred value": "#059669"
                    }
                )
                bar_fig.update_layout(
                    barmode='stack',
                    yaxis_title=None,
                    xaxis_title="Value ($)",
                    height=220,
                    margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(orientation="h", y=-0.35, xanchor="center", x=0.5)
                )
                st.plotly_chart(bar_fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with col_right:
                st.markdown('<div class="chart-card" style="min-height: 310px;">', unsafe_allow_html=True)
                st.markdown("##### STOCK VALUE PER FASD STATUS")

                if not scrap_df.empty:
                    scrap_df['Stock Value'] = scrap_df['Stock qty'] * scrap_df['Unit price'].fillna(0)
                    fasd_df = scrap_df.groupby('FASD')['Stock Value'].sum().reset_index()
                    fasd_df = fasd_df.sort_values(by='Stock Value', ascending=True)

                    fasd_bar_fig = px.bar(
                        fasd_df,
                        y='FASD',
                        x='Stock Value',
                        orientation='h',
                        color_discrete_sequence=['#475569'],
                        text_auto='.2s'
                    )
                    fasd_bar_fig.update_layout(
                        yaxis_title=None,
                        height=220,
                        margin=dict(t=10, b=10, l=10, r=10)
                    )
                    st.plotly_chart(fasd_bar_fig, use_container_width=True)
                else:
                    st.info("No data available for FASD breakdown.")
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        else:
            st.info("💡 Please upload the Impacted BOM template to preview interactive visualization panels!")
            selected_char = None
            filtered_by_char = pd.DataFrame()

    with tab2:
        if bom_loaded:
            if selected_char:
                st.markdown(f"### 📋 Materials in selected Group: **{selected_char}**")
                st.dataframe(filtered_by_char, use_container_width=True)

            st.markdown(f"### 📋 {plant} potential material list for scrapping")
            display_columns = [
                'Material n°', 'Material description', 'Material discipline',
                'Plant code', 'Plant', 'Storage bin', 'FASD', 'Blocking status',
                'MRP Type', 'Stock qty', 'Blocked Stock Qty', 'Safety', 'Min',
                'Max', 'Unit price', 'Action', 'Optimization Status', 'Description Characteristic'
            ]
            existing_display_cols = [col for col in display_columns if col in Interested_plant.columns]
            Interested_plant_display = Interested_plant[existing_display_cols]
            st.dataframe(Interested_plant_display, use_container_width=True)

            # Export Option
            buffer_interested = io.BytesIO()
            with pd.ExcelWriter(buffer_interested, engine='openpyxl') as writer:
                Interested_plant_display.to_excel(writer, index=False, sheet_name='Interested Plant')
            st.download_button(
                label="📥 Download Excel file",
                data=buffer_interested.getvalue(),
                file_name=f"Interested_Plant_{plant}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.markdown(f"### 🔄 Potential materials to be transferred from {plant}")
            if not materials_to_transfer.empty:
                st.dataframe(materials_to_transfer, use_container_width=True)

                # Export Option
                buffer_transfer = io.BytesIO()
                with pd.ExcelWriter(buffer_transfer, engine='openpyxl') as writer:
                    materials_to_transfer.to_excel(writer, index=False, sheet_name='Materials to Transfer')
                st.download_button(
                    label="📥 Download Excel file",
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
