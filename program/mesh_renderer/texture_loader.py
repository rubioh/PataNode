from io import BytesIO
from PIL import Image
import pygltflib
import numpy as np

def load_texture_from_gltf(gltf, gltf_image):
	bufferView = gltf.bufferViews[gltf_image.bufferView]
	buf = gltf.buffers[bufferView.buffer]
	data = gltf.get_data_from_buffer_uri(buf.uri)
	index = bufferView.byteOffset
	buf = data[index:index+bufferView.byteLength]
	image_data = BytesIO(buf)
	#todo check if conversion
	image = Image.open(image_data).convert("RGB")
	#image_data = bytes(image_data)
	return (image.width, image.height, image.tobytes() )