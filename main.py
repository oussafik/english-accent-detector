from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import uuid
import requests
from moviepy.editor import VideoFileClip
import whisper
from openai import OpenAI
import json
from pydantic import BaseModel
from urllib.parse import urlparse
import subprocess
import tempfile

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Whisper model for transcription
whisper_model = whisper.load_model("base")

# Configure OpenAI with the new client format
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class VideoURL(BaseModel):
    url: str

@app.post("/detect-accent-url/")
async def detect_accent_url(video_data: VideoURL):
    # Generate unique filenames
    video_filename = f"temp_{uuid.uuid4()}.mp4"
    
    url = video_data.url.strip()
    parsed_url = urlparse(url)
    
    # Check if it's a YouTube URL
    is_youtube = "youtube.com" in parsed_url.netloc or "youtu.be" in parsed_url.netloc
    
    if is_youtube:
        try:
            # Use yt-dlp to download YouTube videos (including Shorts)
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
                return JSONResponse(status_code=500, content={"error": "Failed to download YouTube audio"})
            
            # Skip video processing since we already have audio
            video_filename = None
            
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed to process YouTube video: {str(e)}"})
    else:
        # For non-YouTube URLs, use the original method
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(video_filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Extract audio
            audio_filename = video_filename.replace(".mp4", ".wav")
            try:
                clip = VideoFileClip(video_filename)
                clip.audio.write_audiofile(audio_filename, codec='pcm_s16le', fps=16000, verbose=False, logger=None)
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": f"Audio extraction failed: {str(e)}"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed to download video: {str(e)}"})

    # Transcribe audio using Whisper
    try:
        result = whisper_model.transcribe(audio_filename)
        transcription = result["text"]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Transcription failed: {str(e)}"})

    # Use LLM to analyze accent based on transcription
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in linguistics and accent detection. Analyze the following transcription and determine the English accent (American, British, Australian, Indian, etc.). Provide your answer as a JSON with fields 'accent', 'confidence' (0-1), and 'summary' (a brief explanation of why you identified this accent, including key linguistic features)."},
                {"role": "user", "content": f"Transcription: {transcription}"}
            ]
        )
        
        accent_analysis = json.loads(response.choices[0].message.content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Accent analysis failed: {str(e)}"})

    # Clean up temp files
    if video_filename and os.path.exists(video_filename):
        os.remove(video_filename)
    if audio_filename and os.path.exists(audio_filename):
        os.remove(audio_filename)

    return accent_analysis

# Keep the original file upload endpoint
@app.post("/detect-accent/")
async def detect_accent(video: UploadFile = File(...)):
    # Save uploaded video to a temporary file
    video_filename = f"temp_{uuid.uuid4()}.mp4"
    with open(video_filename, "wb") as f:
        f.write(await video.read())

    # Extract audio
    audio_filename = video_filename.replace(".mp4", ".wav")
    try:
        clip = VideoFileClip(video_filename)
        clip.audio.write_audiofile(audio_filename, codec='pcm_s16le', fps=16000, verbose=False, logger=None)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Audio extraction failed: {str(e)}"})

    # Transcribe audio using Whisper
    try:
        result = whisper_model.transcribe(audio_filename)
        transcription = result["text"]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Transcription failed: {str(e)}"})

    # Use LLM to analyze accent based on transcription with the new client format
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in linguistics and accent detection. Analyze the following transcription and determine the English accent (American, British, Australian, Indian, etc.). Provide your answer as a JSON with fields 'accent', 'confidence' (0-1), and 'summary' (a brief explanation of why you identified this accent, including key linguistic features)."},
                {"role": "user", "content": f"Transcription: {transcription}"}
            ]
        )
        
        accent_analysis = json.loads(response.choices[0].message.content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Accent analysis failed: {str(e)}"})

    # Clean up temp files
    os.remove(video_filename)
    os.remove(audio_filename)

    return accent_analysis

# Mount static files AFTER defining API routes
app.mount("/", StaticFiles(directory="static", html=True), name="static")
