import jwt
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import hashlib



def get_claim_from_token_http(request, claim_key):
    # Retrieve the token from the request's headers (assuming it's a Bearer token)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    # Extract the token string
    token = auth_header.split(' ')[1]

    # Decode the token
    try:
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        claim_value = decoded_token.get(claim_key)
        return claim_value
    except Exception as e:
        # Handle token decoding exceptions (e.g., expired, invalid token)
        print(f"Token decoding failed: {str(e)}")
        return None
    


def get_claim_from_token_ws(scope, claim_key):
    # Retrieve the token from the request's headers (assuming it's a Bearer token)
    query_string = scope['query_string'].decode('utf-8')
    # Manually parse the query string to get the access_token
    query_params = dict(param.split('=') for param in query_string.split('&'))
    token = query_params.get('access_token', None)

    # Decode the token
    try:
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        claim_value = decoded_token.get(claim_key)
        return claim_value
    except Exception as e:
        # Handle token decoding exceptions (e.g., expired, invalid token)
        print(f"Token decoding failed: {str(e)}")
        return None
    


def get_parameter_ws(scope, parameter_key: str):
    # Retrieve the token from the request's headers (assuming it's a Bearer token)
    query_string = scope['query_string'].decode('utf-8')
    # Manually parse the query string to get the access_token
    query_params = dict(param.split('=') for param in query_string.split('&'))
    parameter = query_params.get(parameter_key, None)
    return parameter



def scrape_url(url):
    def run(playwright):
        # Launch Chromium browser
        browser = playwright.chromium.launch(headless=True)  # Run in headless mode for automation
        page = browser.new_page()

        # Block video and media resources
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["media", "image"] else route.continue_())

        # Navigate to the target page
        page.goto(url)

        # Wait for the network to become idle (all requests complete)
        page.wait_for_load_state('networkidle')

        # Scrape the content (for example, the page's full HTML or specific content)
        content = page.inner_text('body')

        # Close the browser
        browser.close()

        return content

    with sync_playwright() as playwright:
        return run(playwright)



def generate_file_name_from_url(url, extension="txt"):
    # Parse the URL to extract the domain (netloc) and path
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace('.', '_')  # Replace '.' with '_' for safe blob name
    path = parsed_url.path.strip('/').replace('/', '_')  # Make the path blob-safe

    # # Create a hash of the entire URL
    # url_hash = hashlib.sha256(url.encode()).hexdigest()

    # Combine the domain, path, and hash for a readable unique name
    blob_name = f"{domain}_{path}.{extension}"  # Use first 8 chars of the hash

    return blob_name