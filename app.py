import os
import textwrap
from typing import List, Dict

import requests
import feedparser
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI


# ---------- Helpers for content fetching ----------

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBuilder/1.0)"}


def is_rss_or_atom(url: str) -> bool:
    lowered = url.lower()
    return any(x in lowered for x in ["rss", "atom", ".xml", "feed"])


def fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch a URL and return raw text content.

    For HTML pages: returns concatenated text from headings + paragraphs.
    For RSS/Atom feeds: returns concatenated titles + descriptions of recent items.
    """
    try:
        if is_rss_or_atom(url):
            parsed = feedparser.parse(url)
            parts: List[str] = []
            for entry in parsed.entries[:10]:  # limit items
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                parts.append(f"Title: {title}\nSummary: {summary}")
            return "\n\n".join(parts)

        # Fallback to HTML fetch
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        texts: List[str] = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            txt = tag.get_text(strip=True)
            if txt:
                texts.append(txt)

        content = "\n".join(texts)
        # Trim to avoid token explosion
        return content[:8000]
    except Exception as e:  # noqa: BLE001
        return f"[Error fetching {url}: {e}]"


# ---------- OpenAI / ChatGPT client ----------

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
) -> Dict[str, str]:
    """Call ChatGPT to generate newsletter body + subject lines.

    Returns dict with keys: body, subjects (newline-separated list)
    """

    system_prompt = (
        "You are an expert newsletter copywriter. "
        "Given curated links and extracted content, you write a polished, "
        "Gmail-ready newsletter that is easy to copy-paste into the email body. "
        "Avoid Markdown. Use plain text with clear section headings, bullet points, "
        "and short paragraphs."
    )

    # Build a compact representation of sources for the model
    sources_text_parts: List[str] = []
    for idx, item in enumerate(items, start=1):
        sources_text_parts.append(
            textwrap.dedent(
                f"""
                Source {idx}:
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
        You are creating a newsletter that the user will paste directly into Gmail.

        Audience: {audience or 'General readers'}
        Desired tone/style: {tone or 'Clear, concise, and engaging'}

        Curated sources and extracted content:
        {sources_block}

        Additional instructions from user (if any):
        {additional_instructions or 'None'}

        Tasks:
        1. Write a strong newsletter title line at the top.
        2. Then write the full newsletter body in plain text, using:
           - Short intro (2-3 sentences max).
           - One section per source with a clear heading or label.
           - 2-4 bullet points per source summarizing the key insights.
           - Optional closing paragraph with call-to-action.
        3. After the body, provide 5 alternative email subject lines, each on its own line,
           prefixed with "- " under a heading "Subject line ideas:".

        Do NOT include Markdown syntax (#, **, etc.).
        Do NOT include placeholders or ask questions back to the user.
        """.strip()
    )

    client = get_openai_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    full_text = response.choices[0].message.content.strip()

    # Best-effort split: separate subject lines block if present
    splitter = "Subject line ideas:"
    if splitter in full_text:
        body, subjects_block = full_text.split(splitter, 1)
        subjects_block = splitter + subjects_block
    else:
        body, subjects_block = full_text, ""

    return {"body": body.strip(), "subjects": subjects_block.strip()}


# ---------- Streamlit UI ----------

st.set_page_config(
    page_title="Newsletter Builder",
    page_icon="📨",
    layout="wide",
)

st.title("📨 Custom Newsletter Builder")
st.write(
    "Paste your favorite websites or RSS feeds, and get a Gmail-ready newsletter "
    "body you can copy-paste and send in minutes."
)

with st.sidebar:
    st.header("Sources")
    st.write("Add news sites, blogs, or RSS feed URLs. We'll fetch and summarize them.")

    default_sources = "https://news.ycombinator.com/\nhttps://www.bloomberg.com/"
    sources_raw = st.text_area(
        "Source URLs (one per line)",
        value=default_sources,
        height=150,
        help="You can mix normal websites and RSS/Atom feeds.",
    )

    st.markdown("---")
    st.header("Style")
    tone = st.text_input(
        "Tone", value="Smart, concise, and friendly", help="e.g. formal, playful, analytical"
    )
    audience = st.text_input(
        "Audience", value="Busy professionals", help="Who are you writing for?"
    )
    additional_instructions = st.text_area(
        "Additional instructions (optional)",
        value="",
        help="Anything special to emphasize, CTA, length constraints, etc.",
        height=100,
    )

    st.markdown("---")
    model = st.selectbox(
        "ChatGPT model",
        options=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"],
        index=0,
        help="Requires an OpenAI (ChatGPT) API key.",
    )

    generate_btn = st.button("Build my newsletter ✨", type="primary")


st.markdown("---")
st.subheader("Step 1: Configure sources in the sidebar, then click the button.")

if generate_btn:
    urls = [u.strip() for u in sources_raw.splitlines() if u.strip()]

    if not urls:
        st.error("Please add at least one source URL in the sidebar.")
        st.stop()

    with st.spinner("Fetching content from your sources..."):
        items: List[Dict[str, str]] = []
        for url in urls:
            content = fetch_url(url)
            label = url
            items.append({"url": url, "label": label, "content": content})

    st.success("Fetched content. Asking ChatGPT to craft your newsletter...")

    try:
        with st.spinner("Calling ChatGPT (OpenAI API)..."):
            result = build_newsletter_with_llm(
                items=items,
                tone=tone,
                audience=audience,
                additional_instructions=additional_instructions,
                model=model,
            )
    except RuntimeError as e:
        st.error(str(e))
        st.info(
            "In Streamlit Cloud, set `OPENAI_API_KEY` as a secret or environment variable. "
            "Locally, you can export it in your shell: `export OPENAI_API_KEY=...`."
        )
        st.stop()
    except Exception as e:  # noqa: BLE001
        st.error(f"Error calling ChatGPT API: {e}")
        st.stop()

    st.markdown("---")
    st.subheader("Step 2: Copy-paste into Gmail ✉️")

    st.write(
        "Below is your Gmail-ready newsletter body. "
        "Click the copy button, then paste into a new Gmail draft."
    )

    st.text_area(
        "Newsletter body",
        value=result["body"],
        height=400,
    )

    st.write("You can also tweak the text above before sending.")

    if result.get("subjects"):
        st.markdown("---")
        st.subheader("Subject line ideas")
        st.text_area("Suggested subject lines", value=result["subjects"], height=180)

else:
    st.info(
        "Configure your sources and style in the sidebar, then click "
        "'Build my newsletter ✨' to generate a Gmail-ready draft."
    )
