import streamlit as st
import plotly.graph_objects as go
import geopandas as gpd
import os
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon
from plotly.colors import sample_colorscale, get_colorscale
from numpy import interp
import random
# The fuzzywuzzy library is used for smart string matching.
# Make sure to install it: pip install fuzzywuzzy python-Levenshtein
try:
    from fuzzywuzzy import process
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Nepal Interactive Map",
    page_icon="🇳🇵",
    layout="wide"
)

# --- Icons ---
icons = ['📍', '⭐', '🏔️', '🏛️', '🏞️', '🌳', '🏨','🎄','🏠','🚉','🌊']

# --- SESSION STATE INITIALIZATION ---
if 'map_view' not in st.session_state:
    st.session_state.map_view = {}
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = {}
if 'province_colors' not in st.session_state:
    st.session_state.province_colors = {}
if 'province_visibility' not in st.session_state:
    st.session_state.province_visibility = {}


# --- SIDEBAR STYLING ---
st.markdown("""
<style>
    /* Custom button for file uploader */
    div.stButton > button:first-child {
        background-color: #FFA500; /* Orange */
        color: white;
        border-radius: 20px;
        border: 1px solid #FFA500;
        padding: 10px 24px;
        font-size: 16px;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #FF8C00; /* Darker Orange */
        border-color: #FF8C00;
    }
</style>
""", unsafe_allow_html=True)


st.sidebar.title("🗺️ Map Controls")

# --- DATA UPLOAD ---
uploaded_file = st.sidebar.file_uploader("Upload a CSV to add a new layer", type=["csv"], key="file_uploader")
with st.sidebar.expander("CSV Formatting Rules"):
    st.markdown("""
    - Your CSV file **must** have exactly two columns.
    - One column must be named `Location` and contain official district names.
    - The second column should contain your data and can have any name.
    - **[View Sample CSV](https://drive.google.com/file/d/1XyMeRPVgKEDKXrdSI62EU6vyEXNau99C/view?usp=sharing)**
    - **[View Detailed Rules](https://drive.google.com/file/d/1Dl5QW-U3QoQRf13IjC9llkefC4Fm8keo/view?usp=sharing)**
    """)


if uploaded_file is not None:
    file_key = uploaded_file.name
    if file_key not in st.session_state.uploaded_files:
        try:
            df = pd.read_csv(uploaded_file)
            value_column = next((col for col in df.columns if col.lower() != 'location'), None)
            if value_column:
                st.session_state.uploaded_files[file_key] = {
                    "data": df,
                    "value_column": value_column,
                    "visible": True,
                    "color": '#FF4500', 
                    "tooltip_visible": True,
                    "display_name": file_key.replace('.csv', ''),
                    "tooltip_label": value_column.replace('_', ' '),
                    "icon": '🏞️' # Default icon for string data
                }
            else:
                st.error(f"Could not identify a data column in '{file_key}'. Ensure one column is 'Location'.")
        except Exception as e:
            st.error(f"Failed to read {file_key}: {e}")

# --- CUSTOM DATA LAYER CONTROLS ---
with st.sidebar.expander("Custom Data Layers", expanded=True):
    if not st.session_state.uploaded_files:
        st.markdown("<p style='font-size: smaller; font-style: italic;'>Upload a CSV file to add layers here.</p>", unsafe_allow_html=True)
    else:
        for file_name, file_info in st.session_state.uploaded_files.items():
            with st.expander(f"Layer: {file_info['display_name']}", expanded=True):
                
                file_info['display_name'] = st.text_input("Layer Name", value=file_info['display_name'], key=f"dname_{file_name}")
                file_info['tooltip_label'] = st.text_input("Tooltip Label", value=file_info['tooltip_label'], key=f"tlabel_{file_name}")
                
                is_numeric = pd.to_numeric(file_info['data'][file_info['value_column']], errors='coerce').notna().all()
                
                col1, col2 = st.columns([5, 2])
                with col1:
                    file_info['visible'] = st.checkbox(f"Show Layer", value=file_info['visible'], key=f"vis_{file_name}")
                
                with col2:
                    if is_numeric:
                        file_info['color'] = st.color_picker("Color", value=file_info['color'], key=f"color_{file_name}", label_visibility="collapsed")
                    else: # Is string/categorical data
                        file_info['icon'] = st.selectbox(
                            "Icon", 
                            icons, 
                            index=icons.index(file_info.get('icon', '🏞️')),
                            key=f"icon_{file_name}",
                            label_visibility="collapsed"
                        )


