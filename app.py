"""Run with: python -m streamlit run app.py"""
import hashlib
import html
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_utils import read_csv, prepare, spacing, marker_sizes

st.set_page_config(page_title="CPT / MASW visualizer", layout="wide")
st.title("CPT / MASW 3D data visualizer")
st.caption("Upload CSV files, assign coordinates and a measured variable, then rotate the point clouds.")
st.info("Use one coordinate reference system and consistent coordinate units for every file. "
        "Sampling spacing estimates point density; it is not the physical resolution of CPT or MASW.")
SYMBOLS = ["circle", "square", "diamond", "cross", "x", "circle-open", "square-open", "diamond-open"]
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]


@st.cache_data(show_spinner=False)
def load(content, separator, decimal):
    return read_csv(content, separator, decimal)


@st.cache_data(show_spinner=False)
def estimate(points):
    return spacing(points)


with st.sidebar:
    st.header("View settings")
    reverse_z = st.checkbox("Positive depth increases downward", value=False)
    exaggeration = st.slider("Vertical exaggeration", 0.1, 20.0, 1.0, 0.1)
    base_size = st.slider("Base marker size (pixels)", 2, 12, 5)
    opacity = st.slider("Point opacity", 0.1, 1.0, 0.85, 0.05)
    point_limit = st.number_input("Maximum displayed points per dataset", 1000, 1000000, 100000, 1000)
    st.caption("Spacing is estimated before display sampling. Depth signs are preserved.")

uploads = st.file_uploader("Select one or more CSV files", type="csv", accept_multiple_files=True)
datasets = []
for i, upload in enumerate(uploads):
    content = upload.getvalue()
    key = f"{i}_{hashlib.sha256(content).hexdigest()[:12]}"
    with st.expander(f"Dataset {i+1}: {upload.name}", expanded=True):
        a, b = st.columns(2)
        separator = a.selectbox("CSV separator", ["Auto", "Comma", "Semicolon", "Tab"], key=key+"sep")
        decimal = b.selectbox("Decimal separator", [".", ","], key=key+"decimal")
        try:
            frame = load(content, separator, decimal)
        except Exception as error:
            st.error(f"Cannot read CSV: {error}")
            continue
        st.dataframe(frame.head(10), hide_index=True)
        if len(frame.columns) < 4:
            st.error("The file needs at least four columns: three coordinates and a variable.")
            continue
        names = list(frame.columns)
        def preferred(candidates, fallback):
            return next((j for j, name in enumerate(names) if name.lower() in candidates), fallback)
        defaults = [preferred(["easting", "x"], 0), preferred(["northing", "y"], 1),
                    preferred(["depth", "z", "elevation"], 2), preferred(["vs", "qc"], 3)]
        st.write("Column mapping")
        fields = st.columns(4)
        mappings = [field.selectbox(label, names, index=default, key=key+label)
                    for field, label, default in zip(fields, ["X coordinate", "Y coordinate", "Z coordinate", "Variable"], defaults)]
        st.table(pd.DataFrame({"Role": ["X", "Y", "Z", "Variable"], "CSV column": mappings}))
        a, b, c = st.columns(3)
        title = a.text_input("Dataset name", upload.name.rsplit(".", 1)[0], key=key+"name")
        variable_title = b.text_input("Variable label (include units)", mappings[3], key=key+"varname")
        symbol = c.selectbox("Marker shape", SYMBOLS, index=i % len(SYMBOLS), key=key+"symbol")
        variable_type = st.selectbox("Variable type", ["Numeric (continuous)", "Categorical (soil type / discrete codes)"], key=key+"type")
        categorical = variable_type.startswith("Categorical")
        id_choice = st.selectbox("CPT / borehole ID column (optional)", ["No ID"] + names, key=key+"id")
        id_column = None if id_choice == "No ID" else id_choice
        id_labels = st.checkbox("Show one ID label per CPT / borehole", False, key=key+"idlabels", disabled=id_column is None)
        color_mode = st.selectbox("Color mode", ["Category colors"] if categorical else ["Value color scale", "Single dataset color"], key=key+"colormode"+str(categorical))
        colorscale = "Viridis"
        if color_mode == "Value color scale":
            colorscale = st.selectbox("Color scale", ["Viridis", "Plasma", "Cividis", "Turbo", "RdBu", "Blues", "Greens"], key=key+"scale")
            if st.checkbox("Custom low / high color codes", False, key=key+"customscale"):
                low = st.color_picker("Low-value color", "#440154", key=key+"low")
                high = st.color_picker("High-value color", "#fde725", key=key+"high")
                colorscale = [[0, low], [1, high]]
        dataset_color = PALETTE[i % len(PALETTE)]
        if color_mode == "Single dataset color":
            dataset_color = st.color_picker("Dataset color / HEX code", dataset_color, key=key+"color")
        a, b = st.columns(2)
        mode = a.selectbox("Resolution / sampling spacing", ["Estimate from coordinates", "Enter known spacing"], key=key+"mode")
        known = b.number_input("Known spacing (coordinate units)", min_value=0.000001, value=1.0, format="%.6f", key=key+"spacing")
        visible = st.checkbox("Include in visualization", True, key=key+"visible")
        try:
            data, rejected = prepare(frame, mappings, decimal, categorical, id_column)
        except ValueError as error:
            st.error(str(error))
            continue
        if rejected:
            st.warning(f"Excluded {rejected:,} rows with invalid coordinates or missing/invalid variables (including #REF!).")
        if data.empty:
            st.error("No valid rows for this mapping.")
            continue
        category_colors = {}
        if categorical:
            st.write("Category colors (choose a color or enter a HEX code)")
            for j, category in enumerate(sorted(data.value.unique())):
                category_key = hashlib.sha256(category.encode()).hexdigest()[:16]
                category_colors[category] = st.color_picker(str(category), PALETTE[j % len(PALETTE)], key=key+"cat"+category_key)
        if id_column is not None and (data.id == "").any():
            st.caption("Rows with blank IDs remain plotted without an ID label.")
        distance = known if mode == "Enter known spacing" else estimate(data[["x", "y", "z"]].to_numpy())
        st.caption(f"Valid rows: {len(data):,}. Spacing: {distance:.6g}" if distance is not None else f"Valid rows: {len(data):,}. Spacing unavailable: only one unique location.")
        if visible:
            datasets.append(dict(data=data, mapping=mappings, title=title or upload.name,
                                 variable=variable_title or mappings[3], symbol=symbol, spacing=distance,
                                 categorical=categorical, category_colors=category_colors, color_mode=color_mode,
                                 color=dataset_color, colorscale=colorscale, id_column=id_column, id_labels=id_labels))

