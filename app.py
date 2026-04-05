import os
import textwrap
from typing import List, Dict
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBuilder/1.1)"}

STYLE_GUIDES = {
    "Default": """
Write a polished plain-text newsletter for Gmail.
Use short paragraphs and bullet points.
Keep it concise, clear, and easy to copy-paste.
""".strip(),
    "Neuron-inspired": """
Write a daily AI-newsletter-style email inspired by fast, witty, business-friendly digests.

Important:
- Do not copy exact phrasing from any existing newsletter.
- Do not mention The Neuron.
- Capture only high-level traits: concise, playful, sharp, highly scannable, and lightly witty.
- Write for busy professionals who want the most important updates quickly.

Required structure:
1. Newsletter title at the very top.
2. A 1-2 sentence intro that feels energetic and human.
3. Section: What you need to know today:
   - 3 to 5 bullets max.
   - each bullet should be a headline plus a short explanation.
4. Section: Why it matters:
   - 2 to 4 bullets connecting the news to business impact, workflow change, market direction, or practical use.
5. Section: Around the web:
   - 2 to 4 short extra items from the sources.
6. Section: Tools to try:
   - 1 to 3 practical tools, launches, or features if present in the sources.
7. A short closing line with personality.

Voice:
- Plain text only, no markdown symbols.
- Smart, punchy, lightly humorous.
- Not too formal, not slang-heavy.
- Prioritize clarity, momentum, and curiosity.
- Keep sentences short.
- Avoid fluff and generic transitions.
""".strip(),
}


def is_rss_or_atom(url: str) -> bool:
    lowered = url.lower()
    return any(x in lowered for x in ["rss", "atom", ".xml", "feed"])


def domain_label(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.replace("www.", "")
        return netloc or url
    except Exception:
        return url


def fetch_url(url: str, timeout: int = 15) -> str:
    try:
        if is_rss_or_atom(url):
            parsed = feedparser.parse(url)
            parts: List[str] = []
            for entry in parsed.entries[:10]:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                parts.append(f"Title: {title}\nSummary: {summary}")
            return "\n\n".join(parts)

        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        texts: List[str] = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            txt = tag.get_text(" ", strip=True)
            if txt:
                texts.append(txt)

        return "\n".join(texts)[:9000]
    except Exception as e:
        return f"[Error fetching {url}: {e}]"


@st.cache_resource(show_spinner=False)
def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it as an environment variable or in Streamlit secrets."
        )
    return OpenAI(api_key=api_key)


def build_newsletter_with_llm(
    items: List[Dict[str, str]],
    tone: str,
    audience: str,
    additional_instructions: str,
    model: str = "gpt-4.1-mini",
    style_preset: str = "Neuron-inspired",
) -> Dict[str, str]:
    system_prompt = textwrap.dedent(
        f"""
        You are an expert newsletter copywriter.

        {STYLE_GUIDES.get(style_preset, STYLE_GUIDES['Default'])}
        """
    ).strip()

    sources_text_parts: List[str] = []
    for idx, item in enumerate(items, start=1):
        sources_text_parts.append(
            textwrap.dedent(
                f"""
                Source {idx}
                URL: {item.get('url', '')}
                Label: {item.get('label', '')}
                Extracted content:
                {item.get('content', '')}
                """.strip()
            )
        )

    sources_block = "\n\n".join(sources_text_parts)

    user_prompt = textwrap.dedent(
        f"""
        Create a Gmail-ready plain-text newsletter.

        Audience: {audience or 'Busy professionals'}
        Tone preference: {tone or 'Smart, concise, friendly'}
        Style preset: {style_preset}

        Additional instructions:
        {additional_instructions or 'None'}

        Sources:
        {sources_block}

        Requirements:
        - Use only the provided source material.
        - Make the newsletter feel editorial and polished.
        - Keep it copy-paste ready for Gmail.
        - Include clear line breaks between sections.
        - End with 5 subject line ideas under the heading: Subject line ideas:
        - Never copy exact lines or branded catchphrases from existing newsletters.
        - Do not ask follow-up questions.
        """
    ).strip()

    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8 if style_preset == "Neuron-inspired" else 0.7,
    )

    full_text = response.choices[0].message.content.strip()
    splitter = "Subject line ideas:"
    if splitter in full_text:
        body, subjects_block = full_text.split(splitter, 1)
        subjects_block = splitter + subjects_block
    else:
        body, subjects_block = full_text, ""

    return {"body": body.strip(), "subjects": subjects_block.strip()}


