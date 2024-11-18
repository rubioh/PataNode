from PIL import Image
import random
import math

def distance(x1, y1, x2, y2):
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

def update_circle_position(center_x, center_y, max_disp):
    angle = random.uniform(0, 2*math.pi)
    displacement = random.uniform(0, max_disp)
    new_center_x = center_x + displacement * math.cos(angle)
    new_center_y = center_y + displacement * math.sin(angle)
    return new_center_x, new_center_y

# Function to generate the pixel colors
def generate_pixel_colors(time):
    num_circles = 20
    min_radius = 5
    max_radius = 20
    image_width = 1024
    image_height = 1024
    max_displacement = 5

    # List to store circle centers
    circle_centers = []

    # Generate random circle centers
    for _ in range(num_circles):
        center_x = random.randint(0, image_width - 1)
        center_y = random.randint(0, image_height - 1)
        radius = random.randint(min_radius, max_radius)
        circle_centers.append((center_x, center_y, radius))

    # Update circle positions based on time
    updated_circle_centers = []
    for center_x, center_y, radius in circle_centers:
        new_center_x, new_center_y = update_circle_position(center_x, center_y, max_displacement)
        updated_circle_centers.append((new_center_x, new_center_y, radius))

    # Initialize image data
    pixel_data = []

    # Check if the pixel is within any of the circles
    for x in range(image_width):
        row = []
        for y in range(image_height):
            is_inside_circle = False
            for center_x, center_y, radius in updated_circle_centers:
                if distance(x, y, center_x, center_y) <= radius:
                    is_inside_circle = True
                    break
            if is_inside_circle:
                row.append((255, 0, 0))  # Red
            else:
                row.append((0, 0, 0))  # Black
        pixel_data.append(row)

    return pixel_data

# Function to save the image as a BMP file
def save_image(image_data):
    width = 1024
    height = 1024
    image = Image.new("RGB", (width, height))
    pixels = image.load()

    # Fill the image with pixel colors based on the provided data
    for x in range(width):
        for y in range(height):
            pixels[x, y] = image_data[x][y]

    # Save the image as a BMP file
    image.save("output_image.bmp")

# Generate the pixel colors
pixel_data = generate_pixel_colors(0)  # You can adjust the time parameter as needed

# Save the image
save_image(pixel_data)
