__version__ = '1.6.1'
__author__ = 'ego-lay-atman-bay'

import argparse
import glob
import logging
import os
import pathlib
import re
import shutil
import sys
import time
from textwrap import dedent
import colorama
import colorama

import toml

from .blender_utils import (build_extension, check_blender_binary,
                            install_extension, match_blender_python_version, get_blender_python_version)
from .constents import BLENDER_PLATFORMS
from .package_management import download_packages


def gather_dependencies(
    blender_manifest: dict,
    wheel_dir: str,
    build: str,
    ensure_cp311: bool | None = None,
    all_wheels: bool = False,
    python_version: str = '3.11',
):

    if os.path.exists(os.path.join(build, wheel_dir)):
        shutil.rmtree(os.path.join(build, wheel_dir), ignore_errors = True)
    
    wheels = blender_manifest.get('wheels', [])
    if not isinstance(wheels, list):
        wheels = []
    
    platforms = blender_manifest.get('platforms', BLENDER_PLATFORMS.copy())
    
    used_platforms = platforms.copy()
    
    dir = os.path.join(build, wheel_dir)
    if 'dependencies' in blender_manifest:
        dependencies = blender_manifest['dependencies']
        downloaded_wheels, used_platforms = download_packages(
            dependencies,
            dir,
            no_deps = False,
            all_wheels = all_wheels,
            python_version = python_version,
            platforms = platforms,
        )
        wheels.extend(os.path.relpath(wheel, build).replace('\\', '/') for wheel in downloaded_wheels)

    if len(used_platforms) == 0:
        logging.warning('Could not find any compatible dependencies')

    if ensure_cp311 is None:
        ensure_cp311 = blender_manifest.get('ensure-cp311', False)

    if ensure_cp311:
        for wheel in glob.glob(
            '*.whl',
            root_dir = dir,
        ):
            source = wheel
            dest = re.sub('cp\d+', 'cp311', wheel)

            if source in wheels:
                wheels[wheels.index(source)] = dest
            
            os.rename(
                os.path.join(dir, source),
                os.path.join(dir, dest),
            )
    
    wheels.extend([os.path.join(wheel_dir, wheel) for wheel in glob.glob('*.whl', root_dir = os.path.join(build, wheel_dir))])

    for i, wheel in enumerate(wheels):
        wheels[i] = os.path.join('./', pathlib.Path(wheel).as_posix())

    wheels = list(dict.fromkeys(wheels))

    blender_manifest['wheels'] = wheels
    blender_manifest['platforms'] = used_platforms
    
    return blender_manifest

def build(
    manifest_path: str,
    dist: str | None = None,
    output_filepath: str | None = None,
    ensure_cp311: bool = False,
    all_wheels: bool = False,
    split_platforms: bool = False,
    python_version: str | None = '3.11',
) -> str:
    """Build blender extension

    Args:
        manifest (str): Path to manifest.
        dist (str | None, optional): Path to dist folder. Defaults to `None`.
        output_filepath (str | None, optional): Output filename formatted with values from `blender_manifest`. Defaults to `None`.
        ensure_cp311 (bool, optional): Ensure cp311 for compatibility. Defaults to `False`.

    Raises:
        FileNotFoundError: Could not find blender manifest.

    Returns:
        str: Path to build extension.
    """
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f'could not find "{manifest_path}"')
    
    with open(manifest_path, 'r') as path:
        blender_manifest = toml.load(path)
    
    if dist is None:
        dist = blender_manifest.get('build', {}).get('dist', './dist')
    
    if output_filepath is None:
        output_filepath = blender_manifest.get('build', {}).get('output-filepath', '{id}-{version}.zip')
    
    if python_version is None:
        blender_version_min = blender_manifest.get('blender_version_min', '4.2.0')
        
        python_version = match_blender_python_version(blender_version_min)
    
    manifest_dir = os.path.dirname(os.path.abspath(manifest_path))
    
    build = os.path.abspath(os.path.join(manifest_dir, blender_manifest.get('build', {}).get('build', './build')))
    src = os.path.abspath(os.path.join(manifest_dir, blender_manifest.get('build', {}).get('source', './')))
    ignore = blender_manifest.get('build', {}).get('paths_exclude_pattern', [])
    include = blender_manifest.get('build', {}).get('paths', [])
    wheel_path = blender_manifest.get('wheel-path', './wheels')
    
    if os.path.exists(build):
        if os.path.samefile(build, manifest_dir) or os.path.samefile(build, src):
            raise FileExistsError('Build directory cannot be root or source')
        shutil.rmtree(build, ignore_errors = True)
    os.makedirs(build, exist_ok = True)

    shutil.copytree(
        src = src,
        dst = build,
        ignore = shutil.ignore_patterns(*ignore),
        dirs_exist_ok = True,
    )
    for path in include:
        path_src = os.path.join(manifest_dir, path)
        if os.path.isdir(path_src):
            os.makedirs(os.path.join(build, path), exist_ok = True)
            shutil.copytree(
                src = path_src,
                dst = os.path.join(build, path),
                ignore = shutil.ignore_patterns(*ignore),
                dirs_exist_ok = True,
            )
        elif os.path.isfile(path_src):
            os.makedirs(os.path.join(build, os.path.dirname(path)), exist_ok = True)
            shutil.copy(
                src = path_src,
                dst = os.path.join(build, path),
            )
    
    if split_platforms:
        platforms = blender_manifest.get('platforms')
        if platforms is None:
            platforms = ["windows-x64", "windows-arm64", "macos-arm64", "macos-x64" , "linux-x64"]
        
        blender_manifest['platforms'] = platforms
    
    raw_dependencies = blender_manifest.get('dependencies')
    if isinstance(raw_dependencies, str):
        if os.path.isfile(os.path.join(manifest_dir, raw_dependencies)):
            with open(os.path.join(manifest_dir, raw_dependencies), 'r') as file_in:
                dependencies = file_in.readlines()
            
            blender_manifest['dependencies'] = dependencies
        else:
            raise TypeError('dependencies can only be list of dependencies or path to a dependencies.txt')
    
    gather_dependencies(
        blender_manifest,
        wheel_path,
        build,
        ensure_cp311 = ensure_cp311,
        all_wheels = all_wheels,
        python_version = python_version,
    )

    if blender_manifest.get('build', {}).get('paths') is not None and blender_manifest.get('build', {}).get('paths_exclude_pattern') is not None:
        del blender_manifest['build']['paths']
    
    with open(os.path.join(build, 'blender_manifest.toml'), 'w') as file:
        toml.dump(blender_manifest, file)
    
    output_filepath = output_filepath.format(**blender_manifest)
    
    build_extension(
        blender_manifest,
        build,
        dist,
        output_filepath,
        split_platforms = split_platforms,
    )
    
    return os.path.abspath(os.path.join(dist, output_filepath))