# --- BASE LAYER CONTROLS ---
with st.sidebar.expander("Base Layer Controls", expanded=True):
    show_district_borders = st.checkbox("Show District Borders", value=True)
    show_province_borders = st.checkbox("Show Province Borders", value=True)
    color_by_province = st.checkbox("Color by Province")
    if color_by_province:
        with st.expander("Province Colors & Visibility", expanded=False):
            provinces_gdf_for_colors = gpd.read_file(os.path.join("geo_data", "provinces.geojson"))
            default_prov_colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692']
            
            for idx, row in provinces_gdf_for_colors.iterrows():
                display_name = row.get('PROV_EN', f"Province {idx+1}")
                
                if idx not in st.session_state.province_visibility:
                    st.session_state.province_visibility[idx] = True

                col1, col2 = st.columns([5, 2])
                with col1:
                    st.session_state.province_visibility[idx] = st.checkbox(
                        display_name, 
                        value=st.session_state.province_visibility[idx], 
                        key=f"prov_vis_{idx}"
                    )
                with col2:
                    st.session_state.province_colors[idx] = st.color_picker(
                        f"Color for {display_name}", 
                        st.session_state.province_colors.get(idx, default_prov_colors[idx % len(default_prov_colors)]), 
                        key=f"prov_color_{idx}",
                        label_visibility="collapsed"
                    )


# --- TOOLTIP CONTROLS ---
with st.sidebar.expander("Tooltip Controls", expanded=True):
    show_district_tooltip = st.checkbox("Show District Name", value=True)
    
    if st.session_state.uploaded_files:
        st.markdown("---")
        st.write("**Data Layer Tooltips**")
        for file_name, file_info in st.session_state.uploaded_files.items():
            file_info['tooltip_visible'] = st.checkbox(f"Show '{file_info['display_name']}' values", value=file_info.get('tooltip_visible', True), key=f"tooltip_{file_name}")

