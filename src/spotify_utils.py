import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import pandas as pd
import numpy as np
import time
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
except ImportError:
    st.error("Configuration Error: `src/config.py` not found or missing CLIENT_ID, CLIENT_SECRET, or REDIRECT_URI. Please set these up correctly.")
    print(f"CRITICAL ERROR: [config_import] Failed to import config.py. Check file path and content.", file=sys.stderr)
    st.stop()

# Scopes needed for application
SCOPE = "user-library-read playlist-modify-public playlist-modify-private user-read-private user-read-email playlist-read-private playlist-read-collaborative"

@st.cache_resource
def get_spotify_client_credentials_manager():
    print(f"DEBUG: [get_spotify_client_credentials_manager] Attempting to get Spotify client credentials manager...", file=sys.stderr)
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("Spotify CLIENT_ID or CLIENT_SECRET is not set. Cannot initialize public Spotify client.")
        print(f"ERROR: [get_spotify_client_credentials_manager] CLIENT_ID or CLIENT_SECRET missing in config.py", file=sys.stderr)
        return None
    try:
        manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        print(f"DEBUG: [get_spotify_client_credentials_manager] SpotifyClientCredentials manager created successfully.", file=sys.stderr)
        return manager
    except Exception as e:
        st.error(f"Failed to initialize Spotify client credentials manager: {e}. Check CLIENT_ID/SECRET.")
        print(f"ERROR: [get_spotify_client_credentials_manager] Failed to initialize SpotifyClientCredentials manager: {e}", file=sys.stderr)
        return None

@st.cache_resource
def get_spotify_oauth_manager():
    print(f"DEBUG: [get_spotify_oauth_manager] Attempting to get Spotify OAuth manager...", file=sys.stderr)
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        st.error("Spotify CLIENT_ID, CLIENT_SECRET, or REDIRECT_URI is not set. Cannot initialize Spotify OAuth manager.")
        print(f"ERROR: [get_spotify_oauth_manager] OAuth config missing in config.py", file=sys.stderr)
        return None
    try:
        manager = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=".spotify_cache" # Spotipy caches token info
        )
        print(f"DEBUG: [get_spotify_oauth_manager] SpotifyOAuth manager created successfully.", file=sys.stderr)
        return manager
    except Exception as e:
        st.error(f"Failed to initialize Spotify OAuth manager: {e}")
        print(f"ERROR: [get_spotify_oauth_manager] Failed to initialize SpotifyOAuth manager: {e}", file=sys.stderr)
        return None

@st.cache_resource
def get_spotify_client(_auth_manager):
    print(f"DEBUG: [get_spotify_client] Attempting to get Spotify client with auth manager type: {type(_auth_manager)}", file=sys.stderr)
    if _auth_manager is None:
        print(f"ERROR: [get_spotify_client] _auth_manager is None.", file=sys.stderr)
        return None
    try:
        client = spotipy.Spotify(auth_manager=_auth_manager)
        print(f"DEBUG: [get_spotify_client] Spotipy client created successfully.", file=sys.stderr)
        return client
    except Exception as e:
        st.error(f"Failed to create Spotipy client: {e}")
        print(f"ERROR: [get_spotify_client] Failed to create Spotipy client: {e}", file=sys.stderr)
        return None

