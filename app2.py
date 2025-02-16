from flask import Flask, request, render_template
import requests

app = Flask(__name__)

BASE_URL = "https://discoveryprovider.audius.co"

@app.route('/music-feed', methods=['GET'])
def search_songs():
    query = request.args.get('query', 'trending')

    if query.lower() == "trending":
        url = f"{BASE_URL}/v1/tracks/trending"
    else:
        url = f"{BASE_URL}/v1/tracks/search?query={query}"

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        results = []

        for track in data.get("data", []):
            track_id = track.get("id")
            stream_url = f"{BASE_URL}/v1/tracks/{track_id}/stream"

            results.append({
                "id": track_id,
                "title": track["title"],
                "album": track.get("album", "N/A"),  # Audius API doesn't have albums
                "artist": track["user"]["name"],
                "genre": track.get("genre", "Unknown"),
                "link": track.get("permalink", "#"),
                "image": track.get("artwork", {}).get("150x150", ""),  # Fetch artwork
                "stream_url": stream_url
            })

        return render_template('music-feed.html', songs=results, query=query)
    else:
        return render_template('music-feed.html', error="Failed to fetch data", songs=[], query=query)

if __name__ == "__main__":
    app.run(debug=True)  # Runs the Flask app locally