if not datasets:
    st.info("Select files and configure their columns to create the plot.")
    st.stop()

st.subheader("Axis labels")
axis_fields = st.columns(3)
labels = []
for j, field in enumerate(axis_fields):
    default = " / ".join(dict.fromkeys(d["mapping"][j] for d in datasets))
    labels.append(field.text_input(f"{'XYZ'[j]} axis title", default))
st.caption("Defaults follow selected column names. Edit these titles to use a common coordinate label and units.")
sizes = marker_sizes([d["spacing"] for d in datasets], base_size)
fig = go.Figure()
summary = []
for i, (dataset, size) in enumerate(zip(datasets, sizes)):
    data = dataset["data"]
    shown = data if len(data) <= point_limit else data.sample(n=int(point_limit), random_state=42).sort_index()
    groups = [(category, shown.loc[shown.value == category]) for category in dataset["category_colors"]] if dataset["categorical"] else [(None, shown)]
    for category, points in groups:
        marker = dict(size=size, symbol=dataset["symbol"], opacity=opacity)
        if dataset["categorical"]:
            marker["color"] = dataset["category_colors"][category]
        elif dataset["color_mode"] == "Single dataset color":
            marker["color"] = dataset["color"]
        else:
            marker.update(color=points.value, colorscale=dataset["colorscale"],
                          cmin=float(data.value.min()), cmax=float(data.value.max()), showscale=True,
                          colorbar=dict(title=dict(text=dataset["variable"]),
                                        x=1.02 + 0.16*(i // 3), y=1-(i % 3)/3, yanchor="top", len=0.28, thickness=14))
        hover = []
        for row in points.itertuples():
            value = str(row.value) if dataset["categorical"] else f"{row.value:g}"
            info = html.escape(f"{dataset['variable']}: {value}")
            if dataset["id_column"] is not None:
                info += "<br>" + html.escape(f"{dataset['id_column']}: {row.id or '(blank)'}")
            hover.append(info)
        fig.add_trace(go.Scatter3d(
            x=points.x, y=points.y, z=points.z, mode="markers",
            name=html.escape(dataset["title"] + (f" — {category}" if category is not None else "")),
            legendgroup=f"dataset_{i}", text=hover,
            hovertemplate="X: %{x}<br>Y: %{y}<br>Z: %{z}<br>%{text}<extra>%{fullData.name}</extra>", marker=marker))
    if dataset["id_column"] is not None and dataset["id_labels"]:
        # Anchor at the highest elevation / shallowest positive depth, before sampling.
        anchors = data.loc[data.id != ""].sort_values("z", ascending=reverse_z).drop_duplicates("id")
        fig.add_trace(go.Scatter3d(x=anchors.x, y=anchors.y, z=anchors.z, mode="text",
            text=[html.escape(value) for value in anchors.id], textposition="top center",
            textfont=dict(size=12, color="#222222"), showlegend=False,
            legendgroup=f"dataset_{i}", hoverinfo="skip"))
    summary.append({"Dataset": dataset["title"], "Variable": dataset["variable"],
                    "Valid rows": len(data), "Shown rows": len(shown), "Spacing": dataset["spacing"],
                    "Marker": dataset["symbol"], "Size (px)": round(size, 2)})
    if len(shown) < len(data):
        st.warning(f"{dataset['title']}: displaying {len(shown):,} of {len(data):,} points. Increase the display limit to show more.")
extent = np.ptp(np.vstack([d["data"][["x", "y", "z"]].to_numpy() for d in datasets]), axis=0)
extent = np.maximum(extent, max(float(extent.max()) * 0.01, 1e-6))
extent[2] *= exaggeration
ratio = extent / extent.max()
fig.update_layout(height=780, margin=dict(l=0, r=180+100*((len(datasets)-1)//3), t=30, b=0),
    uirevision="keep-camera", legend=dict(orientation="h", y=1.08),
    scene=dict(xaxis=dict(title=labels[0], showgrid=True),
               yaxis=dict(title=labels[1], showgrid=True),
               zaxis=dict(title=labels[2], showgrid=True, autorange="reversed" if reverse_z else True),
               aspectmode="manual", aspectratio=dict(x=ratio[0], y=ratio[1], z=ratio[2])))
st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
st.caption("Drag to rotate; scroll to zoom; use the toolbar to pan or reset the camera. Hover for values and IDs. Category colors appear in the legend; continuous variables have separate color bars.")
st.dataframe(pd.DataFrame(summary), hide_index=True)
st.download_button("Download interactive HTML plot", fig.to_html(include_plotlyjs=True),
                   file_name="CPT_MASW_3D.html", mime="text/html")

st.subheader("Rotating GIF for GitHub")
st.caption("Exports a full 360° orbit with the current plot settings and displayed points. "
           "Browser camera movements and legend clicks are not captured; use the dataset controls above. "
           "Rendering may take several minutes. Chrome or Chromium is required.")
a, b, c = st.columns(3)
gif_frames = a.selectbox("Animation frames", [30, 60, 90], index=1)
gif_seconds = b.slider("Loop duration (seconds)", 3, 15, 6)
gif_dimensions = c.selectbox("GIF dimensions", ["800 × 600", "1000 × 750", "1200 × 900"])
gif_width, gif_height = [int(v.strip()) for v in gif_dimensions.split("×")]
gif_signature = hashlib.sha256((fig.to_json() + str((gif_frames, gif_seconds, gif_width, gif_height))).encode()).hexdigest()
if st.button("Generate rotating GIF"):
    from gif_export import rotating_gif
    bar = st.progress(0.0, text="Rendering camera orbit…")
    try:
        gif_bytes = rotating_gif(fig, gif_frames, gif_seconds, gif_width, gif_height,
                                progress=lambda value: bar.progress(value, text=f"Rendering: {round(value*100)}%"))
        st.session_state["rotating_gif"] = (gif_signature, gif_bytes)
    except Exception as error:
        st.error(f"GIF export failed: {error}")
        st.info("In VisualizeData run: python -m pip install -r requirements.txt. "
                "If Chrome is missing, run: plotly_get_chrome")
    finally:
        bar.empty()
saved_gif = st.session_state.get("rotating_gif")
if saved_gif and saved_gif[0] == gif_signature:
    st.image(saved_gif[1], caption="Rotating CPT / MASW preview")
    st.download_button("Download rotating GIF", saved_gif[1],
                       file_name="cpt_masw_demo.gif", mime="image/gif")
    st.caption(f"GIF size: {len(saved_gif[1])/1024/1024:.1f} MB. Add it to assets/cpt_masw_demo.gif in your GitHub repository.")
elif saved_gif:
    st.caption("Plot or animation settings changed. Generate a new GIF to match them.")
