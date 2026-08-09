from pathlib import Path

import fitz
import pandas as pd
import streamlit as st

from chatbot import get_chatbot_response
from model import JobRecommendationEngine


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset.csv"

st.set_page_config(
    page_title="JobGenie AI | Smart Job Matcher",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def load_engine():
    return JobRecommendationEngine(DATASET_PATH)


@st.cache_data(show_spinner=False)
def extract_pdf_text(pdf_bytes: bytes):
    if not pdf_bytes:
        raise ValueError("The uploaded PDF is empty.")
    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        raise ValueError("The uploaded file does not appear to be a valid PDF.")

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        text = "\n".join(page.get_text("text") for page in document).strip()
        pages = document.page_count

    if not text:
        raise ValueError(
            "No selectable text was found. Please upload a text-based PDF resume."
        )
    return text, pages


def inject_css():
    st.markdown(
        """
        <style>
        .stApp {
            background: #f7f8fc;
        }
        [data-testid="stHeader"] {
            background: rgba(247,248,252,0.85);
        }
        .hero {
            padding: 2rem 2.2rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #111827 0%, #312e81 52%, #2563eb 100%);
            color: white;
            margin-bottom: 1.4rem;
            box-shadow: 0 18px 50px rgba(37, 99, 235, .18);
        }
        .hero h1 {
            font-size: clamp(2rem, 5vw, 3.4rem);
            margin: 0 0 .45rem 0;
            line-height: 1.05;
        }
        .hero p {
            margin: 0;
            max-width: 780px;
            color: #dbeafe;
            font-size: 1.05rem;
        }
        .metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 1rem 1.1rem;
            min-height: 105px;
            box-shadow: 0 8px 28px rgba(15,23,42,.05);
        }
        .metric-label { color: #64748b; font-size: .85rem; }
        .metric-value { color: #111827; font-size: 1.7rem; font-weight: 750; margin-top: .2rem; }
        .job-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 1.2rem;
            margin: .65rem 0;
            box-shadow: 0 8px 25px rgba(15,23,42,.045);
        }
        .job-title { font-size: 1.15rem; font-weight: 750; color: #111827; }
        .job-meta { color: #64748b; font-size: .9rem; margin: .25rem 0 .75rem; }
        .skill {
            display: inline-block;
            padding: .3rem .55rem;
            margin: .18rem .2rem .18rem 0;
            border-radius: 999px;
            background: #eef2ff;
            color: #3730a3;
            font-size: .78rem;
            border: 1px solid #e0e7ff;
        }
        .skill-missing {
            display: inline-block;
            padding: .3rem .55rem;
            margin: .18rem .2rem .18rem 0;
            border-radius: 999px;
            background: #fff7ed;
            color: #c2410c;
            font-size: .78rem;
            border: 1px solid #fed7aa;
        }
        .section-title { font-size: 1.55rem; font-weight: 750; color: #111827; margin: .5rem 0 .15rem; }
        .muted { color: #64748b; }
        div[data-testid="stFileUploader"] section { border-radius: 18px; }
        .stButton > button, .stDownloadButton > button {
            border-radius: 12px;
            font-weight: 650;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def skill_pills(skills, missing=False):
    cls = "skill-missing" if missing else "skill"
    if not skills:
        st.markdown('<span class="muted">None detected</span>', unsafe_allow_html=True)
        return
    html = "".join(f'<span class="{cls}">{skill.title()}</span>' for skill in skills)
    st.markdown(html, unsafe_allow_html=True)


def metric(label, value):
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def build_report(result):
    lines = [
        "JOBGENIE AI — CAREER REPORT",
        "=" * 40,
        "",
        f"Dataset jobs: {result['summary']['dataset_rows']}",
        f"Detected resume skills: {result['summary']['resume_skill_count']}",
        f"Top match: {result['summary']['top_match']}%",
        f"Top category: {result['summary']['most_relevant_category']}",
        "",
        "DETECTED SKILLS",
        ", ".join(result["resume_skills"]) or "None",
        "",
        "TOP JOB MATCHES",
    ]
    for i, job in enumerate(result["recommendations"], 1):
        lines.extend(
            [
                f"{i}. {job['job_title']} — {job['match_percent']}%",
                f"   Category: {job['category']} | Location: {job['location']}",
                f"   Matched: {', '.join(job['matched_skills']) or 'None'}",
                f"   Missing: {', '.join(job['missing_skills']) or 'None'}",
                "",
            ]
        )
    return "\n".join(lines)


inject_css()

if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

try:
    engine = load_engine()
except Exception as exc:
    st.error(f"JobGenie could not load the dataset: {exc}")
    st.stop()

with st.sidebar:
    st.markdown("## 🎯 JobGenie AI")
    st.caption("Smart Resume Analysis & Job Recommendation")
    st.divider()
    st.markdown("### How it works")
    st.markdown(
        "1. Upload a text-based PDF resume.\n"
        "2. Extract skills with NLP keyword matching.\n"
        "3. Compare the resume with job descriptions using TF-IDF + cosine similarity.\n"
        "4. Review match scores and skill gaps."
    )
    st.divider()
    st.caption(f"Jobs in dataset: {len(engine.df):,}")
    st.caption("Model: TF-IDF + cosine similarity")

st.markdown(
    '<div class="hero"><h1>Find Your Dream Job with AI</h1>'
    '<p>Upload your resume, discover your strongest job matches, and see exactly which skills can move you closer to the roles you want.</p></div>',
    unsafe_allow_html=True,
)

upload_col, info_col = st.columns([1.25, 1])
with upload_col:
    uploaded = st.file_uploader(
        "Upload your resume (PDF)",
        type=["pdf"],
        help="Use a text-based PDF. Scanned image-only PDFs cannot be analysed without OCR.",
    )
    analyze = st.button("🚀 Analyze Resume", type="primary", use_container_width=True)

with info_col:
    st.markdown("### What you get")
    st.markdown(
        "- **Top 5 job recommendations**\n"
        "- **Match percentage** for each role\n"
        "- **Matched & missing skills**\n"
        "- **Searchable job database**\n"
        "- **Career Coach chatbot**\n"
        "- **Downloadable career report**"
    )

if analyze:
    if not uploaded:
        st.warning("Upload a PDF resume first.")
    else:
        try:
            with st.spinner("Reading resume and calculating job matches..."):
                pdf_bytes = uploaded.getvalue()
                text, pages = extract_pdf_text(pdf_bytes)
                result = engine.recommend(text, top_n=5)
                result["_pages"] = pages
                result["_filename"] = uploaded.name
                st.session_state.resume_text = text
                st.session_state.analysis = result
                st.session_state.chat_messages = []
            st.success(f"Analysis complete — {pages} page(s), {len(text):,} characters processed.")
        except Exception as exc:
            st.error(f"Resume analysis failed: {exc}")

result = st.session_state.analysis

if result:
    st.markdown('<div class="section-title">Resume Overview</div>', unsafe_allow_html=True)
    st.caption(f"Analysed file: {result.get('_filename', 'resume.pdf')}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric("Top Match", f"{result['summary']['top_match']}%")
    with c2:
        metric("Resume Skills", result["summary"]["resume_skill_count"])
    with c3:
        metric("Jobs Compared", f"{result['summary']['dataset_rows']:,}")
    with c4:
        metric("Top Category", result["summary"]["most_relevant_category"])

    tabs = st.tabs(["🎯 Recommendations", "🧩 Skill Gap", "📊 Analytics", "🔎 Job Search", "🤖 Career Coach"])

    with tabs[0]:
        st.markdown('<div class="section-title">Top Job Matches</div>', unsafe_allow_html=True)
        for rank, job in enumerate(result["recommendations"], 1):
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"### {rank}. {job['job_title']}")
                    st.caption(f"{job['category']}  •  {job['location']}")
                with right:
                    st.metric("Match", f"{job['match_percent']}%")
                st.write(job["job_description"])
                st.markdown("**Matched skills**")
                skill_pills(job["matched_skills"])
                st.markdown("**Missing skills**")
                skill_pills(job["missing_skills"], missing=True)
                if job["suggestions"]:
                    with st.expander("How to close this gap"):
                        for suggestion in job["suggestions"]:
                            st.write(f"• {suggestion}")

        st.download_button(
            "⬇️ Download Career Report",
            data=build_report(result),
            file_name="jobgenie_career_report.txt",
            mime="text/plain",
            use_container_width=False,
        )

    with tabs[1]:
        st.markdown('<div class="section-title">Skill Gap Analysis</div>', unsafe_allow_html=True)
        st.caption("Skills detected in your resume are compared with the requirements of your top matches.")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Your detected skills")
            skill_pills(result["resume_skills"])
        with col2:
            missing = result["chart_data"]["pie"]["labels"]
            _ = missing
            missing_skills = []
            for job in result["recommendations"]:
                for skill in job["missing_skills"]:
                    if skill not in missing_skills:
                        missing_skills.append(skill)
            st.markdown("#### Skills to improve")
            skill_pills(missing_skills, missing=True)

        st.markdown("#### Priority learning targets")
        if missing_skills:
            gap_rows = []
            for skill in missing_skills:
                jobs_count = sum(skill in job["missing_skills"] for job in result["recommendations"])
                gap_rows.append({"Skill": skill.title(), "Top matches needing it": jobs_count})
            gap_df = pd.DataFrame(gap_rows).sort_values("Top matches needing it", ascending=False)
            st.dataframe(gap_df, use_container_width=True, hide_index=True)
        else:
            st.success("No major skill gaps were detected across the top matches.")

    with tabs[2]:
        st.markdown('<div class="section-title">Match Analytics</div>', unsafe_allow_html=True)
        labels = result["chart_data"]["bar"]["labels"]
        scores = result["chart_data"]["bar"]["scores"]
        if labels:
            chart_df = pd.DataFrame({"Job": labels, "Match %": scores}).set_index("Job")
            st.bar_chart(chart_df, y="Match %", height=360)

        pie_labels = result["chart_data"]["pie"]["labels"]
        pie_values = result["chart_data"]["pie"]["values"]
        pie_df = pd.DataFrame({"Skill status": pie_labels, "Count": pie_values}).set_index("Skill status")
        st.markdown("#### Skill coverage")
        st.bar_chart(pie_df, y="Count", height=280)

    with tabs[3]:
        st.markdown('<div class="section-title">Smart Job Search</div>', unsafe_allow_html=True)
        query = st.text_input("Search jobs by title, skill, category, or keyword", placeholder="e.g. Python Data Analyst")
        if query.strip():
            results = engine.search_jobs(query.strip(), limit=8)
            if results:
                for job in results:
                    with st.container(border=True):
                        st.markdown(f"### {job['job_title']}")
                        st.caption(f"{job['category']}  •  {job['location']}  •  relevance score {job['score']}")
                        st.write(job["job_description"])
                        skill_pills(job["skills"])
            else:
                st.info("No matching jobs found. Try a broader title, skill, or category.")
        else:
            st.caption("Try searches such as Python, Data Analyst, Power BI, Machine Learning, or Product Manager.")

    with tabs[4]:
        st.markdown('<div class="section-title">AI Career Coach</div>', unsafe_allow_html=True)
        st.caption("The coach uses your current resume analysis as context. It is rule-based, not a generative LLM.")

        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        prompt = st.chat_input("Ask about your matches, skills, resume, interviews, or roadmap...")
        if prompt:
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            context = {
                "resume_skills": result.get("resume_skills", []),
                "recommendations": result.get("recommendations", []),
            }
            reply = get_chatbot_response(prompt, context)
            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            st.rerun()
else:
    st.markdown("### Start with your resume")
    st.info("Upload a PDF above and click **Analyze Resume**. Results will appear here without requiring a separate Flask server.")
