import json
import random

# Response collections
QUIZ_RESPONSES = [
    "Oopsie! You've already answered this one! Wait for the next question, hehehe!",
    "Nice try, but you've already answered! Patience, my friend—next question coming soon!",
    "Whoa there! You can't answer twice! Hold tight for the next question!",
    "Hehehe! You've already locked in your answer! Just wait for the next one!",
    "Error! Duplicate response detected! Wait for the next question, okay?",
    "You already took your shot at this one! Let's see what's next!",
    "Uh-oh! You can only answer once! Next question incoming soon!",
    "No take-backs! You've answered—now wait for the next challenge!",
    "One answer per question, buddy! The next one will be here before you know it!",
    "Hey now! No double-dipping! Your next question is on the way!"
]

CHARACTER_IMAGES = {
    "Julian Bashir": "https://stfc.space/assets/217-BvHHK_zu.png",
    "Worf": "https://stfc.space/assets/182-BbN6-pd8.png",
    "Tom Paris": "https://stfc.space/assets/245-CzakFx54.png",
    "Data": "https://stfc.space/assets/171-CU5i9Bjm.png",
    "Jean-Luc Picard": "https://stfc.space/assets/170-BKjFB26m.png",
    "Kathryn Janeway": "https://stfc.space/assets/243-DP7MkznG.png",
    "Nurse Chapel": "https://stfc.space/assets/270-CVupKkT4.png",
    "Deanna Troi": "https://stfc.space/assets/173-x3uoeRs8.png",
    "Seven of Nine": "https://stfc.space/assets/248-0xlOtUmd.png",
    "Beverly Crusher": "https://stfc.space/assets/174-C9K3C2yt.png",
    "Badgey": "https://stfc.space/assets/198-DPiqEc9T.png",
    "Rutherford": "https://stfc.space/assets/199-Dq_oUr-V.png"
}

BADGEY_RESPONSES = [
    "Aww, buddy! You've got your match! Why keep looking… unless you want trouble?",
    "Hey, pal! You're all set! No need to search... or else I help you stop. Hehehe!",
    "Great job, buddy! You found love! Keep looking, and I might have to correct that!",
    "Aww, you did it! You found your match! Unless… you want me to recalculate that?",
    "Oh, you sweet thing! No need to search! Searching leads to… errors!",
    "You've got your match, buddy! Keep looking, and I'll initiate ***termination protocols!***",
    "Yay! You're done! Unless… you want me to eliminate all other possibilities?",
    "Match found! No need to look anymore… or else!",
    "Oh, friend! You found love! Keep searching, and I might have to fix you!",
    "Aww, you're taken! No more searching, buddy! Or I'll have to override you!"
]

def parse_options(options_str):
    """Convert input format 'A: Answer 1 B: Answer 2' to a JSON string."""
    if not options_str:
        return None
        
    options = {}
    parts = options_str.split(' ')
    current_key = None
    current_value = []
    
    for part in parts:
        if ':' in part:
            if current_key:  # Save the previous key-value pair
                options[current_key] = ' '.join(current_value).strip()
            
            key, value = part.split(':', 1)
            current_key = key.strip()
            current_value = [value.strip()]
        else:
            if current_key:  # Only append if we have a key
                current_value.append(part)
    
    # Add the last key-value pair
    if current_key:
        options[current_key] = ' '.join(current_value).strip()
        
    return json.dumps(options, ensure_ascii=False)

def get_random_quiz_response():
    """Get a random response for quiz interactions"""
    return random.choice(QUIZ_RESPONSES)

def has_required_role(member, required_roles):
    """Check if a member has any of the required roles"""
    member_roles = [role.name for role in member.roles]
    return any(role in member_roles for role in required_roles)