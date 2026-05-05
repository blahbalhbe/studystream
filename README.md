# StudyStream Generator

A Streamlit study guide generator using Google Gemini (`google-genai`). Upload text, PDF, or DOCX notes and generate a structured study guide.

## Files

- `streamlit_app.py` — main Streamlit application
- `requirements.txt` — Python dependencies

## Setup

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run the app:

```bash
python -m streamlit run streamlit_app.py
```

## Usage

- Enter your Gemini API key in the sidebar
- Choose a model and difficulty level
- Upload `.txt`, `.pdf`, or `.docx` notes, or paste notes directly
- Click **Generate Study Guide**

## Notes

- If `streamlit` is not recognized, run it through Python:

```bash
python -m streamlit run streamlit_app.py
```

- The app uses `google-genai`; if you see deprecation warnings for `google.generativeai`, switch to `google-genai`.
