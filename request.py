import requests

BASE_URL = "https://discoveryprovider.audius.co"

def get_trending_tracks():
    """Fetch trending tracks and return a list of (track_id, title, artist)."""
    url = f"{BASE_URL}/v1/tracks/trending"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        tracks = data.get('data', [])
        return [(track['id'], track['title'], track['user']['name']) for track in tracks]
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def get_stream_url(track_id):
    """Generate the streaming URL for a given track ID."""
    return f"{BASE_URL}/v1/tracks/{track_id}/stream"

# Fetch trending tracks and display their streaming links
trending_tracks = get_trending_tracks()

if trending_tracks:
    print("\nTrending Tracks and their Stream URLs:\n")
    for track_id, title, artist in trending_tracks[:5]:  # Display top 5 tracks
        stream_url = get_stream_url(track_id)
        print(f"🎵 {title} by {artist}")
        print(f"🔗 Stream URL: {stream_url}\n")
else:
    print("Failed to fetch trending tracks.")

