from yt_dlp import YoutubeDL


url = "https://www.youtube.com/watch?v=hY40eLF2Ocs"

ydl_opts = {
    "format": "bestvideo+bestaudio/best",
    "merge_output_format": "mp4",
    "outtmpl": "downloads/%(title)s.%(ext)s",
}

with YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])