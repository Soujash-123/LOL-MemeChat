import requests

def fetch_memes(keywords, number, media_type):
    api_key = "dce9e0817bc145a8810a1b1d84d2d51b"
    url = f"https://api.humorapi.com/memes/search?number={number}&keywords={keywords}&media={media_type}&api-key={api_key}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        
        if "memes" in data:
            filtered_memes = [meme for meme in data["memes"] if meme.get("type") == media_type]
            return filtered_memes
        else:
            return "No memes found."
    else:
        return f"Error: {response.status_code}, {response.text}"

# Example usage
if __name__ == "__main__":
    keywords = input("Enter keywords: ")
    number = input("Enter number of memes: ")
    media_type = input("Enter media type (e.g., video/mp4): ")
    
    memes = fetch_memes(keywords, number, media_type)
    print(memes)
