from pathlib import Path
from PIL import Image


class OpenFileAndDeleteAfterClosing:
    """Context manager that opens a file and deletes the file after its closing"""

    def __init__(self, file_path, mode='r') -> None:
        self.file_path = Path(file_path)
        self.mode = mode
        self.file = open(self.file_path, self.mode)

    def __enter__(self):
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()
        self.file_path.unlink()


def is_file_exists(file_path) -> bool:
    """check if the file exists"""
    return Path(file_path).exists()


def delete_file(file_path) -> None:
    """Delete file"""
    Path(file_path).unlink()


def delete_if_exists(file_path, raise_if_exists=True) -> None:
    if Path(file_path).exists() and raise_if_exists:
        FileExistsError('A file or folder with the name already exists')
    else:
        delete_file(file_path)


def create_img(img_name: str, width, height, save=True, color_mode='RGBA', bg_color='white'):
    """Create a image that is width x height and save it if save is True"""
    img = Image.new(color_mode, (width, height), bg_color)
    if save:
        img.save(img_name)
    img.path = Path(img_name).absolute()
    return img
