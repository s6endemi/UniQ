"""UniQ — Unified Questionnaire Intelligence"""

import json, sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

# ── Design tokens ────────────────────────────────────────────────────────────
G = "#00C9A7"
G2 = "#00B396"
BG = "#F0F4F8"
CARD = "#FFFFFF"
TX = "#1B2559"
TX2 = "#718096"
BD = "#E2E8F0"
R = "#F56565"
B = "#4299E1"
P = "#9F7AEA"
O = "#ED8936"
COLORS = [G, B, P, O, R, "#38B2AC", "#E53E9C", "#48BB78", "#ECC94B", "#667EEA"]


def setup():
    st.set_page_config(page_title="UniQ", page_icon="⚕️", layout="wide")
    st.markdown(f"""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        *, html, body, [class*="st-"] {{ font-family: 'Inter', sans-serif !important; }}
        .stApp {{ background: {BG}; }}
        [data-testid="stSidebar"] {{ background: {TX}; }}
        [data-testid="stSidebar"] * {{ color: #CBD5E0 !important; }}
        [data-testid="stSidebar"] .stRadio label:hover {{ color: white !important; }}
        .block-container {{ padding: 1.5rem 2.5rem; max-width: 1200px; }}
        h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
        [data-testid="stHeading"] {{ color: {TX} !important; }}
        h1 {{ font-size: 1.5rem !important; font-weight: 800 !important;
              letter-spacing: -0.03em; margin-bottom: 0.5rem !important; }}
        h2 {{ font-size: 1.15rem !important; font-weight: 700 !important; }}
        h3 {{ font-size: 0.95rem !important; font-weight: 600 !important; }}
        p, span, li, div {{ color: {TX}; }}
        [data-testid="stMetric"] {{ background:{CARD}; padding:14px 18px; border-radius:12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04); border: 1px solid {BD}; }}
        [data-testid="stMetricValue"] {{ font-size:1.5rem !important; font-weight:800 !important; color:{TX} !important; }}
        [data-testid="stMetricLabel"] {{ font-size:0.7rem !important; font-weight:600 !important;
            color:{TX2} !important; text-transform:uppercase; letter-spacing:0.06em; }}
        .stTabs [data-baseweb="tab-list"] {{ gap:2px; background:{CARD}; border-radius:10px; padding:3px;
            border:1px solid {BD}; }}
        .stTabs [data-baseweb="tab"] {{ border-radius:8px; font-weight:500; font-size:0.82rem; padding:8px 16px; }}
        .stTabs [aria-selected="true"] {{ background:{G} !important; color:white !important; }}
        .stDownloadButton button {{ background:{CARD} !important; border:1px solid {BD} !important;
            border-radius:10px !important; font-weight:500 !important; }}
        .stDownloadButton button:hover {{ border-color:{G} !important; }}
        .stSelectbox > div > div {{ border-radius:10px !important; }}
        .stDataFrame {{ border-radius:10px !important; }}
        hr {{ border-color:{BD} !important; opacity:0.5; }}
        .streamlit-expanderHeader {{ background:{BG} !important; border-radius:10px !important;
            font-weight:600 !important; font-size:0.85rem !important; }}
        .stButton > button[kind="primary"] {{ background:linear-gradient(135deg, {G}, {G2}) !important;
            border:none !important; border-radius:10px !important; font-weight:600 !important;
            color:white !important; padding:8px 24px !important; }}
    </style>""", unsafe_allow_html=True)


def _s(n): return str(n).split("(")[0].split("-")[0].strip()

def _pc(val):
    try:
        r = json.loads(str(val))
        return r if isinstance(r, list) else []
    except: return []

def _layout(h=260, **kw):
    d = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font=dict(family="Inter", color=TX, size=11), height=h,
             margin=dict(l=0, r=0, t=0, b=0))
    d.update(kw)
    return d


