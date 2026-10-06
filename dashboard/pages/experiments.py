from dashboard.adapters.experiment_view import FIGURES, TABLES, load_json

def render_experiments(st, snapshot, presentation=False):
    st.title("Experiments & Results")
    st.caption("Read-only frozen evidence summary")
    c1,c2,c3=st.columns(3)
    c1.metric("V1 research runtime", "802 passed")
    c2.metric("V2 agentic runtime", "84 passed · 1 skipped")
    c3.metric("Industrial runtime", "66 passed")
    st.subheader("Software lifecycle benchmark — 100 non-mutating simulation assessments")
    c1,c2=st.columns(2); c1.metric("Median", "0.0081 ms"); c2.metric("P95", "0.0129 ms")
    st.caption("This is not PLC, real-time control, or plant-response latency.")

    figures, tables = st.tabs(["Publication figures", "Publication tables"])
    with figures:
        title, image_path, caption_path = st.selectbox("Select figure", FIGURES, format_func=lambda item: item[0])
        if image_path.exists():
            st.image(str(image_path), caption=title, use_container_width=True)
            if caption_path.exists():
                st.caption(caption_path.read_text())
            st.download_button("Download PNG", image_path.read_bytes(), file_name=image_path.name, mime="image/png")
        else:
            st.warning("Frozen figure artifact is unavailable.")
    with tables:
        title, path = st.selectbox("Select table", TABLES, format_func=lambda item: item[0])
        if path.exists():
            data = load_json(path)
            st.dataframe(data, use_container_width=True)
            st.download_button("Download JSON", path.read_bytes(), file_name=path.name, mime="application/json")
        else:
            st.warning("Frozen table artifact is unavailable.")
