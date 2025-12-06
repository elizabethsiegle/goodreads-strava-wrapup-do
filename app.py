import altair as alt
from dotenv import load_dotenv
import os
import re
import requests
import json
import pandas as pd
import streamlit as st
from data.strava import clean_workouts_df, compute_workout_stats, compute_daily_steps_2025
from data.goodreads import clean_books_df, compute_book_stats

# Load .env file
load_dotenv()

st.markdown(
    "<h1 style='margin:0'>Goodreads and <span style='color:#f97316'>Strava</span> 2025 Wrap-up</h1>",
    unsafe_allow_html=True,
)

# get yours @ https://cloud.digitalocean.com/gen-ai/model-access-keys
MODEL_ACCESS_KEY = os.getenv("MODEL_ACCESS_KEY")
print("MODEL_ACCESS_KEY loaded:",MODEL_ACCESS_KEY)
# Instructions for uploading files
st.markdown(
    (
        '<div style="margin-bottom: 12px; font-size: 16px; line-height: 1.6;">'
        'Upload your Strava activities and/or Goodreads library exports to see an analysis and summary of your 2025 activities and reading.</br></br>'
        'You can <a href="https://www.strava.com/athlete/delete_your_account">export your Strava activities here</a> and <a href="https://www.goodreads.com/review/import">your Goodsreads data here</a>. (You must be logged in to access these links.)'
        '</div>'
    ),
    unsafe_allow_html=True,
)

# Upload inputs (optional): users can upload one or both files
uploaded_goodreads = st.file_uploader(
    'Upload Goodreads library export (.csv)', type=['csv'], accept_multiple_files=False
)
uploaded_strava = st.file_uploader(
    'Upload Strava activities (.csv)', type=['csv'], accept_multiple_files=False
)


