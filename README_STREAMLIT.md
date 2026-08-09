# JobGenie AI — Streamlit Deployment

This version runs the JobGenie AI recommendation engine directly inside Streamlit. It does not require the Flask server.

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Community Cloud

- Repository: `Sudhir831883/JobGenie-AI`
- Branch: `main`
- Main file: `streamlit_app.py`

The app expects `dataset.csv` in the same directory as `streamlit_app.py`.
