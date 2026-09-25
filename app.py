"""
Streamlit UI for news_engine.py

Lets you:
  1. Pull the latest world news from RSS feeds
  2. Generate a social-media-style post (template or Claude-written)
  3. Email the chosen post to a recipient via SMTP

Run locally:
    streamlit run app.py

Deploy on Streamlit Community Cloud:
    1. Push this folder to a GitHub repo
    2. On https://share.streamlit.io, "New app" -> point at the repo -> app.py
    3. In the app's Settings -> Secrets, paste the contents of
       .streamlit/secrets.toml.example (filled in with your real values)
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText

import streamlit as st

from news_engine import RSS_FEEDS, gather_news, template_post, ai_post

# Make the Claude API key available to news_engine.ai_post() if it's set in secrets
if "ANTHROPIC_API_KEY" in st.secrets:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

DEFAULT_RECIPIENT = "doremon123@gmail.com"

st.set_page_config(page_title="World News → Post", page_icon="📰", layout="centered")
st.title("📰 World News → Social Post")
st.caption("Pulls the latest world news and drafts a ready-to-publish post. Optionally emails it.")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    sources = st.multiselect(
        "News sources",
        options=list(RSS_FEEDS.keys()),
        default=list(RSS_FEEDS.keys()),
    )
    count = st.slider("Number of stories", min_value=1, max_value=10, value=5)
    style = st.selectbox("Post style", ["generic", "twitter", "linkedin"], index=0)
    use_ai = st.checkbox(
        "Use Claude to write the post",
        value=False,
        help="Requires an ANTHROPIC_API_KEY in Streamlit secrets. Falls back to a template if missing.",
    )
    fetch_clicked = st.button("🔄 Fetch latest news", type="primary", use_container_width=True)

if "posts" not in st.session_state:
    st.session_state.posts = []

# ---------------------------------------------------------------------------
# Fetch + generate posts
# ---------------------------------------------------------------------------
if fetch_clicked:
    if not sources:
        st.warning("Pick at least one source in the sidebar.")
    else:
        with st.spinner("Fetching news and drafting posts..."):
            news = gather_news(sources)
            seen, picked = set(), []
            for item in news:
                if item.title in seen:
                    continue
                seen.add(item.title)
                picked.append(item)
                if len(picked) == count:
                    break

            if not picked:
                st.error("No news items were retrieved. Try again or check your network/feed access.")
            else:
                posts = []
                for item in picked:
                    text = ai_post(item, style) if use_ai else template_post(item, style)
                    posts.append({"title": item.title, "source": item.source, "link": item.link, "text": text})
                st.session_state.posts = posts

# ---------------------------------------------------------------------------
# Display posts + email action
# ---------------------------------------------------------------------------
def send_email(subject: str, body: str, to_addr: str) -> tuple[bool, str]:
    """Send an email using SMTP credentials from Streamlit secrets."""
    try:
        smtp_host = st.secrets["smtp"]["host"]
        smtp_port = int(st.secrets["smtp"]["port"])
        smtp_user = st.secrets["smtp"]["user"]
        smtp_pass = st.secrets["smtp"]["password"]
        from_addr = st.secrets["smtp"].get("from", smtp_user)
    except KeyError:
        return False, "SMTP secrets are not configured. See .streamlit/secrets.toml.example."

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        return True, "Email sent."
    except Exception as exc:  # noqa: BLE001
        return False, f"Failed to send email: {exc}"


if st.session_state.posts:
    st.subheader("Generated posts")
    for i, post in enumerate(st.session_state.posts, 1):
        with st.expander(f"{i}. {post['title']}  —  ({post['source']})", expanded=(i == 1)):
            edited = st.text_area("Post text", value=post["text"], key=f"text_{i}", height=160)
            recipient = st.text_input("Send to", value=DEFAULT_RECIPIENT, key=f"recipient_{i}")
            if st.button("✉️ Send this post by email", key=f"send_{i}"):
                ok, msg = send_email(subject=post["title"][:120], body=edited, to_addr=recipient)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
else:
    st.info("Set your options in the sidebar and click **Fetch latest news** to get started.")