# Readability styles
st.markdown(
    """
    <style>
    /* Hide the settings menu */
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    .stApp > header {visibility: hidden;}
    /* Base font for readability */
    html, body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1f2937; }
    /* Make Altair chart labels and rendered text larger and more legible */
    div[data-testid="stAltairChart"] text { font-size: 16px !important; }
    /* Improve line-height for markdown and general text blocks */
    div[data-testid="stMarkdownContainer"] { line-height: 1.6; }
    /* Wider tooltip containers (browser-dependent) */
    .vega-tooltip { max-width: 600px !important; white-space: normal !important; }
    /* Wrap-up card styling */
    .wrapup-card {
        margin: 16px 0;
        padding: 20px 24px;
        border-radius: 12px;
        background: #ffffff;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
        border: 1px solid #e5e7eb;
        color: #111827;
    }
    .wrapup-card h1, .wrapup-card h2, .wrapup-card h3 { 
        margin: 0.4em 0 0.3em; 
        letter-spacing: 0.2px; 
        color: #111827;
    }
    .wrapup-card p { margin: 0.6em 0; color: #374151; }
    .wrapup-card ul { margin: 0.5em 0 0.5em 1.1em; }
    .wrapup-card strong { color: #111827; }
    .wrapup-card-divider {
        height: 1px;
        background: #e5e7eb;
        margin: 14px 0;
        border: 0;
    }
    .wrapup-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
    }
    .wrapup-badge {
        padding: 4px 10px;
        border-radius: 999px;
        background: #111827;
        color: #ffffff;
        font-size: 12px;
        font-weight: 600;
    }
    /* Section-specific font colors */
    .section-strava { color: #0b65c2; } /* blue for workouts */
    .section-books { color: #0f766e; }  /* teal for books */
    .section-strava h1, .section-strava h2, .section-strava h3, .section-strava p, .section-strava span { color: #0b65c2; }
    .section-books h1, .section-books h2, .section-books h3, .section-books p, .section-books span { color: #0f766e; }

    /* Make headings pop: bigger, colorful, subtle motion */
    @keyframes glowPulse {
        0% { text-shadow: 0 0 0 rgba(34,211,238,0.0); }
        50% { text-shadow: 0 6px 18px rgba(99,102,241,0.35); }
        100% { text-shadow: 0 0 0 rgba(34,211,238,0.0); }
    }
    @keyframes colorPulse {
        0% { color: #6366f1; }
        33% { color: #22d3ee; }
        66% { color: #10b981; }
        100% { color: #6366f1; }
    }
    h1 { font-size: 2.2rem; letter-spacing: 0.3px; animation: glowPulse 3s ease-in-out infinite, colorPulse 6s linear infinite; }
    h2 { font-size: 1.6rem; letter-spacing: 0.2px; animation: glowPulse 3s ease-in-out infinite, colorPulse 6s linear infinite; }
    .wrapup-card h3 { font-size: 1.4rem; }
    .section-books h2 { color: #0f766e; }

    /* Cooler, bigger Generate wrap-up button */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1 0%, #22d3ee 100%);
        color: #ffffff;
        border: none;
        padding: 14px 22px;
        font-size: 18px;
        font-weight: 700;
        border-radius: 12px;
        box-shadow: 0 10px 22px rgba(34, 211, 238, 0.25);
        transition: transform 0.15s ease, box-shadow 0.2s ease, filter 0.2s ease;
        cursor: pointer;
    }
    .stButton > button:hover {
        transform: translateY(-1px) scale(1.02);
        box-shadow: 0 16px 28px rgba(34, 211, 238, 0.35);
        filter: brightness(1.05);
    }
    .stButton > button:active {
        transform: translateY(0) scale(0.99);
        box-shadow: 0 8px 18px rgba(34, 211, 238, 0.25);
    }
    /* Add subtle wiggle animation to draw attention */
    @keyframes wiggle {
        0%, 100% { transform: rotate(0deg); }
        25% { transform: rotate(0.6deg); }
        75% { transform: rotate(-0.6deg); }
    }
    .stButton > button:focus-visible { animation: wiggle 0.25s ease-in-out; }
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #0e1117;
        color: white;
        text-align: center;
        padding: 10px 0;
        border-top: 1px solid #262730;
        z-index: 1000;
        font-size: 14px;
    }
    
    .footer a {
        color: #ff6b6b;
        text-decoration: none;
        font-weight: 500;
    }
    
    .footer a:hover {
        color: #ff5252;
        text-decoration: underline;
    }
    
    /* Ensure content doesn't get hidden behind footer */
    .stApp {
        margin-bottom: 60px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if uploaded_goodreads is None and uploaded_strava is None:
    st.warning("Upload one or both CSV files to begin.")
else:
    if "wrapup_ready" not in st.session_state:
        st.session_state.wrapup_ready = False
    if not st.session_state.wrapup_ready:
        if st.button("Generate wrap-up"):
            st.session_state.wrapup_ready = True

book_data = pd.read_csv(uploaded_goodreads) if uploaded_goodreads is not None else None
strava_data = pd.read_csv(uploaded_strava) if uploaded_strava is not None else None

# Only show filtered 2025 data

# Compute filtered data and stats up-front
has_books = uploaded_goodreads is not None
has_strava = uploaded_strava is not None
books_clean = clean_books_df(book_data) if has_books else None
# Filter for 2025 reads even if columns vary/missing
if has_books and isinstance(books_clean, pd.DataFrame) and len(books_clean):
    date_col = 'Date Read' if 'Date Read' in books_clean.columns else None
    shelf_col = 'Exclusive Shelf' if 'Exclusive Shelf' in books_clean.columns else None
    if date_col:
        date_str = books_clean[date_col].astype(str)
        mask_2025 = date_str.str.contains('2025', na=False)
    else:
        mask_2025 = pd.Series([False] * len(books_clean))
    if shelf_col:
        shelf_mask = books_clean[shelf_col].astype(str).str.lower().eq('read')
    else:
        shelf_mask = pd.Series([True] * len(books_clean))
    books_this_year = books_clean[mask_2025 & shelf_mask].copy()
else:
    books_this_year = pd.DataFrame()
book_stats = compute_book_stats(books_this_year) if has_books else {}

tidy_strava = clean_workouts_df(strava_data) if has_strava else None
workouts_this_year = (
    tidy_strava[tidy_strava['Activity Date'].dt.year == 2025].copy() if has_strava else pd.DataFrame()
)
workout_stats = compute_workout_stats(workouts_this_year) if has_strava else {}

# Precompute steps summary once (used by LLM and charts)
steps_source_df = None
if has_strava and isinstance(workouts_this_year, pd.DataFrame) and 'Total Steps' in workouts_this_year.columns:
    steps_source_df = workouts_this_year.copy()
else:
    csv_path = os.path.join(os.getcwd(), 'data_csvs', 'activities.csv')
    if os.path.exists(csv_path):
        try:
            steps_source_df = pd.read_csv(csv_path)
        except Exception:
            steps_source_df = None

daily_steps = compute_daily_steps_2025(steps_source_df) if isinstance(steps_source_df, pd.DataFrame) else pd.DataFrame()
steps_summary = {
    'days_with_steps': int(len(daily_steps)) if len(daily_steps) else 0,
    'total_steps': int(pd.to_numeric(daily_steps['Steps']).sum()) if len(daily_steps) else 0,
}

# Build Strava activity links from Filename (strip .gpx)
if has_strava and not workouts_this_year.empty:
    # Prefer Activity ID when available; fallback to Filename-derived ID
    if 'Activity ID' in workouts_this_year.columns:
        id_series = pd.to_numeric(workouts_this_year['Activity ID'], errors='coerce').astype('Int64').astype(str)
    else:
        id_series = None
    fallback_ids = None
    if 'Filename' in workouts_this_year.columns:
        fn_series = workouts_this_year['Filename'].astype(str)
        fn_series = fn_series.str.replace('.gpx', '', regex=False)
        fn_series = fn_series.str.replace('.fit.gz', '', regex=False)
        fallback_ids = fn_series.str.replace(r'\D', '', regex=True)
    final_ids = id_series if id_series is not None else fallback_ids
    if final_ids is None:
        final_ids = pd.Series([], dtype=str)
    workouts_this_year['Link'] = 'https://www.strava.com/activities/' + final_ids

def _build_strava_sample(workouts_df: pd.DataFrame) -> list:
    df = workouts_df.head(10).copy()
    if len(df) and 'Activity Date' in df.columns:
        df['Activity Date'] = df['Activity Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    ids = None
    if 'Activity ID' in df.columns:
        ids = pd.to_numeric(df['Activity ID'], errors='coerce').astype('Int64').astype(str)
    elif 'Filename' in df.columns:
        fn = df['Filename'].astype(str)
        fn = fn.str.replace('.gpx', '', regex=False)
        fn = fn.str.replace('.fit.gz', '', regex=False)
        ids = fn.str.replace(r'\D', '', regex=True)
    if ids is not None:
        df['Link'] = 'https://www.strava.com/activities/' + ids
    return df.to_dict(orient='records') if len(df) else []

def _build_books_sample(books_df: pd.DataFrame) -> list:
    if not isinstance(books_df, pd.DataFrame) or not len(books_df):
        return []
    b = books_df.head(10).copy()
    if 'Date Read' in b.columns:
        b['Date Read'] = pd.to_datetime(b['Date Read'], errors='coerce').dt.strftime('%Y-%m-%d')
    return b.to_dict(orient='records')

def _call_wrapup_api(title: str, messages: list, max_tokens: int = 800) -> str:
    url = "https://inference.do-ai.run/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MODEL_ACCESS_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama3.3-70b-instruct", "messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    with st.spinner(f"Generating {title}…"):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
        except Exception as e:
            st.error(f"Wrap-up request failed: {e}")
            return ""
    if resp.status_code != 200:
        st.error(f"Wrap-up API error {resp.status_code}: {resp.text}")
        return ""
    try:
        data = resp.json()
    except Exception:
        st.error("Wrap-up API returned non-JSON response.")
        return ""
    text = (data.get("choices", [{}])[0].get('message', {}) or {}).get("content", "")
    if not text:
        st.warning("No wrap-up text returned. Showing raw response for debugging.")
        st.code(json.dumps(data, indent=2)[:6000])
    return text

# Render wrap-up cards BEFORE visualizations (simplified)
if st.session_state.get("wrapup_ready", False):
    if has_strava and not has_books:
        stats_json = json.dumps({**workout_stats, 'steps_summary': steps_summary})
        sample_json = json.dumps(_build_strava_sample(workouts_this_year))
        messages = [{"role": "user", "content": (
            "Generate a 2025 year-end wrap-up for the user based on their Strava workouts. "
            "Use the exact numeric stats provided (do not make up numbers). "
            "Highlight totals, per-activity-type distances, longest activity, elevation gain, heart rate, and calories. "
            "Also include the steps summary (total steps and number of days with steps) from 'steps_summary'. "
            "When referencing specific activities, include the provided Strava link using Markdown format [link](url). "
            "Write in a funny, friendly, engaging tone.\n\n"
            f"Stats (including steps_summary): {stats_json}\n"
            f"Sample workouts (up to 10): {sample_json}"
        )}]
        text = _call_wrapup_api("Strava wrap-up", messages, max_tokens=700)
        if text:
            st.markdown(f"""
            <div class='wrapup-card'>
            <div class='wrapup-header'><span class='wrapup-badge'>2025 Wrap-up</span><h3 style='margin:0;'>Strava Summary</h3></div>
            <hr class='wrapup-card-divider' />
            {text}
            </div>
            """, unsafe_allow_html=True)
            st.text_area("Copy & share", value=text, height=240)
            st.download_button("Download wrap-up text", data=text, file_name="2025-wrapup-strava.txt")

    if has_books and not has_strava:
        book_stats_json = json.dumps(book_stats)
        book_sample_json = json.dumps(_build_books_sample(books_this_year))
        messages = [{"role": "user", "content": (
            "Generate a 2025 year-end reading wrap-up. Use the exact stats provided (do not make up numbers). "
            "Summarize total books, average rating, total pages, longest book, top authors, and notable highlights. "
            "Write in a funny, friendly, engaging tone. Use human-friendly book titles and author names; do NOT mention internal IDs.\n\n"
            f"Book stats: {book_stats_json}\n"
            f"Sample books (up to 10): {book_sample_json}"
        )}]
        text = _call_wrapup_api("Goodreads wrap-up", messages, max_tokens=700)
        if text:
            st.markdown(f"""
            <div class='wrapup-card'>
            <div class='wrapup-header'><span class='wrapup-badge'>2025 Wrap-up</span><h3 style='margin:0;'>Goodreads Summary</h3></div>
            <hr class='wrapup-card-divider' />
            {text}
            </div>
            """, unsafe_allow_html=True)
            st.text_area("Copy & share", value=text, height=240)
            st.download_button("Download wrap-up text", data=text, file_name="2025-wrapup-books.txt")

    if has_books and has_strava:
        stats_json = json.dumps({**workout_stats, 'steps_summary': steps_summary})
        sample_json = json.dumps(_build_strava_sample(workouts_this_year))
        book_stats_json = json.dumps(book_stats)
        book_sample_json = json.dumps(_build_books_sample(books_this_year))
        messages = [{"role": "user", "content": (
            "Generate a 2025 year-end wrap-up for Strava + Goodreads in the humorous, succinct, slightly deprecating manner of Spotify Wrapups. "
            "Use the exact stats provided (do not make up numbers). "
            "For Strava: summarize total distance, workout count, per-type distances, longest activity, elevation, heart rate, calories. "
            "Also include the steps summary (total steps and number of days with steps) from 'steps_summary'. "
            "For books: summarize total read, average rating, total pages, longest book, top authors, and highlights. "
            "Write in a funny, friendly, engaging tone. Use human-friendly book titles and author names; do NOT mention internal IDs.\n\n"
            "Make comparisons about trends, improvements, or interesting observations between the reading and workout data. What author was most popular? Or workout type, if only one is present?\n\n"
            "Split up some of the sections into Strava-specific and Goodreads-specific paragraphs for clarity. Make it like a Spotify Wrapped--how many total pages were read? How many total miles were ridden or run?\n\n"
            "When referencing specific Strava activities (e.g., a max heart rate event), include the provided Strava link using Markdown format [link](url).\n\n"
            f"Strava stats (including steps_summary): {stats_json}\n"
            f"Strava sample (up to 10): {sample_json}\n"
            f"Book stats: {book_stats_json}\n"
            f"Book sample (up to 10): {book_sample_json}"
        )}]
        text = _call_wrapup_api("combined wrap-up", messages, max_tokens=2000)
        if text:
            st.markdown(f"""
            <div class='wrapup-card'>
            <div class='wrapup-header'><span class='wrapup-badge'>2025 Wrap-up</span><h3 style='margin:0;'>Combined Summary</h3></div>
            <hr class='wrapup-card-divider' />
            {text}
            </div>
            """, unsafe_allow_html=True)
            st.text_area("Copy & share", value=text, height=240)
            st.download_button("Download wrap-up text", data=text, file_name="2025-wrapup.txt")

# Layout: two columns if both CSVs, centered single if one 
if st.session_state.get("wrapup_ready", False):
    if has_books and has_strava:
        col_books, col_strava = st.columns(2)
    elif has_books and not has_strava:
        left, col_books, right = st.columns([1, 2, 1])
        col_strava = None
    elif has_strava and not has_books:
        left, col_strava, right = st.columns([1, 2, 1])
        col_books = None
    else:
        col_books = None
        col_strava = None

    # Books section
    if has_books:
        with col_books if col_books is not None else st:
            st.markdown("<div class='section-books'>", unsafe_allow_html=True)
            st.subheader('Books read in 2025')
            st.caption(f"Total: {len(books_this_year)} • Avg rating: {book_stats['avg_my_rating']:.2f} • Pages: {book_stats['total_pages']}")
            st.dataframe(books_this_year.iloc[:, 2:])
            # Replace shelves chart: Books read per month (2025)
            if 'Date Read' in books_this_year.columns:
                bdf = books_this_year.copy()
                bdf['Date Read Parsed'] = pd.to_datetime(bdf['Date Read'], errors='coerce')
                bdf = bdf.dropna(subset=['Date Read Parsed'])
                bdf['Month'] = bdf['Date Read Parsed'].dt.strftime('%Y-%m')
                month_counts = bdf.groupby('Month').agg(count=('Title', 'count')).reset_index()
                month_counts['count'] = pd.to_numeric(month_counts['count'], errors='coerce').fillna(0).astype(int)
                books_month_chart = (
                    alt.Chart(month_counts)
                    .mark_bar(color='#10b981')
                    .encode(
                        x=alt.X('Month:N', title='Month'),
                        y=alt.Y('count:Q', title='Books', axis=alt.Axis(format='d')),
                        tooltip=[
                            alt.Tooltip('Month:N', title='Month'),
                            alt.Tooltip('count:Q', title='Count', format='d')
                        ]
                    )
                    .properties(height=300, title='Books Read by Month (2025)')
                )
                st.altair_chart(
                    books_month_chart.configure_axis(labelFontSize=14, titleFontSize=14),
                    use_container_width=True
                )
                # Recent 10 books list (to mirror recent activities)
                recent_books = bdf.sort_values('Date Read Parsed', ascending=False).head(10)[['Title', 'Author']]
                if len(recent_books):
                    lines = "\n".join([f"- {row['Title']} — {row['Author']}" for _, row in recent_books.iterrows()])
                    st.markdown("Recent books:" + "\n" + lines)
                # Add cumulative reading line chart across months
                month_counts_sorted = month_counts.sort_values('Month').copy()
                month_counts_sorted['Cumulative'] = month_counts_sorted['count'].cumsum()
                cumulative_chart = (
                    alt.Chart(month_counts_sorted)
                    .mark_line(point=True, color='#22d3ee')
                    .encode(
                        x=alt.X('Month:N', title='Month'),
                        y=alt.Y('Cumulative:Q', title='Cumulative Books', axis=alt.Axis(format='d')),
                        tooltip=[
                            alt.Tooltip('Month:N', title='Month'),
                            alt.Tooltip('Cumulative:Q', title='Cumulative', format='d')
                        ]
                    )
                    .properties(height=260, title='Cumulative Books Read (2025)')
                )
                st.altair_chart(
                    cumulative_chart.configure_axis(labelFontSize=14, titleFontSize=14),
                    use_container_width=True
                )

            # LLM-based genre guessing (experimental)
            if has_books and ((isinstance(books_this_year, pd.DataFrame) and len(books_this_year)) or (isinstance(books_clean, pd.DataFrame) and len(books_clean))):
                # Cache to avoid repeated calls
                cache_key = 'guessed_genres_2025'
                if cache_key not in st.session_state:
                    source_df = books_this_year if len(books_this_year) else books_clean
                    cols = [c for c in ['Title', 'Author'] if c in (source_df.columns if source_df is not None else [])]
                    sample = source_df[cols].dropna().head(50).to_dict(orient='records') if cols else []
                    prompt_payload = {
                        "model": "llama3.3-70b-instruct",
                        "messages": [
                            {"role": "system", "content": "You are a strict JSON generator. Output only valid JSON with no commentary."},
                            {"role": "user", "content": (
                                "You are classifying book genres. Given a list of book titles and authors, "
                                "estimate the most likely broad genre for each item based on title wording and author known works. "
                                "Return a single JSON object with two keys and nothing else: 'items' (array of objects with keys: title, author, genre) and 'counts' (object mapping genre to count). "
                                "Use broad genres only: Fantasy, Sci-Fi, Mystery, Thriller, Romance, Nonfiction, Biography, History, Self-Help, Literary Fiction, Young Adult. "
                                "If unsure, pick a genre and stick with it. Guess but do not include extra text, only valid JSON. "
                                "Be decisive but reasonable: prefer a single best-guess genre per book; no subgenres.\n\n"
                                f"Books: {json.dumps(sample)}"
                            )}
                        ],
                        "temperature": 0.0,
                        "max_tokens": 1200,
                        "response_format": {"type": "json_object"}
                    }
                    resp = requests.post(
                        "https://inference.do-ai.run/v1/chat/completions",
                        headers={"Authorization": f"Bearer {MODEL_ACCESS_KEY}", "Content-Type": "application/json"},
                        json=prompt_payload,
                        timeout=30,
                    )
                res_json = resp.json()
                msg_obj = res_json.get("choices", [{}])[0].get("message", {})
                raw = msg_obj.get("content") or msg_obj.get("reasoning_content") or ""
                print('raw ', raw)
                # Robust JSON extraction: trim to outermost braces or fenced code block
                raw_str = str(raw).strip()
                if '```' in raw_str:
                    # Attempt to extract content inside first fenced block
                    fence_start = raw_str.find('```')
                    fence_end = raw_str.find('```', fence_start + 3)
                    block = raw_str[fence_start + 3:fence_end] if fence_start != -1 and fence_end != -1 else raw_str
                    raw_str = block.strip()
                start = raw_str.find('{')
                end = raw_str.rfind('}')
                json_only = raw_str[start:end+1] if start != -1 and end != -1 and end > start else "{}"
                # Parse JSON; on failure, retry with a lighter prompt, then fallback to heuristic
                parsed = None
                try:
                    parsed = json.loads(json_only)
                except Exception:
                    parsed = None
                if not parsed or not isinstance(parsed, dict):
                    # Retry without response_format to coax output
                    retry_payload = {
                        "model": "llama3.3-70b-instruct",
                        "messages": [
                            {"role": "system", "content": "Return only raw JSON. No prose."},
                            {"role": "user", "content": (
                                "Return a JSON with keys 'items' (objects: title, author, genre) and 'counts' (genre->count). "
                                "Valid genres: Fantasy, Sci-Fi, Mystery, Thriller, Romance, Nonfiction, Biography, History, Self-Help, Literary Fiction, Young Adult. "
                                f"Books: {json.dumps(sample)}"
                            )}
                        ],
                        "temperature": 0.0,
                        "max_tokens": 800
                    }
                    try:
                        retry_resp = requests.post(
                            "https://inference.do-ai.run/v1/chat/completions",
                            headers={"Authorization": f"Bearer {MODEL_ACCESS_KEY}", "Content-Type": "application/json"},
                            json=retry_payload,
                            timeout=30,
                        )
                        retry_msg = retry_resp.json().get("choices", [{}])[0].get("message", {})
                        retry_raw = retry_msg.get("content") or retry_msg.get("reasoning_content") or ""
                        rstr = str(retry_raw)
                        rs = rstr.find('{')
                        re = rstr.rfind('}')
                        robj = rstr[rs:re+1] if rs != -1 and re != -1 and re > rs else "{}"
                        parsed = json.loads(robj)
                    except Exception:
                        parsed = {"items": [], "counts": {}}
                # If still empty, build heuristic genres from titles
                if not parsed.get("items") and not parsed.get("counts"):
                    src_df = source_df if 'source_df' in locals() and source_df is not None else pd.DataFrame()
                    items = []
                    counts = {}
                    genre_map = {
                        'fantasy': 'Fantasy', 'dragon': 'Fantasy', 'magic': 'Fantasy',
                        'sci-fi': 'Sci-Fi', 'science fiction': 'Sci-Fi', 'galaxy': 'Sci-Fi', 'space': 'Sci-Fi',
                        'mystery': 'Mystery', 'detective': 'Mystery', 'murder': 'Mystery',
                        'thrill': 'Thriller', 'chase': 'Thriller', 'spy': 'Thriller',
                        'romance': 'Romance', 'love': 'Romance', 'heart': 'Romance',
                        'nonfiction': 'Nonfiction', 'essay': 'Nonfiction', 'memoir': 'Biography',
                        'biography': 'Biography', 'life of': 'Biography',
                        'history': 'History', 'war': 'History',
                        'self-help': 'Self-Help', 'habits': 'Self-Help', 'guide': 'Self-Help',
                        'literary': 'Literary Fiction', 'novel': 'Literary Fiction',
                        'young adult': 'Young Adult', 'ya': 'Young Adult'
                    }
                    if not src_df.empty:
                        cols = [c for c in ['Title', 'Author'] if c in src_df.columns]
                        for _, row in src_df[cols].dropna().head(50).iterrows():
                            title = str(row.get('Title', '')).lower()
                            author = str(row.get('Author', ''))
                            assigned = 'Literary Fiction'
                            for key, g in genre_map.items():
                                if key in title:
                                    assigned = g
                                    break
                            items.append({"title": row.get('Title', ''), "author": author, "genre": assigned})
                            counts[assigned] = counts.get(assigned, 0) + 1
                    parsed = {"items": items, "counts": counts}
                # Use parsed JSON for the summary input
                compact_insight = json.dumps({
                    "top_genres": sorted([(k, v) for k, v in (parsed.get("counts", {}) or {}).items()], key=lambda x: -x[1])[:5],
                    "samples": (parsed.get("items", []) or [])[:10]
                })
                print('compact_insight', compact_insight)
                # Build a local concise paragraph from compact_insight to avoid API verbosity
                try:
                    ci = json.loads(compact_insight)
                except Exception:
                    ci = {"top_genres": [], "samples": []}
                tops = ci.get("top_genres", [])
                primary = tops[0][0] if tops else "Literary Fiction"
                pcount = tops[0][1] if tops else 0
                minor = [t[0] for t in tops[1:3]]
                minor_text = ", ".join(minor) if minor else ""

                # Compute totals and shares for conditional phrasing
                total_books = sum([int(t[1]) for t in tops]) if tops else max(pcount, 1)
                shares = {g.lower(): (int(c) / total_books) for g, c in tops} if total_books else {}
                top_share = shares.get(primary.lower(), 0.0)

                # Conditional vibe lines based on genre ratios
                vibe_bits = []
                # Eclectic: no single genre dominates
                if top_share < 0.3 and total_books >= 5:
                    vibe_bits.append("Eclectic taste: you sampled widely and often.")
                # Balanced top-3: spread across three genres
                top3 = tops[:3]
                if len(top3) == 3:
                    s1 = int(top3[0][1]) / total_books
                    s2 = int(top3[1][1]) / total_books
                    s3 = int(top3[2][1]) / total_books
                    if s1 >= 0.2 and s2 >= 0.2 and s3 >= 0.2 and (s1 <= 0.4 and s2 <= 0.4 and s3 <= 0.4):
                        vibe_bits.append("Balanced shelf: evenly split across your top three.")
                # Nonfiction-heavy
                if shares.get("nonfiction", 0.0) >= 0.6:
                    vibe_bits.append("Curious, clear-eyed, relentlessly fact-fueled.")
                # Biography/History heavy
                if (shares.get("biography", 0.0) + shares.get("history", 0.0)) >= 0.5:
                    vibe_bits.append("Lives and eras: biography/history took the spotlight.")
                # Self-Help heavy
                if shares.get("self-help", 0.0) >= 0.35:
                    vibe_bits.append("Systems, habits, and upgrades—self-help was a theme.")
                # Romance-heavy
                if shares.get("romance", 0.0) >= 0.4:
                    vibe_bits.append("Big feelings, bigger heart—romance ruled.")
                # Fantasy-heavy
                if shares.get("fantasy", 0.0) >= 0.4:
                    vibe_bits.append("Portals, prophecies, and plenty of magic.")
                # Sci-Fi heavy
                if shares.get("sci-fi", 0.0) >= 0.4:
                    vibe_bits.append("Futures, frontiers, and thought experiments—sci‑fi soared.")
                # YA heavy
                if shares.get("young adult", 0.0) >= 0.4:
                    vibe_bits.append("YA energy: fast beats, big arcs, high empathy.")
                # Mystery/Thriller edge
                if (shares.get("mystery", 0.0) + shares.get("thriller", 0.0)) >= 0.5:
                    vibe_bits.append("Twists ahead: you chased clues and adrenaline.")
                # Default literary/fiction vibe
                if not vibe_bits:
                    if primary.lower() == "nonfiction":
                        vibe_bits.append("Curious, clear-eyed, and fact-forward.")
                    else:
                        # Literary/fiction-heavy nuance
                        if shares.get("literary fiction", 0.0) >= 0.4:
                            vibe_bits.append("Lyrical turns, quiet stakes, character-first focus.")
                        else:
                            vibe_bits.append("Punchy plots, smart prose, self-aware vibes.")

                # Compose concise paragraph under ~80 words
                base = f"Your year was {primary.lower()} forward ({pcount}). "
                cameo = f"{minor_text} showed up occasionally. " if minor_text else ""
                vibe = " ".join(vibe_bits) + " "
                wrap = "TBR towering, taste refined—another ‘quiet, luminous’ pick awaits."
                genre_resp_json = (base + cameo + vibe + wrap)
                # Hard cap ~80 words
                words = genre_resp_json.split()
                if len(words) > 80:
                    genre_resp_json = " ".join(words[:80]).rstrip(".,;") + "."
                print('genre_resp_json', genre_resp_json)
                st.markdown(
                    f"""
                    <div class='wrapup-card'>
                        <div class='wrapup-header'><span class='wrapup-badge'>Genres</span><h3 style='margin:0;'>Estimated Flavor</h3></div>
                        <hr class='wrapup-card-divider' />
                        <p>{genre_resp_json}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

    # Strava section
    if has_strava:
        with col_strava if col_strava is not None else st:
            st.markdown("<div class='section-strava'>", unsafe_allow_html=True)
            st.subheader('Workouts in 2025')
            st.caption(f"Total: {len(workouts_this_year)} • Distance: {workout_stats['total_distance_miles']:.2f} mi • Elev Gain: {workout_stats['total_elev_gain_m']:.0f} m")
            distance_numeric = pd.to_numeric(workouts_this_year['Distance'], errors='coerce') * 0.621371
            df_display = workouts_this_year.iloc[:, 2:].copy()
            if 'Link' in workouts_this_year.columns:
                df_display['Link'] = workouts_this_year['Link']
            st.dataframe(
                df_display,
                column_config={
                    'Link': st.column_config.LinkColumn("Activity Link")
                },
                hide_index=True,
            )
            # Render a linked list of recent activities with names as the clickable text
            if 'Link' in df_display.columns and 'Activity Name' in workouts_this_year.columns:
                # Sort by most recent activity date and then take top 10
                preview_df = workouts_this_year.sort_values('Activity Date', ascending=False).head(10)
                preview = preview_df[['Activity Name', 'Activity Date']].copy()
                preview['Link'] = preview_df['Link']
                # Format dates as YYYY-MM-DD
                if 'Activity Date' in preview.columns:
                    preview['Date'] = preview['Activity Date'].dt.strftime('%Y-%m-%d')
                linked_lines = "\n".join(
                    [f"- [" + str(row['Activity Name']) + "](" + str(row['Link']) + ") — " + str(row.get('Date', '')) for _, row in preview.iterrows()]
                )
                st.markdown("Recent activities:" + "\n" + linked_lines)
            st.markdown("</div>", unsafe_allow_html=True)


if strava_data is not None and st.session_state.get("wrapup_ready", False):
    with col_strava if 'col_strava' in locals() and col_strava is not None else st:
        st.markdown("<div class='section-strava'>", unsafe_allow_html=True)
        st.subheader('Workouts by Activity Type')
        # Aggregate counts per activity type
        type_counts = (
            workouts_this_year.groupby("Activity Type").agg(
                count=("Activity Name", "count")
            ).reset_index()
        )
        type_counts["Activity Type"] = type_counts["Activity Type"].fillna("Unknown").astype(str)
        type_counts["count"] = pd.to_numeric(type_counts["count"], errors="coerce").fillna(0).astype(int)

        # Simple bar chart comparing number of workouts per type
        base_chart = (
            alt.Chart(type_counts)
            .mark_bar()
            .encode(
                x=alt.X("Activity Type:N", title="Activity Type", sort='-y'),
                y=alt.Y("count:Q", title="Workouts", axis=alt.Axis(format="d")),
                tooltip=[
                    alt.Tooltip("Activity Type:N", title="Type"),
                    alt.Tooltip("count:Q", title="Count", format="d")
                ],
                color=alt.Color("Activity Type:N", legend=None)
            )
            .properties(height=300)
        )
        labels = (
            alt.Chart(type_counts)
            .mark_text(dy=-5, color="#111827")
            .encode(x="Activity Type:N", y="count:Q", text=alt.Text("count:Q"))
        )
        st.altair_chart(
            (base_chart + labels).configure_axis(labelFontSize=14, titleFontSize=14).configure_legend(labelFontSize=14, titleFontSize=14),
            use_container_width=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

if strava_data is not None and st.session_state.get("wrapup_ready", False):
    with col_strava if 'col_strava' in locals() and col_strava is not None else st:
        st.markdown("<div class='section-strava'>", unsafe_allow_html=True)
        st.subheader('Workouts by Month')
        # Optional filter by category
        categories = sorted(workouts_this_year["Activity Type"].dropna().astype(str).unique()) if "Activity Type" in workouts_this_year.columns else []
        selected_cat = None
        if categories:
            selected_cat = st.selectbox("Filter by category (optional)", options=["All"] + categories, index=0)
        month_df = workouts_this_year.copy()
        if selected_cat and selected_cat != "All":
            month_df = month_df[month_df["Activity Type"].astype(str) == selected_cat]
        month_df["Month"] = month_df["Activity Date"].dt.strftime('%Y-%m')
        month_counts = (
            month_df.groupby("Month").agg(
                count=("Activity Name", "count")
            ).reset_index()
        )
        month_counts["count"] = pd.to_numeric(month_counts["count"], errors="coerce").fillna(0).astype(int)
        chart = (
            alt.Chart(month_counts)
            .mark_bar()
            .encode(
                x=alt.X("Month:N", title="Month"),
                y=alt.Y("count:Q", title="Workouts", axis=alt.Axis(format="d")),
                tooltip=[
                    alt.Tooltip("Month:N", title="Month"),
                    alt.Tooltip("count:Q", title="Count", format="d")
                ],
                color=alt.Color("Month:N", legend=None)
            )
            .properties(height=300)
        )
        labels = (
            alt.Chart(month_counts)
            .mark_text(dy=-5, color="#111827")
            .encode(x="Month:N", y="count:Q", text=alt.Text("count:Q"))
        )

        st.altair_chart(
            (chart + labels).configure_axis(labelFontSize=14, titleFontSize=14).configure_legend(labelFontSize=14, titleFontSize=14),
            use_container_width=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

if strava_data is not None and st.session_state.get("wrapup_ready", False):
    with col_strava if 'col_strava' in locals() and col_strava is not None else st:
        st.markdown("<div class='section-strava'>", unsafe_allow_html=True)
        st.subheader('Workout Metrics by Month')
        mdf = workouts_this_year.copy()
        mdf["Month"] = mdf["Activity Date"].dt.strftime('%Y-%m')
        # Compute aggregates
        # Elapsed Time: sum (minutes) to hours if time given in minutes; dataset likely seconds. We'll treat as minutes if values are small; otherwise convert seconds to hours.
        elapsed = pd.to_numeric(mdf.get('Elapsed Time', pd.Series(dtype=float)), errors='coerce')
        # Heuristic: if median > 1000, assume seconds; else minutes
        unit_seconds = elapsed.median() > 1000 if len(elapsed) else False
        elapsed_hours_series = (elapsed / 3600.0) if unit_seconds else (elapsed / 60.0)
        mdf['Elapsed Hours'] = elapsed_hours_series
        # Distance miles
        mdf['Distance Miles'] = pd.to_numeric(mdf.get('Distance', pd.Series(dtype=float)), errors='coerce') * 0.621371
        # Average speed mph
        mdf['Avg Speed MPH'] = pd.to_numeric(mdf.get('Average Speed', pd.Series(dtype=float)), errors='coerce') * 0.621371
        # Elevation gain meters (sum)
        mdf['Elev Gain m'] = pd.to_numeric(mdf.get('Elevation Gain', pd.Series(dtype=float)), errors='coerce')

        agg = (
            mdf.groupby('Month').agg(
                elapsed_hours=('Elapsed Hours', 'sum'),
                distance_miles=('Distance Miles', 'sum'),
                avg_speed_mph=('Avg Speed MPH', 'mean'),
                elev_gain_m=('Elev Gain m', 'sum')
            ).reset_index()
        )
        # Round for display
        agg['elapsed_hours'] = agg['elapsed_hours'].round(1)
        agg['distance_miles'] = agg['distance_miles'].round(1)
        agg['avg_speed_mph'] = agg['avg_speed_mph'].round(1)
        agg['elev_gain_m'] = agg['elev_gain_m'].round(0)

        import altair as alt
        charts = []
        charts.append(
            alt.Chart(agg).mark_line(point=True, color='#f59e0b').encode(
                x=alt.X('Month:N', title='Month'),
                y=alt.Y('elapsed_hours:Q', title='Elapsed Hours'),
                tooltip=[alt.Tooltip('Month:N'), alt.Tooltip('elapsed_hours:Q', title='Hours')]
            ).properties(title='Elapsed Time (hours)', height=220)
        )
        charts.append(
            alt.Chart(agg).mark_line(point=True, color='#10b981').encode(
                x=alt.X('Month:N', title='Month'),
                y=alt.Y('distance_miles:Q', title='Distance (mi)'),
                tooltip=[alt.Tooltip('Month:N'), alt.Tooltip('distance_miles:Q', title='Miles')]
            ).properties(title='Distance (miles)', height=220)
        )
        charts.append(
            alt.Chart(agg).mark_line(point=True, color='#6366f1').encode(
                x=alt.X('Month:N', title='Month'),
                y=alt.Y('avg_speed_mph:Q', title='Avg Speed (mph)'),
                tooltip=[alt.Tooltip('Month:N'), alt.Tooltip('avg_speed_mph:Q', title='mph')]
            ).properties(title='Average Speed (mph)', height=220)
        )
        charts.append(
            alt.Chart(agg).mark_line(point=True, color='#ef4444').encode(
                x=alt.X('Month:N', title='Month'),
                y=alt.Y('elev_gain_m:Q', title='Elev Gain (m)', axis=alt.Axis(format='d')),
                tooltip=[alt.Tooltip('Month:N'), alt.Tooltip('elev_gain_m:Q', title='m')]
            ).properties(title='Elevation Gain (m)', height=220)
        )

        st.altair_chart(
            alt.vconcat(*charts).configure_axis(labelFontSize=14, titleFontSize=14),
            use_container_width=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.get("wrapup_ready", False):
    # Steps section: derive from uploaded Strava or local CSV fallback
    if isinstance(steps_source_df, pd.DataFrame) and len(steps_source_df) and ('Activity Date' in steps_source_df.columns and 'Total Steps' in steps_source_df.columns):
        # daily_steps already computed above
        if len(daily_steps):
            st.markdown("<div class='section-strava'>", unsafe_allow_html=True)
            st.subheader('Steps in 2025')
            st.caption(f"Days: {len(daily_steps)} • Total steps: {int(pd.to_numeric(daily_steps['Steps']).sum()):,}")

            view = st.radio('View', options=['Daily', 'Weekly', '7-day Avg', 'Daily + 7-day Avg'], index=0, horizontal=True)

            # Weekly aggregation prepared once
            wk = daily_steps.copy()
            wk['DateParsed'] = pd.to_datetime(wk['Date'], errors='coerce')
            wk = wk.dropna(subset=['DateParsed'])
            iso = wk['DateParsed'].dt.isocalendar()
            wk['ISOYear'] = iso.year.astype(int)
            wk['ISOWeek'] = iso.week.astype(int)
            weekly = (
                wk.groupby(['ISOYear', 'ISOWeek'])['Steps'].sum().astype(int).reset_index()
            )
            weekly['Label'] = weekly['ISOYear'].astype(str) + '-W' + weekly['ISOWeek'].astype(str)

            if view == 'Daily':
                daily_chart = (
                    alt.Chart(daily_steps)
                    .mark_bar(color='#0ea5e9')
                    .encode(
                        x=alt.X('Date:N', title='Date'),
                        y=alt.Y('Steps:Q', title='Steps', axis=alt.Axis(format='d')),
                        tooltip=[alt.Tooltip('Date:N', title='Date'), alt.Tooltip('Steps:Q', title='Steps', format='d')]
                    )
                    .properties(height=420, title='Daily Steps (2025)')
                )

                st.altair_chart(
                    daily_chart.configure_axis(labelFontSize=14, titleFontSize=14),
                    use_container_width=True
                )
            elif view == 'Weekly':
                weekly_chart = (
                    alt.Chart(weekly)
                    .mark_bar(color='#10b981')
                    .encode(
                        x=alt.X('Label:N', title='ISO Week'),
                        y=alt.Y('Steps:Q', title='Steps', axis=alt.Axis(format='d')),
                        tooltip=[alt.Tooltip('Label:N', title='Week'), alt.Tooltip('Steps:Q', title='Steps', format='d')]
                    )
                    .properties(height=360, title='Weekly Steps (2025)')
                )

                st.altair_chart(
                    weekly_chart.configure_axis(labelFontSize=14, titleFontSize=14),
                    use_container_width=True
                )
            else:
                # 7-day rolling average line chart
                roll = daily_steps.copy()
                roll['DateParsed'] = pd.to_datetime(roll['Date'], errors='coerce')
                roll = roll.dropna(subset=['DateParsed']).sort_values('DateParsed')
                roll['Rolling7'] = pd.to_numeric(roll['Steps'], errors='coerce').rolling(7, min_periods=1).mean().round(0).astype(int)
                if view == '7-day Avg':
                    avg_chart = (
                        alt.Chart(roll)
                        .mark_line(point=True, color='#7c3aed')
                        .encode(
                            x=alt.X('Date:N', title='Date'),
                            y=alt.Y('Rolling7:Q', title='7-day Avg Steps', axis=alt.Axis(format='d')),
                            tooltip=[alt.Tooltip('Date:N', title='Date'), alt.Tooltip('Rolling7:Q', title='Avg', format='d')]
                        )
                        .properties(height=420, title='7-day Average Steps (2025)')
                    )

                    st.altair_chart(
                        avg_chart.configure_axis(labelFontSize=14, titleFontSize=14),
                        use_container_width=True
                    )
                else:
                    # Overlay: daily bars + 7-day average line
                    daily_chart = (
                        alt.Chart(daily_steps)
                        .mark_bar(color='#0ea5e9', opacity=0.7)
                        .encode(
                            x=alt.X('Date:N', title='Date'),
                            y=alt.Y('Steps:Q', title='Steps', axis=alt.Axis(format='d')),
                            tooltip=[alt.Tooltip('Date:N', title='Date'), alt.Tooltip('Steps:Q', title='Steps', format='d')]
                        )
                        .properties(height=420)
                    )
                    avg_line = (
                        alt.Chart(roll)
                        .mark_line(point=True, color='#7c3aed')
                        .encode(
                            x=alt.X('Date:N', title='Date'),
                            y=alt.Y('Rolling7:Q', title='Steps / 7-day Avg', axis=alt.Axis(format='d')),
                            tooltip=[alt.Tooltip('Date:N', title='Date'), alt.Tooltip('Rolling7:Q', title='Avg', format='d')]
                        )
                        .properties(title='Daily Steps + 7-day Average (2025)')
                    )

                    st.altair_chart(
                        (daily_chart + avg_line).configure_axis(labelFontSize=14, titleFontSize=14),
                        use_container_width=True
                    )
            st.markdown("</div>", unsafe_allow_html=True)

# Removed redundant empty section-books wrapper

if book_data is not None and st.session_state.get("wrapup_ready", False):
    with col_books if 'col_books' in locals() and col_books is not None else st:
        st.markdown("<div class='section-books'>", unsafe_allow_html=True)
        st.subheader('Books ratings')
        df_ratings = (
            books_this_year.groupby("My Rating").agg(
                count=("Title", "count"),
                titles=("Title", lambda x: ", ".join(x.tolist()[:15]))
            ).reset_index()
        )

        # Ensure rating labels are integers and counts are ints
        df_ratings["My Rating"] = pd.to_numeric(df_ratings["My Rating"], errors="coerce").fillna(0).astype(int)
        df_ratings["count"] = df_ratings["count"].astype(int)

        rating_chart = (
            alt.Chart(df_ratings)
            .mark_bar()
            .encode(
                x=alt.X("My Rating:N", title="Rating"),
                y=alt.Y("count:Q", title="Books", axis=alt.Axis(format="d")),
                color=alt.Color(
                    "My Rating:N",
                    title="Rating",
                    scale=alt.Scale(scheme="tableau10"),
                    legend=alt.Legend(title="Rating")
                ),
                tooltip=[alt.Tooltip("My Rating:N", title="Rating"),
                            alt.Tooltip("count:Q", title="Count", format="d")]
            )
            .properties(height=300)
        )

        # Interactive selection: click a bar to filter titles below
        rating_select = alt.selection_single(fields=["My Rating"], empty="none")
        rating_chart = rating_chart.add_selection(rating_select)

        titles_base = books_this_year[["Title", "Author", "My Rating"]].copy()
        titles_base = titles_base.dropna(subset=["Title", "Author"])
        titles_base = titles_base[(titles_base["Title"].str.len() > 0) & (titles_base["Author"].str.len() > 0)]
        titles_base["Line"] = titles_base["Title"].str.strip() + " — " + titles_base["Author"].str.strip()

        titles_chart = (
            alt.Chart(titles_base)
            .mark_text(align="center", baseline="middle", size=14, color="white")
            .encode(
                y=alt.Y("Line:N", sort=None, axis=alt.Axis(title=None, labels=False, ticks=False)),
                text="Line:N"
            )
            .transform_filter(rating_select)
            .properties(height=500)
        )

        st.altair_chart(
            alt.vconcat(
                rating_chart,
                titles_chart
            ).configure_axis(labelFontSize=14, titleFontSize=14)
                .configure_legend(labelFontSize=14, titleFontSize=14),
            use_container_width=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

selected_rating = None
if book_data is not None and st.session_state.get("wrapup_ready", False):
    with col_books if 'col_books' in locals() and col_books is not None else st:
        st.markdown("<div class='section-books'>", unsafe_allow_html=True)
        selected_rating = st.selectbox(
        "Show books with rating:",
        options=sorted(df_ratings["My Rating"].unique()),
        index=0 if len(df_ratings) else None,
        placeholder="Select a rating"
        )
        st.markdown("</div>", unsafe_allow_html=True)

if book_data is not None and st.session_state.get("wrapup_ready", False) and selected_rating is not None:
    with col_books if 'col_books' in locals() and col_books is not None else st:
        st.markdown("<div class='section-books'>", unsafe_allow_html=True)
        st.subheader(f"Books rated {selected_rating}")
        df_sel = books_this_year.loc[
            books_this_year["My Rating"] == selected_rating,
            ["Title", "Author", "Original Publication Year", "My Rating"]
        ].copy()
        # Ensure integers display without commas
        df_sel["Original Publication Year"] = pd.to_numeric(df_sel["Original Publication Year"], errors="coerce").astype('Int64').astype(str)
        df_sel["My Rating"] = pd.to_numeric(df_sel["My Rating"], errors="coerce").astype('Int64').astype(str)
        st.write(df_sel)
        st.markdown("</div>", unsafe_allow_html=True)

if book_data is not None and st.session_state.get("wrapup_ready", False):
    with col_books if 'col_books' in locals() and col_books is not None else st:
        st.markdown("<div class='section-books'>", unsafe_allow_html=True)
        st.subheader('Year Published')
    df_years = (
        books_this_year.groupby("Original Publication Year").agg(
            count=("Title", "count"),
            titles=("Title", lambda x: ", ".join(x.tolist()[:15]))
        ).reset_index()
    )

    # Ensure year and counts are integers
    df_years["Original Publication Year"] = pd.to_numeric(df_years["Original Publication Year"], errors="coerce").fillna(0).astype(int)
    df_years["count"] = df_years["count"].astype(int)

    # Prevent thousands-separator commas by using string labels for years
    df_years["Original Publication Year"] = df_years["Original Publication Year"].astype(str)

selected_year = None
if book_data is not None and st.session_state.get("wrapup_ready", False):
    with col_books if 'col_books' in locals() and col_books is not None else st:
        st.markdown("<div class='section-books'>", unsafe_allow_html=True)
        selected_year = st.selectbox(
        "Show books from year:",
        options=sorted(df_years["Original Publication Year"].unique()),
        index=0 if len(df_years) else None,
        placeholder="Select a year"
        )
        st.markdown("</div>", unsafe_allow_html=True)

if book_data is not None and st.session_state.get("wrapup_ready", False) and selected_year is not None:
    with col_books if 'col_books' in locals() and col_books is not None else st:
        st.markdown("<div class='section-books'>", unsafe_allow_html=True)
        st.subheader(f"Books published in {selected_year}")
        # Ensure comparable types (cast column to string before comparing to selected_year)
        col_year = "Original Publication Year"
        df_year_filter = books_this_year.copy()
        df_year_filter[col_year] = pd.to_numeric(df_year_filter[col_year], errors="coerce").astype('Int64').astype(str)
        df_year_sel = df_year_filter.loc[
            df_year_filter[col_year] == str(selected_year),
            ["Title", "Author", col_year, "My Rating"]
        ].copy()
        # Ensure integers display without commas
        df_year_sel["My Rating"] = pd.to_numeric(df_year_sel["My Rating"], errors="coerce").astype('Int64').astype(str)
        st.write(df_year_sel)
        st.markdown("</div>", unsafe_allow_html=True)
# Custom sticky footer
st.markdown("""
<div class="footer">
    made with <3 in sf | <a href="https://github.com/elizabethsiegle/goodreads-strava-wrapup-do" target="_blank">View on GitHub</a>
</div>
""", unsafe_allow_html=True)