def merge(files: list[str]):
    raise NotImplementedError()

def setup_logger(level = logging.INFO):
    if isinstance(level, str):
        level = logging._nameToLevel.get(level.upper(), logging.INFO)
    
    logging.basicConfig(
        level = level,
        format = '[%(levelname)s] %(message)s',
    )
    logging.captureWarnings(True)
    
def main():
    colorama.just_fix_windows_console()
    
    argparser = argparse.ArgumentParser(
        description = 'Build blender extension with dependencies',
    )
    
    argparser.add_argument(
        '--verbosity', '-v',
        dest = 'log_level',
        help = f'log level {{{", ".join(logging._nameToLevel.keys())}}}',
        default = logging.INFO,
    )
    
    argparser.add_argument(
        '-m', '--manifest',
        dest = 'manifest',
        default = 'blender_manifest.toml',
        help = 'path to blender manifest',
    )
    
    argparser.add_argument(
        '-d', '--dist',
        dest = 'dist',
        help = 'override dist folder',
    )
    
    argparser.add_argument(
        '-cp311', '--ensure-cp311',
        dest = 'ensure_cp311',
        action = 'store_true',
        help = 'Renames any instance of "cp##" in wheels to "cp311" to make blender not ignore it. You won\'t have to use this with blender 4.3.1, but is an issue in 4.3.0 and 4.2.4 LTS.',
    )
    
    argparser.add_argument(
        '-a', '--all-wheels',
        dest = 'all_wheels',
        action = 'store_true',
        help = 'Download all wheels packages for all platforms. May result in large file sizes.',
    )
    
    argparser.add_argument(
        '--split-platforms',
        dest = 'split_platforms',
        action = 'store_true',
        help = dedent("""\
            Build a separate package for each platform.
            Adding the platform as a file name suffix (before the extension).

            This can be useful to reduce the upload size of packages that bundle large       
            platform-specific modules (``*.whl`` files)."""),
    )
    argparser.add_argument(
        '--python',
        dest = 'python_version',
        help = 'Python version to use. Defaults to the python version the minimum blender version uses (most likely 3.11).',
    )
    
    install_parser = argparser.add_argument_group(
        'Install options',
        description = 'Options for installing. If --install is omitted, all of these will be ignored.'
    )
    install_parser.add_argument(
        '-I', '--install',
        dest = 'install',
        action = 'store_true',
        help = 'Install the extension.',
    )
    install_parser.add_argument(
        '-r', '--repo',
        dest = 'repo',
        help = 'The repository identifier.',
        default = 'user_default',
    )
    install_parser.add_argument(
        '-e', '--enable',
        dest = 'enable',
        action = 'store_true',
        help = 'Enable the extension after installation.',
    )
    install_parser.add_argument(
        '--no-prefs',
        dest = 'no_prefs',
        action = 'store_true',
        help = 'Treat the user-preferences as read-only, preventing updates for operations that would otherwise modify them. This means removing extensions or repositories for example, wont update the user-preferences.',
    )
    
    args = argparser.parse_args()
    
    setup_logger(args.log_level)
    
    try:
        check_blender_binary()
    except FileNotFoundError as e:
        logging.error(e)
        exit()
    
    blender_python_version = get_blender_python_version()
    python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
    
    if blender_python_version != python_version:
        logging.warning(f'{colorama.Fore.YELLOW}The current python version {python_version} is different from the blender python version {blender_python_version}. If you experience issues building, use the same python version as blender.{colorama.Style.RESET_ALL}')
        time.sleep(2)
    
    output = build(
        args.manifest,
        args.dist,
        ensure_cp311 = args.ensure_cp311,
        all_wheels = args.all_wheels,
        split_platforms = args.split_platforms,
        python_version = args.python_version,
    )

    if args.install:
        install_extension(
            output,
            manifest_path = args.manifest,
            repo = args.repo,
            enable = args.enable,
            no_prefs = args.no_prefs,
        )
    
if __name__ == "__main__":
    main()
