import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import concurrent.futures
import unicodedata
import re

app = Flask(__name__)
CORS(app)

# Common headers to avoid immediate blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def normalize_name(name):
    # Remove accents and special characters
    nfkd_form = unicodedata.normalize('NFKD', name)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z0-9\s]', '', only_ascii).lower()

def generate_permutations(name):
    clean_name = normalize_name(name)
    parts = clean_name.split()
    if len(parts) < 2:
        return [clean_name]
    
    first = parts[0]
    last = parts[-1]
    
    perms = [
        f"{first}{last}",
        f"{first}.{last}",
        f"{first}_{last}",
        f"{last}{first}",
        f"{last}_{first}",
        "".join(parts),
        "_".join(parts),
        f"{first}{parts[1] if len(parts)>2 else ''}{last}"
    ]
    # Remove duplicates
    return list(set(perms))

def check_url(platform_name, url_template, username):
    url = url_template.format(username=username)
    try:
        # Timeout is short because we are scanning many
        response = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True)
        # Note: Many platforms return 200 for missing pages but show a custom 404 UI.
        # For a truly advanced tool, we'd check page content. For now, strict status code check.
        if response.status_code == 200:
            return {
                "platform": platform_name,
                "url": url,
                "username": username,
                "status": "valid"
            }
    except requests.RequestException:
        pass
    
    return {
        "platform": platform_name,
        "url": url,
        "username": username,
        "status": "invalid"
    }

# Platform configurations mapping
PLATFORMS = {
    "adult": [
        ("X (Twitter)", "https://twitter.com/{username}"),
        ("GitHub", "https://github.com/{username}"),
        ("Linktree", "https://linktr.ee/{username}"),
        ("Medium", "https://medium.com/@{username}"),
        ("Reddit", "https://www.reddit.com/user/{username}")
    ],
    "teen": [
        ("TikTok", "https://www.tiktok.com/@{username}"),
        ("Roblox", "https://www.roblox.com/user.aspx?username={username}"),
        ("Steam", "https://steamcommunity.com/id/{username}"),
        ("Twitch", "https://www.twitch.tv/{username}"),
        ("Reddit", "https://www.reddit.com/user/{username}")
    ]
}
# Instagram, Facebook, LinkedIn block automated requests heavily or require login.
# Using platforms above as they are more scrape-friendly for a simple HTTP GET.

@app.route('/api/scan', methods=['POST'])
def scan_target():
    data = request.json
    name = data.get('name')
    profile_type = data.get('type', 'adult') # 'adult' or 'teen'
    
    if not name:
        return jsonify({"error": "Nome nao fornecido"}), 400
        
    usernames = generate_permutations(name)
    platforms_to_check = PLATFORMS.get(profile_type, PLATFORMS["adult"])
    
    tasks = []
    results = []
    
    # We will test all username permutations against all platforms
    # This can be many requests, so we use ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for platform_name, url_template in platforms_to_check:
            for uname in usernames:
                tasks.append(executor.submit(check_url, platform_name, url_template, uname))
                
        # Gather results as they complete
        for future in concurrent.futures.as_completed(tasks):
            result = future.result()
            results.append(result)
            
    # Filter only valid ones
    valid_links = [r for r in results if r['status'] == 'valid']
    
    return jsonify({
        "target": name,
        "type_scanned": profile_type,
        "permutations_tested": len(usernames),
        "total_requests": len(tasks),
        "valid_links": valid_links,
        "all_results": results # sending all so frontend can show the validation progress visually
    })

if __name__ == '__main__':
    print("Mourisco Founder OSINT Engine Server starting...")
    app.run(port=5000, debug=True)