def main():
    st.title("🇳🇵 Map of Nepal: All Boundaries")
    st.markdown("A clean map showing the national, provincial, and district boundaries of Nepal.")

    try:
        districts_filepath = os.path.join("geo_data", "districts.geojson")
        provinces_filepath = os.path.join("geo_data", "provinces.geojson")
        
        districts_gdf = gpd.read_file(districts_filepath)
        provinces_gdf = gpd.read_file(provinces_filepath)
        
        district_col_name = 'DIST_EN' if 'DIST_EN' in districts_gdf.columns else 'DISTRICT'
        
        nepal_border_gdf = provinces_gdf.dissolve()
        fig = go.Figure()
        
        if color_by_province:
            for i, row in provinces_gdf.iterrows():
                if st.session_state.province_visibility.get(i, True):
                    color = st.session_state.province_colors.get(i, '#CCCCCC')
                    if isinstance(row.geometry, MultiPolygon):
                        for poly in row.geometry.geoms:
                            lons, lats = poly.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), fill="toself", fillcolor=color, line_color=color, mode='lines', hoverinfo='none'))
                    else:
                        lons, lats = row.geometry.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), fill="toself", fillcolor=color, line_color=color, mode='lines', hoverinfo='none'))

        # Draw custom data layers
        for file_name, file_info in st.session_state.uploaded_files.items():
            if file_info['visible']:
                user_df = file_info['data'].copy()
                value_col = file_info.get('value_column')
                
                if 'Location' in user_df.columns and value_col:
                    
                    if FUZZYWUZZY_AVAILABLE:
                        official_districts = districts_gdf[district_col_name].tolist()
                        def get_match(loc):
                            match, score = process.extractOne(loc, official_districts)
                            if score >= 80:
                                if loc != match:
                                    st.toast(f"Matched '{loc}' to '{match}'", icon='✅')
                                return match
                            return None
                        user_df['matched_location'] = user_df['Location'].apply(get_match)
                        merge_on_col = 'matched_location'
                    else:
                        merge_on_col = 'Location'
                    
                    user_data_gdf = pd.merge(districts_gdf, user_df, left_on=district_col_name, right_on=merge_on_col, how='inner')

                    if user_data_gdf.empty:
                        st.warning(f"For '{file_info['display_name']}', no matching locations were found.")
                        continue

                    is_numeric = pd.to_numeric(user_data_gdf[value_col], errors='coerce').notna().all()
                    
                    if is_numeric:
                        user_data_gdf[value_col] = pd.to_numeric(user_data_gdf[value_col])
                        min_val, max_val = user_data_gdf[value_col].min(), user_data_gdf[value_col].max()
                        for _, row in user_data_gdf.iterrows():
                            normalized_val = interp(row[value_col], [min_val, max_val], [0, 1]) if min_val != max_val else 0.5
                            colorscale = [[0, 'rgba(255,255,255,0)'], [1, file_info['color']]]
                            color = sample_colorscale(colorscale, normalized_val)[0]
                            if isinstance(row.geometry, MultiPolygon):
                                for poly in row.geometry.geoms: lons, lats = poly.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), fill="toself", fillcolor=color, line_color='rgba(0,0,0,0)', mode='lines', hoverinfo='none'))
                            else: lons, lats = row.geometry.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), fill="toself", fillcolor=color, line_color='rgba(0,0,0,0)', mode='lines', hoverinfo='none'))
                    else: # String data (icons)
                        for idx, user_row in user_data_gdf.iterrows():
                            centroid = user_row.geometry.centroid
                            jitter_x = (random.random() - 0.5) * 0.01
                            jitter_y = (random.random() - 0.5) * 0.01
                            fig.add_trace(go.Scatter(
                                x=[centroid.x + jitter_x], 
                                y=[centroid.y + jitter_y],
                                mode='text',
                                text=file_info.get('icon', '📍'),
                                textfont=dict(size=16, color=file_info['color']),
                                hoverinfo='none'
                            ))

        def add_border_trace(geom, fig, line_color, line_width):
            if isinstance(geom, MultiPolygon):
                for poly in geom.geoms: lons, lats = poly.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), mode='lines', line_color=line_color, line_width=line_width, hoverinfo='none'))
            else: lons, lats = geom.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), mode='lines', line_color=line_color, line_width=line_width, hoverinfo='none'))

        if show_district_borders:
            for _, row in districts_gdf.iterrows(): add_border_trace(row.geometry, fig, 'dimgray', 0.5)
        if show_province_borders:
            for _, row in provinces_gdf.iterrows(): add_border_trace(row.geometry, fig, 'black', 1.5)
        for geom in nepal_border_gdf.geometry: add_border_trace(geom, fig, 'black', 3.5)

        for _, row in districts_gdf.iterrows():
            text_parts = []
            district_name = row.get(district_col_name, 'N/A')
            if show_district_tooltip: text_parts.append(f"<b>District:</b> {district_name}")
            
            for file_name, file_info in st.session_state.uploaded_files.items():
                if file_info.get('tooltip_visible', False):
                    user_df = file_info['data']
                    value_col = file_info.get('value_column')
                    
                    items_in_district = user_df[user_df['Location'] == district_name]
                    if not items_in_district.empty:
                        label = file_info['tooltip_label']
                        
                        if len(items_in_district) > 1:
                            text_parts.append(f"<b>{label}:</b>")
                            for i, item_row in items_in_district.iterrows():
                                item_value = item_row[value_col]
                                text_parts.append(f"  {chr(97+i)}. {item_value}")
                        else:
                            item_value = items_in_district.iloc[0][value_col]
                            try:
                                numeric_val = float(item_value)
                                text_parts.append(f"<b>{label}:</b> {numeric_val:,.2f}")
                            except (ValueError, TypeError):
                                text_parts.append(f"<b>{label}:</b> {item_value}")

            hover_text = "<br>".join(text_parts)
            
            if text_parts:
                if isinstance(row.geometry, MultiPolygon):
                    for poly in row.geometry.geoms: lons, lats = poly.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), fill="toself", fillcolor="rgba(0,0,0,0)", line_color="rgba(0,0,0,0)", mode='lines', hoverinfo='text', text=hover_text))
                else: lons, lats = row.geometry.exterior.coords.xy; fig.add_trace(go.Scatter(x=list(lons), y=list(lats), fill="toself", fillcolor="rgba(0,0,0,0)", line_color="rgba(0,0,0,0)", mode='lines', hoverinfo='text', text=hover_text))

        fig.update_layout(
            margin={"r":0, "t":0, "l":0, "b":0}, showlegend=False,
            yaxis=dict(scaleanchor="x", scaleratio=1), xaxis_visible=False, yaxis_visible=False,
            plot_bgcolor='white', paper_bgcolor='white',
        )

        if st.session_state.map_view and 'xaxis.range' in st.session_state.map_view:
            fig.update_layout(xaxis_range=st.session_state.map_view['xaxis.range'], yaxis_range=st.session_state.map_view['yaxis.range'])
        else:
            lons, lats = nepal_border_gdf.geometry.union_all().exterior.coords.xy
            fig.update_layout(xaxis_range=[min(lons), max(lons)], yaxis_range=[min(lats), max(lats)])
        
        event_data = st.plotly_chart(fig, use_container_width=True, key="nepal_map")
        
        if isinstance(event_data, dict) and "relayoutData" in event_data:
            if 'xaxis.range' in event_data['relayoutData']: st.session_state.map_view = event_data["relayoutData"]

    except FileNotFoundError as e:
        st.error(f"ERROR: GeoJSON file not found: `{e.filename}`. Please ensure your geojson files are in the correct `geo_data` folder.")
    except Exception as e:
        st.error("An unexpected error occurred. See details below.")
        st.exception(e)

if __name__ == "__main__":
    main()
