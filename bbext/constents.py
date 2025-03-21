from enum import StrEnum

from packaging.specifiers import SpecifierSet
from packaging.version import Version

BLENDER_PLATFORMS = [
    "windows-x64",
    "windows-arm64",
    "macos-arm64",
    "macos-x64",
    "linux-x64",
]

class BlenderPlatform(StrEnum):
    windows_x64 = 'windows-x64'
    windows_arm64 = 'windows-arm64'
    macos_arm64 = 'macos-arm64'
    macos_x64 = 'macos-x64'
    linux_x64 = 'linux-x64'

BLENDER_PYTHON_VERSIONS = {
    Version('4.2.0'): Version('3.11')
}

