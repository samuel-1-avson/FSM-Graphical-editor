import os
from PIL import Image, ImageDraw

# Define the base path for icons relative to this script
# Assuming this script is in bsm_designer_project
icons_dir = os.path.join("dependencies", "icons")

# Create directories if they don't exist
os.makedirs(icons_dir, exist_ok=True)

# Create check.png
check_png_path = os.path.join(icons_dir, "check.png")
if not os.path.exists(check_png_path):
    try:
        img_check = Image.new('RGBA', (16, 16), (0, 0, 0, 0)) # Transparent background
        draw_check = ImageDraw.Draw(img_check)
        # Draw a simple green checkmark (like a V)
        draw_check.line([(4, 8), (7, 11), (12, 5)], fill=(0, 180, 0, 255), width=2)
        img_check.save(check_png_path)
        print(f"Created dummy icon: {check_png_path}")
    except Exception as e:
        print(f"Error creating {check_png_path}: {e}")
else:
    print(f"Icon already exists: {check_png_path}")


# Create arrow_down.png
arrow_down_png_path = os.path.join(icons_dir, "arrow_down.png")
if not os.path.exists(arrow_down_png_path):
    try:
        img_arrow = Image.new('RGBA', (12, 12), (0,0,0,0)) # Transparent background
        draw_arrow = ImageDraw.Draw(img_arrow)
        # Draw a simple grey down arrow (triangle)
        draw_arrow.polygon([(2,3), (10,3), (6,9)], fill=(100,100,100,255))
        img_arrow.save(arrow_down_png_path)
        print(f"Created dummy icon: {arrow_down_png_path}")
    except Exception as e:
        print(f"Error creating {arrow_down_png_path}: {e}")
else:
    print(f"Icon already exists: {arrow_down_png_path}")

print("Icon generation script finished.")--- START OF FILE bsm_designer_project/debounce_template.json ---

{
    "name": "Debounce Logic",
    "description": "A simple debounce pattern for an input signal.",
    "icon_resource": ":/icons/debounce_template.png",
    "states": [
        {
            "name": "Unstable",
            "x": 0, "y": 0, "width": 120, "height": 60,
            "description": "Input is currently unstable or bouncing."
        },
        {
            "name": "Waiting",
            "x": 200, "y": 0, "width": 120, "height": 60,
            "entry_action": "start_debounce_timer()"
        },
        {
            "name": "Stable",
            "x": 400, "y": 0, "width": 120, "height": 60,
            "description": "Input is considered stable."
        }
    ],
    "transitions": [
        {
            "source": "Unstable", "target": "Waiting",
            "event": "input_change"
        },
        {
            "source": "Waiting", "target": "Stable",
            "event": "debounce_timer_expired"
        },
        {
            "source": "Waiting", "target": "Unstable",
            "event": "input_change_while_waiting", 
            "control_offset_y": 40 
        },
        {
            "source": "Stable", "target": "Unstable",
            "event": "input_goes_unstable_again",
            "control_offset_y": -40 }
    ],
    "comments": [
        {
            "text": "Debounce timer should be set appropriately.",
            "x": 200, "y": 100, "width": 180
        }
    ]