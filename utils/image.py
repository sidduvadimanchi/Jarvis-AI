import asyncio
import requests
import os
from random import randint
from PIL import Image
from time import sleep
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("HuggingFaceAPIKey")

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

NUM_IMAGES = 3


def open_images(prompt):
    prompt = prompt.replace(" ", "_")

    for i in range(1, NUM_IMAGES + 1):

        path = f"Data/{prompt}{i}.jpg"

        try:
            img = Image.open(path)
            print("Opening:", path)
            img.show()
            sleep(1)

        except:
            print("Unable to open", path)


async def generate_image(prompt):

    payload = {
        "inputs": prompt
    }

    response = await asyncio.to_thread(
        requests.post,
        API_URL,
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.headers.get("content-type","").startswith("image"):
        return response.content

    else:
        print("API ERROR:", response.text)
        return None


async def generate_images(prompt):

    os.makedirs("Data", exist_ok=True)

    tasks = []

    for _ in range(NUM_IMAGES):

        task = asyncio.create_task(generate_image(prompt))
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    saved = []

    for i, img in enumerate(results, start=1):

        if img is None:
            continue

        path = f"Data/{prompt.replace(' ','_')}{i}.jpg"

        with open(path, "wb") as f:
            f.write(img)

        saved.append(path)
        print("Saved:", path)

    return saved


def GenerateImages(prompt):

    print("Generating images...")

    files = asyncio.run(generate_images(prompt))

    if files:
        open_images(prompt)
    else:
        print("No images generated.")


def main():

    while True:

        try:

            with open("Frontend/Files/ImageGeneration.data","r") as f:
                data = f.read().strip()

            prompt, status = data.split(",")

            print("Prompt:", prompt, "| Status:", status)

            if status == "True":

                GenerateImages(prompt)

                with open("Frontend/Files/ImageGeneration.data","w") as f:
                    f.write("False,False")

                break

            else:
                sleep(1)

        except Exception as e:
            print("Error:", e)
            sleep(1)


if __name__ == "__main__":
    print("ImageGeneration service started...")
    main()