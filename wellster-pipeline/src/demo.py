"""UniQ — Unified Questionnaire Intelligence — Live Demo"""

import json, sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

G = "#00C9A7"; TX = "#1B2559"; TX2 = "#718096"; BD = "#E2E8F0"
R = "#F56565"; B = "#4299E1"; P = "#9F7AEA"; O = "#ED8936"
COLORS = [G, B, P, O, R, "#38B2AC", "#E53E9C", "#48BB78"]


def setup():
    st.set_page_config(page_title="UniQ", page_icon="⚕️", layout="wide")
    st.markdown(f"""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        *, [class*="st-"] {{ font-family: 'Inter', sans-serif !important; }}
        .stApp {{ background: #F7F9FC; }}
        [data-testid="stSidebar"] {{ background: {TX}; }}
        [data-testid="stSidebar"] * {{ color: #CBD5E0 !important; }}
        .block-container {{ padding: 2rem 2.5rem; max-width: 1100px; }}
        h1, h2, h3, p, span, li, div, label {{ color: {TX} !important; }}
        h1 {{ font-size: 1.6rem !important; font-weight: 800 !important; letter-spacing: -0.03em; }}
        h3 {{ font-size: 0.95rem !important; font-weight: 700 !important; }}
        [data-testid="stMetric"] {{ background:white; padding:14px 18px; border-radius:14px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04); border: 1px solid {BD}; }}
        [data-testid="stMetricValue"] {{ font-size:1.5rem !important; font-weight:800 !important; }}
        [data-testid="stMetricLabel"] {{ font-size:0.7rem !important; font-weight:600 !important;
            color:{TX2} !important; text-transform:uppercase; letter-spacing:0.06em; }}
        .stDownloadButton button {{ background:white !important; border:1px solid {BD} !important;
            border-radius:10px !important; font-weight:500 !important; }}
        .stButton > button[kind="primary"] {{ background:linear-gradient(135deg, {G}, #00B396) !important;
            border:none !important; border-radius:12px !important; font-weight:700 !important;
            color:white !important; padding:10px 28px !important; }}
        hr {{ border-color: {BD} !important; opacity: 0.4; }}
        .stTabs [data-baseweb="tab-list"] {{ gap:2px; background:white; border-radius:10px; padding:3px;
            border:1px solid {BD}; }}
        .stTabs [data-baseweb="tab"] {{ border-radius:8px; font-weight:500; font-size:0.82rem; padding:8px 16px; }}
        .stTabs [aria-selected="true"] {{ background:{G} !important; color:white !important; }}
        .streamlit-expanderHeader {{ background:white !important; border-radius:10px !important;
            font-weight:500 !important; font-size:0.85rem !important; padding-left:16px !important; }}
    </style>""", unsafe_allow_html=True)


def _s(n): return str(n).split("(")[0].split("-")[0].strip()
def _pc(v):
    try: r = json.loads(str(v)); return r if isinstance(r, list) else []
    except: return []
def _lay(h=260, **kw):
    d = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font=dict(family="Inter", color=TX, size=11), height=h,
             margin=dict(l=0,r=0,t=0,b=0)); d.update(kw); return d


# ═══════════════════════════════════════════════════════════════════════
# LOAD FROM FILES (for pre-computed data)
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data
def _load_from_files():
    """Load all results from output files."""
    r = {}
    r["mapping"] = pd.read_csv(config.MAPPING_TABLE)
    r["survey"] = pd.read_csv(config.SURVEY_UNIFIED_TABLE, low_memory=False)
    r["patients"] = pd.read_csv(config.PATIENTS_TABLE)
    r["episodes"] = pd.read_csv(config.TREATMENT_EPISODES_TABLE)
    r["bmi"] = pd.read_csv(config.BMI_TIMELINE_TABLE)
    if "date" in r["bmi"].columns:
        r["bmi"]["date"] = pd.to_datetime(r["bmi"]["date"], errors="coerce", utc=True)
    r["med_hist"] = pd.read_csv(config.MEDICATION_HISTORY_TABLE)
    r["quality"] = pd.read_csv(config.QUALITY_REPORT_TABLE)
    norm_path = config.OUTPUT_DIR / "answer_normalization.json"
    r["norm"] = json.loads(norm_path.read_text()) if norm_path.exists() else {}
    return r


