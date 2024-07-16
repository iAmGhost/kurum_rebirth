import PyInstaller.__main__
from shutil import copytree

if __name__ == '__main__':
    PyInstaller.__main__.run([
        'kurumrebirth_gui.spec',
    ])
    copytree('data/assets', 'dist/data/assets')
