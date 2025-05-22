from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import uuid
import requests
from moviepy.editor import VideoFileClip
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

# Remove Whisper model loading
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

    # Transcribe audio using OpenAI API instead of local Whisper model
    try:
        with open(audio_filename, "rb") as audio_file:
            transcription_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcription = transcription_response.text
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Transcription failed: {str(e)}"})

    # Use LLM to analyze accent based on transcription
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in linguistics and accent detection. Analyze the following transcription and determine the English accent (American, British, Australian, Indian, etc.). If the transcription is too short or lacks distinctive features, make your best guess based on available cues and note the limitations in your summary. Provide your answer as a JSON with fields 'accent', 'confidence' (0-1), and 'summary' (a brief explanation of why you identified this accent, including key linguistic features)."},
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

    # Transcribe audio using OpenAI API instead of local Whisper model
    try:
        with open(audio_filename, "rb") as audio_file:
            transcription_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcription = transcription_response.text
        print(f"DEBUG - Transcription: {transcription}")  # Add debug logging
        
        # Check if transcription is too short
        if not transcription or len(transcription.split()) < 5:
            return JSONResponse(
                status_code=400, 
                content={
                    "accent": "Insufficient data",
                    "confidence": 0,
                    "summary": "The audio sample contains insufficient speech for accurate accent detection. Please provide a longer sample with more speech content."
                }
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Transcription failed: {str(e)}"})

    # Use LLM to analyze accent based on transcription with the new client format
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in linguistics and accent detection. Your task is to analyze the transcription and identify the English accent (American, British, Australian, Indian, etc.). Even with limited data, provide your best assessment. If you truly cannot determine the accent, suggest the most likely possibilities based on any subtle cues. ALWAYS respond with a valid JSON containing 'accent' (the identified accent or 'American' if uncertain), 'confidence' (0.1-1.0, use at least 0.1 even when uncertain), and 'summary' (your explanation)."},
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
