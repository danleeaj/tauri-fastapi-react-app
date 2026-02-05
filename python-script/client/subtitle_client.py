"""
Subtitle client - handles local video processing and API communication.
"""

import subprocess
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_silence
import httpx
import static_ffmpeg


# Ensure ffmpeg is available
try:
    static_ffmpeg.add_paths()
except Exception:
    pass


API_URL = "http://localhost:8000"


def convert_video_to_audio(input_path: Path, output_path: Path) -> None:
    """Convert video to 16kHz mono WAV."""
    cmd = [
        'ffmpeg', '-i', str(input_path),
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        '-y', str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def chunk_audio(audio_path: Path, output_dir: Path, max_duration_ms: int = 600000) -> list[Path]:
    """Split audio into chunks at silence points."""
    audio = AudioSegment.from_file(audio_path)
    
    if len(audio) <= max_duration_ms:
        chunk_path = output_dir / "chunk_0_0.wav"
        audio.export(chunk_path, format="wav")
        return [chunk_path]
    
    silence_thresh = audio.dBFS - 16
    flexibility = max_duration_ms // 5
    
    silences = detect_silence(audio, min_silence_len=300, silence_thresh=silence_thresh)
    silence_midpoints = [(s + e) // 2 for s, e in silences]
    
    chunks = []
    start = 0
    idx = 0
    
    while start < len(audio):
        ideal_end = start + max_duration_ms
        
        if ideal_end >= len(audio):
            chunk_path = output_dir / f"chunk_{idx}_{start}.wav"
            audio[start:].export(chunk_path, format="wav")
            chunks.append(chunk_path)
            break
        
        # Find silence near ideal cut point
        window_start = ideal_end - flexibility
        window_end = ideal_end + flexibility
        candidates = [s for s in silence_midpoints if window_start <= s <= window_end]
        
        cut_point = min(candidates, key=lambda s: abs(s - ideal_end)) if candidates else ideal_end
        
        chunk_path = output_dir / f"chunk_{idx}_{start}.wav"
        audio[start:cut_point].export(chunk_path, format="wav")
        chunks.append(chunk_path)
        
        start = cut_point
        idx += 1
    
    return chunks


def transcribe(video_path: str, target_language: str = "Chinese", api_url: str = API_URL) -> dict:
    """
    Process video and get subtitles from API.
    
    Returns dict with english_srt, translated_srt, bilingual_srt
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    # Create temp directory
    temp_dir = video_path.parent / f".subtitle_temp_{video_path.stem}"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # Step 1: Convert to audio
        audio_path = temp_dir / "audio.wav"
        print("Converting video to audio...")
        convert_video_to_audio(video_path, audio_path)
        
        # Step 2: Chunk audio
        chunks_dir = temp_dir / "chunks"
        chunks_dir.mkdir(exist_ok=True)
        print("Chunking audio...")
        chunk_files = chunk_audio(audio_path, chunks_dir)
        
        # Step 3: Upload to API
        print(f"Uploading {len(chunk_files)} chunk(s) to API...")
        files = [
            ("files", (f.name, open(f, "rb"), "audio/wav"))
            for f in chunk_files
        ]
        
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{api_url}/transcribe",
                files=files,
                params={"target_language": target_language}
            )
        
        # Close file handles
        for _, (_, fh, _) in files:
            fh.close()
        
        if response.status_code != 200:
            raise RuntimeError(f"API error: {response.text}")
        
        return response.json()
    
    finally:
        # Cleanup temp files
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate subtitles from video")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--language", "-l", default="Chinese", help="Target translation language")
    parser.add_argument("--api", default=API_URL, help="API URL")
    parser.add_argument("--output", "-o", help="Output directory (default: same as video)")
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    output_dir = Path(args.output) if args.output else video_path.parent
    
    result = transcribe(args.video, args.language, args.api)
    
    # Save outputs
    base_name = video_path.stem
    
    en_path = output_dir / f"{base_name}_en.srt"
    with open(en_path, "w", encoding="utf-8") as f:
        f.write(result["english_srt"])
    print(f"Saved: {en_path}")
    
    trans_path = output_dir / f"{base_name}_{args.language.lower()}.srt"
    with open(trans_path, "w", encoding="utf-8") as f:
        f.write(result["translated_srt"])
    print(f"Saved: {trans_path}")
    
    bi_path = output_dir / f"{base_name}_bilingual.srt"
    with open(bi_path, "w", encoding="utf-8") as f:
        f.write(result["bilingual_srt"])
    print(f"Saved: {bi_path}")


if __name__ == "__main__":
    main()
