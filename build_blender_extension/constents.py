from enum import StrEnum

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