# ═══════════════════════════════════════════════════════════════════════
# PIPELINE
# ═══════════════════════════════════════════════════════════════════════

def run_real_pipeline(uploaded_path: Path, status) -> dict:
    """Run the full pipeline for an uploaded file and return the UI results dict.

    Delegates to `src.engine.run_pipeline` — no separate orchestration. UI-only
    concerns (progress display, FHIR export, summary metrics) stay here.
    """
    from src.engine import run_pipeline

    status.markdown("⏳ **Running pipeline...**")
    artifacts = run_pipeline(
        raw_path=uploaded_path,
        on_progress=lambda msg: status.markdown(f"⏳ {msg}..."),
    )
    status.markdown("✅ Pipeline complete")

    # FHIR export (UI-specific side effect — not part of the core engine yet)
    from src.export_fhir import export_fhir_bundle
    bundle = export_fhir_bundle(
        artifacts.patients, artifacts.bmi_timeline,
        artifacts.medication_history, artifacts.survey,
    )
    fhir_path = config.OUTPUT_DIR / "fhir_bundle.json"
    fhir_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")

    # Compute UI summary metrics from artifacts
    raw = artifacts.raw
    survey = artifacts.survey
    mapping = artifacts.mapping
    norm = artifacts.answer_normalization

    worst = raw.groupby("question_en")["question_id"].nunique().sort_values(ascending=False)
    det = len(survey) - survey["parse_method"].value_counts().get("free_text", 0)

    return {
        # summary metrics
        "raw_rows": len(raw),
        "raw_qids": raw["question_id"].nunique(),
        "raw_patients": raw["user_id"].nunique(),
        "raw_products": raw["product"].nunique() if "product" in raw.columns else 0,
        "worst_text": worst.index[0][:70] if len(worst) > 0 else "",
        "worst_count": int(worst.iloc[0]) if len(worst) > 0 else 0,
        "n_categories": mapping["clinical_category"].nunique(),
        "n_texts": mapping["question_en"].nunique(),
        "det_pct": round(det / len(survey) * 100, 1) if len(survey) else 0.0,
        "answer_variants": sum(len(v) for v in norm.values()) if norm else 0,
        "answer_canonical": len({c for v in norm.values() for c in v.values()}) if norm else 0,
        "fhir_resources": bundle["total"],
        # dataframes (keys kept stable for existing UI pages)
        "mapping": mapping,
        "survey": survey,
        "patients": artifacts.patients,
        "episodes": artifacts.episodes,
        "bmi": artifacts.bmi_timeline,
        "med_hist": artifacts.medication_history,
        "quality": artifacts.quality_report,
        "norm": norm,
    }


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    setup()

    if "processed" not in st.session_state:
        st.session_state.processed = False
    if "results" not in st.session_state:
        st.session_state.results = None

    # ── NOT YET PROCESSED: show upload screen ──
    if not st.session_state.processed:
        _page_upload()
        return

    # ── PROCESSED: show sidebar + pages ──
    r = st.session_state.results
    # Ensure all data is loaded (handles both live pipeline and file-based)
    if r is None or "mapping" not in r:
        r = _load_from_files()
        st.session_state.results = r

    st.sidebar.markdown(f"""<div style="padding:20px 16px 8px;">
        <span style="font-size:22px; font-weight:800; color:white;">Uni</span><span
        style="font-size:22px; font-weight:800; color:{G};">Q</span>
        <div style="font-size:0.65rem; color:#718096; margin-top:2px; letter-spacing:0.05em;">
            QUESTIONNAIRE INTELLIGENCE</div>
    </div>""", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    page = st.sidebar.radio("", ["Results", "Explorer", "Patient", "Insights", "Export"],
                            label_visibility="collapsed")

    st.sidebar.markdown("---")
    if st.sidebar.button("New Upload", use_container_width=True):
        st.session_state.processed = False
        st.session_state.results = None
        st.rerun()

    if page == "Results":
        _page_results(r)
    elif page == "Explorer":
        _page_explorer(r)
    elif page == "Patient":
        _page_patient(r)
    elif page == "Insights":
        _page_insights(r)
    elif page == "Export":
        _page_export(r)


# ═══════════════════════════════════════════════════════════════════════
# UPLOAD + PROCESSING
# ═══════════════════════════════════════════════════════════════════════

def _page_upload():
    st.markdown(f"""<div style="text-align:center; margin:80px 0 20px;">
        <span style="font-size:3rem; font-weight:800; color:{TX};">Uni</span><span
        style="font-size:3rem; font-weight:800; color:{G};">Q</span>
        <div style="font-size:1.1rem; color:{TX2}; margin-top:8px;">Unified Questionnaire Intelligence</div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div style="text-align:center; color:{TX2}; max-width:500px; margin:0 auto 40px;">
        Drop your questionnaire data. We'll unify it.
    </div>""", unsafe_allow_html=True)

    uploaded = st.file_uploader("", type=["csv", "tsv", "txt"], label_visibility="collapsed")

    if uploaded:
        save_path = config.DATA_RAW_DIR / uploaded.name
        save_path.write_bytes(uploaded.getvalue())

        st.markdown("---")
        status = st.container()

        try:
            results = run_real_pipeline(save_path, status)

            st.markdown(f"""<div style="background:white; border:1px solid {BD}; border-radius:16px;
                padding:24px; text-align:center; margin:24px 0;">
                <div style="font-size:1.4rem; font-weight:800; color:{G};">Pipeline Complete</div>
                <div style="color:{TX2}; font-size:0.85rem; margin-top:8px;">
                    {results['raw_rows']:,} rows → {results['n_categories']} categories →
                    {results['answer_canonical']} canonical labels → {results['fhir_resources']:,} FHIR resources
                </div>
            </div>""", unsafe_allow_html=True)

            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("Explore Results", type="primary", use_container_width=True):
                    st.session_state.processed = True
                    st.session_state.results = results
                    st.rerun()

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            import traceback
            st.code(traceback.format_exc())

    st.markdown(f"""<div style="text-align:center; margin-top:40px; color:{TX2}; font-size:0.8rem;">
        CSV · TSV · Auto-detected</div>""", unsafe_allow_html=True)

    # Option to skip to pre-computed results
    if config.MAPPING_TABLE.exists():
        st.markdown("---")
        st.markdown(f"""<div style="text-align:center; color:{TX2}; font-size:0.85rem;">
            Or explore the pre-processed dataset:
        </div>""", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("View Existing Results", use_container_width=True):
                st.session_state.processed = True
                st.session_state.results = _load_from_files()
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# RESULTS — before/after proof
# ═══════════════════════════════════════════════════════════════════════

def _page_results(r):
    st.markdown("# Before → After")

    mapping = r["mapping"]
    survey = r["survey"]
    quality = r["quality"]
    norm = r.get("norm", {})

    # Problem — find worst duplicate
    deduped = mapping.drop_duplicates(subset="question_en")
    worst_row = deduped.sort_values("duplicate_count", ascending=False).iloc[0]
    worst_text = worst_row["question_en"][:70]
    worst_count = int(worst_row["duplicate_count"])

    st.markdown(f"""<div style="background:#FFF5F5; border:1px solid #FED7D7; border-radius:14px;
        padding:16px; margin-bottom:20px; text-align:center;">
        <span style="color:{R}; font-weight:600;">"{worst_text}..."</span> existed under
        <span style="color:{R}; font-weight:800; font-size:1.3rem;"> {worst_count}</span> different IDs
    </div>""", unsafe_allow_html=True)

    n_qids = mapping["question_id"].nunique()
    n_cats = mapping["clinical_category"].nunique()
    n_variants = sum(len(v) for v in norm.values()) if norm else 0
    n_canonical = len(set(c for v in norm.values() for c in v.values())) if norm else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Question IDs", f"{n_qids:,}", delta=f"→ {n_cats} categories")
    c2.metric("Answer Variants", f"{n_variants}", delta=f"→ {n_canonical} canonical")
    c3.metric("Quality Alerts", f"{len(quality):,}", delta="previously invisible")
    fhir_path = config.OUTPUT_DIR / "fhir_bundle.json"
    fhir_count = json.loads(fhir_path.read_text())["total"] if fhir_path.exists() else 0
    c4.metric("FHIR Resources", f"{fhir_count:,}", delta="auto-generated")

    st.markdown("")

    # Engine stats
    st.markdown(f"""<div style="background:white; border:1px solid {BD}; border-radius:16px; padding:20px; margin-bottom:20px;">
        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:16px; text-align:center;">
            <div><div style="font-size:1.8rem; font-weight:800; color:{G};">1</div>
                <div style="font-size:0.8rem; font-weight:600;">AI Call</div></div>
            <div><div style="font-size:1.8rem; font-weight:800; color:{B};">0</div>
                <div style="font-size:0.8rem; font-weight:600;">Hardcoded Rules</div></div>
            <div><div style="font-size:1.8rem; font-weight:800; color:{P};">{round((len(survey) - survey['parse_method'].value_counts().get('free_text', 0)) / len(survey) * 100, 1)}%</div>
                <div style="font-size:0.8rem; font-weight:600;">Deterministic</div></div>
            <div><div style="font-size:1.8rem; font-weight:800; color:{O};">$0.10</div>
                <div style="font-size:0.8rem; font-weight:600;">Total Cost</div></div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Normalization examples
    norm = r.get("norm", {})
    if norm:
        col1, col2 = st.columns(2)
        with col1:
            bp = norm.get("BLOOD_PRESSURE_CHECK", {})
            if bp:
                st.markdown("### Blood Pressure")
                for orig, canon in sorted(bp.items(), key=lambda x: x[1])[:8]:
                    color = G if canon == "NORMAL" else R
                    st.markdown(f"""<div style="font-size:0.75rem; padding:2px 0; display:flex; justify-content:space-between;">
                        <span style="color:{TX2};">{orig[:35]}</span>
                        <code style="color:{color}; font-weight:700;">{canon}</code></div>""", unsafe_allow_html=True)
        with col2:
            mc = norm.get("MEDICAL_CONDITIONS", {})
            if mc:
                st.markdown("### Free Text → Codes")
                shown = 0
                for orig, canon in sorted(mc.items(), key=lambda x: x[1]):
                    if canon not in ("NONE", "NO", "YES") and shown < 8:
                        st.markdown(f"""<div style="font-size:0.75rem; padding:2px 0; display:flex; justify-content:space-between;">
                            <span style="color:{TX2};">{orig[:30]}</span>
                            <code style="color:{P}; font-weight:700;">{canon}</code></div>""", unsafe_allow_html=True)
                        shown += 1

    # Categories
    st.markdown("---")
    st.markdown("### Categories Discovered")
    cat_stats = (deduped.groupby("clinical_category")
                 .agg(texts=("question_en", "nunique"), ids=("duplicate_count", "sum"))
                 .reset_index().sort_values("ids", ascending=False))
    for _, row in cat_stats.iterrows():
        cat = row["clinical_category"]
        data_rows = len(survey[survey["clinical_category"] == cat])
        label = f"{cat} — {row['texts']:.0f} questions, {data_rows:,} rows"
        with st.expander(label):
            for _, q_ in deduped[deduped["clinical_category"] == cat].iterrows():
                st.markdown(f"- [{int(q_['duplicate_count'])} IDs] {q_['question_en'][:90]}...")


# ═══════════════════════════════════════════════════════════════════════
# EXPLORER — filter by category × medication
# ═══════════════════════════════════════════════════════════════════════

def _page_explorer(r):
    survey, mapping, episodes = r["survey"], r["mapping"], r["episodes"]
    st.markdown("# Category Explorer")

    f1, f2, f3 = st.columns([2, 1, 1])
    cats = sorted(survey["clinical_category"].dropna().unique())
    with f1:
        cat = st.selectbox("Category", cats,
            format_func=lambda c: f"{c} ({len(survey[survey['clinical_category']==c]):,})")
    with f2:
        prods = ["All"] + sorted(episodes["product"].apply(_s).unique())
        prod = st.selectbox("Medication", prods)
    with f3:
        gen = st.selectbox("Gender", ["All", "Female", "Male"])

    data = survey[survey["clinical_category"] == cat].copy()
    if prod != "All": data = data[data["product"].apply(_s) == prod]
    if gen != "All": data = data[data["gender"] == gen.lower()]

    c1, c2, c3 = st.columns(3)
    c1.metric("Responses", f"{len(data):,}")
    c2.metric("Patients", f"{data['user_id'].nunique():,}")
    c3.metric("Question IDs", f"{len(mapping[mapping['clinical_category']==cat])}")

    canonicals = [c for _, row in data.iterrows() for c in _pc(row.get("answer_canonical"))]
    if canonicals:
        left, right = st.columns([3, 2])
        with left:
            counts = pd.Series(canonicals).value_counts().head(12)
            colors_l = ["#CBD5E0" if l in ("NONE","NO","NO_SIDE_EFFECTS","YES","NO_SEVERE_DISCONTINUATION")
                         else COLORS[i % len(COLORS)] for i, l in enumerate(counts.index)]
            fig = go.Figure(go.Bar(y=counts.index, x=counts.values, orientation="h",
                marker=dict(color=colors_l, cornerradius=6), text=counts.values, textposition="outside"))
            fig.update_layout(**_lay(max(200, len(counts)*30), margin=dict(l=220, r=50, t=5, b=5)))
            st.plotly_chart(fig, use_container_width=True)
        with right:
            mv = [{"a": c, "m": _s(row["product"])} for _, row in data.iterrows() for c in _pc(row.get("answer_canonical"))]
            if mv:
                cross = pd.crosstab(pd.DataFrame(mv)["a"], pd.DataFrame(mv)["m"])
                st.dataframe(cross.loc[cross.index.isin(counts.head(8).index)], use_container_width=True)
    else:
        raw_ans = data["answer_en"].dropna().value_counts().head(10)
        if len(raw_ans) > 0:
            fig = go.Figure(go.Bar(y=raw_ans.index.str[:45], x=raw_ans.values, orientation="h",
                marker=dict(color=G, cornerradius=6), text=raw_ans.values, textposition="outside"))
            fig.update_layout(**_lay(max(200, len(raw_ans)*30), margin=dict(l=250, r=50, t=5, b=5)))
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# PATIENT
# ═══════════════════════════════════════════════════════════════════════

def _page_patient(r):
    patients, bmi, med_hist, quality, survey = r["patients"], r["bmi"], r["med_hist"], r["quality"], r["survey"]
    if "date" in bmi.columns:
        bmi["date"] = pd.to_datetime(bmi["date"], errors="coerce", utc=True)

    st.markdown("# Patient Record")
    f1, f2 = st.columns([1, 3])
    with f1:
        filt = st.selectbox("Filter", ["All", "Multi-Treatment", "Active"])
        f = patients.copy()
        if filt == "Multi-Treatment": f = f[f["total_treatments"] > 1]
        elif filt == "Active": f = f[f["active_treatments"] > 0]
    with f2:
        if len(f) == 0: st.info("No results"); return
        pid = st.selectbox(f"Patient ({len(f)})", sorted(f["user_id"].unique()))

    pat = patients[patients["user_id"] == pid].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Age", int(pat["current_age"]))
    c2.metric("Gender", pat["gender"].title())
    c3.metric("Medication", _s(pat["current_medication"]))
    c4.metric("Treatments", int(pat["total_treatments"]))

    left, right = st.columns(2)
    with left:
        pb = bmi[bmi["user_id"] == pid].sort_values("date")
        if len(pb) > 0:
            latest = pb.iloc[-1]
            st.metric("BMI", f"{latest['bmi']:.1f}")
            if len(pb) > 1:
                fig = go.Figure(go.Scatter(x=pb["date"], y=pb["bmi"], mode="lines+markers",
                    marker=dict(size=7, color=G), line=dict(color=G, width=2)))
                fig.update_layout(**_lay(170, margin=dict(l=40, r=10, t=10, b=30),
                    yaxis=dict(gridcolor="#EDF2F7")))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No BMI data")
    with right:
        pm = med_hist[med_hist["user_id"] == pid]
        if "started" in pm.columns:
            pm = pm.sort_values("started")
        for _, med in pm.iterrows():
            active = pd.isna(med.get("ended"))
            status = "Active" if active else f"{int(med['duration_days'])}d" if pd.notna(med.get("duration_days")) else "?"
            clr = G if active else BD
            st.markdown(f"""<div style="border-left:3px solid {clr}; padding:5px 10px; margin-bottom:3px;
                border-radius:0 8px 8px 0; background:{'#F0FFF4' if active else 'white'}; font-size:0.85rem;">
                <b>{_s(med['product'])}</b> <code>{med['dosage'] if pd.notna(med.get('dosage')) else ''}</code> — {status}
            </div>""", unsafe_allow_html=True)
        for _, iss in quality[quality["user_id"] == pid].iterrows():
            st.markdown(f"""<div style="border-left:3px solid {R}; padding:5px 10px; background:#FFF5F5;
                border-radius:0 8px 8px 0; margin-bottom:3px; font-size:0.85rem;">
                <b>{iss['check_type']}</b>: {iss['description']}</div>""", unsafe_allow_html=True)

    st.markdown("---")
    ps = survey[survey["user_id"] == pid][["clinical_category", "question_en", "answer_en", "answer_canonical"]].copy()
    ps["question_en"] = ps["question_en"].str[:60]
    ps["answer_canonical"] = ps["answer_canonical"].apply(lambda x: ", ".join(_pc(x)) if pd.notna(x) else "—")
    ps.columns = ["Category", "Question", "Answer", "Canonical"]
    cat_sel = st.selectbox("Category", ["All"] + sorted(ps["Category"].unique()), key="pc")
    if cat_sel != "All": ps = ps[ps["Category"] == cat_sel]
    st.dataframe(ps, use_container_width=True, height=250, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
# INSIGHTS
# ═══════════════════════════════════════════════════════════════════════

def _page_insights(r):
    survey, patients, episodes, bmi, quality = r["survey"], r["patients"], r["episodes"], r["bmi"], r["quality"]

    st.markdown("# Insights")
    st.caption("What was invisible in the raw data")

    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Side Effects", "Compliance", "Conditions"])

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Patients", f"{len(patients):,}")
        c2.metric("Treatments", f"{len(episodes):,}")
        c3.metric("Active", f"{(episodes['t_status']=='in_progress').sum()}")
        c4.metric("Alerts", f"{len(quality):,}")
        left, right = st.columns(2)
        with left:
            prod = episodes["product"].apply(_s).value_counts()
            fig = go.Figure(go.Pie(labels=prod.index, values=prod.values, hole=0.55,
                marker=dict(colors=COLORS), textinfo="label+percent", textposition="outside", textfont=dict(size=10)))
            fig.update_layout(**_lay(270))
            st.plotly_chart(fig, use_container_width=True)
        with right:
            if len(bmi) > 0:
                bp = bmi.copy(); bp["med"] = bp["product_at_time"].apply(_s)
                fig = go.Figure()
                for i, med in enumerate(bp["med"].value_counts().head(4).index):
                    fig.add_trace(go.Box(y=bp[bp["med"]==med]["bmi"], name=med, marker_color=COLORS[i]))
                fig.update_layout(**_lay(270, showlegend=False, yaxis_title="BMI", margin=dict(l=50,r=10,t=10,b=40)))
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        vals = [{"e": c, "m": _s(row["product"])}
                for _, row in survey[survey["clinical_category"]=="SIDE_EFFECT_REPORT"].iterrows()
                for c in _pc(row.get("answer_canonical"))
                if c not in ("NONE","NO_SIDE_EFFECTS","NO_SEVERE_DISCONTINUATION")]
        if vals:
            df_ = pd.DataFrame(vals)
            left, right = st.columns([3, 2])
            with left:
                counts = df_["e"].value_counts().head(8)
                fig = go.Figure(go.Bar(y=counts.index, x=counts.values, orientation="h",
                    marker=dict(color=R, cornerradius=6), text=counts.values, textposition="outside"))
                fig.update_layout(**_lay(280, margin=dict(l=220, r=50, t=5, b=5)))
                st.plotly_chart(fig, use_container_width=True)
            with right:
                cross = pd.crosstab(df_["e"], df_["m"])
                st.dataframe(cross.loc[cross.index.isin(counts.head(6).index)], use_container_width=True)
        else:
            st.info("No side effect data")

    with tab3:
        vals = [c for _, row in survey[survey["clinical_category"]=="TREATMENT_ADHERENCE"].iterrows()
                for c in _pc(row.get("answer_canonical"))]
        if vals:
            counts = pd.Series(vals).value_counts()
            compliant = sum(counts.get(k,0) for k in ["CONTINUOUS","WEEKLY","DAILY"])
            rate = compliant / counts.sum() * 100 if counts.sum() > 0 else 0
            c1, c2 = st.columns([1, 2])
            with c1:
                fig = go.Figure(go.Indicator(mode="gauge+number", value=rate,
                    number=dict(suffix="%", font=dict(size=36, color=TX)),
                    gauge=dict(axis=dict(range=[0,100]), bar=dict(color=G, thickness=0.7), bgcolor=BD, borderwidth=0)))
                fig.update_layout(**_lay(200, margin=dict(l=30,r=30,t=30,b=10)))
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Compliance Rate")
            with c2:
                fig = go.Figure(go.Bar(y=counts.index, x=counts.values, orientation="h",
                    marker=dict(color=[G if v in ("CONTINUOUS","WEEKLY","DAILY") else O for v in counts.index], cornerradius=6),
                    text=counts.values, textposition="outside"))
                fig.update_layout(**_lay(300, margin=dict(l=200,r=50,t=5,b=5)))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No compliance data")

    with tab4:
        vals = [c for _, row in survey[survey["clinical_category"]=="MEDICAL_CONDITIONS"].iterrows()
                for c in _pc(row.get("answer_canonical")) if c not in ("NONE","NO","YES")]
        if vals:
            counts = pd.Series(vals).value_counts().head(10)
            fig = go.Figure(go.Bar(y=counts.index, x=counts.values, orientation="h",
                marker=dict(color=P, cornerradius=6), text=counts.values, textposition="outside"))
            fig.update_layout(**_lay(350, margin=dict(l=200,r=50,t=5,b=5)))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No condition data")


# ═══════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════

def _page_export(r):
    st.markdown("# Export")
    st.caption("Your unified data. Your format. Your infrastructure.")

    # Standards
    st.markdown(f"""<div style="background:white; border:1px solid {BD}; border-radius:14px; padding:20px; margin-bottom:24px;">
        <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:12px; text-align:center; font-size:0.75rem;">
            <div><div style="font-weight:800; color:{G}; font-size:1rem;">LOINC</div>BMI: 39156-5</div>
            <div><div style="font-weight:800; color:{B}; font-size:1rem;">ICD-10</div>Hypertension: I10</div>
            <div><div style="font-weight:800; color:{P}; font-size:1rem;">SNOMED</div>Nausea: 422587007</div>
            <div><div style="font-weight:800; color:{O}; font-size:1rem;">RxNorm</div>Tirzepatide: 2601734</div>
            <div><div style="font-weight:800; color:{R}; font-size:1rem;">FHIR R4</div>{r['fhir_resources']:,} resources</div>
        </div>
    </div>""", unsafe_allow_html=True)

    from src.export_fhir import export_all_formats
    exports = export_all_formats()

    tab1, tab2, tab3 = st.tabs(["CSV", "JSON", "FHIR R4"])

    with tab1:
        cols = st.columns(3)
        for i, (fn, label) in enumerate([
            ("survey_unified.csv","Unified Survey"), ("patients.csv","Patients"),
            ("bmi_timeline.csv","BMI Timeline"), ("treatment_episodes.csv","Treatments"),
            ("medication_history.csv","Medications"), ("mapping_table.csv","Question Map"),
            ("quality_report.csv","Quality Report")]):
            if fn in exports:
                size = len(exports[fn]) / 1024
                with cols[i % 3]:
                    st.download_button(f"↓ {label}", exports[fn], fn, use_container_width=True)
                    st.caption(f"{size:.0f} KB")

    with tab2:
        for fn, label in [("unified_data.json","Unified Data"),("taxonomy.json","Taxonomy"),
                          ("answer_normalization.json","Answer Map")]:
            if fn in exports:
                st.download_button(f"↓ {label}", exports[fn], fn, mime="application/json", use_container_width=True)

    with tab3:
        if "fhir_bundle.json" in exports:
            bundle = json.loads(exports["fhir_bundle.json"])
            c1, c2 = st.columns(2)
            c1.metric("FHIR Resources", f"{bundle['total']:,}")
            rtypes = {}
            for entry in bundle["entry"]:
                rt = entry["resource"]["resourceType"]
                rtypes[rt] = rtypes.get(rt, 0) + 1
            c2.metric("Resource Types", len(rtypes))
            st.download_button("↓ FHIR R4 Bundle", exports["fhir_bundle.json"],
                               "fhir_bundle.json", mime="application/json", use_container_width=True)
            with st.expander("Preview"):
                for entry in bundle["entry"]:
                    if entry["resource"]["resourceType"] == "Condition":
                        st.json(entry["resource"]); break

    # Auto-classify
    st.markdown("---")
    st.markdown("### Auto-Classify")
    st.caption("Paste any new question — classified against the existing taxonomy.")
    new_q = st.text_input("", placeholder="e.g. How has your sleep quality changed?", label_visibility="collapsed")
    if new_q and st.button("Classify", type="primary"):
        if config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                cats = sorted(r["mapping"]["clinical_category"].unique())
                resp = client.messages.create(model=config.LLM_MODEL, max_tokens=200,
                    messages=[{"role":"user","content":f"Classify into ONE category.\nCategories: {', '.join(cats)}\nQuestion: {new_q}\nJSON: {{\"category\":\"...\",\"confidence\":\"high|medium|low\",\"reasoning\":\"...\"}}"}])
                raw = resp.content[0].text
                j = raw.split("```json")[-1].split("```")[0] if "```" in raw else raw
                result = json.loads(j.strip())
                st.success(f"**{result['category']}** · {result.get('confidence','')}")
                st.caption(result.get("reasoning", ""))
            except Exception as e:
                st.error(str(e))


if __name__ == "__main__":
    main()
