"""
generate_video.py — reads secrets from .env
"""
import json, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
import anthropic
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
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
FPS  = 24

BG_COLOR     = (249, 250, 251)
CARD_COLOR   = (255, 255, 255)
ACCENT_COLOR = (37, 99, 235)
TEXT_COLOR   = (17, 24, 39)
TEXT2_COLOR  = (107, 114, 128)
GREEN_COLOR  = (16, 163, 127)
RED_COLOR    = (220, 38, 38)

APP_COLORS = {
    'ChatGPT': (16,163,127), 'Claude': (217,119,87),
    'Google_Gemini': (66,133,244), 'Microsoft_Copilot': (0,120,212), 'Perplexity': (34,211,238),
}

os.makedirs(TMP_DIR, exist_ok=True)

def load_data():
    with open(DATA_FILE) as f: return json.load(f)

def generate_script(data):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    ctx = "\n".join([f"{i['App'].replace('_',' ')}: {i['Avg_Star']:.2f}★, sentiment {i['Avg_Sentiment']:.3f}, {i['Total_Reviews']:,} reviews" for i in data['overview']])
    msg = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=600, messages=[{"role":"user","content":f"""
You are a data analyst presenting a weekly GenAI app sentiment report.
Write a 60-90 second video script (spoken words only, no stage directions).
Structure: 1) Hook 2) Overview 3) Winner 4) Concerns 5) Closing
Data: {ctx}
Keep it conversational, energetic, and data-driven."""}])
    return msg.content[0].text

def generate_voiceover(script):
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    audio_path = os.path.join(TMP_DIR, "voiceover.mp3")
    audio = client.text_to_speech.convert(voice_id="JBFqnCBsd6RMkjVDRZzb", text=script,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.3, use_speaker_boost=True))
    with open(audio_path, "wb") as f:
        for chunk in audio: f.write(chunk)
    print(f"  ✓ Voiceover saved")
    return audio_path

def get_font(size, bold=False):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size, index=1 if bold else 0)
    except:
        return ImageFont.load_default()

def draw_rounded_rect(draw, xy, radius, fill):
    x1,y1,x2,y2 = xy
    draw.rectangle([x1+radius,y1,x2-radius,y2],fill=fill)
    draw.rectangle([x1,y1+radius,x2,y2-radius],fill=fill)
    for ex,ey in [(x1,y1),(x2-2*radius,y1),(x1,y2-2*radius),(x2-2*radius,y2-2*radius)]:
        draw.ellipse([ex,ey,ex+2*radius,ey+2*radius],fill=fill)

