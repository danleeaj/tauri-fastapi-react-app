"""
Subtitle transcription and translation API.
Receives audio chunks, transcribes via Whisper, translates via ChatGPT.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from uuid import uuid4
import shutil
import os
import logging

from openai import OpenAI
from dotenv import load_dotenv

from models import Transcription
from process_transcription import create_transcription, process_transcription

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Subtitle API")
client = OpenAI()

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


class TranscriptionRequest(BaseModel):
    target_language: str = "Chinese"


class TranscriptionResponse(BaseModel):
    english_srt: str
    translated_srt: str
    bilingual_srt: str


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    files: list[UploadFile] = File(...),
    target_language: str = "Chinese"
):
    """
    Receive audio chunks, transcribe and translate.
    
    Files should be named with offset info: chunk_{index}_{start_ms}.wav
    """
    job_id = str(uuid4())
    job_dir = TEMP_DIR / job_id
    chunks_dir = job_dir / "chunks"
    whisper_dir = job_dir / "whisper"
    
    logger.info(f"Starting transcription job {job_id} with {len(files)} files, target_language={target_language}")
    
    try:
        chunks_dir.mkdir(parents=True)
        whisper_dir.mkdir(parents=True)
        
        # Save uploaded chunks
        for file in files:
            chunk_path = chunks_dir / file.filename
            with open(chunk_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        
        logger.info(f"Job {job_id}: Saved {len(files)} chunks, starting Whisper transcription")
        
        # Transcribe with Whisper
        create_transcription(chunks_dir, whisper_dir, client)
        
        logger.info(f"Job {job_id}: Whisper transcription complete, processing SRT files")
        
        # Process and merge
        combined = process_transcription(whisper_dir)
        
        logger.info(f"Job {job_id}: Merged {len(combined.subtitles)} subtitles, starting translation")
        
        # Translate
        combined.translate_subtitles(target_language=target_language, client=client)
        
        logger.info(f"Job {job_id}: Translation complete, returning response")
        
        return TranscriptionResponse(
            english_srt=combined.to_srt(),
            translated_srt=combined.to_srt(use_translation=True),
            bilingual_srt=combined.to_srt(is_bilingual=True)
        )
    
    except Exception as e:
        logger.error(f"Job {job_id}: Error during transcription - {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup
        if job_dir.exists():
            shutil.rmtree(job_dir)


@app.get("/health")
async def health():
    return {"status": "ok"}
    