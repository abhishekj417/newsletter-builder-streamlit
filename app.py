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

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Newsletter Builder",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stSidebar"]          { background: #161b27; border-right: 1px solid #2a2f45; }
h1,h2,h3 { color: #f0f4ff !important; }
p,li,label { color: #c8d0e7 !important; }

.hero {
    background: linear-gradient(135deg,#1a1f36 0%,#0d1b2a 100%);
    border: 1px solid #2e3a5c; border-radius:16px;
    padding:2rem 2.5rem; margin-bottom:1.5rem;
}
.hero h1 { font-size:2.4rem !important; font-weight:800; margin-bottom:0.3rem; }
.hero p  { font-size:1.05rem; color:#8892b0 !important; margin:0; }

.step-badge {
    display:inline-block; background:#1e3a5f; color:#64b5f6 !important;
    border-radius:20px; padding:4px 14px; font-size:0.78rem;
    font-weight:600; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:0.5rem;
}

.source-card {
    background:#1a1f36; border:1px solid #2e3a5c; border-left:4px solid #4f8ef7;
    border-radius:10px; padding:0.75rem 1rem; margin-bottom:0.6rem;
    display:flex; align-items:center; gap:0.75rem;
}
.source-card .favicon { width:20px; height:20px; border-radius:4px; }
.source-card a { color:#7eb8f7 !important; text-decoration:none; font-weight:500; }
.source-card a:hover { text-decoration:underline; }
.source-card .domain { font-size:0.8rem; color:#5a6a8a !important; }

/* ---- Email preview pane ---- */
.nl-preview {
    background:#ffffff; border-radius:12px; padding:0;
    box-shadow:0 8px 32px rgba(0,0,0,0.4);
    max-height:700px; overflow-y:auto;
    font-family: Georgia, 'Times New Roman', serif;
    font-size:15px; line-height:1.8; color:#1a1a2e !important;
}
.nl-preview .nl-header {
    background:#1a1a2e; padding:28px 36px;
    border-radius:12px 12px 0 0;
}
.nl-preview .nl-header h1 {
    color:#ffffff !important; font-size:1.6rem !important;
    font-weight:800; margin:0 0 4px 0; letter-spacing:-0.5px;
}
.nl-preview .nl-header p {
    color:#8892b0 !important; font-size:0.82rem; margin:0;
}
.nl-preview .nl-body { padding:28px 36px; }
.nl-preview .nl-intro {
    background:#f8f9ff; border-left:4px solid #4f8ef7;
    padding:14px 18px; border-radius:6px;
    margin-bottom:28px; font-style:italic;
    color:#2d3561 !important; font-size:0.97rem;
}
.nl-preview .story-block { margin-bottom:32px; border-bottom:1px solid #e8eaf6; padding-bottom:28px; }
.nl-preview .story-block:last-child { border-bottom:none; }
.nl-preview .story-tag {
    display:inline-block; background:#e8f0fe; color:#1a73e8 !important;
    border-radius:12px; padding:3px 12px; font-size:0.75rem;
    font-weight:700; text-transform:uppercase; letter-spacing:0.05em;
    margin-bottom:10px; font-family:Arial,sans-serif;
}
.nl-preview .story-headline {
    font-size:1.18rem; font-weight:800; color:#1a1a2e !important;
    margin:0 0 12px 0; line-height:1.4; font-family:Georgia,serif;
}
.nl-preview .story-body {
    color:#3d3d3d !important; font-size:0.96rem; margin:0 0 12px 0; line-height:1.8;
}
.nl-preview .story-insight {
    background:#fff8e1; border-left:3px solid #f9a825;
    padding:10px 16px; border-radius:4px;
    font-size:0.9rem; color:#5d4037 !important;
    margin:12px 0; font-family:Arial,sans-serif;
}
.nl-preview .read-more {
    display:inline-block; color:#1a73e8 !important;
    font-size:0.85rem; font-weight:600; text-decoration:none;
    font-family:Arial,sans-serif;
}
.nl-preview .read-more:hover { text-decoration:underline; }
.nl-preview .nl-cta {
    background:#1a1a2e; border-radius:8px; padding:18px 24px;
    margin:24px 0; text-align:center;
}
.nl-preview .nl-cta p { color:#ffffff !important; font-size:0.97rem; margin:0 0 12px 0; font-family:Arial,sans-serif; }
.nl-preview .nl-footer {
    background:#f5f5f5; padding:20px 36px;
    border-radius:0 0 12px 12px; border-top:1px solid #e0e0e0;
    font-size:0.78rem; color:#888888 !important; font-family:Arial,sans-serif;
    line-height:1.6;
}

.metric-box {
    background:#1a1f36; border:1px solid #2e3a5c;
    border-radius:10px; padding:1rem; text-align:center;
}
.metric-box .val { font-size:1.8rem; font-weight:700; color:#4f8ef7 !important; }
.metric-box .lbl { font-size:0.8rem; color:#5a6a8a !important; }

.subject-pill {
    display:inline-block; background:#1e3a5f; color:#90caf9 !important;
    border:1px solid #2e5c9a; border-radius:20px;
    padding:5px 14px; margin:4px 4px 4px 0; font-size:0.85rem;
}

.stButton > button {
    background:linear-gradient(135deg,#1e6fff,#4f8ef7) !important;
    color:white !important; border:none !important;
    border-radius:10px !important; font-weight:600 !important;
    padding:0.6rem 1.5rem !important; width:100%;
}
.stButton > button:hover { opacity:0.88; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBuilder/1.3)"}

# This prompt mirrors the ticks_trends HTML newsletter format exactly:
# - Newsletter title + issue line at top
# - Short italicised intro paragraph (the hook)
# - Per-story blocks: category tag | bold headline | 2-paragraph narrative | insight callout | Read More link
# - Closing editorial note with engagement question
# - AI disclaimer footer
FORMAT_GUIDE = """
You are an expert newsletter editor producing a premium editorial email in the style of a
high-quality industry digest (think: polished financial / luxury / tech trade letter).

OUTPUT FORMAT — follow this structure exactly, in plain text:

---
[NEWSLETTER TITLE WITH EMOJI] | [ISSUE LABEL, e.g. "Vol. 1 • April 2026"]

[INTRO: 1-2 sentence hook. Vivid, scene-setting, draws the reader in immediately.]

──────────────────────────────────────────────────
[CATEGORY TAG — e.g. MARKET MOVE / PRODUCT LAUNCH / INDUSTRY SHIFT / DATA DROP]
[STORY HEADLINE — bold, punchy, 8-12 words]

[PARAGRAPH 1: 3-5 sentences. Core facts, what happened, who is involved, numbers if available.
Include the source URL inline in parentheses at the end of the relevant sentence.]

[PARAGRAPH 2: 2-3 sentences. The “so what” — implication, context, what it means for the reader.
End with a relevant emoji for energy.]

💡 Insight: [One punchy sentence connecting this story to the reader’s world or business.]

Read More: [source URL]

──────────────────────────────────────────────────
[Repeat the above CATEGORY TAG / HEADLINE / PARAGRAPHS / INSIGHT / READ MORE block
for EACH story from the sources. Aim for 3-5 story blocks total.]

──────────────────────────────────────────────────
[CLOSING NOTE: 1-2 sentences, editorial voice, end with an engagement question for the reader.]

This newsletter was curated with the assistance of AI tools. All stories reference real
published sources (linked inline). Content should be independently verified before use in
any client-facing, commercial, or external communication.
---

Rules:
- Plain text only. No markdown (no **, no ##, no bullet lists).
- Keep each story block separated by a line of dashes (───...).
- Every story MUST include its source URL inline and in the Read More line.
- The Insight line must start with the 💡 emoji.
- Closing question must be engaging and relevant to the content.
- Do not use placeholder text. Only use content from the provided sources.
- Do not copy branded phrases from existing newsletters.
- End with exactly 5 subject line ideas under the heading: Subject line ideas:
""".strip()

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
                title   = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                link    = entry.get("link", url)
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
    newsletter_name: str,
    audience: str,
    extra: str,
    model: str,
) -> Dict[str, str]:
    today = datetime.now().strftime("%B %d, %Y")

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

    system_prompt = f"You are an expert newsletter editor.\n\n{FORMAT_GUIDE}"

    user_prompt = textwrap.dedent(f"""
        Today's date: {today}
        Newsletter name: {newsletter_name or 'The Daily Brief'}
        Audience: {audience or 'Busy professionals'}
        Extra instructions: {extra or 'None'}

        Sources to use:
        {sources_block}

        Write the full newsletter now, following the format guide exactly.
        After the newsletter body, add the subject line ideas section.
    """).strip()

    client = get_openai_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
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


def render_preview(body: str, newsletter_name: str, urls: List[str]) -> str:
    """Convert the plain-text newsletter body into a styled HTML email preview."""
    today = datetime.now().strftime("%B %d, %Y")
    lines = body.split("\n")

    html_parts = []
    html_parts.append(f"""
    <div class="nl-preview">
      <div class="nl-header">
        <h1>{newsletter_name or 'The Daily Brief'}</h1>
        <p>{today} &nbsp;•&nbsp; Curated from {len(urls)} source{'s' if len(urls)!=1 else ''}</p>
      </div>
      <div class="nl-body">
    """)

    in_story = False
    intro_done = False
    buffer = []

    def flush_buffer():
        nonlocal buffer
        text = " ".join(buffer).strip()
        buffer = []
        return text

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip separator lines
        if set(line) <= {"─", "-", "="} and len(line) > 4:
            if buffer:
                text = flush_buffer()
                if not intro_done:
                    html_parts.append(f'<div class="nl-intro">{text}</div>')
                    intro_done = True
                else:
                    html_parts.append(f'<p class="story-body">{text}</p>')
            if in_story:
                html_parts.append('</div>')  # close story-block
            in_story = False
            i += 1
            continue

        # Insight line
        if line.startswith("💡 Insight:") or line.startswith("💡Insight:"):
            if buffer:
                text = flush_buffer()
                html_parts.append(f'<p class="story-body">{text}</p>')
            html_parts.append(f'<div class="story-insight">{line}</div>')
            i += 1
            continue

        # Read More line
        if line.lower().startswith("read more:"):
            url_part = line.split(":", 1)[1].strip() if ":" in line else "#"
            if buffer:
                text = flush_buffer()
                html_parts.append(f'<p class="story-body">{text}</p>')
            html_parts.append(f'<a class="read-more" href="{url_part}" target="_blank">🔗 Read More →</a>')
            i += 1
            continue

        # Category tag lines (ALL CAPS short label)
        if line.isupper() and 2 < len(line.split()) <= 5 and not line.startswith("HTTP"):
            if buffer:
                text = flush_buffer()
                html_parts.append(f'<p class="story-body">{text}</p>')
            if in_story:
                html_parts.append('</div>')
            html_parts.append('<div class="story-block">')
            html_parts.append(f'<span class="story-tag">{line}</span>')
            in_story = True
            i += 1
            continue

        # Story headline detection: next non-empty line after category tag
        # Detect by: not starting with emoji/number, title-case, medium length
        if in_story and line and not line.startswith("💡") and not line.lower().startswith("read more") and len(line) > 20 and not any(c.isdigit() and line.startswith(c) for c in "0123456789"):
            # Check if it looks like a headline (short-ish, no period at end, bold feel)
            prev_was_tag = i > 0 and lines[i-1].strip().isupper() and len(lines[i-1].strip().split()) <= 5
            if prev_was_tag:
                if buffer:
                    text = flush_buffer()
                    html_parts.append(f'<p class="story-body">{text}</p>')
                html_parts.append(f'<p class="story-headline">{line}</p>')
                i += 1
                continue

        # Empty line = flush buffer as paragraph
        if not line:
            if buffer:
                text = flush_buffer()
                if not intro_done:
                    html_parts.append(f'<div class="nl-intro">{text}</div>')
                    intro_done = True
                else:
                    html_parts.append(f'<p class="story-body">{text}</p>')
            i += 1
            continue

        buffer.append(line)
        i += 1

    if buffer:
        text = flush_buffer()
        html_parts.append(f'<p class="story-body">{text}</p>')
    if in_story:
        html_parts.append('</div>')

    # Footer
    source_links = " &nbsp;•&nbsp; ".join(
        [f'<a href="{u}" target="_blank" style="color:#1a73e8;">{domain_label(u)}</a>' for u in urls]
    )
    html_parts.append(f"""
      </div>
      <div class="nl-footer">
        <strong>Sources:</strong> {source_links}<br><br>
        This newsletter was curated with the assistance of AI tools. All stories reference real
        published sources (linked inline). Content should be independently verified before use in
        any client-facing, commercial, or external communication.
      </div>
    </div>
    """)

    return "\n".join(html_parts)


# ── Hero Banner ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>📨 Newsletter Builder</h1>
  <p>Turn any website or RSS feed into a premium Gmail-ready newsletter — in seconds.</p>
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

    st.markdown("### 📝 Newsletter details")
    newsletter_name = st.text_input("📰 Newsletter name", value="The Daily Brief",
        help="Appears in the header of the email")
    audience = st.text_input("👥 Audience", value="Busy professionals",
        help="Who are you writing for?")
    extra = st.text_area(
        "💬 Extra instructions (optional)",
        value="Keep the tone sharp, insightful, and editorial. Each story should feel like it was written by a knowledgeable industry insider.",
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

# ── Source cards preview ──────────────────────────────────────────────────────
st.markdown('<div class="step-badge">📥 Step 1 — Your Sources</div>', unsafe_allow_html=True)
urls = [u.strip() for u in sources_raw.splitlines() if u.strip()]

if urls:
    cols = st.columns(min(len(urls), 4))
    for idx, url in enumerate(urls):
        with cols[idx % min(len(urls), 4)]:
            label = domain_label(url)
            fav = favicon_url(url)
            st.markdown(f"""
            <div class="source-card">
              <img class="favicon" src="{fav}" onerror="this.style.display='none'">
              <div>
                <a href="{url}" target="_blank">{label}</a><br>
                <span class="domain">{url[:55]}{'...' if len(url)>55 else ''}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("👆 Add source URLs in the sidebar to get started.")

# ── Generate ──────────────────────────────────────────────────────────────────
if generate_btn:
    if not urls:
        st.error("❌ Please add at least one source URL.")
        st.stop()

    st.markdown("---")
    st.markdown('<div class="step-badge">⏳ Step 2 — Fetching & Writing</div>', unsafe_allow_html=True)

    progress = st.progress(0, text="Starting...")
    items: List[Dict] = []
    for i, url in enumerate(urls):
        pct = int((i / len(urls)) * 50)
        progress.progress(pct, text=f"🔍 Fetching {domain_label(url)}...")
        items.append({"url": url, "label": domain_label(url), "content": fetch_source(url)})
    progress.progress(50, text="🤖 Writing your newsletter with ChatGPT...")

    try:
        result = build_newsletter(
            items=items,
            newsletter_name=newsletter_name,
            audience=audience,
            extra=extra,
            model=model,
        )
        progress.progress(100, text="✅ Done!")
    except RuntimeError as e:
        progress.empty()
        st.error(str(e))
        st.info("🔑 Set OPENAI_API_KEY in Streamlit Cloud → App Settings → Secrets")
        st.stop()
    except Exception as e:
        progress.empty()
        st.error(f"❌ ChatGPT error: {e}")
        st.stop()

    # Metrics
    st.markdown("---")
    wc = len(result["body"].split())
    rt = max(1, round(wc / 200))
    stories = result["body"].count("💡 Insight:")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-box"><div class="val">{len(urls)}</div><div class="lbl">🔗 Sources</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box"><div class="val">{stories}</div><div class="lbl">📰 Stories</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box"><div class="val">{wc}</div><div class="lbl">📝 Words</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-box"><div class="val">{rt} min</div><div class="lbl">⏱️ Read time</div></div>', unsafe_allow_html=True)

    # Two-column output
    st.markdown("---")
    st.markdown('<div class="step-badge">📨 Step 3 — Your Newsletter</div>', unsafe_allow_html=True)
    st.caption("Left: styled email preview · Right: plain text to copy into Gmail")

    left, right = st.columns([1.15, 0.85])

    with left:
        st.markdown("👁️ **Email preview**")
        preview_html = render_preview(result["body"], newsletter_name, urls)
        st.markdown(preview_html, unsafe_allow_html=True)

    with right:
        st.markdown("📋 **Copy into Gmail** — select all → Ctrl+C → paste")
        st.text_area("", value=result["body"], height=620, label_visibility="collapsed")

    # Subject lines
    if result.get("subjects"):
        st.markdown("---")
        st.markdown("🎯 **Subject line ideas** — pick one for your Gmail subject field")
        lines = [
            l.strip().lstrip("-").strip()
            for l in result["subjects"].splitlines()
            if l.strip() and l.strip() != "Subject line ideas:"
        ]
        for line in lines:
            if line:
                st.markdown(f'<span class="subject-pill">📧 {line}</span>', unsafe_allow_html=True)
        st.markdown("")
        st.text_area("📬 Full subject block", value=result["subjects"], height=160)

else:
    st.markdown("---")
    st.markdown("""
    <div style="background:#1a1f36;border:1px solid #2e3a5c;border-radius:12px;padding:1.5rem 2rem;text-align:center;">
      <p style="font-size:1.1rem;color:#7eb8f7 !important;margin:0;">
        👈 Configure sources in the sidebar, then click <strong style='color:#4f8ef7;'>✨ Build my newsletter</strong>
      </p>
      <p style="color:#5a6a8a !important;font-size:0.85rem;margin-top:0.5rem;">
        Supports websites · RSS feeds · Blogs · News sites
      </p>
    </div>
    """, unsafe_allow_html=True)
