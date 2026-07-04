import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF

st.set_page_config(page_title="Horizon • Travel AI", page_icon="🌊", layout="wide")

st.markdown("""
<style>
    .main-header { font-family: 'Playfair Display', serif; color: #FF6B6B; text-align: center; }
    .hero { border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
    
    /* Custom Navigation */
    .nav-button {
        background: linear-gradient(90deg, #FF6B6B, #FFB800);
        color: white;
        border: none;
        padding: 12px 20px;
        border-radius: 50px;
        font-weight: bold;
        margin: 6px 0;
        width: 100%;
        text-align: left;
        transition: all 0.3s ease;
    }
    .nav-button:hover {
        transform: translateX(8px);
        box-shadow: 0 4px 15px rgba(255,107,107,0.4);
    }
    .nav-button.active {
        background: linear-gradient(90deg, #FF4757, #FFA502);
        box-shadow: 0 0 0 3px rgba(255,107,107,0.3);
    }
    
    .destination-card { 
        background: #1e2937; border-radius: 20px; padding: 0; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.3); overflow: hidden;
        transition: all 0.4s ease;
    }
    .destination-card:hover { transform: translateY(-10px); box-shadow: 0 20px 40px rgba(255,107,107,0.3); }
    .card-image { height: 240px; object-fit: cover; width: 100%; }
    .card-content { padding: 20px; }
</style>
""", unsafe_allow_html=True)

# Navigation using session state
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

def set_page(p):
    st.session_state.current_page = p
    st.rerun()

with st.sidebar:
    st.image("https://via.placeholder.com/180x180/FF6B6B/FFFFFF?text=🌊", width=150)
    st.title("Horizon")
    st.caption("Your Intelligent Travel Companion")
    
    pages = ["Home", "Chat", "Itinerary", "Travel DNA", "Explore"]
    icons = ["🏠", "💬", "🗺️", "🧬", "✨"]
    
    for p, icon in zip(pages, icons):
        if st.button(f"{icon} {p}", key=p, use_container_width=True):
            set_page(p)

page = st.session_state.current_page

def generate_mock_itinerary(dest="Kyoto"):
    return [
        {"day":1, "title":f"Arrival in {dest}", "activity":"Airport → Hotel + Evening Walk", "walking":"3.2 km", "confidence":95},
        {"day":2, "title":"Cultural Highlights", "activity":"Temples & Shrines", "walking":"6.5 km", "confidence":92},
        {"day":3, "title":"Nature Day", "activity":"Bamboo Forest", "walking":"5.8 km", "confidence":89}
    ]

if page == "Home":
    st.markdown("<h1 class='main-header'>Welcome to Horizon, Hirak! 🌴</h1>", unsafe_allow_html=True)
    st.image("https://picsum.photos/id/1015/1400/620", use_column_width=True, caption="Your next unforgettable journey begins here")
    
    st.subheader("Quick Start Your Adventure")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("💬 Chat with Horizon", use_container_width=True):
            set_page("Chat")
    with col2:
        if st.button("✨ Browse Destinations", use_container_width=True):
            set_page("Explore")
    with col3:
        if st.button("🗺️ My Itinerary", use_container_width=True):
            set_page("Itinerary")
    with col4:
        if st.button("🧬 My Travel DNA", use_container_width=True):
            set_page("Travel DNA")

elif page == "Chat":
    st.title("💬 Chat with Horizon")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hi Hirak! How can I help plan your next adventure?"}]
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    if prompt := st.chat_input("Describe your dream trip..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            st.write("Planning using your Travel DNA...")

elif page == "Itinerary":
    st.title("📍 Your Interactive Itinerary")
    itinerary = generate_mock_itinerary()
    for day in itinerary:
        st.info(f"**Day {day['day']}**: {day['activity']} ({day['walking']}) — Confidence: {day['confidence']}%")
    if st.button("📄 Export as PDF", type="primary"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=16)
        pdf.cell(200, 10, txt="Horizon Itinerary - Kyoto", ln=True, align='C')
        for day in itinerary:
            pdf.cell(200, 10, txt=f"Day {day['day']}: {day['activity']}", ln=True)
        pdf.output("itinerary.pdf")
        with open("itinerary.pdf", "rb") as f:
            st.download_button("Download PDF", f, file_name="Horizon_Itinerary.pdf", mime="application/pdf")

elif page == "Travel DNA":
    st.title("🧬 Your Travel DNA")
    col1, col2 = st.columns(2)
    with col1:
        categories = ['Adventure','Culture','Food','Photography','Relax','Walking']
        values = [72,94,88,95,68,81]
        fig = go.Figure(go.Scatterpolar(r=values+[values[0]], theta=categories+[categories[0]], fill='toself', line_color='#FF6B6B'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,100])), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Explore":
    st.title("✨ Top 10 International Destinations")
    st.caption("Curated based on your Travel DNA preferences")
    
    destinations = [
        ("Kyoto, Japan", "Immerse yourself in timeless temples, serene gardens, and the magical cherry blossom season.", "97%", "https://picsum.photos/id/1015/600/280"),
        ("Bali, Indonesia", "Discover golden beaches, lush rice terraces, spiritual yoga retreats, and vibrant Hindu culture.", "92%", "https://picsum.photos/id/1016/600/280"),
        ("Paris, France", "Stroll along the Seine, visit iconic museums, enjoy world-class cuisine and romantic charm.", "88%", "https://picsum.photos/id/1018/600/280"),
        ("Santorini, Greece", "Experience breathtaking cliffside views, dramatic sunsets, and charming white-washed villages.", "91%", "https://picsum.photos/id/102/600/280"),
        ("Swiss Alps, Switzerland", "Journey through majestic mountains and scenic trains in this alpine paradise.", "85%", "https://picsum.photos/id/103/600/280"),
        ("Marrakech, Morocco", "Wander bustling souks, experience vibrant markets, and traditional riad hospitality.", "79%", "https://picsum.photos/id/104/600/280"),
        ("Banff, Canada", "Explore turquoise glacial lakes, towering peaks, and abundant wildlife.", "82%", "https://picsum.photos/id/105/600/280"),
        ("Barcelona, Spain", "Admire Gaudí’s architectural wonders, relax on Mediterranean beaches, and savor tapas culture.", "87%", "https://picsum.photos/id/106/600/280"),
        ("Queenstown, New Zealand", "Dive into adventure with bungee jumping and stunning fjord landscapes.", "76%", "https://picsum.photos/id/107/600/280"),
        ("Dubai, UAE", "Marvel at futuristic skyscrapers, enjoy luxury shopping, desert safaris, and world-class entertainment.", "81%", "https://picsum.photos/id/108/600/280")
    ]
    
    cols = st.columns(2)
    for i, (name, desc, match, img) in enumerate(destinations):
        with cols[i % 2]:
            st.markdown(f"""
            <div class="destination-card">
                <img src="{img}" class="card-image">
                <div class="card-content">
                    <h3>{name}</h3>
                    <p>{desc}</p>
                    <p><strong>DNA Match: {match}</strong></p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"🌟 Plan Trip to {name.split(',')[0]}", key=f"plan_{i}"):
                st.session_state.current_destination = name
                st.session_state.current_page = "Itinerary"
                st.rerun()

st.caption("Horizon Travel AI • Capstone Demo")
