import streamlit as st

CUSTOM_CSS = '''<style>
:root {
  --primary: #1E3A8A;
  --success: #10B981;
  --warn:    #F59E0B;
  --error:   #EF4444;
  --text:    #111827;
  --muted:   #6B7280;
  --bg:      #FFFFFF;
  --bg-2:    #F3F4F6;
}

[data-testid="stAppViewContainer"] {
  animation: fadeIn 0.6s ease-out both;
}
@keyframes fadeIn {
  from {opacity:0; transform:translateY(6px);}
  to   {opacity:1; transform:translateY(0);}
}

[data-testid="stAlert"] {
  animation: slideIn .45s cubic-bezier(.2,.7,.2,1) both;
}
@keyframes slideIn {
  from {opacity:0; transform:translateX(-10px);}
  to   {opacity:1; transform:translateX(0);}
}

button[kind="primary"] {
  background: var(--primary) !important;
  border-color: var(--primary) !important;
  color: #FFF !important;
  transition: transform .1s ease, box-shadow .2s ease;
}
button[kind="secondary"] {
  color: var(--primary) !important;
  border-color: var(--primary) !important;
  transition: transform .1s ease, box-shadow .2s ease;
}
button:hover {
  transform: scale(1.02);
  box-shadow: 0 6px 16px rgba(0,0,0,.12);
}

.pulse { animation: pulse 2s ease-in-out infinite; }
@keyframes pulse {
  0%   { box-shadow: 0 0 0 0 rgba(16,185,129,.35); }
  70%  { box-shadow: 0 0 0 12px rgba(16,185,129,0); }
  100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); }
}

[data-testid="stMetricValue"] { color: var(--primary); font-weight:600; }
[data-testid="stMetricDelta"] { font-weight:600; }
.streamlit-expanderHeader { color: var(--text); font-weight:600; }
[data-testid="stTable"], .stDataFrame {
  border-radius: 12px; overflow: hidden; border: 1px solid var(--bg-2);
}
</style>'''

def apply_style():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)