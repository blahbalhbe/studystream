import streamlit as st
import google.generativeai as genai
from docx import Document
import PyPDF2
import json
import io
import re

# 1. Page Configuration
st.set_page_config(
    page_title="StudyStream | Powered by Gemini",
    page_icon="📚",
    layout="wide",
)

# 2. Modern Academic Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #fcfcfc;
    }

    .header-style {
        font-size: 3rem;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: -0.05em;
        margin-bottom: 0px;
    }
    
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        background-color: #e0f2fe;
        color: #0369a1;
    }

    /* Term Card */
    .term-card {
        background: white;
        padding: 1.2rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 3. Helpers
def parse_files(uploaded_files):
    text = ""
    for f in uploaded_files:
        try:
            if f.name.endswith('.pdf'):
                pdf = PyPDF2.PdfReader(f)
                text += f"\n\n--- {f.name} ---\n" + "\n".join([p.extract_text() or "" for p in pdf.pages])
            elif f.name.endswith('.docx'):
                doc = Document(f)
                text += f"\n\n--- {f.name} ---\n" + "\n".join([p.text for p in doc.paragraphs])
            else:
                text += f"\n\n--- {f.name} ---\n" + f.read().decode("utf-8")
        except Exception as e:
            st.error(f"Error parsing {f.name}: {e}")
    return text

def extract_json(text):
    try:
        # Clean up Markdown formatting if Gemini wraps it in ```json
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(text)
    except:
        return None

# 4. Sidebar Workspace
with st.sidebar:
    st.title("📚 StudyStream Pro")
    st.markdown("<span class='status-badge'>Powered by Streamlit</span>", unsafe_allow_html=True)
    st.divider()
    
    api_key_input = st.text_input("Gemini API Key", type="password", help="Get one at aistudio.google.com")
    
    # Using 'latest' is usually safest for 404 errors
    model_id = st.selectbox(
        "Model Version",
        ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
        help="If you get 404, stick to 'gemini-1.5-flash-latest'."
    )
    
    topic = st.text_input("Topic Name", "Molecular Chemistry")
    level = st.select_slider("Level", ["Intro", "Mid", "Pro"], value="Mid")
    
    st.divider()
    uploaded_docs = st.file_uploader("Upload Source Documents", type=["pdf", "docx", "txt"], accept_multiple_files=True)
    
    if st.button("Reset Session"):
        st.session_state.clear()
        st.rerun()

# 5. Application UI
st.markdown("<h1 class='header-style'>StudyStream Generator</h1>", unsafe_allow_html=True)
st.write("Generate professional-grade study materials from your notes.")

left, right = st.columns([1, 1.2], gap="large")

with left:
    st.markdown("### 📥 Source Notes")
    if len(source_content) > 15000:
        st.warning("⚠️ High character count. If you encounter a '429 Quota' error, try selecting a smaller portion of text.")
        
    source_content = st.text_area(
        "Paste or Preview Content",
        value=source_content,
        height=400,
        placeholder="Upload files in sidebar or paste text here..."
    )
    
    if st.button("Generate Study Guide", use_container_width=True):
        if not api_key_input:
            st.error("Missing API Key.")
        elif not source_content.strip():
            st.warning("Please provide notes.")
        else:
            with st.spinner(f"Gemini {model_id} is analyzing..."):
                try:
                    genai.configure(api_key=api_key_input)
                    model = genai.GenerativeModel(model_id)
                    
                    prompt = f"""
                    Role: Expert Academic Tutor.
                    Topic: {topic}
                    Level: {level}
                    Context: {source_content}

                    Task: Create a precise study guide. 
                    Format: Result MUST be ONLY a JSON object. No conversational filler or markdown code blocks.
                    Structure:
                    {{ 
                      "summary": "3-5 high-level sentences",
                      "keyTerms": [{{ "term": "term name", "definition": "clear academic definition" }}],
                      "practiceQuestions": [{{ "question": "the question", "hint": "a helpful clue" }}] 
                    }}
                    """
                    
                    response = model.generate_content(prompt)
                    data = extract_json(response.text)
                    
                    if data:
                        st.session_state.study_data = data
                        st.session_state.study_topic = topic
                        st.success("Analysis Complete!")
                    else:
                        st.error("Gemini didn't return a valid format. Try again.")
                        st.code(response.text)
                        
                except Exception as e:
                    err = str(e)
                    if "429" in err:
                        st.error("Quota Exceeded (429). The Free Tier has limits. Wait 60 seconds and try again, or use a smaller amount of text.")
                    elif "404" in err:
                        st.error(f"Model {model_id} not found (404). Try 'gemini-1.5-flash-latest'.")
                    else:
                        st.error(f"Error: {e}")

with right:
    st.markdown("### 🚀 Generated Result")
    if "study_data" in st.session_state:
        res = st.session_state.study_data
        
        st.markdown(f"#### {st.session_state.study_topic}")
        st.write("---")
        
        st.markdown("##### 📖 Summary")
        st.write(res.get('summary', 'No summary generated.'))
        
        st.markdown("##### 🏷️ Key Terms")
        t_col1, t_col2 = st.columns(2)
        for i, item in enumerate(res.get('keyTerms', [])):
            col = t_col1 if i % 2 == 0 else t_col2
            col.markdown(f"""
            <div class='term-card'>
                <strong style='color: #0369a1;'>{item.get('term')}</strong><br/>
                <small>{item.get('definition')}</small>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("##### 📝 Practice")
        for i, q in enumerate(res.get('practiceQuestions', [])):
            with st.expander(f"Question {i+1}"):
                st.write(q.get('question'))
                st.caption(f"Hint: {q.get('hint')}")
                
        # Export
        export_txt = f"TOPIC: {st.session_state.study_topic}\n\nSUMMARY\n{res.get('summary')}\n\nKEY TERMS\n"
        for t in res.get('keyTerms', []): export_txt += f"- {t.get('term')}: {t.get('definition')}\n"
        
        st.download_button("📥 Download txt", data=export_txt, file_name="studyguide.txt")
    else:
        st.info("Your study guide will appear here after generation.")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #94a3b8; font-size: 0.8rem;'>
    Made with StudyStream • Built with <b>Streamlit</b> & <b>Google Gemini</b> 
</div>
""", unsafe_allow_html=True)
