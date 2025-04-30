from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Set up the ThreadPoolExecutor for handling multiple requests concurrently
executor = ThreadPoolExecutor(max_workers=10)

# Function to fetch player info
def fetch_player_info(uid, region):
    player_info_url = f'https://as-info.onrender.com/player-info?uid={uid}&region={region}'
    response = requests.get(player_info_url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

# Function to fetch and process an image from URL
def fetch_and_process_image(image_url, size=None):
    response = requests.get(image_url)
    if response.status_code == 200:
        try:
            image = Image.open(BytesIO(response.content))
            if size:
                image = image.resize(size)
            return image
        except Exception as e:
            print(f"Error processing image: {e}")
            return None
    else:
        return None

# Route for generating outfit image
@app.route('/outfit', methods=['GET'])
def outfit_image():
    uid = request.args.get('uid')
    region = request.args.get('region')

    if not uid or not region:
        return jsonify({'error': 'Missing uid or region'}), 400

    player_data = fetch_player_info(uid, region)
    if player_data is None:
        return jsonify({'error': 'Failed to fetch player info'}), 500

    outfit_ids = player_data.get("profileInfo", {}).get("clothes", [])
    avatar_id = player_data.get("profileInfo", {}).get("avatarId")
    pet_info = player_data.get("petInfo", {})
    pet_id = pet_info.get("id")

    required_starts = ["211", "214", "211", "203", "204", "205", "203"]
    fallback_ids = ["211000000", "214000000", "208000000", "203000000", "204000000", "205000000", "212000000"]

    used_ids = set()
    outfit_images = []

    # Fetch outfit images in parallel
    def fetch_outfit_image(idx, code):
        matched = None
        for oid in outfit_ids:
            str_oid = str(oid)
            if str_oid.startswith(code) and oid not in used_ids:
                matched = oid
                used_ids.add(oid)
                break

        if matched is None:
            matched = fallback_ids[idx]

        image_url = f'https://pika-ffitmes-api.vercel.app/?item_id={matched}&key=PikaApis'
        return fetch_and_process_image(image_url, size=(150, 150))

    # Asynchronously fetch all outfit images
    for idx, code in enumerate(required_starts):
        outfit_images.append(executor.submit(fetch_outfit_image, idx, code))

    # Background image
    bg_url = 'https://iili.io/39iE4rF.jpg'
    background_image = fetch_and_process_image(bg_url)

    if not background_image:
        return jsonify({'error': 'Failed to fetch background image'}), 500

    positions = [
        {'x': 280, 'y': 20, 'height': 150, 'width': 150},
        {'x': 470, 'y': 95, 'height': 150, 'width': 150},
        {'x': 550, 'y': 280, 'height': 150, 'width': 150},
        {'x': 470, 'y': 455, 'height': 150, 'width': 150},
        {'x': 280, 'y': 535, 'height': 150, 'width': 150},
        {'x': 100, 'y': 455, 'height': 150, 'width': 150},
        {'x': 25, 'y': 280, 'height': 150, 'width': 150}
    ]

    # Process the outfit images and place them on the background
    for idx, future in enumerate(outfit_images):
        outfit_image = future.result()
        if outfit_image:
            pos = positions[idx]
            resized = outfit_image.resize((pos['width'], pos['height']))
            background_image.paste(resized, (pos['x'], pos['y']), resized.convert("RGBA"))

    # Add avatar image if available
    if avatar_id:
        avatar_url = f'https://pika-ffitmes-api.vercel.app/?item_id={avatar_id}&key=PikaApis'
        avatar_image = fetch_and_process_image(avatar_url, size=(90, 90))
        if avatar_image:
            background_image.paste(avatar_image, (315, 300), avatar_image.convert("RGBA"))

    # Add pet image if available
    if pet_id:
        pet_image_url = f'https://pika-ffitmes-api.vercel.app/?item_id={pet_id}&key=PikaApis'
        pet_image = fetch_and_process_image(pet_image_url, size=(120, 120))
        if pet_image:
            pet_position = {'x': 115, 'y': 115, 'height': 150, 'width': 150}  # Set custom position for pet
            background_image.paste(pet_image, (pet_position['x'], pet_position['y']), pet_image.convert("RGBA"))

    # Save the final image
    output_image = BytesIO()
    background_image.save(output_image, format='PNG')
    output_image.seek(0)

    return send_file(output_image, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)