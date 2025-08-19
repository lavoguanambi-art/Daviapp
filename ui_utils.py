import streamlit as st

def mobile_friendly_button(label, key=None, type="primary", help=None, small=False):
    """Create a mobile-friendly button with optimized styling."""
    style = """
        <style>
            div[data-testid="stButton"] > button:first-child {
                width: 100%;
                padding: 0.5rem;
                height: auto !important;
                min-height: 2.5rem;
                font-size: 0.875rem;
                margin: 0.25rem 0;
                border-radius: 0.375rem;
                background-color: var(--primary-color);
                color: white;
            }
            div[data-testid="stButton"] > button:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            @media (max-width: 640px) {
                div[data-testid="stButton"] > button:first-child {
                    padding: 0.375rem;
                    font-size: 0.75rem;
                    min-height: 2rem;
                }
            }
        </style>
    """
    st.markdown(style, unsafe_allow_html=True)
    return st.button(label, key=key, type=type, help=help)

def mobile_friendly_table(data, cols, key=None):
    """Create a mobile-friendly table with responsive design."""
    style = """
        <style>
            div[data-testid="stTable"] {
                font-size: 0.875rem;
                width: 100%;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }
            @media (max-width: 640px) {
                div[data-testid="stTable"] {
                    font-size: 0.75rem;
                }
                div[data-testid="stTable"] td, 
                div[data-testid="stTable"] th {
                    padding: 0.375rem !important;
                    white-space: nowrap;
                }
            }
        </style>
    """
    st.markdown(style, unsafe_allow_html=True)
    return st.dataframe(data, columns=cols, key=key)

def show_confirmation_dialog(message, key):
    """Show a mobile-friendly confirmation dialog."""
    col1, col2 = st.columns(2)
    with col1:
        confirm = mobile_friendly_button("✅ Confirmar", f"confirm_{key}")
    with col2:
        cancel = mobile_friendly_button("❌ Cancelar", f"cancel_{key}", type="secondary")
    return confirm, cancel

def show_action_buttons(item_id, small=True):
    """Show edit and delete buttons in a compact format."""
    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        edit = mobile_friendly_button("✏️", f"edit_{item_id}", small=small)
    with col2:
        delete = mobile_friendly_button("🗑️", f"delete_{item_id}", type="secondary", small=small)
    return edit, delete
