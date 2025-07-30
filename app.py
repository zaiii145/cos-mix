import streamlit as st
import spotipy
import time
from src.spotify_utils import (
    get_spotify_client_credentials_manager,
    get_spotify_oauth_manager,
    get_spotify_client,
    load_and_prepare_data, # For background public data check
    get_all_user_playlists_metadata, # to get list - user's playlists
    get_songs_from_playlist_ids,     # to get songs - selected playlists
    get_audio_features,              # fetch features - selected songs
    filter_and_select_songs_by_mood  # for mood-based filtering
)
from src.config import REDIRECT_URI
import pandas as pd 

st.set_page_config(
    page_title="Cosmix: Mood Playlist Creator",
    page_icon="🎶",
    layout="wide"
)

sp_client_credentials_manager = get_spotify_client_credentials_manager()
sp_client = get_spotify_client(sp_client_credentials_manager)

if sp_client is None:
    st.error("CRITICAL ERROR: Initial Spotify client (for public data collection) could not be initialized. Please check your CLIENT_ID and CLIENT_SECRET in src/config.py.")
    st.stop()

sp_oauth_manager = get_spotify_oauth_manager()

# Main Streamlit UI
st.title("🎶 Cosmix: Mood Playlist Creator")
st.markdown("Log in to Spotify, select your playlists, and create a new playlist based on your desired mood and song count!")

st.markdown("---")
st.sidebar.header("Spotify Authentication")

# Session state variables
if 'sp_user' not in st.session_state:
    st.session_state['sp_user'] = None
if 'processed_code' not in st.session_state:
    st.session_state['processed_code'] = None
if 'user_playlists_metadata' not in st.session_state:
    st.session_state['user_playlists_metadata'] = [] # meta data storage
if 'last_generated_playlist_info' not in st.session_state:
    st.session_state['last_generated_playlist_info'] = None # last generated playlist info

user_logged_in = False
user_display_name = "Guest"

if st.session_state['sp_user']:
    try:
        user_profile = st.session_state['sp_user'].current_user()
        user_display_name = user_profile['display_name']
        user_logged_in = True
        st.sidebar.success(f"Logged in as: **{user_display_name}**")
    except spotipy.SpotifyException as e:
        if "The access token expired" in str(e) or "Invalid access token" in str(e):
            st.sidebar.warning("Your Spotify session has expired. Please log in again.")
        else:
            st.sidebar.error(f"Error accessing Spotify user data: {e}. Please try logging in again.")
        st.session_state['sp_user'] = None
        st.session_state['token_info'] = None
        st.session_state['auth_started'] = False
        st.session_state['processed_code'] = None
        st.session_state['user_playlists_metadata'] = [] 
        st.session_state['last_generated_playlist_info'] = None
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"An unexpected error occurred during user data retrieval: {e}")
        st.session_state['sp_user'] = None
        st.session_state['token_info'] = None
        st.session_state['auth_started'] = False
        st.session_state['processed_code'] = None
        st.session_state['user_playlists_metadata'] = []
        st.session_state['last_generated_playlist_info'] = None
        st.rerun()

# Login button if not logged in
if not user_logged_in:
    auth_button_placeholder = st.sidebar.empty()
    if auth_button_placeholder.button("Login to Spotify"):
        auth_url = sp_oauth_manager.get_authorize_url()
        st.sidebar.markdown(f"Please click [**here to log in to Spotify**]({auth_url}) and grant permissions.", unsafe_allow_html=True)
        st.session_state['auth_started'] = True
    else:
        st.sidebar.info(f"Make sure your Spotify App's Redirect URI is set to: `{REDIRECT_URI}`")