def extract_songs_from_playlist_items(sp_client, playlist_tracks_result, playlist_context_name="N/A"):
    """
    Helper function to extract song details from a playlist_items API response.
    It returns a list of dictionaries, where each dictionary represents a song.
    """
    songs = []
    if not sp_client or not playlist_tracks_result or 'items' not in playlist_tracks_result or not playlist_tracks_result['items']:
        print(f"DEBUG: [extract_songs_from_playlist_items] No tracks result or sp_client is None. Result type: {type(playlist_tracks_result)} for context '{playlist_context_name}'", file=sys.stderr)
        return []

    for track_idx, item in enumerate(playlist_tracks_result['items']):
        if not item or 'track' not in item:
            print(f"WARNING: [extract_songs_from_playlist_items] Track item at index {track_idx} in playlist context '{playlist_context_name}' is invalid or missing 'track' key. Skipping.", file=sys.stderr)
            continue

        track = item.get('track')
        if not track:
            print(f"WARNING: [extract_songs_from_playlist_items] 'track' object is None for item {track_idx} in playlist context '{playlist_context_name}'. Skipping.", file=sys.stderr)
            continue

        track_id = track.get('id')
        track_name = track.get('name')
        duration_ms = track.get('duration_ms')
        popularity = track.get('popularity')
        preview_url = track.get('preview_url')
        spotify_url = track.get('external_urls', {}).get('spotify')

        if not track_id or not track_name or duration_ms is None:
            print(f"WARNING: [extract_songs_from_playlist_items] Track {track_idx} in playlist context '{playlist_context_name}' missing critical data (id, name, duration_ms). Skipping.", file=sys.stderr)
            continue

        artist_name = 'Unknown'
        artists = track.get('artists')
        if artists and isinstance(artists, list) and len(artists) > 0 and artists[0].get('name'):
            artist_name = artists[0]['name']
        else:
            print(f"WARNING: [extract_songs_from_playlist_items] Track {track_id} in context '{playlist_context_name}' missing artist name. Using 'Unknown'.", file=sys.stderr)

        song_data = {
            'track_id': track_id,
            'track_name': track_name,
            'artist_name': artist_name,
            'duration_ms': duration_ms,
            'popularity': popularity if popularity is not None else 0,
            'preview_url': preview_url,
            'spotify_url': spotify_url
        }
        songs.append(song_data)
    return songs

# Define FEATURE_COLUMNS globally, as it's used in get_audio_features and filter_and_select_songs_by_mood
FEATURE_COLUMNS = ['danceability', 'energy', 'valence', 'tempo', 'acousticness',
                   'instrumentalness', 'liveness', 'speechiness', 'loudness']

def get_audio_features(sp_client, track_ids):
    print(f"DEBUG: [get_audio_features] Starting get_audio_features for {len(track_ids)} tracks. sp_client is None: {sp_client is None}", file=sys.stderr)
    features = []
    if not sp_client or not track_ids:
        print(f"ERROR: [get_audio_features] sp_client is None or no track_ids.", file=sys.stderr)
        return [] 

    # Process in batches of 100 - spotify API token limit 
    for i in range(0, len(track_ids), 100):
        batch_track_ids = track_ids[i:i + 100]
        
        try:
            audio_features_batch_response = sp_client.audio_features(batch_track_ids)
            
            for j, track_id_in_batch in enumerate(batch_track_ids):
                default_feature_dict = {'track_id': track_id_in_batch}
                for col in FEATURE_COLUMNS:
                    default_feature_dict[col] = np.nan 

                af = None
                if audio_features_batch_response and j < len(audio_features_batch_response):
                    af = audio_features_batch_response[j]

                if af is not None and 'id' in af:
                    af['track_id'] = af.pop('id')
                    merged_af = {**default_feature_dict, **af}
                    features.append(merged_af)
                else:
                    features.append(default_feature_dict) 
                    print(f"WARNING: [get_audio_features] Received None or invalid audio feature for track ID '{track_id_in_batch}'. Adding with default NaN data.", file=sys.stderr)
            
            time.sleep(0.01) # Small sleep to be gentle with API :-), wont cause errors later hehe
        except spotipy.SpotifyException as e:
            print(f"ERROR: [get_audio_features] Spotify API error fetching audio features for batch starting with '{batch_track_ids[0]}': {e}. Adding default NaN data for batch.", file=sys.stderr)
            for track_id_in_batch in batch_track_ids:
                default_feature_dict = {'track_id': track_id_in_batch}
                for col in FEATURE_COLUMNS:
                    default_feature_dict[col] = np.nan
                features.append(default_feature_dict)
            continue
        except Exception as e:
            print(f"ERROR: [get_audio_features] General error fetching audio features for batch starting with '{batch_track_ids[0]}': {e}. Adding default NaN data for batch.", file=sys.stderr)
            for track_id_in_batch in batch_track_ids:
                default_feature_dict = {'track_id': track_id_in_batch}
                for col in FEATURE_COLUMNS:
                    default_feature_dict[col] = np.nan
                features.append(default_feature_dict)
            continue
    print(f"DEBUG: [get_audio_features] Finished. Total features collected: {len(features)}", file=sys.stderr)
    return features

