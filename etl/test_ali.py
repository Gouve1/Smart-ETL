import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def test_exact_curl_reproduction():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY não encontrada no .env!")
        return

    url = "https://aliexpress-business-api.p.rapidapi.com/textsearch.php"
    
    # Todos os headers capturados do cURL real
    headers = {
        "accept": "application/json",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "csrf-token": "99X7jhQJ-tcBleFhLQzhw3wrGnaRdYCQNJRc",
        "origin": "https://rapidapi.com",
        "rapid-client": "hub-service",
        "referer": "https://rapidapi.com/",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "x-entity-id": "12194946",
        "x-rapidapi-host": "aliexpress-business-api.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-ua": "RapidAPI-Playground"
    }

    params = {
        "keyWord": "mechanical keyboard",
        "pageSize": "20",
        "pageIndex": "1",
        "country": "DE",
        "currency": "EUR",
        "lang": "en",
        "filter": "orders",
        "sortBy": "asc"
    }

    print("🚀 Testando com a réplica exata do cURL da interface...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=12)
        print(f"HTTP Status Code: {response.status_code}")
        
        data = response.json()
        print("\n--- RESPOSTA DA API ---")
        print(json.dumps(data, indent=2)[:800])
        print("-----------------------\n")

    except Exception as e:
        print(f"❌ Erro na requisição: {e}")

if __name__ == "__main__":
    test_exact_curl_reproduction()