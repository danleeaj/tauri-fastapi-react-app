# Models for subtitle transcription - copied from root models.py

from pydantic import BaseModel, Field
from typing import Optional
import re

from prompts import get_translation_prompt


class Translation(BaseModel):
    id: int
    text: str


class FullTranslation(BaseModel):
    translations: list[Translation]


class Timestamp:
    def __init__(self, time: str = None, milliseconds: int = None):
        if milliseconds is not None:
            self.milliseconds = milliseconds
        elif time is not None:
            self.milliseconds = self._parse(time)
        else:
            self.milliseconds = 0
    
    def _parse(self, time: str) -> int:
        pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
        match = re.match(pattern, time)
        if not match:
            raise ValueError(f"Invalid timestamp format: {time}")
        hr, min, s, ms = map(int, match.groups())
        return (hr * 3600 + min * 60 + s) * 1000 + ms
    
    def __str__(self) -> str:
        ms = self.milliseconds % 1000
        s = (self.milliseconds // 1000) % 60
        min = (self.milliseconds // (1000 * 60)) % 60
        hr = self.milliseconds // (1000 * 3600)
        return f"{hr:02}:{min:02}:{s:02},{ms:03}"
    
    def __add__(self, other: "Timestamp") -> "Timestamp":
        return Timestamp(milliseconds=self.milliseconds + other.milliseconds)


class SubtitleEntry(BaseModel):
    index: int
    start_time: str
    end_time: str
    text: str
    translation: Optional[str] = None

    def to_srt_block(self, use_translation: bool = False, is_bilingual: bool = False) -> str:
        content = self.translation if use_translation and self.translation else self.text
        if is_bilingual and self.translation:
            content = f"{self.text}\n{self.translation}"
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{content}\n"
    
    def offset(self, offset_ms: int) -> None:
        start_ts = Timestamp(self.start_time) + Timestamp(milliseconds=offset_ms)
        end_ts = Timestamp(self.end_time) + Timestamp(milliseconds=offset_ms)
        self.start_time = str(start_ts)
        self.end_time = str(end_ts)


class Transcription(BaseModel):
    subtitles: list[SubtitleEntry] = Field(default_factory=list)
    end_time: int = 0
    end_index: int = 0
    language: Optional[str] = None

    @classmethod
    def from_srt(cls, srt_content: str, end_time: int) -> "Transcription":
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)'
        matches = re.findall(pattern, srt_content.strip() + '\n\n', re.DOTALL)
        
        subtitles = [
            SubtitleEntry(index=int(idx), start_time=start, end_time=end, text=text.strip())
            for idx, start, end, text in matches
        ]
        end_index = int(subtitles[-1].index) if subtitles else 0
        return cls(subtitles=subtitles, end_time=end_time, end_index=end_index)
    
    def offset(self, offset_ms: int, offset_index: int) -> None:
        for subtitle in self.subtitles:
            subtitle.offset(offset_ms)
            subtitle.index += offset_index
    
    def to_srt(self, use_translation: bool = False, is_bilingual: bool = False) -> str:
        return "\n".join(
            sub.to_srt_block(use_translation=use_translation, is_bilingual=is_bilingual) 
            for sub in self.subtitles
        )

    def translate_subtitles(self, target_language: str, client, batch_size: int = 30, overlap: int = 5) -> None:
        for i in range(0, len(self.subtitles), batch_size):
            batch = self.subtitles[i:i + batch_size]
            
            start_ctx = max(0, i - overlap)
            end_ctx = min(len(self.subtitles), i + batch_size + overlap)
            
            prev_ctx = self.subtitles[start_ctx:i] if i > 0 else []
            next_ctx = self.subtitles[i + batch_size:end_ctx] if i + batch_size < len(self.subtitles) else []
            
            context_before = [{'id': s.index, 'text': s.text} for s in prev_ctx]
            texts_to_translate = [{'id': s.index, 'text': s.text} for s in batch]
            context_after = [{'id': s.index, 'text': s.text} for s in next_ctx]
            
            prompt = get_translation_prompt(
                target_language=target_language,
                context_before=context_before,
                texts_to_translate=texts_to_translate,
                context_after=context_after
            )
            
            response = client.responses.parse(
                model="gpt-4o-mini-2024-07-18",
                input=prompt,
                text_format=FullTranslation
            )
            
            for subtitle in batch:
                translated = next(
                    (t for t in response.output_parsed.translations if t.id == subtitle.index), 
                    None
                )
                subtitle.translation = translated.text if translated else ""
