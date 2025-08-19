import streamlit as st

def inject_mobile_ui():
    st.markdown("""
    <style>
      @media (max-width: 420px){
        .block-container{padding-top:.75rem!important;padding-bottom:4.8rem!important;}
        .stButton>button,.stTextInput input,.stNumberInput input,.stDateInput input{border-radius:12px;}
        .stCheckbox label{display:inline!important;}
      }
      .fab-menu{
        position:fixed; top:14px; left:14px; z-index:9999;
        width:44px;height:44px;border-radius:12px;background:#111827;border:1px solid #1f2937;
        display:flex;align-items:center;justify-content:center;box-shadow:0 6px 16px rgba(0,0,0,.25);cursor:pointer;
      }
      .burger,.burger:before,.burger:after{content:"";display:block;width:20px;height:2px;background:#e5e7eb;position:relative}
      .burger:before{top:-6px;position:relative}.burger:after{top:4px;position:relative}
      .bottom-nav{
        position:fixed; bottom:10px; left:50%; transform:translateX(-50%); z-index:9998;
        width:92vw; background:#111827; border:1px solid #1f2937; border-radius:16px; padding:8px 6px;
        display:flex; justify-content:space-around; box-shadow:0 8px 30px rgba(0,0,0,.35);
      }
      .bottom-item{flex:1;text-align:center;color:#9ca3af;font-size:12px}
      .bottom-item.active{color:#60a5fa;font-weight:600}
    </style>
    """, unsafe_allow_html=True)

def hamburger():
    st.markdown(
        """<div class="fab-menu" title="Menu" onclick="window.parent.postMessage({type:'toggle-menu'}, '*')">
               <span class="burger"></span>
           </div>""",
        unsafe_allow_html=True,
    )
    st.markdown("""
    <script>
      window.addEventListener('message',(e)=>{
        if(e.data && e.data.type==='toggle-menu'){
          const openBtn = Array.from(document.querySelectorAll('button')).find(b=>/Open sidebar/i.test(b.innerText)||b.title==='Open sidebar');
          const closeBtn = Array.from(document.querySelectorAll('button')).find(b=>/Close sidebar/i.test(b.innerText)||b.title==='Close sidebar');
          (closeBtn||openBtn)?.click();
        }
      });
    </script>""", unsafe_allow_html=True)

def bottom_nav(active="home"):
    items=[("home","🏠","Dashboard"),("plan","🎯","Ataque"),("buckets","🪣","Baldes"),("io","💰","Entradas")]
    html='<div class="bottom-nav">'
    for key,icon,label in items:
        cls="bottom-item active" if key==active else "bottom-item"
        html+=f'<div class="{cls}">{icon}<br/>{label}</div>'
    html+='</div>'
    st.markdown(html, unsafe_allow_html=True)
