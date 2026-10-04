## Required Setup
You will need the Pillow image library installed to run the script. Run this in your terminal: [2] 

```python
pip install Pillow
```

## Script Features

* Auto-generation: It reads the layout (like img_001.jpg and img_005.jpg), parses the zero-padding, and automatically scans files 001, 002, 003, 004, and 005.
* Resolution sizing: Scaling constraints are handled smoothly, clamping images to a max-width of 480px (small), 800px (medium), or 1200px (large) while locking the ratio.
* Fault-tolerant handling: If an intermediate sequential photo is missing, the code outputs a minor warning and advances cleanly rather than crashing out.

## CLI Command Options## 1. Basic Generation (Uses Medium Resolution default)

```bash
python create_gif.py -f img_001.jpg img_005.jpg
```

## 2. Specifying a Small Resolution

```bash
python create_gif.py -f img_001.jpg img_005.jpg -s small
```

## 3. Custom Output Name and Custom Timing (e.g., 500ms delay per frame)

```bash
python create_gif.py -f img_001.jpg img_005.jpg -s large -d 500 -o holiday_animation.gif
```


[1] [https://cloudinary.com](https://cloudinary.com/guides/image-effects/python-image-analysis)
[2] [https://www.electronicsforu.com](https://www.electronicsforu.com/electronics-projects/digital-photo-frame)
[3] [https://www.vskills.in](https://www.vskills.in/certification/tutorial/create-a-gif-from-images/)
[4] [https://manus.im](https://manus.im/playbook/video-to-gif)
