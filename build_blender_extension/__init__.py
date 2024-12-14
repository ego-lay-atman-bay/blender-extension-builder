__version__ = '1.0.1'
__author__ = 'ego-lay-atman-bay'

import subprocess
import toml
import os
import glob
import sys
import argparse
import shutil

PYTHON_BINARY = shutil.which('blender')

def build_wheel(dep: str, dest: str = 'wheels'):
    subprocess.run(['pip', 'wheel', dep, '-w', dest])

def build_extension(src: str = './', dest: str = 'dist'):
    os.makedirs(dest, exist_ok = True)
    
    subprocess.run([
        PYTHON_BINARY, '--command', 'extension', 'build',
        '--source-dir', src,
        '--output-dir', dest,
    ])

def gather_dependencies(blender_manifest: dict, wheel_dir: str, build: str):
    if os.path.exists(os.path.join(build, wheel_dir)):
        shutil.rmtree(os.path.join(build, wheel_dir), ignore_errors = True)
    
    wheels = blender_manifest.get('wheels', [])
    if not isinstance(wheels, list):
        wheels = []
    
    if 'dependencies' in blender_manifest:
        for dep in blender_manifest['dependencies']:
            build_wheel(dep, os.path.join(build, wheel_dir))

    wheels.extend([os.path.join(wheel_dir, wheel).replace('\\', '/') for wheel in glob.glob('*.whl', root_dir = os.path.join(build, wheel_dir))])
    
    blender_manifest['wheels'] = wheels
    print('wheels', wheels)
    
    return blender_manifest

def build(
    manifest: str,
    dist: str | None,
):
    if not os.path.isfile(manifest):
        raise FileNotFoundError(f'could not find "{manifest}"')
    
    with open(manifest, 'r') as path:
        blender_manifest = toml.load(path)
    
    if dist is None:
        dist = blender_manifest.get('build', {}).get('dist', './dist')
    
    build = blender_manifest.get('build', {}).get('build', './build')
    src = blender_manifest.get('build', {}).get('source', './')
    ignore = blender_manifest.get('build', {}).get('paths_exclude_pattern', [])
    include = blender_manifest.get('build', {}).get('paths_include', [])
    wheel_path = blender_manifest.get('wheel-path', './wheels')
    
    if os.path.exists(build):
        shutil.rmtree(build, ignore_errors = True)
    os.makedirs(build, exist_ok = True)

    shutil.copytree(
        src = src,
        dst = build,
        ignore = shutil.ignore_patterns(*ignore),
        dirs_exist_ok = True,
    )
    for path in include:
        if os.path.isdir(path):
            os.makedirs(os.path.join(build, path), exist_ok = True)
            shutil.copytree(
                src = path,
                dst = os.path.join(build, path),
                ignore = shutil.ignore_patterns(*ignore),
                dirs_exist_ok = True,
            )
        elif os.path.isfile(path):
            os.makedirs(os.path.join(build, os.path.dirname(path)), exist_ok = True)
            shutil.copy(
                src = path,
                dst = os.path.join(build, path),
            )
    
    
    
    gather_dependencies(blender_manifest, wheel_path, build)
    with open(os.path.join(build, 'blender_manifest.toml'), 'w') as file:
        toml.dump(blender_manifest, file)
    
    build_extension(build, dist)
    
def main():
    argparser = argparse.ArgumentParser(
        description = 'Build blender add-on with dependencies',
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
    
    args = argparser.parse_args()
    
    build(args.manifest, args.dist)
    
if __name__ == "__main__":
    main()