@st.cache_data
def load():
    p = pd.read_csv(config.PATIENTS_TABLE)
    e = pd.read_csv(config.TREATMENT_EPISODES_TABLE)
    b = pd.read_csv(config.BMI_TIMELINE_TABLE)
    mh = pd.read_csv(config.MEDICATION_HISTORY_TABLE)
    m = pd.read_csv(config.MAPPING_TABLE)
    q = pd.read_csv(config.QUALITY_REPORT_TABLE)
    s = pd.read_csv(config.SURVEY_UNIFIED_TABLE, low_memory=False)
    if "date" in b.columns:
        b["date"] = pd.to_datetime(b["date"], errors="coerce", utc=True)
    for c in ["start_date", "latest_date"]:
        if c in e.columns:
            e[c] = pd.to_datetime(e[c], errors="coerce", utc=True)
    return p, e, b, mh, m, q, s


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY EXPLORER — the core product feature
# ═══════════════════════════════════════════════════════════════════════

def page_explorer(patients, episodes, bmi, survey, mapping):
    st.markdown("# Category Explorer")

    # ── Filters bar ──
    f1, f2, f3 = st.columns([2, 1, 1])

    cats = sorted(survey["clinical_category"].dropna().unique())
    cat_options = {c: f"{c} ({len(survey[survey['clinical_category']==c]):,})" for c in cats}

    with f1:
        selected_cat = st.selectbox("Category", cats,
            format_func=lambda c: cat_options[c])
    with f2:
        products = ["All"] + sorted(episodes["product"].apply(_s).unique())
        selected_prod = st.selectbox("Medication", products)
    with f3:
        genders = ["All", "Female", "Male"]
        selected_gender = st.selectbox("Gender", genders)

    # ── Filter data ──
    cat_data = survey[survey["clinical_category"] == selected_cat].copy()
    if selected_prod != "All":
        cat_data = cat_data[cat_data["product"].apply(_s) == selected_prod]
    if selected_gender != "All":
        cat_data = cat_data[cat_data["gender"] == selected_gender.lower()]

    # ── Category header ──
    n_rows = len(cat_data)
    n_patients = cat_data["user_id"].nunique()
    n_questions = mapping[mapping["clinical_category"] == selected_cat]["question_en"].nunique()
    n_ids = len(mapping[mapping["clinical_category"] == selected_cat])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Responses", f"{n_rows:,}")
    c2.metric("Patients", f"{n_patients:,}")
    c3.metric("Questions", f"{n_questions}")
    c4.metric("Question IDs", f"{n_ids}")

    st.markdown("")

    # ── Canonical answer distribution ──
    canonicals = []
    for _, r in cat_data.iterrows():
        for c in _pc(r.get("answer_canonical")):
            canonicals.append(c)

    if canonicals:
        counts = pd.Series(canonicals).value_counts()

        left, right = st.columns([3, 2])
        with left:
            st.markdown("### Normalized Answers")
            display = counts.head(12)
            colors_list = []
            for i, label in enumerate(display.index):
                if label in ("NONE", "NO", "NO_SIDE_EFFECTS", "NO_SEVERE_DISCONTINUATION"):
                    colors_list.append("#CBD5E0")
                else:
                    colors_list.append(COLORS[i % len(COLORS)])

            fig = go.Figure(go.Bar(
                y=display.index, x=display.values, orientation="h",
                marker=dict(color=colors_list, cornerradius=6),
                text=display.values, textposition="outside",
                textfont=dict(size=11, color=TX),
            ))
            fig.update_layout(**_layout(max(200, len(display) * 32),
                margin=dict(l=220, r=60, t=5, b=5)))
            st.plotly_chart(fig, use_container_width=True)

        with right:
            st.markdown("### By Medication")
            med_vals = []
            for _, r in cat_data.iterrows():
                for c in _pc(r.get("answer_canonical")):
                    med_vals.append({"answer": c, "med": _s(r["product"])})
            if med_vals:
                cross = pd.crosstab(pd.DataFrame(med_vals)["answer"],
                                    pd.DataFrame(med_vals)["med"])
                # Only show top answers
                top_answers = counts.head(8).index
                cross = cross.loc[cross.index.isin(top_answers)]
                st.dataframe(cross, use_container_width=True, height=min(350, len(cross) * 38 + 40))

    else:
        # Show raw answer_en for categories without canonical labels
        st.markdown("### Answers")
        raw_answers = cat_data["answer_en"].dropna().value_counts().head(12)
        if len(raw_answers) > 0:
            fig = go.Figure(go.Bar(
                y=raw_answers.index.str[:50], x=raw_answers.values, orientation="h",
                marker=dict(color=G, cornerradius=6),
                text=raw_answers.values, textposition="outside",
            ))
            fig.update_layout(**_layout(max(200, len(raw_answers) * 30),
                margin=dict(l=280, r=60, t=5, b=5)))
            st.plotly_chart(fig, use_container_width=True)

    # ── Questions in this category (expandable) ──
    st.markdown("---")
    with st.expander(f"Questions mapped to {selected_cat} ({n_questions} unique texts, {n_ids} IDs)"):
        cat_qs = mapping[mapping["clinical_category"] == selected_cat].drop_duplicates("question_en")
        for _, q in cat_qs.iterrows():
            n = int(q["duplicate_count"])
            st.markdown(f"- **[{n} IDs]** {q['question_en'][:120]}...")


