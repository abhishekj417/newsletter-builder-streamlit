import os
import textwrap
from datetime import datetime
from typing import List, Dict
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Newsletter Builder",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ---- global ---- */
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stSidebar"] { background: #161b27; border-right: 1px solid #2a2f45; }
h1, h2, h3 { color: #f0f4ff !important; }
p, li, label { color: #c8d0e7 !important; }

/* ---- hero banner ---- */
.hero {
    background: linear-gradient(135deg, #1a1f36 0%, #0d1b2a 100%);
    border: 1px solid #2e3a5c;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
}
.hero h1 { font-size: 2.4rem !important; font-weight: 800; margin-bottom: 0.3rem; }
.hero p  { font-size: 1.05rem; color: #8892b0 !important; margin: 0; }

/* ---- step badge ---- */
.step-badge {
    display: inline-block;
    background: #1e3a5f;
    color: #64b5f6 !important;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

/* ---- source card ---- */
.source-card {
    background: #1a1f36;
    border: 1px solid #2e3a5c;
    border-left: 4px solid #4f8ef7;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.source-card .favicon { width: 20px; height: 20px; border-radius: 4px; }
.source-card a { color: #7eb8f7 !important; text-decoration: none; font-weight: 500; }
.source-card a:hover { text-decoration: underline; }
.source-card .domain { font-size: 0.8rem; color: #5a6a8a !important; }

/* ---- newsletter preview ---- */
.nl-preview {
    background: #ffffff;
    border-radius: 12px;
    padding: 2rem 2.5rem;
    color: #1a1a2e !important;
    font-family: Georgia, serif;
    font-size: 15px;
    line-height: 1.75;
    white-space: pre-wrap;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    max-height: 600px;
    overflow-y: auto;
}
.nl-preview p { color: #1a1a2e !important; }

/* ---- subject pill ---- */
.subject-pill {
    display: inline-block;
    background: #1e3a5f;
    color: #90caf9 !important;
    border: 1px solid #2e5c9a;
    border-radius: 20px;
    padding: 5px 14px;
    margin: 4px 4px 4px 0;
    font-size: 0.85rem;
    cursor: pointer;
}

/* ---- metric card ---- */
.metric-box {
    background: #1a1f36;
    border: 1px solid #2e3a5c;
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
}
.metric-box .val { font-size: 1.8rem; font-weight: 700; color: #4f8ef7 !important; }
.metric-box .lbl { font-size: 0.8rem; color: #5a6a8a !important; }

/* ---- copy box ---- */
.copy-area textarea {
    background: #12161f !important;
    color: #e0e8ff !important;
    border: 1px solid #2e3a5c !important;
    border-radius: 10px !important;
    font-family: monospace !important;
    font-size: 13px !important;
}

/* ---- button ---- */
.stButton > button {
    background: linear-gradient(135deg, #1e6fff, #4f8ef7) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important;
    width: 100%;
}
.stButton > button:hover { opacity: 0.88; transform: translateY(-1px); }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBuilder/1.2)"}

STYLE_GUIDES = {
    "Default": """
Write a polished plain-text newsletter for Gmail.
Use short paragraphs and bullet points.
Keep it concise, clear, and easy to copy-paste.
""".strip(),

    "Neuron-inspired 🧠": """
Write a daily AI-newsletter-style email inspired by fast, witty, business-friendly digests.

Important:
- Do not copy exact phrasing from any existing newsletter.
- Do not mention The Neuron.
- Capture only high-level traits: concise, playful, sharp, highly scannable, and lightly witty.
- Write for busy professionals who want the most important updates quickly.
- Use relevant emojis at the start of each section heading and each bullet point.

Required structure (use these exact section headings with emojis):
1. Newsletter title with a relevant emoji at the very top.
2. A 1-2 sentence intro that feels energetic and human.
3. Section heading: 📡 What you need to know today:
   - 3 to 5 bullets max. Start each bullet with a relevant emoji.
   - Each bullet: bold-style headline (write it in CAPS) + short explanation + source domain in parentheses.
4. Section heading: 💡 Why it matters:
   - 2 to 4 bullets starting with a relevant emoji.
   - Connect news to business impact, workflow change, market direction, or practical use.
5. Section heading: 🌐 Around the web:
   - 2 to 4 short extra items. Each starts with an emoji and ends with the source URL in parentheses.
6. Section heading: 🛠️ Tools to try:
   - 1 to 3 practical tools/launches/features if present. Each starts with 🔧 and includes the URL.
7. Closing line with a fun sign-off emoji.

Voice:
- Plain text only, no markdown symbols like ** or #.
- Smart, punchy, lightly humorous.
- Not too formal, not slang-heavy.
- Prioritize clarity, momentum, and curiosity.
- Keep sentences short.
- Avoid fluff and generic transitions.
- Always include the source URL or domain next to each referenced item.
""".strip(),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_rss_or_atom(url: str) -> bool:
    return any(x in url.lower() for x in ["rss", "atom", ".xml", "feed"])


def domain_label(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url


def favicon_url(url: str) -> str:
    domain = urlparse(url).netloc
    return f"https://www.google.com/s2/favicons?sz=32&domain={domain}"


def fetch_source(url: str, timeout: int = 15) -> str:
    try:
        if is_rss_or_atom(url):
            parsed = feedparser.parse(url)
            parts = []
            for entry in parsed.entries[:10]:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                link = entry.get("link", url)
                parts.append(f"Title: {title}\nSummary: {summary}\nLink: {link}")
            return "\n\n".join(parts)

        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        texts = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            txt = tag.get_text(" ", strip=True)
            if txt and len(txt) > 20:
                texts.append(txt)
        return "\n".join(texts)[:9000]
    except Exception as e:
        return f"[Could not fetch {url}: {e}]"


@st.cache_resource(show_spinner=False)
def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it in Streamlit Secrets or as an environment variable."
        )
    return OpenAI(api_key=api_key)


def build_newsletter(
    items: List[Dict],
    tone: str,
    audience: str,
    extra: str,
    model: str,
    style: str,
) -> Dict[str, str]:
    style_key = style
    guide = STYLE_GUIDES.get(style_key, STYLE_GUIDES["Default"])

    system_prompt = textwrap.dedent(f"""
        You are an expert newsletter copywriter.
        {guide}
    """).strip()

    source_blocks = []
    for i, item in enumerate(items, 1):
        source_blocks.append(textwrap.dedent(f"""
            Source {i}
            URL: {item['url']}
            Domain: {item['label']}
            Content:
            {item['content']}
        """).strip())

    sources_block = "\n\n".join(source_blocks)
    today = datetime.now().strftime("%B %d, %Y")

    user_prompt = textwrap.dedent(f"""
        Today's date: {today}
        Audience: {audience or 'Busy professionals'}
        Tone: {tone or 'Punchy, witty, concise, business-friendly'}
        Style: {style}
        Extra instructions: {extra or 'None'}

        Sources:
        {sources_block}

        Requirements:
        - Use only the provided source material.
        - After each referenced item or bullet, include the source URL in parentheses.
        - Keep it copy-paste ready for Gmail (plain text only, no markdown).
        - Use emojis in section headings and bullets to make it scannable.
        - Include clear blank lines between sections.
        - End with exactly 5 subject line ideas under the heading: Subject line ideas:
        - Do not copy branded phrases from existing newsletters.
        - Do not ask follow-up questions.
    """).strip()

    client = get_openai_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8 if "Neuron" in style else 0.7,
    )

    full = resp.choices[0].message.content.strip()
    splitter = "Subject line ideas:"
    if splitter in full:
        body, subs = full.split(splitter, 1)
        subs = splitter + subs
    else:
        body, subs = full, ""

    return {"body": body.strip(), "subjects": subs.strip()}


# ── Hero Banner ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>📨 Newsletter Builder</h1>
  <p>Turn any website or RSS feed into a Gmail-ready newsletter — in seconds.</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔗 Sources")
    st.caption("One URL per line — websites, blogs, or RSS feeds")
    sources_raw = st.text_area(
        "",
        value="https://www.theneurondaily.com/\nhttps://news.ycombinator.com/\nhttps://techcrunch.com/",
        height=160,
        label_visibility="collapsed",
    )

    st.markdown("### 🎨 Style")
    style_preset = st.selectbox(
        "Newsletter style",
        list(STYLE_GUIDES.keys()),
        index=0,
    )
    tone = st.text_input("🎤 Tone", value="Punchy, witty, concise, and business-friendly")
    audience = st.text_input("👥 Audience", value="Busy professionals keeping up with AI")
    extra = st.text_area(
        "📝 Extra instructions",
        value="Make it feel like a premium daily AI digest. Skimmable, energetic, and Gmail-ready. Prioritize practical takeaways.",
        height=110,
    )

    st.markdown("### 🤖 Model")
    model = st.selectbox(
        "ChatGPT model",
        ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"],
        index=0,
    )

    st.markdown("---")
    generate_btn = st.button("✨ Build my newsletter", type="primary")
    st.caption("🔑 Needs OPENAI_API_KEY in Streamlit Secrets")

# ── Step 1: Source cards ──────────────────────────────────────────────────────
st.markdown('<div class="step-badge">📥 Step 1 — Your Sources</div>', unsafe_allow_html=True)

urls = [u.strip() for u in sources_raw.splitlines() if u.strip()]
if urls:
    for url in urls:
        label = domain_label(url)
        fav = favicon_url(url)
        st.markdown(f"""
        <div class="source-card">
          <img class="favicon" src="{fav}" onerror="this.style.display='none'">
          <div>
            <a href="{url}" target="_blank">{label}</a><br>
            <span class="domain">{url}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("👆 Add source URLs in the sidebar to get started.")

# ── Generate ──────────────────────────────────────────────────────────────────
if generate_btn:
    if not urls:
        st.error("❌ Please add at least one source URL in the sidebar.")
        st.stop()

    st.markdown("---")
    st.markdown('<div class="step-badge">⏳ Step 2 — Fetching Content</div>', unsafe_allow_html=True)

    progress = st.progress(0, text="Starting...")
    items: List[Dict] = []
    for i, url in enumerate(urls):
        progress.progress(int((i / len(urls)) * 50), text=f"🔍 Fetching {domain_label(url)}...")
        items.append({"url": url, "label": domain_label(url), "content": fetch_source(url)})
    progress.progress(50, text="🧠 Sending to ChatGPT...")

    try:
        result = build_newsletter(
            items=items,
            tone=tone,
            audience=audience,
            extra=extra,
            model=model,
            style=style_preset,
        )
        progress.progress(100, text="✅ Done!")
    except RuntimeError as e:
        progress.empty()
        st.error(str(e))
        st.info("🔑 Set OPENAI_API_KEY in Streamlit Cloud → App Settings → Secrets")
        st.stop()
    except Exception as e:
        progress.empty()
        st.error(f"❌ ChatGPT API error: {e}")
        st.stop()

    # ── Metrics row ───────────────────────────────────────────────────────────
    st.markdown("---")
    word_count = len(result["body"].split())
    read_time = max(1, round(word_count / 200))
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-box"><div class="val">{len(urls)}</div><div class="lbl">🔗 Sources</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-box"><div class="val">{word_count}</div><div class="lbl">📝 Words</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-box"><div class="val">{read_time} min</div><div class="lbl">⏱️ Read time</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-box"><div class="val">{style_preset.split()[0]}</div><div class="lbl">🎨 Style</div></div>', unsafe_allow_html=True)

    # ── Two-column output ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="step-badge">📨 Step 3 — Your Newsletter</div>', unsafe_allow_html=True)
    st.caption("Left: Gmail preview · Right: Copy-paste text")

    left, right = st.columns([1.1, 0.9])

    with left:
        st.markdown("👁️ **Preview** (how it looks in an email client)")
        preview_html = result["body"].replace("\n", "<br>")
        st.markdown(f'<div class="nl-preview">{preview_html}</div>', unsafe_allow_html=True)

    with right:
        st.markdown("📋 **Copy-paste ready** (select all → Ctrl+C → paste into Gmail)")
        st.markdown('<div class="copy-area">', unsafe_allow_html=True)
        st.text_area("", value=result["body"], height=540, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Source links used ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("🔗 **Sources used in this edition**")
    cols = st.columns(min(len(urls), 4))
    for i, url in enumerate(urls):
        with cols[i % len(cols)]:
            label = domain_label(url)
            fav = favicon_url(url)
            st.markdown(
                f'<div class="source-card" style="flex-direction:column;align-items:flex-start;">'
                f'<div style="display:flex;align-items:center;gap:8px;">'
                f'<img class="favicon" src="{fav}" onerror="this.style.display=\'none\';">'
                f'<a href="{url}" target="_blank"><strong>{label}</strong></a></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Subject lines ─────────────────────────────────────────────────────────
    if result.get("subjects"):
        st.markdown("---")
        st.markdown("🎯 **Subject line ideas** — pick one and paste into Gmail subject")
        lines = [l.strip().lstrip("-").strip() for l in result["subjects"].splitlines() if l.strip() and l.strip() != "Subject line ideas:"]
        for line in lines:
            if line:
                st.markdown(f'<span class="subject-pill">📧 {line}</span>', unsafe_allow_html=True)
        st.markdown("---")
        st.text_area("📬 Full subject block (copy-paste)", value=result["subjects"], height=160)

else:
    st.markdown("---")
    st.markdown("""
    <div style="background:#1a1f36;border:1px solid #2e3a5c;border-radius:12px;padding:1.5rem 2rem;text-align:center;">
      <p style="font-size:1.1rem;color:#7eb8f7 !important;margin:0;">
        👈 Add your sources in the sidebar, then click <strong style='color:#4f8ef7;'>✨ Build my newsletter</strong>
      </p>
      <p style="color:#4a5568 !important;font-size:0.85rem;margin-top:0.5rem;">
        Supports any website · RSS feeds · Blogs · News sites
      </p>
    </div>
    """, unsafe_allow_html=True)
