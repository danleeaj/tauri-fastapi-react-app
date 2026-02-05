# Transcription processing for API

from pathlib import Path
from models import Transcription


def create_transcription(input_directory: Path, output_directory: Path, client) -> None:
    """Transcribe audio chunks using Whisper API."""
    for chunk in sorted(input_directory.iterdir()):
        if not chunk.suffix == ".wav":
            continue
            
        with open(chunk, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt",
            )
        
        srt_path = output_directory / f"{chunk.stem}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(transcription)


def process_transcription(input_directory: Path) -> Transcription:
    """Merge multiple SRT files into one Transcription."""
    srt_files = sorted(input_directory.glob("*.srt"))
    combined = Transcription(subtitles=[], end_time=0, end_index=0)

    for srt_file in srt_files:
        with open(srt_file, "r", encoding="utf-8") as f:
            srt_content = f.read()
        
        # Extract offset from filename: chunk_{index}_{start_ms}.srt
        end_time = int(srt_file.stem.split("_")[-1])
        transcription = Transcription.from_srt(srt_content, end_time=end_time)

        if combined.subtitles:
            transcription.offset(
                offset_ms=combined.end_time, 
                offset_index=combined.end_index
            )

        combined.subtitles.extend(transcription.subtitles)
        combined.end_time = transcription.end_time
        combined.end_index = transcription.end_index

    return combined
