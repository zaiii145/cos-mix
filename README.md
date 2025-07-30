# Cosmix: Mood Playlist Creator 🎶

Cosmix is a Streamlit-powered web application that helps you create personalized Spotify playlists based on your existing music library and desired mood. Log in with your Spotify account, select your source playlists, choose a mood (like workout, study, or party) and the number of songs, and Cosmix will generate a new custom playlist for you!

## ✨ Features

-   **User Login:** Securely log in with your Spotify account using OAuth 2.0.
-   **Dynamic Playlist Selection:** Choose from *your own* existing Spotify playlists to source songs for your mix.
-   **Mood-Based Filtering:** Generate playlists tailored to specific activities or moods (e.g., workout, drive, study, party, chill) and energy levels.
-   **Song Count Control:** Specify the desired number of songs for your new playlist.
-   **Spotify Integration:** Creates and saves the new mixed playlist directly to your Spotify account.
-   **Audio Previews:** Listen to 30-second audio previews of selected tracks directly within the app.
-   **Embedded Spotify Player:** Play the entire newly generated playlist directly within the Streamlit app.
-   **Responsive Grid Display:** View your generated playlist's songs in a clean, responsive grid with direct links to Spotify.

## 📁 Project Structure
```
CosMix/
├── .streamlit/
│   └── config.toml          # Streamlit UI configuration (e.g., theme)
├── src/
│   ├── __init__.py          # Python package marker
│   ├── config.py            # CRITICAL: Your Spotify API credentials (IGNORED BY GIT)
│   └── spotify_utils.py     # All Spotify API interactions, data processing logic
├── app.py                   # The main Streamlit application entry point
├── requirements.txt         # Python dependencies required for the project
├── .gitignore              # Specifies files/folders to ignore in Git
└── README.md               # This project README file
```
## 🚀 Setup and Running Instructions

Follow these steps carefully to get Cosmix running on your local machine.

### Prerequisites

