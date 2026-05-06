import streamlit as st
import google.generativeai as genai
from docx import Document
import PyPDF2
import json
import os
import re
import time
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================
CONFIG = {
    "MAX_CHARS": 15000,
    "WARN_CHARS": 12000,
    "MAX_RETRIES": 3,
    "RETRY_DELAY": 2,  # seconds
    "TEXTAREA_HEIGHT": 400,
    "ICON_SIZE": 80,
    "MIN_TERMS": 5,
    "NUM_QUESTIONS": 3,
}

# ============================================================================
# 1. PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="StudyStream | Powered by Gemini",
    page_icon="📚",
    layout="wide",
)

# ============================================================================
# 2. CUSTOM STYLING
# ============================================================================
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

    .term-card {
        background: white;
        padding: 1.2rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
        transition: all 0.2s ease;
    }
    
    .term-card:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }
    
    .char-count-good {
        color: #16a34a;
    }
    
    .char-count-warn {
        color: #f97316;
    }
    
    .char-count-bad {
        color: #dc2626;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 3. HELPER FUNCTIONS
# ============================================================================

def parse_files(uploaded_files: List) -> str:
    """
    Parse uploaded files (PDF, DOCX, TXT) and return combined text.
    
    Args:
        uploaded_files: List of uploaded file objects from Streamlit
        
    Returns:
        str: Combined text from all files, with file names as headers
    """
    text = ""
    if not uploaded_files:
        return text
        
    for f in uploaded_files:
        try:
            if f.name.endswith('.pdf'):
                pdf = PyPDF2.PdfReader(f)
                pages_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
                text += f"\n\n--- {f.name} ---\n{pages_text}"
            elif f.name.endswith('.docx'):
                doc = Document(f)
                para_text = "\n".join([p.text for p in doc.paragraphs])
                text += f"\n\n--- {f.name} ---\n{para_text}"
            else:  # .txt or other text files
                try:
                    content = f.read().decode("utf-8")
                except UnicodeDecodeError:
                    # Fallback to latin-1 encoding
                    f.seek(0)
                    content = f.read().decode("latin-1")
                text += f"\n\n--- {f.name} ---\n{content}"
        except Exception as e:
            st.error(f"❌ Error parsing {f.name}: {str(e)}")
    
    return text


def extract_json(text: str) -> Optional[Dict]:
    """
    Extract and parse JSON from text, handling markdown code blocks.
    
    Args:
        text: Raw text response from API
        
    Returns:
        Dict: Parsed JSON object, or None if parsing fails
    """
    try:
        # Try to extract JSON object from markdown code blocks
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            json_str = match.group()
            return json.loads(json_str)
        # If no match, try direct parsing
        return json.loads(text)
    except (json.JSONDecodeError, AttributeError) as e:
        st.debug(f"JSON parsing failed: {e}")
        return None


def validate_input(api_key: str, content: str) -> tuple:
    """
    Validate API key and content before generation.
    
    Args:
        api_key: Gemini API key
        content: User-provided notes/content
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not api_key or not api_key.strip():
        return False, "❌ Missing API Key. Get one at aistudio.google.com"
    
    if not content or not content.strip():
        return False, "❌ Please provide notes or upload documents."
    
    if len(content) > CONFIG["MAX_CHARS"]:
        return False, f"❌ Content too long ({len(content)} chars). Max: {CONFIG['MAX_CHARS']} chars."
    
    return True, ""


def get_char_count_status(char_count: int) -> tuple:
    """
    Get character count status indicator.
    
    Args:
        char_count: Number of characters
        
    Returns:
        tuple: (emoji, css_class)
    """
    if char_count < CONFIG["WARN_CHARS"]:
        return "🟢", "char-count-good"
    elif char_count < CONFIG["MAX_CHARS"]:
        return "🟡", "char-count-warn"
    else:
        return "🔴", "char-count-bad"


def call_gemini_with_retry(model, prompt: str, max_retries: int = CONFIG["MAX_RETRIES"]):
    """
    Call Gemini API with exponential backoff retry logic.
    
    Args:
        model: Gemini GenerativeModel instance
        prompt: Prompt text
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response object from API
        
    Raises:
        Exception: If all retries fail
    """
    for attempt in range(1, max_retries + 1):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            err_str = str(e)
            
            # Don't retry on client errors (401, 403, 404)
            if any(code in err_str for code in ["401", "403", "404"]):
                raise
            
            # Retry on server errors (429, 500, 503)
            if attempt < max_retries and any(code in err_str for code in ["429", "500", "503"]):
                wait_time = CONFIG["RETRY_DELAY"] ** attempt
                with st.spinner(f"⏳ Attempt {attempt}/{max_retries} failed. Retrying in {wait_time}s..."):
                    time.sleep(wait_time)
                continue
            
            raise


# ============================================================================
# 4. SIDEBAR CONFIGURATION
# ============================================================================
with st.sidebar:
    st.title("📚 StudyStream Pro")
    st.markdown("<span class='status-badge'>Powered by Streamlit</span>", unsafe_allow_html=True)
    st.divider()
    
    # API Key with env fallback
    api_key_input = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.getenv("GEMINI_API_KEY", ""),
        help="Get one at aistudio.google.com or set GEMINI_API_KEY env var"
    )
    
    # Model selection
    model_id = st.selectbox(
        "Model Version",
        ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"],
        help="Use 'gemini-1.5-flash-latest' if you encounter 404 errors."
    )
    
    # Topic and difficulty
    topic = st.text_input("Topic Name", "Molecular Chemistry")
    level = st.select_slider(
        "Difficulty Level",
        ["Introductory", "Intermediate", "Advanced"],
        value="Intermediate"
    )
    
    st.divider()
    
    # File upload
    st.subheader("📤 Upload Documents")
    uploaded_docs = st.file_uploader(
        "Upload source materials (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Supports multiple files"
    )
    
    # Session reset
    if st.button("🔄 Reset Session", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ============================================================================
# 5. MAIN APPLICATION UI
# ============================================================================
st.markdown("<h1 class='header-style'>StudyStream Generator</h1>", unsafe_allow_html=True)
st.write("Transform your notes into structured study guides powered by AI.")

# Two-column layout
left_col, right_col = st.columns([1, 1.2], gap="large")

# ============================================================================
# LEFT COLUMN: INPUT SECTION
# ============================================================================
with left_col:
    st.markdown("### 📥 Source Material")
    
    # Parse uploaded files
    parsed_text = parse_files(uploaded_docs)
    
    # Text area with auto-populated content
    source_content = st.text_area(
        "Paste or Preview Content",
        value=parsed_text,
        height=CONFIG["TEXTAREA_HEIGHT"],
        placeholder="Upload files in sidebar or paste text here...",
        help="Enter or paste your study notes, textbook excerpts, or classroom notes."
    )
    
    # Character count with status indicator
    char_count = len(source_content)
    emoji, css_class = get_char_count_status(char_count)
    st.markdown(f"<p class='{css_class}'>{emoji} {char_count:,} / {CONFIG['MAX_CHARS']:,} characters</p>", unsafe_allow_html=True)
    
    if char_count > CONFIG["WARN_CHARS"]:
        st.warning("⚠️ Large content detected. If you hit rate limits (429), try a smaller selection.")
    
    # Generate button
    if st.button("✨ Generate Study Guide", use_container_width=True, type="primary"):
        is_valid, error_msg = validate_input(api_key_input, source_content)
        
        if not is_valid:
            st.error(error_msg)
        else:
            with st.spinner(f"🤖 {model_id} is analyzing your content..."):
                try:
                    # Configure and initialize Gemini
                    genai.configure(api_key=api_key_input)
                    model = genai.GenerativeModel(model_id)
                    
                    # Craft the prompt
                    prompt = f"""You are an expert academic tutor specializing in creating comprehensive study guides.

Topic: {topic}
Difficulty Level: {level}
Source Material:
{source_content}

Task: Create a high-quality study guide in the following JSON format ONLY. Return ONLY valid JSON with no markdown code blocks or extra text.

{{
  "summary": "Write 3-5 comprehensive sentences summarizing the key concepts",
  "keyTerms": [
    {{"term": "Term name", "definition": "Clear, academic definition (1-2 sentences)"}},
    {{"term": "Term name", "definition": "Clear, academic definition (1-2 sentences)"}}
  ],
  "practiceQuestions": [
    {{"question": "A thoughtful practice question", "hint": "A helpful hint or clue"}},
    {{"question": "Another practice question", "hint": "Another helpful hint"}}
  ]
}}

Ensure:
- Minimum {CONFIG['MIN_TERMS']} key terms
- Exactly {CONFIG['NUM_QUESTIONS']} practice questions
- All definitions are academic and precise
- Hints are useful but not spoilers
"""
                    
                    # Call Gemini with retry logic
                    response = call_gemini_with_retry(model, prompt)
                    
                    # Parse response
                    data = extract_json(response.text)
                    
                    if data and isinstance(data, dict):
                        if "summary" in data and "keyTerms" in data and "practiceQuestions" in data:
                            st.session_state.study_data = data
                            st.session_state.study_topic = topic
                            st.session_state.study_level = level
                            st.success("✅ Study guide generated successfully!")
                            st.balloons()
                        else:
                            st.error("❌ Response missing required fields. Try again.")
                            with st.expander("🔍 View raw response"):
                                st.code(response.text)
                    else:
                        st.error("❌ Failed to parse Gemini response as JSON.")
                        with st.expander("🔍 View raw response"):
                            st.code(response.text if hasattr(response, 'text') else str(response))
                
                except Exception as e:
                    err_str = str(e)
                    
                    # Categorized error messages
                    if "429" in err_str:
                        st.error("⏱️ Rate limit exceeded (429). Free tier has limits. Please wait 60 seconds and try again with a smaller text sample.")
                    elif "404" in err_str:
                        st.error(f"❌ Model '{model_id}' not found (404). Try 'gemini-1.5-flash-latest' instead.")
                    elif "401" in err_str or "UNAUTHENTICATED" in err_str:
                        st.error("🔐 Authentication failed (401). Check your API key.")
                    elif "403" in err_str:
                        st.error("🚫 Permission denied (403). Your API key may lack necessary permissions.")
                    else:
                        st.error(f"❌ Generation failed: {err_str}")
                    
                    with st.expander("💡 Troubleshooting tips"):
                        st.write("""
                        - Verify API key is correct
                        - Check if model is available in your region
                        - Try a shorter text sample
                        - Use 'gemini-1.5-flash-latest' as fallback
                        - Wait 60+ seconds before retrying after rate limit
                        """)

# ============================================================================
# RIGHT COLUMN: OUTPUT SECTION
# ============================================================================
with right_col:
    st.markdown("### 🚀 Generated Study Guide")
    
    if "study_data" in st.session_state:
        data = st.session_state.study_data
        topic_display = st.session_state.get("study_topic", "Study Guide")
        level_display = st.session_state.get("study_level", "Intermediate")
        
        # Header
        st.markdown(f"#### {topic_display}")
        st.markdown(f"**Difficulty:** {level_display}")
        st.divider()
        
        # Summary section
        st.markdown("##### 📖 Executive Summary")
        st.write(data.get('summary', 'No summary generated.'))
        
        st.write("")
        
        # Key terms section
        st.markdown("##### 🏷️ Key Terminology")
        term_col1, term_col2 = st.columns(2)
        
        for i, item in enumerate(data.get('keyTerms', [])):
            col = term_col1 if i % 2 == 0 else term_col2
            with col:
                st.markdown(f"""
                <div class='term-card'>
                    <strong style='color: #0369a1;'>{item.get('term', 'N/A')}</strong><br/>
                    <small style='line-height: 1.5;'>{item.get('definition', 'No definition')}</small>
                </div>
                """, unsafe_allow_html=True)
        
        st.write("")
        
        # Practice questions section
        st.markdown("##### 📝 Practice Questions")
        questions = data.get('practiceQuestions', [])
        
        if questions:
            for i, q in enumerate(questions, 1):
                with st.expander(f"Question {i}: {q.get('question', 'No question')[:60]}..."):
                    st.write(f"**Q:** {q.get('question')}")
                    st.info(f"**💡 Hint:** {q.get('hint')}")
        else:
            st.info("No practice questions generated.")
        
        st.write("")
        st.divider()
        
        # Download section
        export_text = f"STUDY GUIDE: {topic_display}\nLevel: {level_display}\n\n{'='*50}\n\nSUMMARY\n{data.get('summary')}\n\n{'='*50}\n\nKEY TERMS\n"
        for term_item in data.get('keyTerms', []):
            export_text += f"• {term_item.get('term')}: {term_item.get('definition')}\n\n"
        
        export_text += f"{'='*50}\n\nPRACTICE QUESTIONS\n"
        for i, q in enumerate(data.get('practiceQuestions', []), 1):
            export_text += f"{i}. {q.get('question')}\n   Hint: {q.get('hint')}\n\n"
        
        # Sanitize filename
        safe_topic = topic_display.replace(" ", "_")[:30]
        filename = f"studyguide_{safe_topic}.txt"
        
        st.download_button(
            "📥 Download as Text File",
            data=export_text,
            file_name=filename,
            use_container_width=True
        )
    else:
        st.info("👈 Generate a study guide to see results here!")

# ============================================================================
# FOOTER
# ============================================================================
st.divider()
st.markdown("""
<div style='text-align: center; color: #94a3b8; font-size: 0.8rem;'>
    <p>Built with <b>Streamlit</b> ✨ Powered by <b>Google Gemini</b> 🤖</p>
    <p>StudyStream © 2026 | <a href='https://github.com/blahbalhbe/studystream' target='_blank'>View on GitHub</a></p>
</div>
""", unsafe_allow_html=True)