st.set_page_config(page_title="Newsletter Builder", page_icon="📨", layout="wide")

st.title("📨 Custom Newsletter Builder")
st.write(
    "Paste websites or RSS feeds, choose a style, and get a Gmail-ready newsletter body "
    "that is easy to copy, tweak, and send."
)

with st.sidebar:
    st.header("Sources")
    st.write("Add news sites, blogs, or RSS feed URLs. The app will fetch and shape them into one email.")

    default_sources = "https://www.theneurondaily.com/\nhttps://news.ycombinator.com/"
    sources_raw = st.text_area(
        "Source URLs (one per line)",
        value=default_sources,
        height=150,
        help="You can mix normal websites and RSS/Atom feeds.",
    )

    st.markdown("---")
    st.header("Style")
    style_preset = st.selectbox(
        "Newsletter style",
        ["Neuron-inspired", "Default"],
        index=0,
        help="Neuron-inspired keeps the output punchy, witty, and highly scannable without copying exact wording.",
    )
    tone = st.text_input(
        "Tone",
        value="Punchy, witty, concise, and business-friendly",
        help="Example: analytical, premium, playful, formal.",
    )
    audience = st.text_input(
        "Audience",
        value="Busy professionals keeping up with AI",
        help="Who are you writing for?",
    )
    additional_instructions = st.text_area(
        "Additional instructions (optional)",
        value="Make it feel like a premium daily AI digest. Keep it skimmable, energetic, and easy to paste into Gmail. Prioritize practical takeaways and why it matters.",
        help="Any extra constraints, CTA requests, length targets, or themes.",
        height=120,
    )

    st.markdown("---")
    model = st.selectbox(
        "ChatGPT model",
        options=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"],
        index=0,
        help="Requires an OpenAI API key in OPENAI_API_KEY.",
    )

    generate_btn = st.button("Build my newsletter ✨", type="primary")

st.markdown("---")
st.subheader("Step 1: Add sources and click the button.")

if generate_btn:
    urls = [u.strip() for u in sources_raw.splitlines() if u.strip()]

    if not urls:
        st.error("Please add at least one source URL in the sidebar.")
        st.stop()

    with st.spinner("Fetching content from your sources..."):
        items: List[Dict[str, str]] = []
        for url in urls:
            items.append(
                {
                    "url": url,
                    "label": domain_label(url),
                    "content": fetch_url(url),
                }
            )

    try:
        with st.spinner("Calling ChatGPT to draft your newsletter..."):
            result = build_newsletter_with_llm(
                items=items,
                tone=tone,
                audience=audience,
                additional_instructions=additional_instructions,
                model=model,
                style_preset=style_preset,
            )
    except RuntimeError as e:
        st.error(str(e))
        st.info(
            "In Streamlit Cloud, set OPENAI_API_KEY in Secrets or environment variables. "
            "Locally, export it in your shell before running the app."
        )
        st.stop()
    except Exception as e:
        st.error(f"Error calling ChatGPT API: {e}")
        st.stop()

    st.markdown("---")
    st.subheader("Step 2: Copy into Gmail")
    st.write("Your newsletter body is below. Copy it and paste it directly into a Gmail draft.")

    st.text_area("Newsletter body", value=result["body"], height=450)

    if result.get("subjects"):
        st.markdown("---")
        st.subheader("Subject line ideas")
        st.text_area("Suggested subject lines", value=result["subjects"], height=180)
else:
    st.info(
        "Use the sidebar to add sources, keep the Neuron-inspired preset selected, and click the button to generate a Gmail-ready draft."
    )