# ═══════════════════════════════════════════════════════════════════════
# PATIENT VIEW
# ═══════════════════════════════════════════════════════════════════════

def page_patient(patients, bmi, med_hist, quality, survey, mapping):
    st.markdown("# Patient Record")

    # ── Selector ──
    f1, f2 = st.columns([1, 3])
    with f1:
        filt = st.selectbox("Filter", ["All", "Multi-Treatment", "Active"])
        f = patients.copy()
        if filt == "Multi-Treatment":
            f = f[f["total_treatments"] > 1]
        elif filt == "Active":
            f = f[f["active_treatments"] > 0]
    with f2:
        if len(f) == 0:
            st.info("No patients match filter")
            return
        pid = st.selectbox(f"Patient ({len(f)} found)", sorted(f["user_id"].unique()))

    pat = patients[patients["user_id"] == pid].iloc[0]

    # ── Profile ──
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Age", int(pat["current_age"]))
    c2.metric("Gender", pat["gender"].title())
    c3.metric("Medication", _s(pat["current_medication"]))
    c4.metric("Treatments", int(pat["total_treatments"]))
    tenure = pat["tenure_days"]
    c5.metric("Tenure", f"{int(tenure)}d" if pd.notna(tenure) and tenure > 0 else "New")

    # ── BMI + Meds ──
    left, right = st.columns(2)

    with left:
        st.markdown("### BMI")
        pb = bmi[bmi["user_id"] == pid].sort_values("date")
        if len(pb) > 0:
            latest = pb.iloc[-1]
            m1, m2 = st.columns(2)
            m1.metric("BMI", f"{latest['bmi']:.1f}")
            m2.metric("Weight", f"{latest['weight_kg']:.0f} kg")
            if len(pb) > 1:
                fig = go.Figure(go.Scatter(
                    x=pb["date"], y=pb["bmi"], mode="lines+markers+text",
                    marker=dict(size=8, color=G),
                    line=dict(color=G, width=2.5),
                    text=[f"{v:.1f}" for v in pb["bmi"]],
                    textposition="top center", textfont=dict(size=10, color=TX),
                    hovertemplate="%{x|%b %d, %Y}: BMI %{y:.1f}<extra></extra>",
                ))
                fig.update_layout(**_layout(200, margin=dict(l=40, r=10, t=25, b=30),
                    yaxis=dict(title="", gridcolor="#EDF2F7"),
                    xaxis=dict(gridcolor="#EDF2F7")))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption(f"Single measurement · {str(latest['date'])[:10]}")
        else:
            st.caption("No BMI data recorded")

    with right:
        st.markdown("### Medications")
        pm = med_hist[med_hist["user_id"] == pid].sort_values("started")
        for _, med in pm.iterrows():
            prod = _s(med["product"])
            dose = med["dosage"] if pd.notna(med["dosage"]) else ""
            if pd.isna(med["ended"]):
                st.markdown(f"""<div style="background:{G}15; border-left:3px solid {G};
                    padding:8px 12px; border-radius:0 8px 8px 0; margin-bottom:6px;">
                    <b>{prod}</b> <code>{dose}</code> — <span style="color:{G};">Active</span>
                </div>""", unsafe_allow_html=True)
            else:
                dur = int(med["duration_days"]) if pd.notna(med["duration_days"]) else "?"
                next_p = _s(med["next_product"]) if pd.notna(med["next_product"]) else None
                label = f"<b>{prod}</b> <code>{dose}</code> — {dur} days"
                if next_p:
                    label += f" → <b>{next_p}</b>"
                st.markdown(f"""<div style="background:#F7FAFC; border-left:3px solid {BD};
                    padding:8px 12px; border-radius:0 8px 8px 0; margin-bottom:6px;">
                    {label}</div>""", unsafe_allow_html=True)

        pq = quality[quality["user_id"] == pid]
        for _, issue in pq.iterrows():
            st.markdown(f"""<div style="background:#FFF5F5; border-left:3px solid {R};
                padding:8px 12px; border-radius:0 8px 8px 0; margin-bottom:6px;">
                <b>{issue['check_type']}</b>: {issue['description']}</div>""", unsafe_allow_html=True)

    # ── Unified record by category ──
    st.markdown("---")
    st.markdown("### Unified Record")

    ps = survey[survey["user_id"] == pid].copy()
    cat_sel = st.selectbox("Filter by category", ["All Categories"] + sorted(ps["clinical_category"].unique()))
    if cat_sel != "All Categories":
        ps = ps[ps["clinical_category"] == cat_sel]

    display = ps[["clinical_category", "question_en", "answer_en", "answer_canonical"]].copy()
    display["question_en"] = display["question_en"].str[:65]
    display["answer_canonical"] = display["answer_canonical"].apply(
        lambda x: ", ".join(_pc(x)) if pd.notna(x) else "—"
    )
    display.columns = ["Category", "Question", "Answer", "Canonical"]
    st.dataframe(display, use_container_width=True, height=300, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

def page_dashboard(patients, episodes, bmi, survey, mapping):
    st.markdown("# Dashboard")

    # ── Hero metrics ──
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Patients", f"{len(patients):,}")
    c2.metric("Treatments", f"{len(episodes):,}")
    active = (episodes["t_status"] == "in_progress").sum()
    c3.metric("Active", f"{active}")
    c4.metric("Categories", f"{mapping['clinical_category'].nunique()}")
    canonical_pct = survey["answer_canonical"].notna().mean() * 100
    c5.metric("Normalized", f"{canonical_pct:.0f}%")

    st.markdown("")

    # ── Row 1: Meds + BMI ──
    left, right = st.columns(2)

    with left:
        st.markdown("### Medication Distribution")
        prod = episodes["product"].apply(_s).value_counts()
        fig = go.Figure(go.Pie(
            labels=prod.index, values=prod.values, hole=0.6,
            marker=dict(colors=COLORS), textinfo="label+percent", textposition="outside",
            textfont=dict(size=11),
        ))
        fig.update_layout(**_layout(260))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("### Blood Pressure")
        bp = survey[survey["clinical_category"] == "BLOOD_PRESSURE_CHECK"]
        bp_vals = []
        for _, r in bp.iterrows():
            for c in _pc(r.get("answer_canonical")):
                bp_vals.append({"bp": c, "med": _s(r["product"])})
        if bp_vals:
            bp_df = pd.DataFrame(bp_vals)
            cross = pd.crosstab(bp_df["med"], bp_df["bp"], normalize="index") * 100
            fig = go.Figure()
            if "NORMAL" in cross.columns:
                fig.add_trace(go.Bar(name="Normal", y=cross.index, x=cross["NORMAL"],
                    orientation="h", marker=dict(color=G, cornerradius=6)))
            if "HIGH" in cross.columns:
                fig.add_trace(go.Bar(name="High", y=cross.index, x=cross["HIGH"],
                    orientation="h", marker=dict(color=R, cornerradius=6)))
            fig.update_layout(**_layout(220, barmode="stack", margin=dict(l=80, r=10, t=5, b=5),
                xaxis=dict(title="% of patients", ticksuffix="%"),
                legend=dict(orientation="h", y=1.12)))
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Side Effects + Compliance ──
    left, right = st.columns(2)

    with left:
        st.markdown("### Side Effects")
        se = survey[survey["clinical_category"] == "SIDE_EFFECT_REPORT"]
        se_vals = []
        for _, r in se.iterrows():
            for c in _pc(r.get("answer_canonical")):
                if c not in ("NONE", "NO_SIDE_EFFECTS", "NO_SEVERE_DISCONTINUATION"):
                    se_vals.append(c)
        if se_vals:
            se_counts = pd.Series(se_vals).value_counts().head(6)
            fig = go.Figure(go.Bar(
                y=se_counts.index, x=se_counts.values, orientation="h",
                marker=dict(color=R, cornerradius=6, opacity=0.85),
                text=se_counts.values, textposition="outside",
            ))
            fig.update_layout(**_layout(200, margin=dict(l=200, r=50, t=5, b=5)))
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("### Compliance")
        adh = survey[survey["clinical_category"] == "TREATMENT_ADHERENCE"]
        adh_vals = []
        for _, r in adh.iterrows():
            for c in _pc(r.get("answer_canonical")):
                adh_vals.append(c)
        if adh_vals:
            adh_counts = pd.Series(adh_vals).value_counts()
            compliant = sum(adh_counts.get(k, 0) for k in ["CONTINUOUS", "WEEKLY", "DAILY"])
            total = adh_counts.sum()
            rate = compliant / total * 100 if total else 0

            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=rate,
                number=dict(suffix="%", font=dict(size=36, color=TX)),
                gauge=dict(
                    axis=dict(range=[0, 100], tickwidth=0, tickcolor=BG),
                    bar=dict(color=G, thickness=0.7),
                    bgcolor=BD, borderwidth=0,
                    steps=[dict(range=[0, 60], color="#FED7D7"),
                           dict(range=[60, 85], color="#FEFCBF"),
                           dict(range=[85, 100], color="#C6F6D5")],
                ),
            ))
            fig.update_layout(**_layout(200, margin=dict(l=30, r=30, t=30, b=10)))
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Comorbidities + Outcomes ──
    left, right = st.columns(2)

    with left:
        st.markdown("### Top Comorbidities")
        mc = survey[survey["clinical_category"] == "MEDICAL_CONDITIONS"]
        mc_vals = []
        for _, r in mc.iterrows():
            for c in _pc(r.get("answer_canonical")):
                if c not in ("NONE", "NO", "YES"):
                    mc_vals.append(c)
        if mc_vals:
            mc_counts = pd.Series(mc_vals).value_counts().head(6)
            fig = go.Figure(go.Bar(
                y=mc_counts.index, x=mc_counts.values, orientation="h",
                marker=dict(color=P, cornerradius=6, opacity=0.85),
                text=mc_counts.values, textposition="outside",
            ))
            fig.update_layout(**_layout(200, margin=dict(l=180, r=50, t=5, b=5)))
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("### Treatment Outcomes")
        te = survey[survey["clinical_category"] == "TREATMENT_EFFECTIVENESS"]
        te_vals = []
        for _, r in te.iterrows():
            for c in _pc(r.get("answer_canonical")):
                te_vals.append(c)
        if te_vals:
            te_counts = pd.Series(te_vals).value_counts().head(6)
            fig = go.Figure(go.Bar(
                y=te_counts.index, x=te_counts.values, orientation="h",
                marker=dict(color=B, cornerradius=6, opacity=0.85),
                text=te_counts.values, textposition="outside",
            ))
            fig.update_layout(**_layout(200, margin=dict(l=200, r=50, t=5, b=5)))
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# PROCESS
# ═══════════════════════════════════════════════════════════════════════

