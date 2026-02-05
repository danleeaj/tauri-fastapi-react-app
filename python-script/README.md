# Subs

This is a script that utilized Whisper API and OpenAI to transcribe and translate subtitles from English to Chinese.

It is currently under development, and the goal is to turn this into a lightweight desktop app, and enable concurrent processing.

All processing is currently done in hello.py. Pydantic used for schema validation, OpenAI API key is required.

## Todos:

* Make the program more modularized.
  * Make it so that if, say, the translation step fails, I can restart just that step, instead of doing the entire thing again.
  * I would like the prompts to exist in a separate `prompt.py` so in the future we can iterate upon the prompts more easily and keep a record of all previous prompts.
* Dockerize the entire thing so the script can be run on any device. Currently, the most time consuming aspect of this program is the need for me to download the video from my user's computer. If they can run this on their own, then it would be amazing.
  * Improve documentation. After dockerizing, record a tutorial on how to use it (incl. how to use Docker), so they can run this on their own.
* At the moment, this program only outputs .srt files. I want it to eventually be able to burn the subtitles back into a video.
  * This also means that we should do some testing and figure out how to truncate the subtitles to make everything fit within the frame of the video.
```python
# Code and ffmpeg command to burn .srt to video. This is only for the Chinese subs for now.
ffmpeg_cmd_burn_subtitles_to_video = [
    'ffmpeg',
    '-i', file_path,
    '-vf', f"subtitles={chinese_srt}:force_style='Fontname=Heiti SC,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'",
    '-c:v', 'h264_videotoolbox',
    '-b:v', '5M',
    '-c:a', 'copy',
    '-y',  # Overwrite output file if it exists
    output_file_path
]

print("Burning subtitles into video...")
result = subprocess.run(ffmpeg_cmd_burn_subtitles_to_video, capture_output=True, text=True)
```
* If Dockerizing is too hard for users to understand, and alternative is to use dropbox webhooks. We link this program to dropbox, so that whenever a new upload is made, this program runs by itself (maybe after some verification), and then uploads the video/subtitle documents back to dropbox.