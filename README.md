# World News → Post

Fetches the latest world news from RSS feeds (BBC, Reuters, Al Jazeera),
drafts a ready-to-publish social post from each story, and can email the
result via SMTP — all through a Streamlit UI.

## Files

- `app.py` — Streamlit UI (fetch news, review/edit posts, send email)
- `news_engine.py` — core logic: RSS fetching, parsing, post generation
  (also runnable standalone as a CLI: `python news_engine.py --help`)
- `requirements.txt` — Python dependencies
- `.streamlit/secrets.toml.example` — template for the secrets you need to add

## 1. Push to GitHub

```bash
cd news-to-post-app
git init
git add .
git commit -m "Initial commit: news-to-post Streamlit app"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

`.gitignore` already excludes `.streamlit/secrets.toml` so you don't
accidentally commit real credentials.

## 2. Run locally (optional)

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml with your real SMTP (and optional Claude) credentials
streamlit run app.py
```

## 3. Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **New app**, pick your repo/branch, and set the main file to `app.py`.
3. Before or after the first deploy, go to **App → Settings → Secrets** and
   paste in the contents of `.streamlit/secrets.toml.example`, filled in with
   your real values (see below).
4. Deploy. The app will be live at a `*.streamlit.app` URL.

## Email setup (Gmail example)

Gmail requires an **App Password** (not your normal password) once
2-Step Verification is on:

1. Enable 2-Step Verification on the Google account.
2. Go to Google Account → Security → App passwords, generate one for "Mail".
3. Use that 16-character password as `smtp.password` in secrets, with:
   ```
   host = "smtp.gmail.com"
   port = 587
   user = "your-email@gmail.com"
   ```

Any other SMTP provider (Outlook, SendGrid, etc.) works the same way —
just swap in its host/port/credentials.

## Note on the default recipient

The app defaults the "Send to" field to `doremon123@gmail.com`. You can
change it in `app.py` (`DEFAULT_RECIPIENT`), and it's also editable per-post
in the UI regardless.

## Optional: AI-written posts

Check "Use Claude to write the post" in the sidebar to have Claude draft the
post instead of the built-in template. This calls the Anthropic API directly,
so it needs `ANTHROPIC_API_KEY` set in secrets. Without it, the app falls
back to the template automatically.
