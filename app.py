import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF

st.set_page_config(page_title="Horizon • Travel AI", page_icon="🌊", layout="wide")

st.markdown("""
<style>
    .main-header { font-family: 'Playfair Display', serif; color: #FF6B6B; text-align: center; }
    .destination-card {
        background: linear-gradient(145deg, #1e1e2e, #2a2a40);
        border-radius: 20px;
        padding: 0;
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        overflow: hidden;
        transition: all 0.4s ease;
    }
    .destination-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 15px 35px rgba(255,107,107,0.3);
    }
    .card-image {
        height: 220px;
        object-fit: cover;
        width: 100%;
    }
    .card-content {
        padding: 20px;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://via.placeholder.com/180x180/FF6B6B/FFFFFF?text=🌊", width=150)
    st.title("Horizon")
    st.caption("Your Intelligent Travel Companion")
    page = st.radio("Navigate", ["Home", "Chat", "Itinerary", "Travel DNA", "Explore"])

def generate_mock_itinerary(dest="Kyoto"):
    return [
        {"day":1, "title":f"Arrival in {dest}", "activity":"Airport → Hotel + Evening Walk", "walking":"3.2 km", "confidence":95},
        {"day":2, "title":"Cultural Highlights", "activity":"Temples & Shrines", "walking":"6.5 km", "confidence":92},
        {"day":3, "title":"Nature Day", "activity":"Bamboo Forest", "walking":"5.8 km", "confidence":89}
    ]

# ====================== EXPLORE PAGE - REFINED ======================
if page == "Explore":
    st.title("✨ Top 10 International Destinations")
    st.caption("Personalized recommendations based on your Travel DNA")
    
    destinations = [
        ("Kyoto, Japan", "Temples & Cherry Blossoms", "97%", "https://picsum.photos/id/1015/600/300"),
        ("Bali, Indonesia", "Beaches & Spiritual Culture", "92%", "https://picsum.photos/id/1016/600/300"),
        ("Paris, France", "Art, Romance & Cuisine", "88%", "https://picsum.photos/id/1018/600/300"),
        ("Santorini, Greece", "Iconic Sunsets & Cliffs", "91%", "https://picsum.photos/id/102/600/300"),
        ("Swiss Alps, Switzerland", "Mountains & Scenic Trains", "85%", "https://picsum.photos/id/103/600/300"),
        ("Marrakech, Morocco", "Vibrant Markets & Desert", "79%", "https://picsum.photos/id/104/600/300"),
        ("Banff, Canada", "Crystal Lakes & Rockies", "82%", "https://picsum.photos/id/105/600/300"),
        ("Barcelona, Spain", "Gaudi Architecture & Vibes", "87%", "https://picsum.photos/id/106/600/300"),
        ("Queenstown, New Zealand", "Adventure Capital", "76%", "https://picsum.photos/id/107/600/300"),
        ("Dubai, UAE", "Luxury & Futuristic Wonders", "81%", "https://picsum.photos/id/108/600/300")
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
                    <div style="background:#333; border-radius:10px; padding:3px;">
                        <div style="background:#FF6B6B; width:{match}; height:8px; border-radius:10px;"></div>
                    </div>
                    <p><strong>DNA Match: {match}</strong></p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"🌟 Plan Trip to {name.split(',')[0]}", key=f"plan_{i}"):
                st.session_state.current_destination = name
                st.success(f"Generating full personalized itinerary for **{name}**...")
                st.switch_page("Itinerary")

else:
    # Other pages (keep as before)
    if page == "Home":
        st.markdown("<h1 class='main-header'>Welcome to Horizon, Hirak! 🌴</h1>", unsafe_allow_html=True)
        st.image("https://picsum.photos/id/1015/1200/500", use_column_width=True)
    # ... (add other pages as needed)

st.caption("Horizon Travel AI • Capstone Demo")
