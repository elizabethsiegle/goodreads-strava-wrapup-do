import pandas as pd

def create_hour_day_heatmap(df: pd.DataFrame, dt_col: str = 'start_dt'):
    """Create a Plotly heatmap of activity counts by hour and day of week.

    Parameters
    - df: DataFrame containing a datetime-like column
    - dt_col: Name of the column to use for datetime; defaults to 'start_dt'
    """
    import plotly.express as px
    if dt_col not in df.columns:
        return None
    temp = df[df[dt_col].notna()].copy()
    # Ensure the column is datetime
    temp[dt_col] = pd.to_datetime(temp[dt_col], errors='coerce')
    temp = temp.dropna(subset=[dt_col])
    temp['hour'] = temp[dt_col].dt.hour
    temp['day'] = temp[dt_col].dt.day_name()
    pivot = temp.groupby(['hour','day']).size().unstack(fill_value=0)
    # Ensure row (hour) order: 0-23 and column (day) order
    desired_hours = list(range(24))
    pivot = pivot.reindex(index=desired_hours, fill_value=0)
    desired_cols = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    pivot = pivot.reindex(columns=desired_cols, fill_value=0)
    # Build text as list-of-lists matching heatmap shape
    custom_text = pivot.where(pivot > 0, '').astype(str).values.tolist()
    hour_labels = {h: pd.to_datetime(str(h), format='%H').strftime('%I:%M %p') for h in range(24)}
    fig = px.imshow(
        pivot.values,
        labels=dict(x='Day', y='Hour', color='Count'),
        color_continuous_scale='Reds'
    )
    fig.update_traces(
        text=custom_text,
        texttemplate='%{text}',
        textfont=dict(color='#666666', size=10)
    )
    vmin, vmax = pivot.values.min(), pivot.values.max()
    fig.update_layout(
        font=dict(color='#666666'),
        xaxis=dict(title='', side='top', tickfont=dict(color='#666666')),
        yaxis=dict(
            title='',
            autorange='reversed',
            tickmode='array',
            tickvals=list(range(24)),
            ticktext=[hour_labels[h] for h in range(24)],
            tickfont=dict(color='#666666')
        ),
        margin=dict(l=40, r=20, t=40, b=60),
        template='plotly_white',
        coloraxis_colorbar=dict(
            orientation='h',
            yanchor='bottom', y=-0.3,
            xanchor='left', x=0,
            tickvals=[vmin, vmax],
            ticktext=['low','high'],
            title='', ticks='outside', len=0.4, thickness=10,
            tickfont=dict(color='#666666', size=10)
        )
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    return fig