def make_title_slide(date_str):
    img=Image.new("RGB",(W,H),BG_COLOR); draw=ImageDraw.Draw(img)
    draw.rectangle([0,0,W,140],fill=ACCENT_COLOR)
    draw.text((W//2,70),"GenAI Sentiment",font=get_font(42,True),fill=(255,255,255),anchor="mm")
    draw.text((W//2,280),"Weekly Update",font=get_font(56,True),fill=TEXT_COLOR,anchor="mm")
    draw.text((W//2,360),date_str,font=get_font(28),fill=TEXT2_COLOR,anchor="mm")
    draw.text((W//2,460),"User Sentiment · 5 GenAI Apps · Google Play",font=get_font(22),fill=TEXT2_COLOR,anchor="mm")
    draw.rectangle([W//2-120,520,W//2+120,524],fill=ACCENT_COLOR)
    path=os.path.join(TMP_DIR,"slide_title.png"); img.save(path); return path

def make_overview_slide(data):
    img=Image.new("RGB",(W,H),BG_COLOR); draw=ImageDraw.Draw(img)
    draw.rectangle([0,0,W,90],fill=ACCENT_COLOR)
    draw.text((W//2,45),"Product Rankings This Week",font=get_font(30,True),fill=(255,255,255),anchor="mm")
    sorted_apps=sorted(data['overview'],key=lambda x:x['Avg_Star'],reverse=True)
    y=130
    for i,item in enumerate(sorted_apps):
        color=APP_COLORS.get(item['App'],(100,100,100))
        draw_rounded_rect(draw,(60,y,W-60,y+80),10,CARD_COLOR)
        draw.text((100,y+40),f"#{i+1}",font=get_font(22,True),fill=ACCENT_COLOR,anchor="mm")
        draw.ellipse([130,y+30,150,y+50],fill=color)
        draw.text((175,y+40),item['App'].replace('_',' '),font=get_font(22,True),fill=TEXT_COLOR,anchor="lm")
        bx,bw=500,300
        draw.rectangle([bx,y+35,bx+bw,y+45],fill=(229,231,235))
        draw.rectangle([bx,y+35,bx+int(bw*(item['Avg_Star']/5)),y+45],fill=color)
        draw.text((bx+bw+15,y+40),f"{item['Avg_Star']:.2f}★",font=get_font(18,True),fill=TEXT_COLOR,anchor="lm")
        sc=GREEN_COLOR if item['Avg_Sentiment']>0.4 else RED_COLOR
        draw.text((W-120,y+40),f"{item['Avg_Sentiment']:.3f}",font=get_font(18,True),fill=sc,anchor="mm")
        y+=96
    draw.text((W-120,115),"Sentiment",font=get_font(14),fill=TEXT2_COLOR,anchor="mm")
    path=os.path.join(TMP_DIR,"slide_overview.png"); img.save(path); return path

def make_highlight_slide(data):
    img=Image.new("RGB",(W,H),BG_COLOR); draw=ImageDraw.Draw(img)
    draw.rectangle([0,0,W,90],fill=(21,128,61))
    draw.text((W//2,45),"🏆  This Week's Leader",font=get_font(30,True),fill=(255,255,255),anchor="mm")
    best=max(data['overview'],key=lambda x:x['Avg_Star'])
    color=APP_COLORS.get(best['App'],(100,100,100))
    draw.text((W//2,220),best['App'].replace('_',' '),font=get_font(64,True),fill=(*color,255),anchor="mm")
    stats=[(f"{best['Avg_Star']:.2f}★","Avg Rating"),(f"{best['Avg_Sentiment']:.3f}","Sentiment"),(f"{best['Total_Reviews']:,}","Reviews")]
    sx=200
    for val,lbl in stats:
        draw_rounded_rect(draw,(sx,300,sx+240,420),12,CARD_COLOR)
        draw.text((sx+120,348),val,font=get_font(32,True),fill=TEXT_COLOR,anchor="mm")
        draw.text((sx+120,390),lbl,font=get_font(16),fill=TEXT2_COLOR,anchor="mm")
        sx+=280
    pos_kw=", ".join(list(best['Keywords_Positive'].keys())[:6])
    draw.text((W//2,490),f"Users say: {pos_kw}",font=get_font(20),fill=TEXT2_COLOR,anchor="mm")
    path=os.path.join(TMP_DIR,"slide_highlight.png"); img.save(path); return path

def make_concerns_slide(data):
    img=Image.new("RGB",(W,H),BG_COLOR); draw=ImageDraw.Draw(img)
    draw.rectangle([0,0,W,90],fill=(185,28,28))
    draw.text((W//2,45),"⚠  Common User Concerns",font=get_font(30,True),fill=(255,255,255),anchor="mm")
    y=140
    for item in data['overview']:
        neg_kw=list(item['Keywords_Negative'].keys())[:3]
        color=APP_COLORS.get(item['App'],(100,100,100))
        draw_rounded_rect(draw,(60,y,W-60,y+72),10,CARD_COLOR)
        draw.ellipse([90,y+26,110,y+46],fill=color)
        draw.text((130,y+36),item['App'].replace('_',' '),font=get_font(18,True),fill=TEXT_COLOR,anchor="lm")
        draw.text((320,y+36)," · ".join(neg_kw),font=get_font(17),fill=TEXT2_COLOR,anchor="lm")
        y+=82
    path=os.path.join(TMP_DIR,"slide_concerns.png"); img.save(path); return path

def make_closing_slide(data):
    img=Image.new("RGB",(W,H),BG_COLOR); draw=ImageDraw.Draw(img)
    draw.rectangle([0,0,W,140],fill=ACCENT_COLOR)
    draw.text((W//2,70),"GenAI Sentiment Dashboard",font=get_font(36,True),fill=(255,255,255),anchor="mm")
    draw.text((W//2,280),"Stay informed every week.",font=get_font(40,True),fill=TEXT_COLOR,anchor="mm")
    draw.text((W//2,360),"Subscribe for the weekly report →",font=get_font(24),fill=ACCENT_COLOR,anchor="mm")
    apps=list(APP_COLORS.items()); dx=W//(len(apps)+1)
    for i,(app,color) in enumerate(apps):
        x=dx*(i+1)
        draw.ellipse([x-18,460,x+18,496],fill=color)
        draw.text((x,520),app.replace('_',' '),font=get_font(14),fill=TEXT2_COLOR,anchor="mm")
    path=os.path.join(TMP_DIR,"slide_closing.png"); img.save(path); return path

def assemble_video(slide_paths, audio_path):
    audio=AudioFileClip(audio_path); duration=audio.duration
    n=len(slide_paths); splits=[duration*0.12]+[(duration*0.88)/(n-1)]*(n-1)
    clips=[ImageClip(p).set_duration(d).fadein(0.4).fadeout(0.4) for p,d in zip(slide_paths,splits)]
    video=concatenate_videoclips(clips,method="compose").set_audio(audio)
    video.write_videofile(OUT_VIDEO,fps=FPS,codec="libx264",audio_codec="aac",verbose=False,logger=None)
    print(f"  ✓ Video saved → {OUT_VIDEO}")

def main():
    date_str=datetime.now().strftime("%B %d, %Y")
    print("📊 Loading data..."); data=load_data()
    print("🤖 Generating script..."); script=generate_script(data)
    print(f"  Script ({len(script)} chars)")
    print("🎙  Generating voiceover..."); audio_path=generate_voiceover(script)
    print("🎨 Creating slides...")
    slides=[make_title_slide(date_str),make_overview_slide(data),make_highlight_slide(data),make_concerns_slide(data),make_closing_slide(data)]
    print("🎬 Assembling video..."); assemble_video(slides,audio_path)
    print(f"\n✅ Done! Video saved to: {OUT_VIDEO}")

if __name__ == "__main__":
    main()