@st.cache_data(show_spinner="Fetching your Spotify playlists...")
def get_all_user_playlists_metadata(_user_id, _sp_oauth_manager): # Pass user_id and oauth_manager for caching
    """
    Fetches all playlists for the current user (only metadata, not tracks).
    Returns a list of dictionaries with playlist ID and name.
    """
    print(f"DEBUG: [get_all_user_playlists_metadata] Starting for user ID: {_user_id}", file=sys.stderr)
    sp_user_client = spotipy.Spotify(auth_manager=_sp_oauth_manager)
    if not sp_user_client: # Should not happen if _sp_oauth_manager is valid
        st.error("Spotify user client is not initialized. Cannot fetch user playlists.")
        return []

    playlists_metadata = []
    try:
        results = sp_user_client.current_user_playlists()
        while results:
            for i, playlist in enumerate(results['items']):
                playlists_metadata.append({
                    'id': playlist['id'],
                    'name': playlist['name'],
                    'owner': playlist['owner']['display_name'] if 'owner' in playlist and 'display_name' in playlist['owner'] else 'Unknown',
                    'total_tracks': playlist['tracks']['total'] if 'tracks' in playlist and 'total' in playlist['tracks'] else 0
                })
            if results['next']:
                results = sp_user_client.next(results)
            else:
                results = None
            time.sleep(0.05) # Be nice to the API, or else extend your quota :D.

        print(f"DEBUG: [get_all_user_playlists_metadata] Fetched {len(playlists_metadata)} playlists metadata.", file=sys.stderr)
        return playlists_metadata
    except spotipy.SpotifyException as e:
        error_msg = e.args[0].get('error_description', str(e)) if isinstance(e.args[0], dict) else str(e)
        st.error(f"Spotify API Error fetching user playlists metadata: {error_msg}. Make sure you granted 'playlist-read-private' and 'playlist-read-collaborative' scopes.")
        print(f"ERROR: [get_all_user_playlists_metadata] Spotify API Error: {e}", file=sys.stderr)
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred fetching user playlists metadata: {e}")
        print(f"ERROR: [get_all_user_playlists_metadata] General Error: {e}", file=sys.stderr)
        return []

