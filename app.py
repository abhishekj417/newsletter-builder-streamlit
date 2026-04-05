import os
import textwrap
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin

import requests
import feedparser
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Newsletter Builder", page_icon="📨", layout="wide", initial_sidebar_state="expanded")

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0f1117}
[data-testid="stSidebar"]{background:#161b27;border-right:1px solid #2a2f45}
h1,h2,h3{color:#f0f4ff!important}
p,li,label{color:#c8d0e7!important}
.hero{background:linear-gradient(135deg,#1a1f36 0%,#0d1b2a 100%);border:1px solid #2e3a5c;border-radius:16px;padding:2rem 2.5rem;margin-bottom:1.5rem}
.hero h1{font-size:2.4rem!important;font-weight:800;margin-bottom:.3rem}
.hero p{font-size:1.05rem;color:#8892b0!important;margin:0}
.step-badge{display:inline-block;background:#1e3a5f;color:#64b5f6!important;border-radius:20px;padding:4px 14px;font-size:.78rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;margin-bottom:.5rem}
.source-card{background:#1a1f36;border:1px solid #2e3a5c;border-left:4px solid #4f8ef7;border-radius:10px;padding:.75rem 1rem;margin-bottom:.6rem;display:flex;align-items:center;gap:.75rem}
.source-card .favicon{width:20px;height:20px;border-radius:4px}
.source-card a{color:#7eb8f7!important;text-decoration:none;font-weight:500}
.source-card a:hover{text-decoration:underline}
.source-card .domain{font-size:.8rem;color:#5a6a8a!important}
/* ---- Email preview shell ---- */
.nl-preview{background:#fff;border-radius:14px;padding:0;box-shadow:0 8px 40px rgba(0,0,0,.5);max-height:780px;overflow-y:auto;font-family:Georgia,'Times New Roman',serif;font-size:15px;line-height:1.8;color:#1a1a2e!important}
.nl-header{background:#1a1a2e;padding:0;border-radius:14px 14px 0 0;overflow:hidden}
.nl-header-img{width:100%;height:180px;object-fit:cover;display:block;opacity:.7}
.nl-header-text{padding:20px 32px 24px}
.nl-header-text h1{color:#fff!important;font-size:1.55rem!important;font-weight:800;margin:0 0 4px;letter-spacing:-.4px}
.nl-header-text p{color:#8892b0!important;font-size:.82rem;margin:0}
.nl-body{padding:24px 32px}
.nl-intro{background:#f0f4ff;border-left:4px solid #4f8ef7;padding:14px 18px;border-radius:6px;margin-bottom:28px;font-style:italic;color:#2d3561!important;font-size:.97rem}
/* story card */
.story-card{margin-bottom:32px;border-radius:10px;overflow:hidden;border:1px solid #e8eaf6;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.story-card-img{width:100%;height:160px;object-fit:cover;display:block}
.story-card-img-placeholder{width:100%;height:100px;background:linear-gradient(135deg,#e8f0fe,#f3e8ff);display:flex;align-items:center;justify-content:center;font-size:2rem}
.story-card-body{padding:18px 20px}
.story-tag{display:inline-block;background:#e8f0fe;color:#1a73e8!important;border-radius:12px;padding:3px 12px;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px;font-family:Arial,sans-serif}
.story-headline{font-size:1.12rem;font-weight:800;color:#1a1a2e!important;margin:0 0 12px;line-height:1.4;font-family:Georgia,serif}
.story-body{color:#3d3d3d!important;font-size:.94rem;margin:0 0 10px;line-height:1.75}
.story-insight{background:#fff8e1;border-left:3px solid #f9a825;padding:10px 16px;border-radius:4px;font-size:.88rem;color:#5d4037!important;margin:12px 0;font-family:Arial,sans-serif}
.read-more{display:inline-block;background:#1a73e8;color:#fff!important;padding:6px 16px;border-radius:20px;font-size:.82rem;font-weight:600;text-decoration:none;font-family:Arial,sans-serif;margin-top:6px}
.read-more:hover{background:#1558b0}
.nl-footer{background:#f5f5f5;padding:18px 32px;border-radius:0 0 14px 14px;border-top:1px solid #e0e0e0;font-size:.77rem;color:#888!important;font-family:Arial,sans-serif;line-height:1.6}
/* app metrics */
.metric-box{background:#1a1f36;border:1px solid #2e3a5c;border-radius:10px;padding:1rem;text-align:center}
.metric-box .val{font-size:1.8rem;font-weight:700;color:#4f8ef7!important}
.metric-box .lbl{font-size:.8rem;color:#5a6a8a!important}
.subject-pill{display:inline-block;background:#1e3a5f;color:#90caf9!important;border:1px solid #2e5c9a;border-radius:20px;padding:5px 14px;margin:4px 4px 4px 0;font-size:.85rem}
.stButton>button{background:linear-gradient(135deg,#1e6fff,#4f8ef7)!important;color:#fff!important;border:none!important;border-radius:10px!important;font-weight:600!important;padding:.6rem 1.5rem!important;width:100%}
.stButton>button:hover{opacity:.88}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBuilder/1.4)"}

FORMAT_GUIDE = """
You are an expert newsletter editor producing a premium editorial email in the style of a
high-quality industry digest (think: polished financial / luxury / tech trade letter).

OUTPUT FORMAT — follow this structure exactly, in plain text:

[NEWSLETTER TITLE WITH EMOJI] | [ISSUE LABEL, e.g. Vol. 1 • April 2026]

[INTRO: 1-2 sentence hook. Vivid, scene-setting, draws the reader in immediately.]

──────────────────────────────────────────────────
[CATEGORY TAG — ALL CAPS, 2-4 words, e.g. MARKET MOVE or PRODUCT LAUNCH or DATA DROP]
[STORY HEADLINE — punchy, 8-12 words]

[PARAGRAPH 1: 3-5 sentences. Core facts, numbers, names, who/what/why. Source URL inline in parentheses.]

[PARAGRAPH 2: 2-3 sentences. The so what — implication, context, reader impact. End with a relevant emoji.]

💡 Insight: [One punchy sentence connecting this to the reader’s world.]

Read More: [source URL]

──────────────────────────────────────────────────
[Repeat for each story — aim for 3-5 story blocks total]
──────────────────────────────────────────────────

[CLOSING NOTE: 1-2 sentences editorial voice + engagement question for the reader.]

This newsletter was curated with the assistance of AI tools. All stories reference real
published sources (linked inline). Content should be independently verified before use in
any client-facing, commercial, or external communication.

Rules:
- Plain text only. No markdown (no **, no ##, no bullet lists).
- Separate story blocks with a line of ─ characters.
- Every story MUST include its source URL inline AND in the Read More line.
- The Insight line must start with the 💡 emoji.
- End with exactly 5 subject line ideas under the heading: Subject line ideas:
""".strip()

# ── Image helpers ────────────────────────────────────────────────────────────────
def fetch_og_image(url: str, timeout: int = 10) -> Optional[str]:
    """Try to get the Open Graph / Twitter card image from a page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # OG image
        for prop in ["og:image", "twitter:image", "og:image:secure_url"]:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                img = tag["content"]
                if img.startswith("http"):
                    return img
                return urljoin(url, img)
        # Fallback: first large <img> in the page
        for img_tag in soup.find_all("img", src=True):
            src = img_tag["src"]
            if any(x in src.lower() for x in [".jpg", ".jpeg", ".png", ".webp"]):
                if src.startswith("http"):
                    return src
                return urljoin(url, src)
    except Exception:
        pass
    return None


def fetch_og_images_for_items(items: List[Dict]) -> Dict[str, Optional[str]]:
    """Return {url: image_url_or_None} for each item."""
    result = {}
    for item in items:
        result[item["url"]] = fetch_og_image(item["url"])
    return result


# ── Content fetching ─────────────────────────────────────────────────────────────
def is_rss_or_atom(url: str) -> bool:
    return any(x in url.lower() for x in ["rss", "atom", ".xml", "feed"])

def domain_label(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url

def favicon_url(url: str) -> str:
    return f"https://www.google.com/s2/favicons?sz=32&domain={urlparse(url).netloc}"

def fetch_source(url: str, timeout: int = 15) -> str:
    try:
        if is_rss_or_atom(url):
            parsed = feedparser.parse(url)
            parts = []
            for entry in parsed.entries[:10]:
                parts.append(
                    f"Title: {entry.get('title','')}\n"
                    f"Summary: {entry.get('summary','') or entry.get('description','')}\n"
                    f"Link: {entry.get('link', url)}"
                )
            return "\n\n".join(parts)
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        texts = [t.get_text(" ", strip=True) for t in soup.find_all(["h1","h2","h3","p","li"]) if len(t.get_text(strip=True)) > 20]
        return "\n".join(texts)[:9000]
    except Exception as e:
        return f"[Could not fetch {url}: {e}]"


# ── OpenAI ───────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it in Streamlit Secrets or as an environment variable.")
    return OpenAI(api_key=api_key)

def build_newsletter(items, newsletter_name, audience, extra, model):
    today = datetime.now().strftime("%B %d, %Y")
    source_blocks = []
    for i, item in enumerate(items, 1):
        source_blocks.append(f"Source {i}\nURL: {item['url']}\nDomain: {item['label']}\nContent:\n{item['content']}")
    sources_block = "\n\n".join(source_blocks)
    system_prompt = f"You are an expert newsletter editor.\n\n{FORMAT_GUIDE}"
    user_prompt = textwrap.dedent(f"""
        Today: {today}
        Newsletter name: {newsletter_name or 'The Daily Brief'}
        Audience: {audience or 'Busy professionals'}
        Extra: {extra or 'None'}

        Sources:
        {sources_block}

        Write the full newsletter following the format guide, then add subject line ideas.
    """).strip()
    client = get_openai_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
        temperature=0.75,
    )
    full = resp.choices[0].message.content.strip()
    splitter = "Subject line ideas:"
    if splitter in full:
        body, subs = full.split(splitter, 1)
        subs = splitter + subs
    else:
        body, subs = full, ""
    return {"body": body.strip(), "subjects": subs.strip()}


# ── HTML preview renderer ──────────────────────────────────────────────────────
def render_preview(body: str, newsletter_name: str, urls: List[str], og_images: Dict[str, Optional[str]]) -> str:
    today = datetime.now().strftime("%B %d, %Y")

    # Pick a hero image: first available OG image from sources
    hero_img = next((v for v in og_images.values() if v), None)

    # Header
    header_img_html = ""
    if hero_img:
        header_img_html = f'<img class="nl-header-img" src="{hero_img}" alt="hero" onerror="this.style.display=\'none\'">'

    html = [f"""
    <div class="nl-preview">
      <div class="nl-header">
        {header_img_html}
        <div class="nl-header-text">
          <h1>{newsletter_name or 'The Daily Brief'}</h1>
          <p>{today} &nbsp;•&nbsp; Curated from {len(urls)} source{'s' if len(urls)!=1 else ''}</p>
        </div>
      </div>
      <div class="nl-body">
    """]

    lines = body.split("\n")
    in_story = False
    intro_done = False
    story_img_used = False  # track if current story block already has an image
    buffer = []
    story_url = None        # track the most recent source URL found in a story
    source_img_cycle = [v for v in og_images.values() if v]  # pool of images
    story_img_idx = 0

    def flush_buffer():
        nonlocal buffer
        text = " ".join(buffer).strip()
        buffer = []
        return text

    def story_image_html(url_hint=None):
        nonlocal story_img_idx
        # try to match image to URL hint
        if url_hint and url_hint in og_images and og_images[url_hint]:
            return f'<img class="story-card-img" src="{og_images[url_hint]}" alt="" onerror="this.style.display=\'none\'">'
        if source_img_cycle:
            img = source_img_cycle[story_img_idx % len(source_img_cycle)]
            story_img_idx += 1
            return f'<img class="story-card-img" src="{img}" alt="" onerror="this.style.display=\'none\'">'
        return '<div class="story-card-img-placeholder">📰</div>'

    SEP = re.compile(r'^[─\-=]{4,}$')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Separator
        if SEP.match(line):
            if buffer:
                text = flush_buffer()
                if not intro_done:
                    html.append(f'<div class="nl-intro">{text}</div>')
                    intro_done = True
                else:
                    html.append(f'<p class="story-body">{text}</p>')
            if in_story:
                html.append('</div></div>')  # close story-card-body + story-card
                story_img_used = False
                story_url = None
            in_story = False
            i += 1
            continue

        # Insight
        if line.startswith("💡"):
            if buffer:
                html.append(f'<p class="story-body">{flush_buffer()}</p>')
            html.append(f'<div class="story-insight">{line}</div>')
            i += 1
            continue

        # Read More
        if line.lower().startswith("read more:"):
            url_part = line.split(":", 1)[1].strip()
            if buffer:
                html.append(f'<p class="story-body">{flush_buffer()}</p>')
            html.append(f'<a class="read-more" href="{url_part}" target="_blank">🔗 Read More →</a>')
            i += 1
            continue

        # Category tag (ALL CAPS, 2-5 words)
        words = line.split()
        if line.isupper() and 1 < len(words) <= 5 and not line.startswith("HTTP"):
            if buffer:
                text = flush_buffer()
                html.append(f'<p class="story-body">{text}</p>')
            if in_story:
                html.append('</div></div>')
            # Open new story card + inject image
            html.append('<div class="story-card">')
            html.append(story_image_html(story_url))
            html.append('<div class="story-card-body">')
            html.append(f'<span class="story-tag">{line}</span>')
            in_story = True
            story_img_used = True
            story_url = None
            i += 1
            continue

        # Story headline (line right after category tag)
        prev = lines[i-1].strip() if i > 0 else ""
        prev_words = prev.split()
        if in_story and prev.isupper() and 1 < len(prev_words) <= 5 and len(line) > 15:
            if buffer:
                html.append(f'<p class="story-body">{flush_buffer()}</p>')
            html.append(f'<p class="story-headline">{line}</p>')
            i += 1
            continue

        # Capture any URL found in the line to associate with story image
        url_match = re.search(r'https?://[^\s)]+', line)
        if url_match and story_url is None:
            story_url = url_match.group(0).rstrip('.,)')

        # Empty line
        if not line:
            if buffer:
                text = flush_buffer()
                if not intro_done:
                    html.append(f'<div class="nl-intro">{text}</div>')
                    intro_done = True
                else:
                    html.append(f'<p class="story-body">{text}</p>')
            i += 1
            continue

        buffer.append(line)
        i += 1

    if buffer:
        html.append(f'<p class="story-body">{flush_buffer()}</p>')
    if in_story:
        html.append('</div></div>')

    # Sources footer
    source_links = " &nbsp;•&nbsp; ".join(
        f'<a href="{u}" target="_blank" style="color:#1a73e8;">{domain_label(u)}</a>' for u in urls
    )
    html.append(f"""
      </div>
      <div class="nl-footer">
        <strong>Sources:</strong> {source_links}<br><br>
        This newsletter was curated with the assistance of AI tools. All stories reference real
        published sources (linked inline). Content should be independently verified before use
        in any client-facing, commercial, or external communication.
      </div>
    </div>
    """)
    return "\n".join(html)


# ── UI ───────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>📨 Newsletter Builder</h1>
  <p>Turn any website or RSS feed into a premium visual newsletter — Gmail-ready in seconds.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🔗 Sources")
    st.caption("One URL per line — websites, blogs, or RSS feeds")
    sources_raw = st.text_area("", value="https://www.theneurondaily.com/\nhttps://news.ycombinator.com/\nhttps://techcrunch.com/",
        height=160, label_visibility="collapsed")
    st.markdown("### 📝 Newsletter details")
    newsletter_name = st.text_input("📰 Newsletter name", value="The Daily Brief")
    audience = st.text_input("👥 Audience", value="Busy professionals")
    extra = st.text_area("💬 Extra instructions",
        value="Keep the tone sharp, insightful, and editorial. Each story should feel like it was written by a knowledgeable industry insider.",
        height=100)
    st.markdown("### 🤖 Model")
    model = st.selectbox("ChatGPT model", ["gpt-4.1-mini","gpt-4.1","gpt-4o-mini","gpt-4o"], index=0)
    st.markdown("---")
    fetch_images = st.toggle("🖼️ Fetch images from sources", value=True,
        help="Automatically pulls the cover image from each source website for the email preview.")
    generate_btn = st.button("✨ Build my newsletter", type="primary")
    st.caption("🔑 Needs OPENAI_API_KEY in Streamlit Secrets")

# Source cards
st.markdown('<div class="step-badge">📥 Step 1 — Your Sources</div>', unsafe_allow_html=True)
urls = [u.strip() for u in sources_raw.splitlines() if u.strip()]
if urls:
    cols = st.columns(min(len(urls), 4))
    for idx, url in enumerate(urls):
        with cols[idx % min(len(urls), 4)]:
            st.markdown(f"""
            <div class="source-card">
              <img class="favicon" src="{favicon_url(url)}" onerror="this.style.display='none'">
              <div>
                <a href="{url}" target="_blank">{domain_label(url)}</a><br>
                <span class="domain">{url[:52]}{'...' if len(url)>52 else ''}</span>
              </div>
            </div>""", unsafe_allow_html=True)
else:
    st.info("👆 Add source URLs in the sidebar to get started.")

# Generate
if generate_btn:
    if not urls:
        st.error("❌ Please add at least one source URL.")
        st.stop()

    st.markdown("---")
    st.markdown('<div class="step-badge">⏳ Fetching content & images...</div>', unsafe_allow_html=True)
    progress = st.progress(0, text="Starting...")

    items: List[Dict] = []
    for i, url in enumerate(urls):
        progress.progress(int(i/len(urls)*40), text=f"🔍 Fetching {domain_label(url)}...")
        items.append({"url": url, "label": domain_label(url), "content": fetch_source(url)})

    og_images: Dict[str, Optional[str]] = {}
    if fetch_images:
        progress.progress(40, text="🖼️ Fetching cover images...")
        for i, item in enumerate(items):
            progress.progress(40 + int(i/len(items)*20), text=f"🖼️ Getting image from {item['label']}...")
            og_images[item["url"]] = fetch_og_image(item["url"])
    else:
        og_images = {item["url"]: None for item in items}

    progress.progress(60, text="🤖 Writing newsletter with ChatGPT...")
    try:
        result = build_newsletter(items=items, newsletter_name=newsletter_name,
            audience=audience, extra=extra, model=model)
        progress.progress(100, text="✅ Done!")
    except RuntimeError as e:
        progress.empty(); st.error(str(e))
        st.info("🔑 Set OPENAI_API_KEY in Streamlit Cloud → App Settings → Secrets")
        st.stop()
    except Exception as e:
        progress.empty(); st.error(f"❌ ChatGPT error: {e}")
        st.stop()

    # Metrics
    st.markdown("---")
    wc = len(result["body"].split())
    rt = max(1, round(wc/200))
    stories = result["body"].count("💡 Insight:")
    imgs_found = sum(1 for v in og_images.values() if v)
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1: st.markdown(f'<div class="metric-box"><div class="val">{len(urls)}</div><div class="lbl">🔗 Sources</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box"><div class="val">{stories}</div><div class="lbl">📰 Stories</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box"><div class="val">{wc}</div><div class="lbl">📝 Words</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-box"><div class="val">{rt} min</div><div class="lbl">⏱️ Read time</div></div>', unsafe_allow_html=True)
    with c5: st.markdown(f'<div class="metric-box"><div class="val">{imgs_found}</div><div class="lbl">🖼️ Images</div></div>', unsafe_allow_html=True)

    # Two-column output
    st.markdown("---")
    st.markdown('<div class="step-badge">📨 Your Newsletter</div>', unsafe_allow_html=True)
    st.caption("Left: visual email preview with images · Right: plain text for Gmail")
    left, right = st.columns([1.2, 0.8])
    with left:
        st.markdown("👁️ **Visual email preview**")
        st.markdown(render_preview(result["body"], newsletter_name, urls, og_images), unsafe_allow_html=True)
    with right:
        st.markdown("📋 **Copy into Gmail** — select all → Ctrl+C → paste")
        st.text_area("", value=result["body"], height=640, label_visibility="collapsed")

    # Subject lines
    if result.get("subjects"):
        st.markdown("---")
        st.markdown("🎯 **Subject line ideas**")
        lines_sub = [l.strip().lstrip("-").strip() for l in result["subjects"].splitlines()
            if l.strip() and l.strip() != "Subject line ideas:"]
        for line in lines_sub:
            if line:
                st.markdown(f'<span class="subject-pill">📧 {line}</span>', unsafe_allow_html=True)
        st.markdown("")
        st.text_area("📬 Full subject block", value=result["subjects"], height=160)

else:
    st.markdown("---")
    st.markdown("""
    <div style="background:#1a1f36;border:1px solid #2e3a5c;border-radius:12px;padding:1.5rem 2rem;text-align:center;">
      <p style="font-size:1.1rem;color:#7eb8f7!important;margin:0;">
        👈 Add sources in the sidebar, then click <strong style='color:#4f8ef7;'>✨ Build my newsletter</strong>
      </p>
      <p style="color:#5a6a8a!important;font-size:.85rem;margin-top:.5rem;">
        Websites · RSS feeds · Blogs · News sites · Auto image fetch included
      </p>
    </div>
    """, unsafe_allow_html=True)
