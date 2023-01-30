import requests
from tests.config import API_URL

def test_get_shops():
    response = requests.get(API_URL)
    assert response.status_code == 400
