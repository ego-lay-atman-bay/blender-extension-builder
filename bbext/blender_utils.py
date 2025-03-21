import logging
import os
import shutil
import subprocess
from textwrap import dedent

import toml
from packaging.version import Version

from .constents import BLENDER_PYTHON_VERSIONS

BLENDER_BINARY = shutil.which('blender')



def check_blender_binary(binary: str | None = BLENDER_BINARY):
    if binary is None or not os.path.isfile(binary):
        raise FileNotFoundError('Blender could not be found. Make sure to add it to the PATH.')

    return True


def match_blender_python_version(version: Version | str):
    if not isinstance(version, Version):
        version = Version(version)

    compatible_versions = [blender_version for blender_version in BLENDER_PYTHON_VERSIONS if blender_version <= version]

    if len(compatible_versions) > 0:
        max_version = max(compatible_versions)
        return str(BLENDER_PYTHON_VERSIONS[max_version])
    else:
        return '3.11'

def get_blender_python_version(blender_binary: str = BLENDER_BINARY):
    result = subprocess.run(
        [
            blender_binary, '--quiet', '--background', '--factory-startup',
            '--python-expr', dedent("""\
                from sys import version_info
                print(f'{version_info.major}.{version_info.minor}')
            """)
        ],
        capture_output = True,
        text = True,
    )
    return result.stdout.strip()


def build_extension(
    blender_manifest: dict,
    src: str = './',
    dest: str = 'dist',
    output_filepath: str = '{id}-{version}.zip',
    split_platforms: bool = False,
    *,
    blender_binary: str = BLENDER_BINARY,
):
    full_path = os.path.join(dest, output_filepath.format(**blender_manifest))

    os.makedirs(os.path.dirname(full_path), exist_ok = True)

    command = [
        blender_binary, '--command', 'extension', 'build',
        '--source-dir', src,
        '--output-filepath', full_path,
    ]

    build_options = ['valid-tags', 'split-platforms', 'verbose']

    build: dict = blender_manifest.get('build', {})

    for build_option in build_options:
        if build.get(build_option) is not None:
            command.extend([f'--{build_option}', build[build_option]])

    subprocess.run(command)

    if split_platforms:
        command.append('--split-platforms')
        subprocess.run(command)


def disable_extension(
    module: str,
    repo: str = 'user_default',
    *,
    blender_binary: str = BLENDER_BINARY,
):
    script = dedent("""\
            import logging

            def setup_logger(level = logging.INFO):
                if isinstance(level, str):
                    level = logging._nameToLevel.get(level.upper(), logging.INFO)
                
                logging.basicConfig(
                    level = level,
                    format = '[%(levelname)s] %(message)s',
                )
                logging.captureWarnings(True)



            import bpy
            import sys
            args = sys.argv
            if '--' in args:
            args = args[args.index('--')+1:]
            module = args[0]
            repo = args[1]
            full_name = f'bl_ext.{repo}.{module}'
            setup_logger(args[2])

            try:
            logging.info(f'Disabling extension {full_name}')
            bpy.ops.preferences.addon_disable(module=full_name)
            logging.info(f'Successfully disabled {full_name}')
            except:
            logging.info(f'extension {full_name} could either not be found or is already disabled')
            """)

    command = [
        blender_binary, '--quiet', '--background',
        '--python-expr', script,
        '--', module, repo, logging._levelToName[logging.root.getEffectiveLevel()],
    ]

    subprocess.run(command)


def install_extension(
    extension_path: str,
    manifest_path: str,
    repo: str = 'user_default',
    enable: bool = False,
    no_prefs: bool = False,
    *,
    blender_binary: str = BLENDER_BINARY,
):
    with open(manifest_path, 'r') as file:
        manifest = toml.load(file)

    disable_extension(
        manifest.get('id'),
        repo = repo,
    )

    command = [
        blender_binary, '--command', 'extension', 'install-file',
        extension_path,
        '--repo', repo,
    ]
    if enable:
        command.append('--enable')
    if no_prefs:
        command.append('--no-prefs')

    logging.info(f'Installing {os.path.relpath(extension_path)}')
    result = subprocess.run(command)
    if result.returncode != 0:
        logging.error(f'Failed to install')
    else:
        logging.info('Successfully installed extension')
