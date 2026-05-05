import streamlit as st
import google.generativeai as genai
from docx import Document
import PyPDF2
import json
import io

# 1. Setup Page Configuration
st.set_page_config(
    page_title="StudyStream Generator", 
    page_icon="📚", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Custom CSS for StudyStream Branding
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Playfair+Display:wght@700&display=swap');
    
    .stApp {
        background-color: #f8fafc;
    }
    .main-title {
        font-family: 'Playfair Display', serif;
        color: #0f172a;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        color: #64748b;
        margin-bottom: 2rem;
    }
    div.stButton > button:first-child {
        background-color: #0284c7;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1rem;
        font-weight: 600;
        width: 100%;
        transition: all 0.2s;
    }
    div.stButton > button:first-child:hover {
        background-color: #0369a1;
        border: none;
        color: white;
        transform: translateY(-1px);
    }
    .guide-card {
        background-color: white;
        padding: 2rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }
    .term-badge {
        background-color: #f1f5f9;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #0284c7;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 3. Helper Functions for File Parsing
def parse_pdf(file):
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        return "\n".join([page.extract_text() or "" for page in pdf_reader.pages])
    except Exception as e:
        return f"Error reading PDF: {e}"

def parse_docx(file):
    try:
        doc = Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        return f"Error reading DOCX: {e}"

# 4. App Sidebar for Configuration
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3429/3429153.png", width=80)
    st.title("StudyStream Config")
    
    api_key = st.text_input("Gemini API Key", type="password", help="Get your key at aistudio.google.com")
    
    model_choice = st.selectbox("Intelligence Model", 
        ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro", "gemini-pro"],
        help="If one fails with 404, try the -latest version."
    )
    
    topic = st.text_input("Subject Topic", value="Chemistry: Wave Properties")
    difficulty = st.selectbox("Target Level", ["Introductory", "Intermediate (MYP Grade 10)", "Advanced (IB DP)"])
    
    st.divider()
    st.subheader("Upload Material")
    uploaded_files = st.file_uploader("Drop notes or PDFs here", type=['txt', 'pdf', 'docx'], accept_multiple_files=True)

# 5. Main UI Layout
st.markdown("<h1 class='main-title'>StudyStream <span style='color: #0284c7;'>v2</span></h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>The Development of a Driven Study Guide Generator • 2026 Academic Supporter</p>", unsafe_allow_html=True)

col_input, col_output = st.columns([1, 1.5], gap="large")

with col_input:
    st.subheader("Source Material")
    
    # Auto-read uploaded files into the text area
    file_content = ""
    if uploaded_files:
        for f in uploaded_files:
            if f.name.endswith('.pdf'): file_content += parse_pdf(f)
            elif f.name.endswith('.docx'): file_content += parse_docx(f)
            else: file_content += f.read().decode("utf-8")
            file_content += "\n\n"

    notes = st.text_area("Paste your notes below:", value=file_content, height=450, placeholder="Paste your raw textbook notes or classroom scribbles here...")
    
    if st.button("✨ Generate Study Guide"):
        if not api_key:
            st.warning("Please enter your API Key in the sidebar first!")
        elif not notes.strip():
            st.error("I need some notes to work with!")
        else:
            with st.spinner("Analyzing text and structuring your guide..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(model_choice)
                    
                    prompt = f"""
                    Role: Academic Supporter
                    Task: Transform notes into a high-quality study guide.
                    Topic: {topic}
                    Level: {difficulty}
                    Notes: {notes}

                    Instructions:
                    1. Provide a 3-sentence executive summary.
                    2. Clean at least 5 key terms with clear definitions.
                    3. Write 3 practice questions with tips/hints.
                    4. Response format: STRICT JSON.
                    JSON Keys: 'summary' (str), 'keyTerms' (list of {{term, definition}}), 'practiceQuestions' (list of {{question, hint}})
                    """
                    
                    response = model.generate_content(prompt)
                    # Cleaning response in case of markdown blocks
                    raw_json = response.text.replace('```json', '').replace('```', '').strip()
                    st.session_state.guide_data = json.loads(raw_json)
                    st.balloons()
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    if "404" in str(e):
                        st.info("💡 Try changing the model in the sidebar to 'gemini-1.5-flash-latest'.")

with col_output:
    st.subheader("Interactive Preview")
    
    if "guide_data" in st.session_state:
        data = st.session_state.guide_data
        
        # Guide Header
        st.markdown(f"""
        <div class='guide-card'>
            <h2 style='margin-top:0;'>{topic}</h2>
            <p style='color:#0284c7; font-weight:bold; font-size:0.8rem;'>LEVEL: {difficulty.upper()}</p>
            <hr>
            <h4>01 / Summary</h4>
            <p style='color:#475569; line-height:1.6;'>{data.get('summary')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        
        # Terms
        st.markdown("#### 02 / Key Terminology")
        cols = st.columns(2)
        for i, term in enumerate(data.get('keyTerms', [])):
            with cols[i % 2]:
                st.markdown(f"""
                <div class='term-badge'>
                    <strong style='color:#0f172a;'>{term.get('term')}</strong><br>
                    <span style='font-size:0.85rem; color:#64748b;'>{term.get('definition')}</span>
                </div>
                """, unsafe_allow_html=True)
        
        # Assessment
        st.markdown("#### 03 / Practice Assessment")
        for i, q in enumerate(data.get('practiceQuestions', [])):
            with st.expander(f"Question {i+1}: {q.get('question')[:50]}..."):
                st.write(q.get('question'))
                st.info(f"**Hint:** {q.get('hint')}")
        
        # Download Action
        st.divider()
        dl_text = f"STUDY GUIDE: {topic}\n\nSUMMARY\n{data.get('summary')}\n\nKEY TERMS\n"
        for t in data.get('keyTerms', []): dl_text += f"- {t.get('term')}: {t.get('definition')}\n"
        
        st.download_button("📥 Download Guide as Text", data=dl_text, file_name="studystream_guide.txt")
        
    else:
        st.info("Waiting for input... Upload your notes and click generate to build your guide!")

# Footer
st.markdown("<br><hr><p style='text-align: center; color: #94a3b8; font-size: 0.7rem;'>© 2026 Scientific Innovation Project • Created by Ameen Fotovat</p>", unsafe_allow_html=True)