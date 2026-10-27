# Blushed & Browed reel

`output/blushedbrowed_reel.mp4`: 16 s, 1080×1920, 30 fps, H.264. Ready to upload as an Instagram Reel.

Scenes: hook on portrait → PMU Brows → Lip Blush → "Hi, I'm Sima" → branded end card with a "Book · link in bio" button.

Re-render (needs Python 3 + Pillow + numpy + ffmpeg):

    python3 reel/make_reel.py                     # silent track, add music in Instagram
    python3 reel/make_reel.py --music track.mp3   # bake in your own audio

Source images are in `assets/`. The polaroid cards are cropped from the pinned posts in `profile_screenshot.png`.
