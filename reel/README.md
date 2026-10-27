# Blushed & Browed reel

`output/blushedbrowed_reel.mp4`: 16 s, 1080×1920, 30 fps, H.264. Ready to upload as an Instagram Reel.

Scenes: hook on portrait → PMU Brows → Lip Blush → "Hi, I'm Sima" → branded end card with a "Book · link in bio" button.

Re-render (needs Python 3 + Pillow + numpy + ffmpeg):

    python3 reel/make_reel.py                     # silent track, add music in Instagram
    python3 reel/make_reel.py --music track.mp3   # bake in your own audio

Source images are in `assets/`. The polaroid cards are cropped from the pinned posts in `profile_screenshot.png`.

## Glam reel (floating products → reveal)

`output/blushedbrowed_glam_reel.mp4`: 10.8 s, follows the example reel's beats. PMU products (lip and brow pigment, PMU pen, spoolie, brow pencil, tweezers, lipstick, compact) float around the portrait, swarm onto the face, and dissolve into a glam close-up. It ends on a dark frame with the Instagram logo and @blushedbrowed.

    python3 reel/make_glam_reel.py                     # silent, pick the sound in Instagram
    python3 reel/make_glam_reel.py --music track.mp3   # bake in your own audio
