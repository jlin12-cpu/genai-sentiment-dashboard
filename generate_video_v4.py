"""
generate_video_v4.py
--------------------
Generates animated weekly GenAI sentiment video with:
- Smooth fade transitions between slides
- Animated number counters (KPIs count up)
- Animated progress bars (ratings fill left to right)
- Typewriter title effect
- ElevenLabs voiceover synced to total duration

Run: /Users/jielin/miniconda3/bin/python generate_video_v4.py
"""

import os, json, math, numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx.all import fadein, fadeout
import anthropic
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY  = os.getenv('ANTHROPIC_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "dashboard", "insights_data.json")
OUT_VIDEO = os.path.join(BASE_DIR, "dashboard", "weekly_update.mp4")
TMP_DIR   = os.path.join(BASE_DIR, "tmp_video")

W, H = 1280, 720
FPS  = 30

# Colors
BG       = (249, 250, 251)
WHITE    = (255, 255, 255)
BLUE     = (37,  99,  235)
BLUE2    = (59, 130, 246)
TEXT     = (17,  24,  39)
TEXT2    = (107, 114, 128)
GREEN    = (16,  163, 127)
RED      = (220,  38,  38)
ORANGE   = (234, 88,  12)
YELLOW   = (234, 179,  8)
GRAY     = (229, 231, 235)

APP_COLORS = {
    'ChatGPT':           (16, 163, 127),
    'Claude':            (217, 119,  87),
    'Google_Gemini':     (66, 133, 244),
    'Microsoft_Copilot': (0,  120, 212),
    'Perplexity':        (34, 211, 238),
}

os.makedirs(TMP_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_font(size, bold=False):
    # Try Mac font first, then Linux fallbacks
    font_paths = [
        ("/System/Library/Fonts/Helvetica.ttc", 1 if bold else 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 0),
    ]
    for path, idx in font_paths:
        try:
            return ImageFont.truetype(path, size, index=idx)
        except:
            continue
    return ImageFont.load_default()

def ease_out(t):
    """Smooth deceleration curve 0→1"""
    return 1 - (1 - t) ** 3

def ease_in_out(t):
    return t * t * (3 - 2 * t)

def draw_rounded_rect(draw, xy, r, fill, outline=None, outline_width=0):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1+r, y1, x2-r, y2], fill=fill)
    draw.rectangle([x1, y1+r, x2, y2-r], fill=fill)
    for ex, ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex, ey, ex+2*r, ey+2*r], fill=fill)
    if outline:
        draw.rounded_rectangle(xy, radius=r, outline=outline, width=outline_width)

def img_to_array(img):
    return np.array(img.convert("RGB"))

# ── Load data ─────────────────────────────────────────────────────────────────
def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)

# ── Generate script + voiceover ───────────────────────────────────────────────
def generate_script(data):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    ov   = data['overview']
    best = max(ov, key=lambda x: x['Avg_Star'])
    ctx  = "\n".join([f"{i['App'].replace('_',' ')}: {i['Avg_Star']:.2f}★ sentiment {i['Avg_Sentiment']:.3f}" for i in ov])
    msg  = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=550,
        messages=[{"role":"user","content":f"""
Write a 70-85 second energetic voiceover for a GenAI sentiment dashboard video.
5 sections matching these slides:
1. HOOK (8s): One surprising insight to grab attention
2. RANKINGS (18s): Overall product rankings, mention top and bottom
3. WINNER (16s): Deep dive on {best['App'].replace('_',' ')}, what users love
4. COMPARE (16s): Compare top 2 products head to head  
5. CLOSE (10s): Invite to subscribe and explore dashboard

Data: {ctx}
Spoken words only. No labels, no directions. Conversational and punchy.
"""}])
    return msg.content[0].text

def generate_voiceover(script):
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    path   = os.path.join(TMP_DIR, "voiceover.mp3")
    audio  = client.text_to_speech.convert(
        voice_id="JBFqnCBsd6RMkjVDRZzb", text=script,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.35, use_speaker_boost=True)
    )
    with open(path, "wb") as f:
        for chunk in audio: f.write(chunk)
    print(f"  ✓ Voiceover: {os.path.getsize(path):,} bytes")
    return path