def page_process(mapping, survey):
    st.markdown("# Process & Export")

    # ── Upload ──
    st.markdown("### Upload")
    uploaded = st.file_uploader("Drop your questionnaire data", type=["csv", "tsv", "txt"],
                                label_visibility="collapsed")
    if uploaded:
        content = uploaded.getvalue().decode("utf-8", errors="replace")
        sep = "\t" if content.split("\n")[0].count("\t") > content.split("\n")[0].count(",") else ","
        uploaded.seek(0)
        df = pd.read_csv(uploaded, sep=sep, low_memory=False)
        q_col = next((c for c in df.columns if "question" in c.lower()), None)
        id_col = next((c for c in df.columns if c.lower() in ("user_id", "patient_id")), None)
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(df):,}")
        c2.metric("Questions", f"{df[q_col].nunique() if q_col else '?'}")
        c3.metric("Entities", f"{df[id_col].nunique() if id_col else '?'}")
        st.info("To process: save to `data/raw/`, run `python pipeline.py`. The AI classifies questions and normalizes answers automatically.")
    else:
        st.caption("CSV, TSV — auto-detected. Or explore the pre-processed dataset below.")

    if mapping is None or survey is None:
        return

    # ── Pipeline Results ──
    st.markdown("---")
    st.markdown("### Pipeline Results")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Question IDs", f"{len(mapping):,}")
    c2.metric("Categories", f"{mapping['clinical_category'].nunique()}")
    det = len(survey) - survey["parse_method"].value_counts().get("free_text", 0)
    c3.metric("Deterministic", f"{det/len(survey)*100:.0f}%")
    c4.metric("Answers Normalized", f"{survey['answer_canonical'].notna().sum():,}")

    # ── Export ──
    st.markdown("---")
    st.markdown("### Export Unified Data")

    # Generate FHIR + JSON on demand
    from src.export_fhir import export_all_formats
    exports = export_all_formats()

    tab_csv, tab_json, tab_fhir = st.tabs(["CSV Tables", "JSON", "FHIR R4"])

    with tab_csv:
        st.caption("Individual unified tables — ready for analytics, BI tools, or databases.")
        csv_files = {
            "survey_unified.csv": ("Unified Survey", "All responses with clinical categories + canonical answer labels"),
            "patients.csv": ("Patient Profiles", "One row per patient — demographics, BMI, medication, tenure"),
            "bmi_timeline.csv": ("BMI Timeline", "Longitudinal BMI measurements"),
            "treatment_episodes.csv": ("Treatment Episodes", "One row per treatment with lifecycle data"),
            "medication_history.csv": ("Medication History", "Chronological medication journey per patient"),
            "mapping_table.csv": ("Question Mapping", "Question ID → clinical category"),
            "quality_report.csv": ("Quality Report", "Data quality issues detected"),
        }
        cols = st.columns(3)
        for i, (fn, (label, desc)) in enumerate(csv_files.items()):
            if fn in exports:
                with cols[i % 3]:
                    size_kb = len(exports[fn]) / 1024
                    st.download_button(f"↓ {label}", exports[fn], fn, use_container_width=True)
                    st.caption(f"{desc} · {size_kb:.0f} KB")

    with tab_json:
        st.caption("Complete unified dataset as a single JSON file — ideal for APIs and web applications.")
        if "unified_data.json" in exports:
            size_mb = len(exports["unified_data.json"]) / (1024 * 1024)
            st.download_button("↓ Unified Data (JSON)", exports["unified_data.json"],
                               "unified_data.json", mime="application/json", use_container_width=True)
            st.caption(f"All tables combined · {size_mb:.1f} MB")

        col1, col2 = st.columns(2)
        with col1:
            if "taxonomy.json" in exports:
                st.download_button("↓ Taxonomy", exports["taxonomy.json"],
                                   "taxonomy.json", mime="application/json", use_container_width=True)
                st.caption("AI-proposed clinical categories")
        with col2:
            if "answer_normalization.json" in exports:
                st.download_button("↓ Answer Map", exports["answer_normalization.json"],
                                   "answer_normalization.json", mime="application/json", use_container_width=True)
                st.caption("Answer value → canonical label mapping")

    with tab_fhir:
        st.caption("HL7 FHIR R4 Bundle — interoperable with any EHR system, hospital, or insurance platform.")
        if "fhir_bundle.json" in exports:
            bundle = json.loads(exports["fhir_bundle.json"])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Resources", f"{bundle['total']:,}")

            # Count by type
            rtypes = {}
            for entry in bundle["entry"]:
                rt = entry["resource"]["resourceType"]
                rtypes[rt] = rtypes.get(rt, 0) + 1
            c2.metric("Patient", f"{rtypes.get('Patient', 0):,}")
            c3.metric("Observation", f"{rtypes.get('Observation', 0):,}")
            c4.metric("MedicationStatement", f"{rtypes.get('MedicationStatement', 0):,}")

            size_mb = len(exports["fhir_bundle.json"]) / (1024 * 1024)
            st.download_button("↓ FHIR R4 Bundle", exports["fhir_bundle.json"],
                               "fhir_bundle.json", mime="application/json", use_container_width=True)
            st.caption(f"FHIR R4 collection bundle · {size_mb:.1f} MB · Patient + Observation (BMI) + MedicationStatement")

            with st.expander("Preview FHIR resource"):
                sample = bundle["entry"][0]["resource"]
                st.json(sample)

    # ── Auto-classify ──
    st.markdown("---")
    st.markdown("### Auto-Classify")
    st.caption("Test the AI — paste any new question and see it classified instantly.")
    new_q = st.text_input("", placeholder="e.g. Have you experienced changes in your sleep quality?",
                          label_visibility="collapsed")
    if new_q and st.button("Classify", type="primary"):
        if config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                cats = sorted(mapping["clinical_category"].unique())
                resp = client.messages.create(
                    model=config.LLM_MODEL, max_tokens=200,
                    messages=[{"role": "user", "content": f"Classify into ONE category.\nCategories: {', '.join(cats)}\nQuestion: {new_q}\nJSON: {{\"category\":\"...\",\"confidence\":\"high|medium|low\",\"reasoning\":\"...\"}}"}],
                )
                raw = resp.content[0].text
                j = raw.split("```json")[-1].split("```")[0] if "```" in raw else raw
                r = json.loads(j.strip())
                st.success(f"**{r['category']}** · {r.get('confidence','')} confidence")
                st.caption(r.get("reasoning", ""))
            except Exception as e:
                st.error(str(e))
        else:
            st.warning("Set ANTHROPIC_API_KEY for live classification")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    setup()

    st.sidebar.markdown(f"""<div style="padding:20px 16px 8px;">
        <span style="font-size:22px; font-weight:800; color:white;">Uni</span><span
        style="font-size:22px; font-weight:800; color:{G};">Q</span>
        <div style="font-size:0.65rem; color:#718096; margin-top:2px; letter-spacing:0.05em;">
            QUESTIONNAIRE INTELLIGENCE</div>
    </div>""", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    page = st.sidebar.radio("", ["Dashboard", "Explorer", "Patient", "Process"],
                            label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption("Wellster Hackathon 2025")

    try:
        p, e, b, mh, m, q, s = load()
    except FileNotFoundError:
        st.error("Run `python pipeline.py` first")
        return

    if page == "Dashboard":
        page_dashboard(p, e, b, s, m)
    elif page == "Explorer":
        page_explorer(p, e, b, s, m)
    elif page == "Patient":
        page_patient(p, b, mh, q, s, m)
    elif page == "Process":
        page_process(m, s)


if __name__ == "__main__":
    main()
