# blender-extension-builder
A builder for blender extensions.

Blender allows you to add dependencies via packaging wheels with the extension, however you have to manually grab the wheels and put the filenames in the `blender_manifest.toml` file. This can be cumbersome, especially with many dependencies, and dependencies of dependencies that you don't control. This project aims to aid in that, and make it all a lot easier.

# Installation

Install via pip

```
pip install blender-extension-builder
```

You also need Blender available on the PATH in order to build the extension.

# Usage

You can use the command

```
build-blender-extension -h
```

Or

```
python -m build_blender_extension -h
```

## Setting up `blender_manifest.toml`

Since this aims to make managing dependencies easier, there are a couple things added to the `blender_manifest.toml` file. The file will be structured like any `blender_manifest.toml` file, just with a few new options.

```toml
schema_version = "1.0.0"
id = "my_example_extension"
version = "1.0.0"
name = "My Example Extension"
tagline = "This is another extension"
maintainer = "Developer name <email@address.com>"
type = "add-on"
blender_version_min = "4.2.0"
license = [
  "SPDX:GPL-3.0-or-later",
]

# Place dependencies here. They can be in any format that pip supports.
dependencies = [
    'numpy'
]
# Folder to store the wheels in the addon.
wheel-path = './wheels'

# If you would like to manually specify the wheels, you still can.
# This If you also specify dependencies, those will be appended into this.
wheels = [
  './wheels/pillow-10.3.0-cp311-cp311-win_amd64.whl',
]

[build]
# Some optional extra options were added to this table

# Folder containing the source code of the extension. Defaults to the current directory
source = './src'
# Folder for where the extension will be stored with all the files (to build the extension). Defaults to ./build
build = './build'
# Output folder for the built addon in the .zip file.
dist = './dist'

# This contains a list of files or folders to keep in the built extension.
paths_include = [
  'LICENSE',
  'README.md',
]
```

All you have to do is now run

```
build-blender-extension -m blender_manifest.toml
```

Note: if you don't specify any arguments, it will try to use `blender_manifest.toml`.