# ── Base frame builder ────────────────────────────────────────────────────────
def base_frame(title_text=None, subtitle=None):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    # Header bar
    draw.rectangle([0, 0, W, 80], fill=BLUE)
    draw.text((40, 40), "GenAI Sentiment Dashboard", font=get_font(22, True), fill=WHITE, anchor="lm")
    date_str = datetime.now().strftime("%B %d, %Y")
    draw.text((W-40, 40), date_str, font=get_font(16), fill=(180,200,255), anchor="rm")
    if title_text:
        draw.text((W//2, 145), title_text, font=get_font(42, True), fill=TEXT, anchor="mm")
    if subtitle:
        draw.text((W//2, 195), subtitle, font=get_font(18), fill=TEXT2, anchor="mm")
    return img, draw

# ── SLIDE 1: Title (animated typewriter) ─────────────────────────────────────
def make_title_frames(n_frames, data):
    best = max(data['overview'], key=lambda x: x['Avg_Star'])
    full_title = "Weekly GenAI Sentiment Report"
    frames = []
    for i in range(n_frames):
        t = i / n_frames
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, W, 80], fill=BLUE)
        draw.text((40, 40), "GenAI Sentiment Dashboard", font=get_font(22, True), fill=WHITE, anchor="lm")
        draw.text((W-40, 40), datetime.now().strftime("%B %d, %Y"), font=get_font(16), fill=(180,200,255), anchor="rm")

        # Typewriter effect for title
        chars = int(ease_out(min(t * 2, 1)) * len(full_title))
        draw.text((W//2, 300), full_title[:chars], font=get_font(48, True), fill=TEXT, anchor="mm")

        # Fade in subtitle
        if t > 0.5:
            alpha = ease_out((t - 0.5) * 2)
            sub   = f"5 Products · {sum(i['Total_Reviews'] for i in data['overview']):,} Reviews · Q1 2026"
            draw.text((W//2, 370), sub, font=get_font(20), fill=(*TEXT2, int(alpha*255)), anchor="mm")

        # Animated accent line grows
        line_w = int(ease_out(t) * 200)
        draw.rectangle([W//2 - line_w, 420, W//2 + line_w, 424], fill=BLUE)

        # App color dots fade in
        if t > 0.6:
            alpha = ease_out((t - 0.6) / 0.4)
            apps  = list(APP_COLORS.items())
            dx    = W // (len(apps)+1)
            for j, (app, color) in enumerate(apps):
                x = dx * (j+1)
                r = int(12 * alpha)
                if r > 0:
                    draw.ellipse([x-r, 480-r, x+r, 480+r], fill=color)
                    if alpha > 0.5:
                        draw.text((x, 510), app.replace('_',' '), font=get_font(13), fill=TEXT2, anchor="mm")
        frames.append(img_to_array(img))
    return frames

# ── SLIDE 2: Rankings (animated progress bars) ────────────────────────────────
def make_rankings_frames(n_frames, data):
    sorted_apps = sorted(data['overview'], key=lambda x: x['Avg_Star'], reverse=True)
    frames = []
    for i in range(n_frames):
        t = i / n_frames
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, W, 80], fill=BLUE)
        draw.text((40, 40), "GenAI Sentiment Dashboard", font=get_font(22, True), fill=WHITE, anchor="lm")
        draw.text((W-40, 40), "Product Rankings", font=get_font(20, True), fill=WHITE, anchor="rm")

        y = 110
        for rank, item in enumerate(sorted_apps):
            app   = item['App']
            color = APP_COLORS.get(app, (100,100,100))
            label = app.replace('_',' ')
            star  = item['Avg_Star']

            # Stagger each row entrance
            row_t = max(0, min(1, (t - rank * 0.08) / 0.4))
            row_t = ease_out(row_t)

            card_alpha = int(row_t * 255)
            if card_alpha <= 0:
                y += 104
                continue

            # Card
            card_img  = Image.new("RGBA", (W-80, 90), (*WHITE, card_alpha))
            card_draw = ImageDraw.Draw(card_img)
            img.paste(Image.fromarray(np.full((90, W-80, 3), WHITE, dtype=np.uint8)), (40, y))

            # Rank badge
            draw.ellipse([50, y+25, 82, y+57], fill=BLUE)
            draw.text((66, y+41), f"#{rank+1}", font=get_font(16, True), fill=WHITE, anchor="mm")

            # Color dot
            draw.ellipse([95, y+31, 115, y+51], fill=color)

            # App name
            draw.text((130, y+41), label, font=get_font(20, True), fill=TEXT, anchor="lm")

            # Animated progress bar
            bar_x, bar_y, bar_w, bar_h = 400, y+33, 500, 16
            draw.rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], fill=GRAY, width=0)
            filled = int(bar_w * (star/5) * row_t)
            if filled > 0:
                draw.rectangle([bar_x, bar_y, bar_x+filled, bar_y+bar_h], fill=color)
            draw.text((bar_x+bar_w+12, y+41), f"{star:.2f} stars", font=get_font(18, True), fill=TEXT, anchor="lm")

            # Sentiment
            s_color = GREEN if item['Avg_Sentiment'] > 0.4 else RED
            draw.text((W-60, y+41), f"{item['Avg_Sentiment']:.3f}", font=get_font(16, True), fill=s_color, anchor="mm")

            y += 104

        # Column labels
        draw.text((W-60, 95), "Sentiment", font=get_font(13), fill=TEXT2, anchor="mm")
        frames.append(img_to_array(img))
    return frames

# ── SLIDE 3: Winner (animated KPI counters) ───────────────────────────────────
def make_winner_frames(n_frames, data):
    best  = max(data['overview'], key=lambda x: x['Avg_Star'])
    color = APP_COLORS.get(best['App'], (37,99,235))
    label = best['App'].replace('_',' ')
    frames = []
    for i in range(n_frames):
        t = i / n_frames
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)

        # Green header for winner
        draw.rectangle([0, 0, W, 80], fill=(21, 128, 61))
        draw.text((W//2, 40), "This Week's Leader", font=get_font(26, True), fill=WHITE, anchor="mm")

        # Big app name fades + scales in
        name_t = ease_out(min(t * 1.5, 1))
        draw.text((W//2, 175), label, font=get_font(int(52 + 8*name_t), True), fill=color, anchor="mm")

        # 3 KPI cards with counting animation
        kpis = [
            (best['Avg_Star'], 5.0, "Avg Rating", " stars"),
            (best['Avg_Sentiment'], 1.0, "Sentiment", ""),
            (best['Total_Reviews'], best['Total_Reviews'], "Reviews", ""),
        ]
        kpi_t = ease_out(max(0, (t - 0.2) / 0.6))
        sx = 130
        for val, max_val, lbl, suffix in kpis:
            draw_rounded_rect(draw, (sx, 250, sx+290, 390), 14, WHITE)
            animated_val = val * kpi_t
            if isinstance(val, int):
                display = f"{int(animated_val):,}"
            else:
                display = f"{animated_val:.2f}"
            draw.text((sx+145, 305), display + (" stars" if suffix=="★" else suffix), font=get_font(34, True), fill=TEXT, anchor="mm")
            draw.text((sx+145, 355), lbl, font=get_font(16), fill=TEXT2, anchor="mm")
            sx += 330

        # Top keywords fade in
        if t > 0.6:
            kw_t = ease_out((t-0.6)/0.4)
            pos_kw = list(best['Keywords_Positive'].keys())[:6]
            draw.text((W//2, 450), "Users love:", font=get_font(16), fill=TEXT2, anchor="mm")
            kw_x = W//2 - 280
            for kw in pos_kw:
                draw_rounded_rect(draw, (kw_x, 470, kw_x+90, 500), 8, (*color, int(kw_t*40)))
                draw.rectangle([kw_x, 470, kw_x+90, 500], fill=None, outline=color, width=1)
                draw.text((kw_x+45, 485), kw, font=get_font(14), fill=color, anchor="mm")
                kw_x += 100

        frames.append(img_to_array(img))
    return frames

# ── SLIDE 4: Compare ──────────────────────────────────────────────────────────
def make_compare_frames(n_frames, data):
    sorted_ov = sorted(data['overview'], key=lambda x: x['Avg_Star'], reverse=True)
    app1, app2 = sorted_ov[0], sorted_ov[1]
    c1 = APP_COLORS.get(app1['App'], (37,99,235))
    c2 = APP_COLORS.get(app2['App'], (107,114,128))
    frames = []
    for i in range(n_frames):
        t = i / n_frames
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, W, 80], fill=BLUE)
        draw.text((W//2, 40), "Head to Head Comparison", font=get_font(26, True), fill=WHITE, anchor="mm")

        panel_t = ease_out(min(t*1.4, 1))

        for idx, (item, color, side) in enumerate([(app1,c1,'left'),(app2,c2,'right')]):
            px = 60 if side=='left' else W//2+20
            pw = W//2-80

            # Slide in from sides
            offset = int((1-panel_t) * 200 * (1 if side=='left' else -1))
            draw_rounded_rect(draw, (px+offset, 100, px+pw+offset, H-60), 14, WHITE)

            # App name with color accent
            draw.rectangle([px+offset, 100, px+pw+offset, 145], fill=color)
            draw.text((px+pw//2+offset, 122), item['App'].replace('_',' '), font=get_font(20, True), fill=WHITE, anchor="mm")

            metrics = [
                ("Avg Star Rating", f"{item['Avg_Star']:.2f}★"),
                ("Sentiment", f"{item['Avg_Sentiment']:.3f}"),
                ("Std Deviation", f"{item['Std_Dev']:.2f}"),
                ("Total Reviews", f"{item['Total_Reviews']:,}"),
            ]
            my = 175
            for label, val in metrics:
                draw.text((px+20+offset, my), label, font=get_font(13), fill=TEXT2, anchor="lm")
                draw.text((px+pw-20+offset, my+20), val, font=get_font(22, True), fill=TEXT, anchor="rm")
                draw.rectangle([px+offset, my+40, px+pw+offset, my+41], fill=GRAY)
                my += 70

            # Top pain point
            top_pain = sorted(item['Theme_Counts'].items(), key=lambda x: x[1], reverse=True)
            if top_pain:
                pain_name = top_pain[0][0]
                draw.text((px+pw//2+offset, my+20), f"Top issue: {pain_name}", font=get_font(14), fill=RED, anchor="mm")

        # VS divider
        vs_t = ease_out(max(0,(t-0.3)/0.4))
        draw.ellipse([W//2-30, H//2-30, W//2+30, H//2+30], fill=BLUE)
        draw.text((W//2, H//2), "VS", font=get_font(20, True), fill=WHITE, anchor="mm")

        frames.append(img_to_array(img))
    return frames

# ── SLIDE 5: Closing ──────────────────────────────────────────────────────────
def make_closing_frames(n_frames, data):
    frames = []
    for i in range(n_frames):
        t = i / n_frames
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, W, 80], fill=BLUE)
        draw.text((40, 40), "GenAI Sentiment Dashboard", font=get_font(22, True), fill=WHITE, anchor="lm")

        # Main CTA fades in
        cta_t = ease_out(min(t*1.5, 1))
        draw.text((W//2, 240), "Stay ahead of the curve.", font=get_font(44, True), fill=TEXT, anchor="mm")

        sub_t = ease_out(max(0,(t-0.25)/0.5))
        draw.text((W//2, 310), "Get the weekly GenAI sentiment report", font=get_font(22), fill=TEXT2, anchor="mm")

        # Subscribe button animation
        btn_t = ease_out(max(0,(t-0.45)/0.4))
        btn_w = int(220 * btn_t)
        if btn_w > 20:
            draw_rounded_rect(draw, (W//2-btn_w//2, 370, W//2+btn_w//2, 415), 10, BLUE)
            if btn_t > 0.7:
                draw.text((W//2, 392), "Subscribe Free", font=get_font(18, True), fill=WHITE, anchor="mm")

        # Product dots appear
        if t > 0.5:
            dot_t = ease_out((t-0.5)/0.5)
            apps  = list(APP_COLORS.items())
            dx    = W // (len(apps)+1)
            for j, (app, color) in enumerate(apps):
                x = dx*(j+1)
                r = int(14 * dot_t)
                if r > 0:
                    draw.ellipse([x-r, 475-r, x+r, 475+r], fill=color)
                    if dot_t > 0.6:
                        draw.text((x, 505), app.replace('_',' '), font=get_font(13), fill=TEXT2, anchor="mm")

        # URL
        url_t = ease_out(max(0,(t-0.7)/0.3))
        if url_t > 0:
            draw.text((W//2, 580), "jlin12-cpu.github.io/genai-sentiment-dashboard", font=get_font(15), fill=BLUE2, anchor="mm")

        frames.append(img_to_array(img))
    return frames

# ── Build animated clip ───────────────────────────────────────────────────────
def frames_to_clip(frames, duration):
    fps_actual = len(frames) / duration
    clips = []
    for frame in frames:
        clips.append(ImageClip(frame).set_duration(1/fps_actual))
    return concatenate_videoclips(clips, method="chain")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("📊 Loading data...")
    data = load_data()

    print("🤖 Generating script...")
    script = generate_script(data)
    print(f"  Preview: {script[:80]}...")

    print("🎙  Generating voiceover...")
    audio_path = generate_voiceover(script)
    audio      = AudioFileClip(audio_path)
    total_dur  = audio.duration
    print(f"  Total duration: {total_dur:.1f}s")

    # Scene durations proportional to script sections
    scene_durs = [
        total_dur * 0.12,   # title
        total_dur * 0.26,   # rankings
        total_dur * 0.23,   # winner
        total_dur * 0.23,   # compare
        total_dur * 0.16,   # closing
    ]

    print("🎨 Generating animated frames...")
    scene_funcs = [
        make_title_frames,
        make_rankings_frames,
        make_winner_frames,
        make_compare_frames,
        make_closing_frames,
    ]
    scene_names = ["Title", "Rankings", "Winner", "Compare", "Closing"]

    clips = []
    for func, dur, name in zip(scene_funcs, scene_durs, scene_names):
        n_frames = max(int(dur * FPS), 10)
        print(f"  {name}: {dur:.1f}s ({n_frames} frames)...")
        frames = func(n_frames, data)
        clip   = frames_to_clip(frames, dur)
        # Add fade transition
        clip = clip.fadein(0.3).fadeout(0.3)
        clips.append(clip)

    print("🎬 Assembling final video...")
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    video.write_videofile(
        OUT_VIDEO, fps=FPS, codec="libx264",
        audio_codec="aac", verbose=False, logger=None
    )

    print(f"\n✅ Done! → {OUT_VIDEO}")

if __name__ == "__main__":
    main()