# Handle the redirect from Spotify after user login
query_params = st.query_params
if 'auth_started' in st.session_state and 'code' in query_params:
    code = query_params["code"]
    
    if st.session_state['processed_code'] != code:
        try:
            st.info("Attempting to get access token from Spotify...")
            token_string = sp_oauth_manager.get_access_token(code, as_dict=False)
            
            sp_user_temp = spotipy.Spotify(auth_manager=sp_oauth_manager)
            st.session_state['sp_user'] = sp_user_temp
            st.session_state['token_info'] = token_string
            st.session_state['processed_code'] = code

            st.query_params.clear()
            st.success("Successfully logged into Spotify! Rerunning app to update status...")
            st.rerun()
        except Exception as e:
            st.error(f"Could not retrieve token or create client: {e}. Please try logging in again.")
            st.session_state['auth_started'] = False
            st.session_state['token_info'] = None
            st.session_state['sp_user'] = None
            st.session_state['processed_code'] = None
            st.session_state['user_playlists_metadata'] = []
            st.session_state['last_generated_playlist_info'] = None
            st.query_params.clear()
            st.rerun()
    else:
        if code in st.query_params:
            st.query_params.clear()
            st.rerun()


st.markdown("---")

if user_logged_in and st.session_state['sp_user']:
    df_public_data = load_and_prepare_data(sp_client)

    user_profile = st.session_state['sp_user'].current_user() # Re fetch user profile to ensure it's current
    st.session_state['user_playlists_metadata'] = get_all_user_playlists_metadata(user_profile['id'], sp_oauth_manager)

    if st.session_state['user_playlists_metadata']:
        st.subheader(f"1. Select Playlists to Mix:")

        playlist_options = {p['name']: p['id'] for p in st.session_state['user_playlists_metadata']}
        selected_playlist_names = st.multiselect(
            "Choose playlists to combine into a new mix:",
            options=list(playlist_options.keys()),
            help="Select multiple playlists. Songs from these will be combined and filtered."
        )

        st.subheader(f"2. Choose Your Mood & Song Count:")
        context_type = st.selectbox(
            "What type of activity/mood is this playlist for?",
            ('workout', 'drive', 'study', 'party', 'chill'),
            help="Select the general context or mood for your playlist."
        )

        energy_goal = st.radio(
            "Energy level:",
            ('low', 'medium', 'high'),
            help="Controls the overall intensity and dynamism of the music."
        )

        num_songs_to_generate = st.slider(
            "Desired number of songs in the playlist:",
            min_value=5, max_value=100, value=20, step=1,
            help="How many songs should be in your mood-based playlist?"
        )

        st.markdown("---")
        create_mood_mix_button = st.button("✨ Create My Mood-Based Playlist!")

        if create_mood_mix_button and selected_playlist_names:
            selected_playlist_ids = [playlist_options[name] for name in selected_playlist_names]
            
            with st.spinner("Collecting songs from your selected playlists..."):
                
                raw_songs_from_selected_playlists_df = get_songs_from_playlist_ids(user_profile['id'], sp_oauth_manager, selected_playlist_ids)
                
                if raw_songs_from_selected_playlists_df.empty:
                    st.warning("No songs found in your selected playlists. Please choose playlists that contain songs.")
                    st.session_state['last_generated_playlist_info'] = None
                else:
                    track_ids_for_features = raw_songs_from_selected_playlists_df['track_id'].dropna().tolist()
                    audio_features_list = get_audio_features(st.session_state['sp_user'], track_ids_for_features) 
                    df_audio_features = pd.DataFrame(audio_features_list)

                    df_songs_with_features = pd.merge(
                        raw_songs_from_selected_playlists_df,
                        df_audio_features,
                        on='track_id',
                        how='inner'
                    )
                    
                    if df_songs_with_features.empty:
                        st.warning("No songs with complete audio features found in your selected playlists. Cannot create mood-based playlist.")
                        st.session_state['last_generated_playlist_info'] = None
                    else:
                        st.session_state['last_generated_playlist_info'] = None # Clear previous info before new generation
                        with st.spinner("Filtering and selecting songs based on your mood..."):
                            # Filter and select songs based on mood criteria
                            final_selected_songs_list_of_dicts = filter_and_select_songs_by_mood(
                                df_songs_with_features,
                                context_type,
                                energy_goal,
                                num_songs_to_generate
                            )
                            
                            if not final_selected_songs_list_of_dicts:
                                st.warning("No songs matched your mood criteria from the selected playlists. Try adjusting your mood/energy or selecting more playlists.")
                            else:
                                mixed_playlist_url = None
                                generated_playlist_info = None
                                try:
                                    user_profile = st.session_state['sp_user'].current_user()
                                    user_id = user_profile['id']
                                    
                                    selected_playlist_names_str = ", ".join(selected_playlist_names[:2])
                                    if len(selected_playlist_names) > 2:
                                        selected_playlist_names_str += f" + {len(selected_playlist_names) - 2} more"
                                    
                                    new_playlist_name = f"Cosmix Mix: {context_type.capitalize()} ({energy_goal.capitalize()} Energy)"
                                    
                                    with st.spinner("Creating new playlist on Spotify..."):
                                        new_playlist = st.session_state['sp_user'].user_playlist_create(
                                            user=user_id,
                                            name=new_playlist_name,
                                            public=True,
                                            description=f"Mood-based playlist generated by Cosmix from your selected playlists ({selected_playlist_names_str}). Mood: {context_type}, Energy: {energy_goal}. Total songs: {len(final_selected_songs_list_of_dicts)}."
                                        )
                                        
                                        track_ids_to_add = [s['track_id'] for s in final_selected_songs_list_of_dicts]
                                        for i in range(0, len(track_ids_to_add), 100):
                                            batch = track_ids_to_add[i:i + 100]
                                            if batch:
                                                st.session_state['sp_user'].playlist_add_items(
                                                    playlist_id=new_playlist['id'],
                                                    items=batch
                                                )
                                            time.sleep(0.05)
                                        mixed_playlist_url = new_playlist['external_urls']['spotify']
                                        st.success(f"Mood-based playlist '{new_playlist_name}' created on Spotify!")

                                        generated_playlist_info = {
                                            'url': mixed_playlist_url,
                                            'name': new_playlist_name,
                                            'songs': final_selected_songs_list_of_dicts,
                                            'total_duration_ms': sum(s['duration_ms'] for s in final_selected_songs_list_of_dicts)
                                        }
                                        st.session_state['last_generated_playlist_info'] = generated_playlist_info # Store for display

                                except spotipy.SpotifyException as e:
                                    error_msg = e.args[0].get('error_description', str(e)) if isinstance(e.args[0], dict) else str(e)
                                    st.error(f"Error creating playlist on Spotify: {error_msg}. Make sure you granted necessary permissions.")
                                    st.session_state['last_generated_playlist_info'] = None
                                except Exception as e:
                                    st.error(f"An unexpected error occurred while creating playlist: {e}")
                                    st.session_state['last_generated_playlist_info'] = None
            st.rerun()
        elif create_mood_mix_button and not selected_playlist_names:
            st.warning("Please select at least one playlist to create a mood-based playlist.")
            st.session_state['last_generated_playlist_info'] = None

        if st.session_state['last_generated_playlist_info']:
            info = st.session_state['last_generated_playlist_info']
            st.markdown(f"### 🎉 Your Mood-Based Playlist: [Listen Now!]({info['url']}) 🎉")
            st.markdown(f"""
            <iframe src="{info['url'].replace('playlist', 'embed/playlist')}?utm_source=generator"
                    width="100%" height="380" frameBorder="0" allowfullscreen=""
                    allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
            """, unsafe_allow_html=True)
            
            st.write("---")
            st.subheader("Mixed Playlist Tracklist:")
            
            cols_per_row = 3
            cols = st.columns(cols_per_row)
            col_idx = 0
            for i, song_data in enumerate(info['songs']):
                with cols[col_idx]:
                    st.markdown(f"**[{song_data['track_name']}]({song_data['spotify_url']})**")
                    st.write(f"by {song_data['artist_name']}")
                    st.write(f"({(song_data['duration_ms'] / 60000):.2f} min)")
                    if song_data['preview_url']:
                        st.audio(song_data['preview_url'], format="audio/mp3", start_time=0)
                    else:
                        st.info("No preview.")
                col_idx = (col_idx + 1) % cols_per_row
            st.markdown("---")


    else: 
        st.info("No playlists found in your Spotify account. Please create some playlists on Spotify, or ensure you granted 'playlist-read-private' and 'playlist-read-collaborative' scopes.")

else:
    st.info("Please log in to Spotify using the button in the sidebar to get started.")
    _ = load_and_prepare_data(sp_client)

st.markdown("---")
st.caption("Cosmix by Bhaanavee | Powered by Spotify API & Streamlit")