@st.cache_data(show_spinner="Fetching songs from selected playlists...")
def get_songs_from_playlist_ids(_user_id, _sp_oauth_manager, playlist_ids): # Pass user_id and oauth_manager for caching
    """
    Fetches all unique songs from a given list of playlist IDs.
    """
    print(f"DEBUG: [get_songs_from_playlist_ids] Starting for {len(playlist_ids)} playlists for user ID: {_user_id}.", file=sys.stderr)
    if not playlist_ids:
        print(f"DEBUG: [get_songs_from_playlist_ids] No playlist IDs provided.", file=sys.stderr)
        return pd.DataFrame()

    sp_user_client = spotipy.Spotify(auth_manager=_sp_oauth_manager)
    if not sp_user_client:
        st.error("Spotify user client is not initialized. Cannot fetch songs from playlists.")
        return pd.DataFrame()

    all_selected_songs_data = []
    processed_track_ids = set()

    for playlist_id in playlist_ids:
        try:
            results = sp_user_client.playlist_items(playlist_id)
            while results:
                extracted_songs = extract_songs_from_playlist_items(sp_user_client, results, playlist_context_name=f"ID: {playlist_id}")
                for song in extracted_songs:
                    if song['track_id'] not in processed_track_ids:
                        all_selected_songs_data.append(song)
                        processed_track_ids.add(song['track_id'])
                if results['next']:
                    results = sp_user_client.next(results)
                else:
                    results = None
                time.sleep(0.05)
        except spotipy.SpotifyException as e:
            print(f"ERROR: [get_songs_from_playlist_ids] Spotify API Error fetching tracks for playlist {playlist_id}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"ERROR: [get_songs_from_playlist_ids] General Error fetching tracks for playlist {playlist_id}: {e}", file=sys.stderr)
            continue

    print(f"DEBUG: [get_songs_from_playlist_ids] Fetched {len(all_selected_songs_data)} unique songs from selected playlists.", file=sys.stderr)
    return pd.DataFrame(all_selected_songs_data)

@st.cache_data
def load_and_prepare_data(_sp_client_credentials):
    st.info("Collecting and processing initial public song data for analysis. This might take a moment...")
    
    if _sp_client_credentials is None:
        st.error("Spotify client for public data collection is not initialized. Check your CLIENT_ID and CLIENT_SECRET.")
        print(f"ERROR: [load_and_prepare_data] _sp_client_credentials is None.", file=sys.stderr)
        return pd.DataFrame()

    try:
        search_terms = {
            'top_hits': ['global top 50', 'today\'s top hits', 'viral hits'],
        }
        songs_data = []
        processed_track_ids = set()

        for category, terms in search_terms.items():
            for term in terms:
                print(f"DEBUG: [load_and_prepare_data] Searching for public playlist term: '{term}'", file=sys.stderr)
                
                playlists_search_result = None
                try:
                    playlists_search_result = _sp_client_credentials.search(q=term, type='playlist', limit=5)
                except spotipy.SpotifyException as e:
                    print(f"ERROR: [load_and_prepare_data] Spotify API error during search for '{term}': {e}", file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"ERROR: [load_and_prepare_data] General error during search for '{term}': {e}", file=sys.stderr)
                    continue

                print(f"DEBUG: [load_and_prepare_data] Raw search result for '{term}': {playlists_search_result}", file=sys.stderr)

                if playlists_search_result and 'playlists' in playlists_search_result and playlists_search_result['playlists'] is not None:
                    extracted_songs = extract_songs_from_playlist_items(_sp_client_credentials, playlists_search_result['playlists'], playlist_context_name=f"Public Search: {term}")
                    print(f"DEBUG: [load_and_prepare_data] Extracted {len(extracted_songs)} songs from playlists for term '{term}'.", file=sys.stderr)
                else:
                    print(f"WARNING: [load_and_prepare_data] 'playlists' key missing or None in search result for term '{term}'. Skipping.", file=sys.stderr)
                    extracted_songs = []

                for song in extracted_songs:
                    if song['track_id'] not in processed_track_ids:
                        songs_data.append(song)
                        processed_track_ids.add(song['track_id'])
                time.sleep(0.05)

        df_songs = pd.DataFrame(songs_data)
        
        print(f"DEBUG: [load_and_prepare_data] Columns in df_songs: {df_songs.columns.tolist()}", file=sys.stderr)

        if df_songs.empty:
            st.warning("No public song data collected. This might limit future criteria-based generation.")
            print(f"WARNING: [load_and_prepare_data] df_songs is empty after public data collection.", file=sys.stderr)
            return pd.DataFrame()
        
        if 'track_id' not in df_songs.columns:
            print(f"ERROR: [load_and_prepare_data] 'track_id' column missing in df_songs. Cannot process further.", file=sys.stderr)
            return pd.DataFrame()

        df_songs.drop_duplicates(subset=['track_id'], inplace=True)
        track_ids = df_songs['track_id'].tolist()
        audio_features = get_audio_features(_sp_client_credentials, track_ids)
        df_audio_features = pd.DataFrame(audio_features)

        df_full_data = pd.merge(df_songs, df_audio_features, on='track_id', how='inner')
        df_full_data.dropna(subset=['danceability', 'energy', 'valence', 'tempo'], inplace=True)
        
        st.success(f"Collected and processed {len(df_full_data)} public songs for analysis.")
        print(f"DEBUG: [load_and_prepare_data] Successfully loaded and prepared public data. Total songs: {len(df_full_data)}", file=sys.stderr)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An error occurred during public data loading: {e}. Please check your internet connection and Spotify API credentials.")
        print(f"CRITICAL ERROR: [load_and_prepare_data] Exception: {e}", file=sys.stderr)
        return pd.DataFrame()


# Mood-based Filtering and Selection Logic
FEATURE_COLUMNS = ['danceability', 'energy', 'valence', 'tempo', 'acousticness',
                   'instrumentalness', 'liveness', 'speechiness', 'loudness']

def get_target_features(context_type, energy_goal):
    """
    Defines target audio feature ranges/means based on context and energy goal.
    """
    base_profiles = {
        'workout': {
            'energy': (0.7, 1.0), 'danceability': (0.6, 1.0), 'valence': (0.5, 0.9),
            'tempo': (120, 160), 'instrumentalness': (0.0, 0.5), 'speechiness': (0.0, 0.2)
        },
        'drive': {
            'energy': (0.5, 0.85), 'danceability': (0.4, 0.8), 'valence': (0.4, 0.8),
            'tempo': (90, 140), 'instrumentalness': (0.0, 0.7), 'speechiness': (0.0, 0.3)
        },
        'study': {
            'energy': (0.0, 0.4), 'danceability': (0.0, 0.3), 'valence': (0.0, 0.4),
            'instrumentalness': (0.7, 1.0), 'speechiness': (0.0, 0.2), 'acousticness': (0.6, 1.0)
        },
        'party': {
            'energy': (0.8, 1.0), 'danceability': (0.7, 1.0), 'valence': (0.6, 1.0),
            'tempo': (120, 180), 'loudness': (-10.0, 0.0)
        },
        'chill': {
            'energy': (0.2, 0.5), 'danceability': (0.3, 0.6), 'valence': (0.2, 0.6),
            'acousticness': (0.4, 0.9), 'tempo': (60, 100), 'loudness': (-15.0, -5.0)
        },
    }

    profile = base_profiles.get(context_type, {})

    if energy_goal == 'low':
        profile['energy'] = (profile.get('energy', (0,0))[0] * 0.5, profile.get('energy', (0,0))[1] * 0.75)
        profile['tempo'] = (profile.get('tempo', (0,0))[0] * 0.8 if profile.get('tempo') else 60, profile.get('tempo', (0,0))[1] * 0.9 if profile.get('tempo') else 100)
        profile['loudness'] = (profile.get('loudness', (-20.0, 0.0))[0] - 5, profile.get('loudness', (-20.0, 0.0))[1] - 5)
    elif energy_goal == 'high':
        profile['energy'] = (min(1.0, profile.get('energy', (0,0))[0] * 1.25), min(1.0, profile.get('energy', (0,0))[1] * 1.25))
        profile['tempo'] = (min(200, profile.get('tempo', (0,0))[0] * 1.1) if profile.get('tempo') else 140, min(200, profile.get('tempo', (0,0))[1] * 1.1) if profile.get('tempo') else 180)
        profile['loudness'] = (profile.get('loudness', (-20.0, 0.0))[0] + 5, profile.get('loudness', (-20.0, 0.0))[1] + 5)
    
    return profile

def calculate_feature_score(song_features, target_profile):
    """
    Calculates a "mismatch" score for how well a song's features align with the target profile.
    A lower score indicates a better fit. Penalizes deviations from the target ranges.
    """
    score = 0
    for feature, (min_val, max_val) in target_profile.items():
        if feature in song_features and pd.notna(song_features[feature]):
            val = song_features[feature]
            if val < min_val:
                score += (min_val - val) * 2
            elif val > max_val:
                score += (val - max_val) * 1
    return score

def filter_and_select_songs_by_mood(df_songs_pool, context_type, energy_goal, num_songs_to_select):
    """
    Filters and selects songs from a given DataFrame based on mood criteria and desired count.
    df_songs_pool should already contain audio features.
    """
    print(f"DEBUG: [filter_and_select_songs_by_mood] Starting filtering for {context_type}, {energy_goal} energy, {num_songs_to_select} songs.", file=sys.stderr)
    if df_songs_pool.empty:
        st.warning("No songs available in the pool to filter by mood.")
        return []

    target_profile = get_target_features(context_type, energy_goal)
    st.info(f"Applying mood filter with target profile: {target_profile}")

    candidate_songs = []
    # Ensure all required feature columns exist and are not NaN, else they'll get dropped
    df_filled_features = df_songs_pool.fillna(0)
    df_filtered_features = df_filled_features.dropna(subset=FEATURE_COLUMNS)
    
    print(f"DEBUG: [filter_and_select_songs_by_mood] Songs in pool after dropping missing features: {len(df_filtered_features)}", file=sys.stderr)

    if df_filtered_features.empty:
        st.warning("No songs in the selected playlists have complete audio features for mood filtering. Cannot generate mood-based playlist.")
        return []

    for index, row in df_filtered_features.iterrows():
        song_features_dict = {f: row[f] for f in FEATURE_COLUMNS}
        score = calculate_feature_score(song_features_dict, target_profile)
        candidate_songs.append({'song': row.to_dict(), 'score': score})

    if not candidate_songs:
        st.warning("No songs found matching the mood criteria after scoring. Try adjusting your mood selection or selecting more playlists.")
        return []

    print(f"DEBUG: [filter_and_select_songs_by_mood] Number of candidate songs after initial scoring: {len(candidate_songs)}", file=sys.stderr)

    # Sort candidates by score (lower score = better match)
    candidate_songs.sort(key=lambda x: x['score'])

    # Select the top N songs
    final_selected_songs = [item['song'] for item in candidate_songs[:num_songs_to_select]]
    print(f"DEBUG: [filter_and_select_songs_by_mood] Final selected {len(final_selected_songs)} songs for mood playlist.", file=sys.stderr)

    return final_selected_songs