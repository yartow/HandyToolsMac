    import os
import shutil

def create_folder_structure(source_folder, destination_folder, max_folder_size):
    total_size = 0
    folder_count = 1
    current_folder_size = 0
    current_destination_folder = os.path.join(destination_folder, f"Folder_{folder_count}")

    os.makedirs(current_destination_folder, exist_ok=True)

    for filename in os.listdir(source_folder):
        file_path = os.path.join(source_folder, filename)
        if os.path.isfile(file_path) and filename.endswith('.png'):
            file_size = os.path.getsize(file_path)
            total_size += file_size

            if current_folder_size + file_size > max_folder_size:
                folder_count += 1
                current_destination_folder = os.path.join(destination_folder, f"Folder_{folder_count}")
                os.makedirs(current_destination_folder, exist_ok=True)
                current_folder_size = 0

            shutil.copy(file_path, current_destination_folder)
            current_folder_size += file_size

    print(f"Total files copied: {folder_count}")
    print(f"Total size: {total_size / (1024 * 1024)} MB")

# Change these values according to your needs
source_folder = "C:/Data/XRays/Oedelem/xrays"
destination_folder = "C:/Data/XRays/Oedelem"
max_folder_size = 500 * 1024 * 1024  # 500MB in bytes

create_folder_structure(source_folder, destination_folder, max_folder_size)
