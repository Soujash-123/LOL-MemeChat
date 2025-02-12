import requests
import random

# Define keyword-based mapping to templates
template_mapping = {
    "aliens": "aag",
    "trap": "ackbar",
    "afraid": "afraid",
    "winking": "agnes",
    "sweet brown": "aint-got-time",
    "awkward": "ams",
    "ants": "ants",
    "redneck": "apcr",
    "always has been": "astronaut",
    "then i said": "atis",
    "life finds a way": "away",
    "awesome": "awesome",
    "penguin": "awesome-awkward",
    "bad": "bad",
    "milk": "badchoice",
    "balloon": "balloon",
    "butthurt": "bd",
    "men in black": "because",
    "bender": "bender",
    "honest work": "bihw",
    "bilbo": "bilbo",
    "insanity wolf": "biw",
    "bad luck": "blb",
    "boat": "boat",
    "bongo": "bongo",
    "both": "both",
    "box": "box",
    "shark": "bs",
    "everywhere": "buzz",
    "cake": "cake",
    "captain": "captain",
    "elevator": "captain-america",
    "confession": "cb",
    "communist": "cbb",
    "comic book": "cbg",
    "center for ants": "center",
    "hindsight": "ch",
    "chopper": "chair",
    "cheems": "cheems",
    "chosen": "chosen",
    "change my mind": "cmm",
    "crazy pills": "crazypills",
    "grind my gears": "gears",
    "doge": "doge",
    "drake": "drake",
    "distracted boyfriend": "db",
    "elon": "musk",
    "matrix": "morpheus",
    "keanu": "keanu",
    "joke": "joker",
    "padme": "right",
    "salt bae": "saltbae",
    "stonks": "stonks",
    "spiderman": "spiderman",
    "trump": "trump",
    "knuckles": "ugandanknuck",
    "y u no": "yuno",
    "all your base": "zero-wing"
}

def choose_template(text):
    """Choose a meme template based on keywords."""
    for keyword, template in template_mapping.items():
        if keyword in text.lower():
            return template
    return random.choice(list(template_mapping.values()))  # Default to a random template

def generate_meme(top_text, bottom_text):
    """Generate a meme using the Memegen API."""
    template_id = choose_template(top_text + " " + bottom_text)
    
    # Format text properly for URL
    top_text = top_text.replace(" ", "_")
    bottom_text = bottom_text.replace(" ", "_")

    # Generate the meme URL
    meme_url = f"https://api.memegen.link/images/{template_id}/{top_text}/{bottom_text}.png"
    
    return meme_url

if __name__ == "__main__":
    # Get user input
    text = input("Enter your meme text: ").strip()
    
    # Split into top and bottom text
    if " " in text:
        words = text.split()
        mid = len(words) // 2
        top_text, bottom_text = " ".join(words[:mid]), " ".join(words[mid:])
    else:
        top_text, bottom_text = text, ""

    # Generate meme
    meme_url = generate_meme(top_text, bottom_text)
    print(f"Generated Meme URL: {meme_url}")
