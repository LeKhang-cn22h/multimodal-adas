from pathlib import Path

from yt_dlp import YoutubeDL


def download_tiktok(
    url: str,
    output_dir: str = "downloads",
):
    output = Path(output_dir)
    output.mkdir(exist_ok=True)

    ydl_opts = {
        "outtmpl": str(output / "%(uploader)s_%(id)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


if __name__ == "__main__":

    url = input("TikTok URL: ").strip()

    download_tiktok(url)