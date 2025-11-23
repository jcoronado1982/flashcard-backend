import requests
import json

url = "http://localhost:8000/api/synthesize-speech"

payload = {
  "category": "adjectives",
  "deck": "1-basic",
  "text": "angry",
  "voice_name": "Callirrhoe", 
  "model_name": "gemini-2.5-pro-tts", # Using the model from the screenshot
  "tone": "Read this like a news anchor",
  "verb_name": "angry"
}

try:
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        audio_url = data.get("audio_url")
        print(f"Status Code: {response.status_code}")
        print(f"Audio URL: {audio_url}")
        
        if audio_url.startswith("http"):
            print("✅ SUCCESS: Audio URL is an absolute URL.")
            
            # Now try to download the audio from the proxy
            # proxy_full_url is just audio_url now
            proxy_full_url = audio_url
            print(f"Testing Proxy Download: {proxy_full_url}")
            
            audio_response = requests.get(proxy_full_url)
            if audio_response.status_code == 200:
                print(f"✅ SUCCESS: Audio downloaded successfully. Size: {len(audio_response.content)} bytes")
            else:
                print(f"❌ FAILURE: Could not download audio. Status: {audio_response.status_code}")
                print(f"Response: {audio_response.text}")
        else:
            print("❌ FAILURE: Audio URL is NOT a proxy URL.")
    else:
        print(f"❌ Request failed with status code: {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"❌ Error: {e}")
