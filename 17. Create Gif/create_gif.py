import os
import re
import argparse
from PIL import Image

def get_file_list(start_file, end_file):
    # Match layout: prefix + optional separation layer + digits + extension
    pattern = r"^(.*?)(_?)(\d+)(\.[^.]+)$"
    match_start = re.match(pattern, start_file)
    match_end = re.match(pattern, end_file)
    
    if not match_start or not match_end:
        print("[-] Error: Filenames must end with a number (e.g., img_001.jpg)")
        return []
        
    prefix_start = match_start.group(1) + match_start.group(2)
    num_str_start = match_start.group(3)
    ext_start = match_start.group(4)
    
    prefix_end = match_end.group(1) + match_end.group(2)
    num_str_end = match_end.group(3)
    ext_end = match_end.group(4)
    
    if prefix_start != prefix_end or ext_start.lower() != ext_end.lower():
        print("[-] Error: Start and end files must have the same name format and extension.")
        return []
        
    start_num = int(num_str_start)
    end_num = int(num_str_end)
    padding = len(num_str_start)
    
    if start_num > end_num:
        print("[-] Error: Start number must be smaller than or equal to the end number.")
        return []
        
    return [f"{prefix_start}{str(i).zfill(padding)}{ext_start}" for i in range(start_num, end_num + 1)]

def resize_image(img, size_preset):
    # Presets mapping to maximum width dimensions while keeping original aspect ratio
    size_map = {"small": 480, "medium": 800, "large": 1200}
    max_width = size_map.get(size_preset.lower(), 800)
    
    w, h = img.size
    if w <= max_width:
        return img  # Keep native size if it is already smaller than preset
        
    ratio = max_width / float(w)
    new_h = int(float(h) * float(ratio))
    return img.resize((max_width, new_h), Image.Resampling.LANCZOS)

def main():
    parser = argparse.ArgumentParser(description="Generate an animated GIF from a range of sequential JPG files.")
    parser.add_argument("-f", "--files", nargs=2, required=True, metavar=("START", "END"),
                        help="The first and last file names in the sequence (e.g., img_001.jpg img_005.jpg)")
    parser.add_argument("-s", "--size", choices=["small", "medium", "large"], default="medium",
                        help="Output resolution width preset (small: 480px, medium: 800px, large: 1200px)")
    parser.add_argument("-d", "--duration", type=int, default=200,
                        help="Duration for each frame in milliseconds (default: 200)")
    parser.add_argument("-o", "--output", default="output.gif",
                        help="Output filename for the GIF (default: output.gif)")
                        
    args = parser.parse_args()
    
    expected_files = get_file_list(args.files[0], args.files[1])
    if not expected_files:
        return

    frames = []
    print("[*] Processing files...")
    
    for filename in expected_files:
        if not os.path.exists(filename):
            print(f"[-] Warning: File '{filename}' not found. Skipping.")
            continue
            
        try:
            with Image.open(filename) as img:
                img_rgb = img.convert("RGB")
                resized_img = resize_image(img_rgb, args.size)
                frames.append(resized_img.copy())
                print(f"[+] Added and resized: {filename}")
        except Exception as e:
            print(f"[-] Failed to process {filename}: {e}")

    if not frames:
        print("[-] Error: No valid image files were found. GIF creation aborted.")
        return

    print(f"[*] Saving GIF to {args.output}...")
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=args.duration,
        loop=0
    )
    print(f"[+] Success! GIF saved as '{args.output}'.")

if __name__ == '__main__':
    main()
