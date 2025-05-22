import streamlit as st
import os
import uuid
import tempfile
import subprocess
from urllib.parse import urlparse
from moviepy.editor import VideoFileClip
from openai import OpenAI
import json
import whisper

# Set page configuration
st.set_page_config(
    page_title="English Accent Detector",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #424242;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .result-container {
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-top: 2rem;
    }
    .accent-label {
        font-size: 1.8rem;
        font-weight: bold;
        color: #1E88E5;
    }
    .confidence-bar {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .summary-text {
        line-height: 1.6;
    }
    .stButton button {
        background-color: #1E88E5;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        width: 100%;
    }
    .upload-section, .url-section {
        background-color: #f5f5f5;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .footer {
        text-align: center;
        margin-top: 3rem;
        color: #757575;
        font-size: 0.8rem;
    }
    .stProgress > div > div {
        background-color: #1E88E5;
    }
</style>
""", unsafe_allow_html=True)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Load Whisper model for transcription
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

whisper_model = load_whisper_model()

# Function to process video file
def process_video(video_file):
    # Save uploaded video to a temporary file
    video_filename = f"temp_{uuid.uuid4()}.mp4"
    with open(video_filename, "wb") as f:
        f.write(video_file.getbuffer())

    # Extract audio
    audio_filename = video_filename.replace(".mp4", ".wav")
    try:
        with st.spinner("Extracting audio from video..."):
            clip = VideoFileClip(video_filename)
            clip.audio.write_audiofile(audio_filename, codec='pcm_s16le', fps=16000, verbose=False, logger=None)
    except Exception as e:
        st.error(f"Audio extraction failed: {str(e)}")
        return None

    # Transcribe audio using Whisper
    try:
        with st.spinner("Transcribing audio..."):
            result = whisper_model.transcribe(audio_filename)
            transcription = result["text"]
    except Exception as e:
        st.error(f"Transcription failed: {str(e)}")
        return None

    # Use LLM to analyze accent
    try:
        with st.spinner("Analyzing accent..."):
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert in linguistics and accent detection. Analyze the following transcription and determine the English accent (American, British, Australian, Indian, etc.). If the transcription is too short or lacks distinctive features, make your best guess based on available cues and note the limitations in your summary. Provide your answer as a JSON with fields 'accent', 'confidence' (0-1), and 'summary' (a brief explanation of why you identified this accent, including key linguistic features)."},
                    {"role": "user", "content": f"Transcription: {transcription}"}
                ]
            )
            
            accent_analysis = json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Accent analysis failed: {str(e)}")
        return None

    # Clean up temp files
    os.remove(video_filename)
    os.remove(audio_filename)

    return accent_analysis, transcription

# Function to process YouTube URL
def process_youtube_url(url):
    # Generate unique filenames
    video_filename = f"temp_{uuid.uuid4()}.mp4"
    
    url = url.strip()
    parsed_url = urlparse(url)
    
    # Check if it's a YouTube URL
    is_youtube = "youtube.com" in parsed_url.netloc or "youtu.be" in parsed_url.netloc
    
    if not is_youtube:
        st.error("Please enter a valid YouTube URL")
        return None
    
    try:
        with st.spinner("Downloading audio from YouTube..."):
            # Use yt-dlp to download YouTube videos
            temp_dir = tempfile.gettempdir()
            output_template = os.path.join(temp_dir, f"yt_video_{uuid.uuid4()}")
            
            # Download best audio format
            subprocess.run([
                "yt-dlp", 
                "-f", "bestaudio", 
                "-o", f"{output_template}.%(ext)s",
                "--extract-audio",
                "--audio-format", "wav",
                url
            ], check=True)
            
            # Find the downloaded file
            audio_filename = None
            for file in os.listdir(temp_dir):
                if file.startswith(os.path.basename(output_template)) and file.endswith(".wav"):
                    audio_filename = os.path.join(temp_dir, file)
                    break
            
            if not audio_filename:
                st.error("Failed to download YouTube audio")
                return None
    except Exception as e:
        st.error(f"Failed to process YouTube video: {str(e)}")
        return None

    # Transcribe audio using Whisper
    try:
        with st.spinner("Transcribing audio..."):
            result = whisper_model.transcribe(audio_filename)
            transcription = result["text"]
    except Exception as e:
        st.error(f"Transcription failed: {str(e)}")
        return None

    # Use LLM to analyze accent
    try:
        with st.spinner("Analyzing accent..."):
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert in linguistics and accent detection. Analyze the following transcription and determine the English accent (American, British, Australian, Indian, etc.). If the transcription is too short or lacks distinctive features, make your best guess based on available cues and note the limitations in your summary. Provide your answer as a JSON with fields 'accent', 'confidence' (0-1), and 'summary' (a brief explanation of why you identified this accent, including key linguistic features)."},
                    {"role": "user", "content": f"Transcription: {transcription}"}
                ]
            )
            
            accent_analysis = json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Accent analysis failed: {str(e)}")
        return None

    # Clean up temp files
    if audio_filename and os.path.exists(audio_filename):
        os.remove(audio_filename)

    return accent_analysis, transcription

# Header
st.markdown("<h1 class='main-header'>English Accent Detector</h1>", unsafe_allow_html=True)
st.markdown("Analyze speech samples to identify English accents with AI-powered detection.")

# Create tabs for different input methods
tab1, tab2 = st.tabs(["Upload Video", "YouTube URL"])

with tab1:
    st.markdown("<div class='upload-section'>", unsafe_allow_html=True)
    st.markdown("<h2 class='sub-header'>Upload a Video File</h2>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "mov", "avi", "mkv"])
    
    process_upload = False
    if uploaded_file is not None:
        process_upload = st.button("Detect Accent", key="process_upload")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("<div class='url-section'>", unsafe_allow_html=True)
    st.markdown("<h2 class='sub-header'>Enter YouTube URL</h2>", unsafe_allow_html=True)
    video_url = st.text_input("YouTube video URL", placeholder="https://www.youtube.com/watch?v=...")
    
    url_button = False
    if video_url:
        url_button = st.button("Detect Accent", key="process_url")
    st.markdown("</div>", unsafe_allow_html=True)

# Process uploaded file
if process_upload and uploaded_file is not None:
    result = process_video(uploaded_file)
    if result:
        accent_analysis, transcription = result
        
        st.markdown("<div class='result-container'>", unsafe_allow_html=True)
        st.markdown("<h2 class='sub-header'>Accent Analysis Result</h2>", unsafe_allow_html=True)
        
        st.markdown(f"<p class='accent-label'>{accent_analysis['accent']}</p>", unsafe_allow_html=True)
        
        st.markdown("<div class='confidence-bar'>", unsafe_allow_html=True)
        st.progress(accent_analysis['confidence'])
        st.markdown(f"Confidence: {int(accent_analysis['confidence'] * 100)}%")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<h3>Analysis Summary</h3>", unsafe_allow_html=True)
        st.markdown(f"<p class='summary-text'>{accent_analysis['summary']}</p>", unsafe_allow_html=True)
        
        with st.expander("Show Transcription"):
            st.write(transcription)
        
        st.markdown("</div>", unsafe_allow_html=True)

# Process YouTube URL
if url_button and video_url:
    result = process_youtube_url(video_url)
    if result:
        accent_analysis, transcription = result
        
        st.markdown("<div class='result-container'>", unsafe_allow_html=True)
        st.markdown("<h2 class='sub-header'>Accent Analysis Result</h2>", unsafe_allow_html=True)
        
        st.markdown(f"<p class='accent-label'>{accent_analysis['accent']}</p>", unsafe_allow_html=True)
        
        st.markdown("<div class='confidence-bar'>", unsafe_allow_html=True)
        st.progress(accent_analysis['confidence'])
        st.markdown(f"Confidence: {int(accent_analysis['confidence'] * 100)}%")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<h3>Analysis Summary</h3>", unsafe_allow_html=True)
        st.markdown(f"<p class='summary-text'>{accent_analysis['summary']}</p>", unsafe_allow_html=True)
        
        with st.expander("Show Transcription"):
            st.write(transcription)
        
        st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("<div class='footer'>English Accent Detector • Powered by AI</div>", unsafe_allow_html=True)