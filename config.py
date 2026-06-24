import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COVERS_DIR = os.path.join(BASE_DIR, 'covers')
os.makedirs(COVERS_DIR, exist_ok=True)
