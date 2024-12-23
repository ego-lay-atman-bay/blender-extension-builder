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

```shell
build-blender-extension -h
# or
bbext -h
# or
python -m build_blender_extension -h
```

You can specify the manifest file with the `-m` argument, however if you run the command with no arguments, it will assume that the blender manifest is `blender_manifest.toml`.

```shell
bbext -m blender_manifest.toml
```

If you have any dependencies that have wheels that are built for multiple platforms, then you may want to grab them all.

```shell
bbext --all-wheels
```

However it may take a while to download all the wheels, so this should only be used for distribution.

This can be used in conjunction with `--split-platforms` to generate builds for each platform.

```shell
bbext -a --split-platforms
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

# You can specify what platforms this can be used with.
platforms = ["windows-x64", "windows-arm64", "macos-arm64", "macos-x64" , "linux-x64"]
# NOTE: All wheels for all platforms will be downloaded in you specify `--all-wheels`
# no matter which platforms are specified here.
# NOTE: If `--all-wheels` is specified and the platforms are not specified, it will
# download all the platforms, and generate builds for all platforms.

# Place dependencies here. They have to be in the dependency format as specified in PEP 508.
# https://packaging.python.org/en/latest/specifications/dependency-specifiers/#dependency-specifiers
# (should be the same as in pyproject.toml files)
dependencies = [
    'numpy'
]
# dependencies can also be a path to a file. This does not follow the same rules as requirements.txt
# It instead follows the same rules as dependencies as a list, just with each line being a dependency.
# This can be used if you have some local paths you don't want sharing to the public.
dependencies = 'dependencies.txt'

# Folder to store the wheels in the addon.
wheel-path = './wheels'

# If you would like to manually specify the wheels, you still can.
# This If you also specify dependencies, those will be appended into this.
wheels = [
  './wheels/pillow-10.3.0-cp311-cp311-win_amd64.whl',
]

# Use this if blender is skipping a wheel for python version
# incompatibility (even though it's compatible)
# This can also be enabled in the commandline with `--ensure-cp311` or `-cp311`
ensure-cp311 = true

[build]
# Some optional extra options were added to this table

# Folder containing the source code of the extension. Defaults to the current directory
source = './src'
# Folder for where the extension will be stored
# with all the files (to build the extension). Defaults to ./build
build = './build'
# Output folder for the built addon in the .zip file.
dist = './dist'

# This contains a list of files or folders to keep in the built extension.
paths = [
  'LICENSE',
  'README.md',
]
```

All you have to do is now run

```
build-blender-extension -m blender_manifest.toml
```

Note: if you don't specify any arguments, it will try to use `blender_manifest.toml`.

## Installing

You can also auto install the extension after building directly with this command.

```shell
bbext --install
```

If you choose to also generate builds for all the platforms, it will install the universal build.

## Other arguments

There are many other options you can use.

```
usage: bbext [-h] [-m MANIFEST] [-d DIST] [-cp311] [-a] [--split-platforms]
             [--python PYTHON_VERSION] [-I] [-r REPO] [-e] [--no-prefs]

Build blender extension with dependencies

options:
  -h, --help            show this help message and exit
  -m MANIFEST, --manifest MANIFEST
                        path to blender manifest
  -d DIST, --dist DIST  override dist folder
  -cp311, --ensure-cp311
                        Renames any instance of "cp##" in wheels to "cp311" to make blender  
                        not ignore it. You won't have to use this with blender 4.3.1, but    
                        is an issue in 4.3.0 and 4.2.4 LTS.
  -a, --all-wheels      Download all wheels packages for all platforms. May result in large  
                        file sizes.
  --split-platforms     Build a separate package for each platform. Adding the platform as   
                        a file name suffix (before the extension). This can be useful to     
                        reduce the upload size of packages that bundle large platform-       
                        specific modules (``*.whl`` files).
  --python PYTHON_VERSION
                        Python version to use. Defaults to the python version the minimum    
                        blender version uses (most likely 3.11).

Install options:
  Options for installing. If --install is omitted, all of these will be ignored.

  -I, --install         Install the extension.
  -r REPO, --repo REPO  The repository identifier.
  -e, --enable          Enable the extension after installation.
  --no-prefs            Treat the user-preferences as read-only, preventing updates for      
                        operations that would otherwise modify them. This means removing     
                        extensions or repositories for example, wont update the user-        
                        preferences.
```