1.  **Python 3.8+:** Ensure you have a compatible Python version installed.
    * [Download Python](https://www.python.org/downloads/)

2.  **Spotify Developer Account:**
    * Go to [Spotify for Developers Dashboard](https://developer.spotify.com/dashboard/).
    * Log in with your Spotify account.
    * Click on "Create an app".
    * Give your app a **Name** (e.g., "Cosmix Playlist Generator") and a **Description**.
    * **Crucial: Configure Redirect URIs**
        * Spotify **no longer allows `http://localhost:PORT`** as a Redirect URI for security reasons. You **must use `https://`** for publicly accessible URLs or **`http://127.0.0.1:PORT`** for local development loopback.
        * **For this project, we highly recommend using `ngrok`** to create a secure HTTPS tunnel to your local Streamlit app.
        * Once `ngrok` is running (see step 3 below, e.g., `ngrok http 8501`), it will provide a **Forwarding HTTPS URL** like `https://abcdef12345.ngrok-free.app`.
        * You **MUST add this exact URL plus `/callback`** to your Spotify App's Redirect URIs.
            * **Example:** `https://abcdef12345.ngrok-free.app/callback`
        * **Important:** `ngrok`'s free tier provides a *new, unique URL* every time you restart it. This means you will need to **update your Spotify App settings and `src/config.py` every single time the `ngrok` URL changes.**
        * After adding the URI, click "Save" at the bottom of the settings page.
    * Once your app is created, copy your **Client ID** and **Client Secret**. Keep these safe!

3.  **ngrok (for HTTPS during local development):**
    * Download `ngrok` from [ngrok.com/download](https://ngrok.com/download).
    * Unzip the executable and place it in a convenient location (e.g., add it to your system's PATH for easy access).

### Installation Steps

1.  **Clone or Download the Project:**
    If you have Git installed, open your terminal and run:
    ```bash
    git clone <repository-url> # Replace <repository-url> with your GitHub repo URL
    cd Cosmix
    ```
    If not, manually create a folder named `Cosmix`, then download all the project files into it.

2.  **Create a Python Virtual Environment (Highly Recommended):**
    This isolates your project's dependencies from your system's Python packages.
    ```bash
    python3 -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    * **On Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    * **On macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```
    You should see `(venv)` at the beginning of your terminal prompt, indicating the environment is active.

4.  **Install Dependencies:**
    Make sure your virtual environment is active and you are in the `Cosmix/` root directory (where `requirements.txt` is located).
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Spotify API Credentials:**
    * Open the file `src/config.py` in your code editor.
    * Replace the placeholder values with your actual `Client ID`, `Client Secret`, and the `REDIRECT_URI` you obtained from `ngrok` and configured in your Spotify App.

    ```python
    # src/config.py
    CLIENT_ID = 'YOUR_SPOTIPY_CLIENT_ID'
    CLIENT_SECRET = 'YOUR_SPOTIPY_CLIENT_SECRET'
    REDIRECT_URI = 'https://<YOUR_NGROK_HTTPS_URL_HERE>/callback' # e.g., '[https://abcdef12345.ngrok-free.app/callback](https://abcdef12345.ngrok-free.app/callback)'
    ```
    * **Save the `src/config.py` file.**

6.  **Set up `.gitignore` (Crucial for Security):**
    * In the **root directory of your `Cosmix/` project**, create a file named `.gitignore`.
    * Paste the following content into it:
        ```
        # Python specific ignores
        __pycache__/
        *.pyc
        *.pyo
        *.pyd
        .Python
        env/
        venv/
        *.egg-info/
        .pytest_cache/
        .mypy_cache/

        # Streamlit specific ignores
        .streamlit/
        .streamlit/config.toml # Ignore local Streamlit config if you prefer

        # Spotify API specific ignores
        src/config.py        # CRITICAL: Prevents your API keys from being pushed!
        .spotify_cache       # Spotipy's cached tokens (contains sensitive data)

        # Operating System / IDE specific ignores
        .DS_Store            # macOS specific
        Thumbs.db            # Windows specific
        *.log
        *.temp
        ```
    * **Save the `.gitignore` file.**
    * **If you previously accidentally added `src/config.py` or `.spotify_cache` to Git, untrack them:**
        ```bash
        git rm --cached src/config.py
        git rm --cached .spotify_cache
        ```
        (If these commands return an error, it means Git wasn't tracking them, which is good.)

### Running the Application

1.  **Start ngrok:**
    Open a **NEW terminal window** (keep your virtual environment terminal open and active).
    Run `ngrok` to tunnel traffic to your Streamlit app's default port (8501):
    ```bash
    ngrok http 8501
    ```ngrok` will display a "Forwarding" HTTPS URL (e.g., `https://abcdef12345.ngrok-free.app`). **Copy this URL and update your `src/config.py` and Spotify Developer Dashboard Redirect URIs if it's new.**

2.  **Run the Streamlit App:**
    In your **first terminal window** (where your virtual environment is active and you are in the `Cosmix/` root directory), run:
    ```bash
    /Users/bhaanaveecs/Documents/Cos-mix/venv/bin/streamlit run app.py
    ```
    (Using the full path ensures you're running Streamlit from your virtual environment).

    This will open the Cosmix app in your default web browser (usually at `http://localhost:8501`).

## 👨‍💻 Using the App

1.  **Initial Load:** The app will display the title, main message, and the "Login to Spotify" button in the sidebar. You'll also see messages about public data collection running in the background.
2.  **Login to Spotify:** Click the "Login to Spotify" button in the sidebar.
    * You will be redirected to Spotify's authorization page.
    * **Carefully review and grant all requested permissions** (especially for reading/modifying playlists).
    * Spotify will redirect you back to your `ngrok` URL, and your Streamlit app will process the authentication.
3.  **Post-Login:**
    * You should see "Logged in as: YourDisplayName" in the sidebar.
    * The main content area will then display:
        * **"1. Select Playlists to Mix:"** with a multi-select dropdown populated with the names of your Spotify playlists.
        * **"2. Choose Your Mood & Song Count:"** with selectors for `context_type` (mood), `energy_goal`, and `num_songs_to_generate`.
4.  **Create Your Playlist:**
    * Select one or more playlists from the dropdown.
    * Choose your desired mood and the number of songs.
    * Click the "✨ Create My Mood-Based Playlist!" button.
    * The app will process the songs (fetching, merging, filtering), create a new playlist on your Spotify account, and then display the resulting tracklist in a responsive grid with song names, artists, and audio previews/links.

## ⚠️ Important Notes & Troubleshooting

* **`ngrok` URL Changes:** As mentioned, `ngrok`'s free tier provides a new HTTPS URL every time you restart it. **You MUST update `src/config.py` and your Spotify Developer Dashboard's Redirect URIs accordingly each time.** This is the most common reason for "Invalid Redirect URI" errors.
* **Clear `.spotify_cache`:** If you encounter persistent authentication issues (e.g., after updating scopes or if tokens seem invalid), delete the hidden `.spotify_cache` file from your `Cosmix/` project root directory. This forces Spotipy to get a fresh token.
    * On macOS/Linux: `rm .spotify_cache`
    * On Windows: You might need to enable "show hidden files" to delete it manually.
* **Browser Cache:** Sometimes, old browser cache can interfere with Streamlit apps. Try clearing your browser's cache or using an incognito/private window for testing.
* **Spotify API Rate Limits:** The app includes small `time.sleep()` delays to respect Spotify's API rate limits. For very large playlists or many selections, this might still take a moment.
* **Missing Audio Features (403 Errors):** Some tracks (e.g., regional exclusives, podcasts, local files) may not have audio features available from Spotify, resulting in `403 Forbidden` errors. The app is designed to gracefully handle this by skipping such tracks or using `NaN` for their features, but it might reduce the pool of songs for mood-based filtering.
* **Performance:** While caching is implemented, the initial fetching of all songs from selected playlists (especially many large ones) can still take time. Subsequent generations with the *same* selected playlists will be faster due to caching.

## Images

![Cosmix Screenshot](images/login.png)
![Cosmix Screenshot](images/playlist.png)
![Cosmix Screenshot](images/mood.png)
![Cosmix Screenshot](images/image.png)
![Cosmix Screenshot](images/spotify.png)
---
