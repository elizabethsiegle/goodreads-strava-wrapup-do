import altair as alt
from dotenv import load_dotenv
import os
import re
import requests
import json
import pandas as pd
import streamlit as st

# Load .env file
load_dotenv()

st.title('Goodreads and Strava 2025 Wrap-up')

# get yours @ https://cloud.digitalocean.com/gen-ai/model-access-keys
MODEL_ACCESS_KEY = os.getenv("MODEL_ACCESS_KEY")

# Instructions for uploading files
st.markdown(
    (
        '<div style="margin-bottom: 12px; font-size: 16px; line-height: 1.6;">'
        'Upload your Strava activities and Goodreads library exports to see an analysis and summary of your 2025 activities and reading.</br></br>'
        'You can <a href="https://www.strava.com/athlete/delete_your_account">export your Strava activities here</a> and <a href="https://www.goodreads.com/review/import">your Goodsreads data here</a>. </br></br>'
        '(you must be logged in to access these links.)'
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

# --- Helpers for Strava workouts ---
def clean_workouts_df(df: pd.DataFrame) -> pd.DataFrame:
    """Select relevant columns, parse types, and return a tidy workouts DataFrame.

    - Keeps core columns for analysis and LLM prompts
    - Parses Activity Date to datetime and filters valid rows
    - Coerces numeric fields for robust aggregation
    """
    if df is None or len(df) == 0:
        return pd.DataFrame()

    core_cols = [
        'Activity ID', 'Activity Date', 'Activity Name', 'Activity Type',
        'Elapsed Time', 'Moving Time', 'Distance', 'Average Speed', 'Max Speed',
        'Elevation Gain', 'Elevation Loss', 'Average Heart Rate', 'Max Heart Rate',
        'Calories', 'Relative Effort'
    ]

    # Only keep columns that exist in incoming CSV
    keep = [c for c in core_cols if c in df.columns]
    tidy = df[keep].copy()

    # Parse datetime and drop invalid
    if 'Activity Date' in tidy.columns:
        tidy['Activity Date'] = pd.to_datetime(
            tidy['Activity Date'], format='%b %d, %Y, %I:%M:%S %p', errors='coerce'
        )
        tidy = tidy.dropna(subset=['Activity Date'])

    # Coerce numerics
    for col in ['Elapsed Time', 'Moving Time', 'Distance', 'Average Speed', 'Max Speed',
                'Elevation Gain', 'Elevation Loss', 'Average Heart Rate', 'Max Heart Rate',
                'Calories', 'Relative Effort']:
        if col in tidy.columns:
            tidy[col] = pd.to_numeric(tidy[col], errors='coerce')

    return tidy


def compute_workout_stats(df: pd.DataFrame) -> dict:
    """Compute useful aggregates for a year of workouts.

    Returns a dict with totals and highlights to feed an LLM.
    """
    if df is None or len(df) == 0:
        base = {
            'workout_count': 0,
            'total_distance_km': 0.0,
            'avg_distance_km': 0.0,
            'longest_distance_km': 0.0,
            'longest_activity_name': None,
            'avg_speed_kmh': 0.0,
            'max_speed_kmh': 0.0,
            'total_elev_gain_m': 0.0,
            'avg_heart_rate': 0.0,
            'max_heart_rate': 0.0,
            'total_calories': 0.0,
            'by_type_counts': {},
            'by_type_distance_km': {},
        }
        return base

    # Basic counts
    workout_count = len(df)
    by_type_counts = df['Activity Type'].value_counts(dropna=False).to_dict() if 'Activity Type' in df.columns else {}

    # Distances
    dist = df['Distance'] if 'Distance' in df.columns else pd.Series(dtype=float)
    total_distance_km = float(pd.to_numeric(dist, errors='coerce').sum()) if len(dist) else 0.0
    avg_distance_km = float(pd.to_numeric(dist, errors='coerce').mean()) if len(dist) else 0.0
    longest_distance_km = float(pd.to_numeric(dist, errors='coerce').max()) if len(dist) else 0.0
    longest_idx = pd.to_numeric(dist, errors='coerce').idxmax() if len(dist) else None
    longest_activity_name = df.loc[longest_idx, 'Activity Name'] if longest_idx is not None and 'Activity Name' in df.columns else None

    # Speeds
    avg_speed_kmh = float(pd.to_numeric(df['Average Speed'], errors='coerce').mean()) if 'Average Speed' in df.columns else 0.0
    max_speed_kmh = float(pd.to_numeric(df['Max Speed'], errors='coerce').max()) if 'Max Speed' in df.columns else 0.0

    # Elevation
    total_elev_gain_m = float(pd.to_numeric(df['Elevation Gain'], errors='coerce').sum()) if 'Elevation Gain' in df.columns else 0.0

    # Heart rate
    avg_heart_rate = float(pd.to_numeric(df['Average Heart Rate'], errors='coerce').mean()) if 'Average Heart Rate' in df.columns else 0.0
    max_heart_rate = float(pd.to_numeric(df['Max Heart Rate'], errors='coerce').max()) if 'Max Heart Rate' in df.columns else 0.0

    # Calories
    total_calories = float(pd.to_numeric(df['Calories'], errors='coerce').sum()) if 'Calories' in df.columns else 0.0

    # Distance by activity type
    if 'Activity Type' in df.columns and 'Distance' in df.columns:
        by_type_distance_km = (
            df[['Activity Type', 'Distance']]
            .assign(Distance=pd.to_numeric(df['Distance'], errors='coerce'))
            .groupby('Activity Type', dropna=False)['Distance']
            .sum()
            .round(2)
            .to_dict()
        )
    else:
        by_type_distance_km = {}

    return {
        'workout_count': int(workout_count),
        'total_distance_km': round(total_distance_km, 2),
        'avg_distance_km': round(avg_distance_km, 2),
        'longest_distance_km': round(longest_distance_km, 2),
        'longest_activity_name': longest_activity_name,
        'avg_speed_kmh': round(avg_speed_kmh, 2),
        'max_speed_kmh': round(max_speed_kmh, 2),
        'total_elev_gain_m': round(total_elev_gain_m, 0),
        'avg_heart_rate': round(avg_heart_rate, 1),
        'max_heart_rate': round(max_heart_rate, 0),
        'total_calories': round(total_calories, 0),
        'by_type_counts': by_type_counts,
        'by_type_distance_km': by_type_distance_km,
    }

# --- Helpers for Goodreads books ---
def clean_books_df(df: pd.DataFrame) -> pd.DataFrame:
    """Keep relevant columns for analysis and LLM and coerce types."""
    if df is None or len(df) == 0:
        return pd.DataFrame()

    keep_cols = [
        'Book Id','Title','Author','Average Rating','My Rating','Publisher',
        'Binding','Number of Pages','Year Published','Original Publication Year',
        'Date Read','Date Added','Exclusive Shelf'
    ]
    keep = [c for c in keep_cols if c in df.columns]
    out = df[keep].copy()
    # Coerce numerics
    for col in ['Average Rating','My Rating','Number of Pages','Year Published','Original Publication Year']:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce')
    # Dates: keep as strings but allow filtering by substring already used
    return out

def compute_book_stats(df: pd.DataFrame) -> dict:
    """Compute compact reading stats for the year."""
    if df is None or len(df) == 0:
        return {
            'books_count': 0,
            'avg_my_rating': 0.0,
            'avg_avg_rating': 0.0,
            'total_pages': 0,
            'longest_book_pages': 0,
            'longest_book_title': None,
            'top_authors': {},
            'year_span': None,
        }

    books_count = int(len(df))
    avg_my_rating = float(pd.to_numeric(df.get('My Rating', pd.Series(dtype=float)), errors='coerce').mean()) if 'My Rating' in df.columns else 0.0
    avg_avg_rating = float(pd.to_numeric(df.get('Average Rating', pd.Series(dtype=float)), errors='coerce').mean()) if 'Average Rating' in df.columns else 0.0
    total_pages = int(pd.to_numeric(df.get('Number of Pages', pd.Series(dtype=float)), errors='coerce').sum()) if 'Number of Pages' in df.columns else 0

    # Longest book
    pages = pd.to_numeric(df.get('Number of Pages', pd.Series(dtype=float)), errors='coerce') if 'Number of Pages' in df.columns else pd.Series(dtype=float)
    longest_idx = pages.idxmax() if len(pages) else None
    longest_book_pages = int(pages.max()) if len(pages) else 0
    longest_book_title = df.loc[longest_idx, 'Title'] if longest_idx is not None and 'Title' in df.columns else None

    # Top authors by count
    top_authors = df['Author'].value_counts(dropna=True).head(5).to_dict() if 'Author' in df.columns else {}

    # Year span of publication
    years = pd.to_numeric(df.get('Original Publication Year', pd.Series(dtype=float)), errors='coerce') if 'Original Publication Year' in df.columns else pd.Series(dtype=float)
    valid_years = years.dropna()
    year_span = None
    if len(valid_years):
        year_span = {'min': int(valid_years.min()), 'max': int(valid_years.max())}

    return {
        'books_count': books_count,
        'avg_my_rating': round(avg_my_rating, 2),
        'avg_avg_rating': round(avg_avg_rating, 2),
        'total_pages': total_pages,
        'longest_book_pages': longest_book_pages,
        'longest_book_title': longest_book_title,
        'top_authors': top_authors,
        'year_span': year_span,
    }

# Readability styles
st.markdown(
    """
    <style>
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
        border-radius: 16px;
        background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(245,245,255,0.95) 100%);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
        border: 1px solid rgba(200, 200, 255, 0.5);
    }
    .wrapup-card h1, .wrapup-card h2, .wrapup-card h3 { 
        margin: 0.4em 0 0.3em; 
        letter-spacing: 0.2px; 
    }
    .wrapup-card p { margin: 0.6em 0; }
    .wrapup-card ul { margin: 0.5em 0 0.5em 1.1em; }
    .wrapup-card strong { color: #2c3e50; }
    .wrapup-card-divider {
        height: 1px;
        background: linear-gradient(90deg, rgba(0,0,0,0), rgba(120,120,200,0.35), rgba(0,0,0,0));
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
        background: #6c5ce7;
        color: white;
        font-size: 12px;
        font-weight: 600;
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

# Only show filtered 2025 datasets (not raw data)

# Layout: two columns if both CSVs, centered single if one 
if st.session_state.get("wrapup_ready", False):
    has_books = uploaded_goodreads is not None
    has_strava = uploaded_strava is not None

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
            books_clean = clean_books_df(book_data)
            books_this_year = books_clean[
                (books_clean['Date Read'].str.contains('2025', na=False)) & (books_clean['Exclusive Shelf'] == 'read')
            ]
            book_stats = compute_book_stats(books_this_year)
            st.subheader('Books read in 2025')
            st.caption(f"Total: {len(books_this_year)} • Avg rating: {book_stats['avg_my_rating']:.2f} • Pages: {book_stats['total_pages']}")
            st.dataframe(books_this_year)

    # Strava section
    if has_strava:
        with col_strava if col_strava is not None else st:
            tidy_strava = clean_workouts_df(strava_data)
            workouts_this_year = tidy_strava[tidy_strava['Activity Date'].dt.year == 2025].copy()
            workout_stats = compute_workout_stats(workouts_this_year)
            st.subheader('Workouts in 2025')
            st.caption(f"Total: {len(workouts_this_year)} • Distance: {workout_stats['total_distance_km']:.2f} km • Elev Gain: {workout_stats['total_elev_gain_m']:.0f} m")
            st.dataframe(workouts_this_year)

# Generate wrap-up via LLM

# Generate wrap-up via LLM for just Strava
if strava_data is not None and st.session_state.get("wrapup_ready", False) and book_data is None:
    url = "https://inference.do-ai.run/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MODEL_ACCESS_KEY}",  # Make sure this variable is defined
        "Content-Type": "application/json"
    }

    # Prepare compact JSON stats and a small sample of workouts for context
    stats_json = json.dumps(workout_stats)
    # Ensure JSON-serializable dates
    sample_df = workouts_this_year.head(10).copy()
    if len(sample_df) and 'Activity Date' in sample_df.columns:
        sample_df['Activity Date'] = sample_df['Activity Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    sample_records = sample_df.to_dict(orient='records') if len(sample_df) else []
    sample_json = json.dumps(sample_records)

    data = {
        "model": "llama3.3-70b-instruct",
        "messages": [
            {"role": "user", "content": (
                "Generate a 2025 year-end wrap-up for the user based on their Strava workouts. "
                "Use the exact numeric stats provided (do not make up numbers). "
                "Highlight totals, per-activity-type distances, longest activity, elevation gain, heart rate, and calories. "
                "Write in a funny, friendly, engaging tone.\n\n"
                f"Stats: {stats_json}\n"
                f"Sample workouts (up to 10): {sample_json}"
            )},
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }

    response = requests.post(url, headers=headers, json=data)
    wrapup_text = response.json().get("choices", [{}])[0].get('message', {}).get("content", "")
    if wrapup_text:
        st.markdown(
            f"""
            <div class='wrapup-card'>
              <div class='wrapup-header'><span class='wrapup-badge'>2025 Wrap-up</span><h3 style='margin:0;'>Strava Summary</h3></div>
              <hr class='wrapup-card-divider' />
              {wrapup_text}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.text_area("Copy & share", value=wrapup_text, height=240)
        st.download_button("Download wrap-up text", data=wrapup_text, file_name="2025-wrapup-strava.txt")

# Generate wrap-up via LLM for just Goodreads
if book_data is not None and st.session_state.get("wrapup_ready", False) and strava_data is None:
    url = "https://inference.do-ai.run/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MODEL_ACCESS_KEY}",  # Make sure this variable is defined
        "Content-Type": "application/json"
    }

    # Prepare compact JSON book stats and small sample
    book_stats_json = json.dumps(book_stats if 'book_stats' in locals() else {})
    book_sample = books_this_year.head(10).to_dict(orient='records') if 'books_this_year' in locals() and len(books_this_year) else []
    book_sample_json = json.dumps(book_sample)

    data = {
        "model": "llama3.3-70b-instruct",
        "messages": [
            {"role": "user", "content": (
                "Generate a 2025 year-end reading wrap-up. Use the exact stats provided (do not make up numbers). "
                "Summarize total books, average rating, total pages, longest book, top authors, and notable highlights. "
                "Write in a funny, friendly, engaging tone. Use human-friendly book titles and author names; do NOT mention internal IDs.\n\n"
                f"Book stats: {book_stats_json}\n"
                f"Sample books (up to 10): {book_sample_json}"
            )},
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }

    response = requests.post(url, headers=headers, json=data)
    wrapup_text = response.json().get("choices", [{}])[0].get('message', {}).get("content", "")
    if wrapup_text:
        st.markdown(
            f"""
            <div class='wrapup-card'>
              <div class='wrapup-header'><span class='wrapup-badge'>2025 Wrap-up</span><h3 style='margin:0;'>Goodreads Summary</h3></div>
              <hr class='wrapup-card-divider' />
              {wrapup_text}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.text_area("Copy & share", value=wrapup_text, height=240)
        st.download_button("Download wrap-up text", data=wrapup_text, file_name="2025-wrapup-books.txt")

# Generate wrap-up via LLM for Strava and Goodreads data
if strava_data is not None and st.session_state.get("wrapup_ready", False) and book_data is not None:
    url = "https://inference.do-ai.run/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MODEL_ACCESS_KEY}",  # Make sure this variable is defined
        "Content-Type": "application/json"
    }

    # Structured Strava stats and small sample for combined summary
    stats_json = json.dumps(workout_stats)
    sample_df = workouts_this_year.head(10).copy()
    if len(sample_df) and 'Activity Date' in sample_df.columns:
        sample_df['Activity Date'] = sample_df['Activity Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    sample_records = sample_df.to_dict(orient='records') if len(sample_df) else []
    sample_json = json.dumps(sample_records)

    # Structured book stats and small sample
    book_stats_json = json.dumps(book_stats)
    book_sample = books_this_year.head(10).to_dict(orient='records') if len(books_this_year) else []
    book_sample_json = json.dumps(book_sample)

    data = {
        "model": "llama3.3-70b-instruct",
        "messages": [
            {"role": "user", "content": (
                "Generate a 2025 year-end wrap-up for Strava + Goodreads. "
                "Use the exact stats provided (do not make up numbers). "
                "For Strava: summarize total distance, workout count, per-type distances, longest activity, elevation, heart rate, calories. "
                "For books: summarize total read, average rating, total pages, longest book, top authors, and highlights. "
                "Write in a funny, friendly, engaging tone. Use human-friendly book titles and author names; do NOT mention internal IDs.\n\n"
                f"Strava stats: {stats_json}\n"
                f"Strava sample (up to 10): {sample_json}\n"
                f"Book stats: {book_stats_json}\n"
                f"Book sample (up to 10): {book_sample_json}"
            )},
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }

    response = requests.post(url, headers=headers, json=data)
    wrapup_text = response.json().get("choices", [{}])[0].get('message', {}).get("content", "")
    if wrapup_text:
        st.markdown(
            f"""
            <div class='wrapup-card'>
              <div class='wrapup-header'><span class='wrapup-badge'>2025 Wrap-up</span><h3 style='margin:0;'>Combined Summary</h3></div>
              <hr class='wrapup-card-divider' />
              {wrapup_text}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.text_area("Copy & share", value=wrapup_text, height=240)
        st.download_button("Download wrap-up text", data=wrapup_text, file_name="2025-wrapup.txt")


if strava_data is not None and st.session_state.get("wrapup_ready", False) and st.checkbox('Show 2025 workouts'):
    st.subheader('2025 Workouts')
    # Ensure numeric distance for proper aggregation/formatting without chained assignment
    distance_numeric = pd.to_numeric(workouts_this_year['Distance'], errors='coerce')
    st.write(workouts_this_year)
    total_distance_km = distance_numeric.sum()
    st.caption(f"Total distance in 2025: {total_distance_km:.2f} km")

if book_data is not None and st.session_state.get("wrapup_ready", False) and st.checkbox('Show 2025 books'):
    st.subheader('2025 Books')
    st.write(books_this_year)
    st.caption(f"Total pages read in 2025: {books_this_year['Number of Pages'].sum():.0f} pages")

if book_data is not None and st.session_state.get("wrapup_ready", False):
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

selected_rating = None
if book_data is not None and st.session_state.get("wrapup_ready", False):
    selected_rating = st.selectbox(
        "Show books with rating:",
        options=sorted(df_ratings["My Rating"].unique()),
        index=0 if len(df_ratings) else None,
        placeholder="Select a rating"
    )

if book_data is not None and st.session_state.get("wrapup_ready", False) and selected_rating is not None:
    st.subheader(f"Books rated {selected_rating}")
    df_sel = books_this_year.loc[
        books_this_year["My Rating"] == selected_rating,
        ["Title", "Author", "Year Published", "My Rating"]
    ].copy()
    # Ensure integers display without commas
    df_sel["Year Published"] = pd.to_numeric(df_sel["Year Published"], errors="coerce").astype('Int64').astype(str)
    df_sel["My Rating"] = pd.to_numeric(df_sel["My Rating"], errors="coerce").astype('Int64').astype(str)
    st.write(df_sel)

if book_data is not None and st.session_state.get("wrapup_ready", False):
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
    selected_year = st.selectbox(
        "Show books from year:",
        options=sorted(df_years["Original Publication Year"].unique()),
        index=0 if len(df_years) else None,
        placeholder="Select a year"
    )

if book_data is not None and st.session_state.get("wrapup_ready", False) and selected_year is not None:
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

