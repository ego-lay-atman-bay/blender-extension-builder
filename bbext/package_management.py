import logging
import os
import shutil
import subprocess
import sys
import tempfile
from functools import cmp_to_key
from typing import NamedTuple

import requests
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import Tag
from packaging.utils import BuildTag, NormalizedName, parse_wheel_filename
from packaging.version import InvalidVersion, Version

from .constents import BLENDER_PLATFORMS, BlenderPlatform


class WheelInfo(NamedTuple):
    name: NormalizedName
    version: Version
    build: BuildTag
    tag: frozenset[Tag]
    
SUPPORTED_INTERPRETERS = [
    'cp',
    'abi',
    'py',
    None,
]

class PythonTag(NamedTuple):
    name: str
    version: Version | None
    extra: str

def parse_python_tag(tag: str):
    interpreter = ''
    
    if '_' in tag:
        result = []
        for t in tag.split('_'):
            result.extend(parse_python_tag(t))
        return result
    
    if '.' in tag:
        result = []
        for t in tag.split('.'):
            result.extend(parse_python_tag(t))
        return result
    
    i = 0
    
    for i, l in enumerate(tag):
        if l.isnumeric():
            break
        interpreter += l
    
    extra = ''
    
    if interpreter == tag:
        version = None
    else:
        major = tag[i]
        rest = tag[i+1:]

        version_name = major
        if rest:
            if rest[0].isnumeric():
                version_name += '.'
            version_name += rest
        
        try:
            version = Version(version_name)
        except InvalidVersion:
            extra = version_name.lstrip('0123456789.')
            if len(extra) > 0:
                version_name = version_name[:-len(extra)]
                version = Version(version_name)
            else:
                version = None
    
    if interpreter == 'none':
        interpreter = None
    
    return [PythonTag(interpreter, version, extra)]


def download_wheels(
    packages: str | list[str],
    output_folder: str = './',
    no_deps: bool = False,
    platforms: list[str] | None = None,
    abis: list[str] | None = None,
    python_version: str | None = '3.11',
):
    result = []
    
    command = [sys.executable, '-m', 'pip', '--isolated', '--disable-pip-version-check']
    
    download_method = 'download'
    
    if isinstance(packages, str):
        packages = [packages]
    
    for i, package in enumerate(packages):
        package = Requirement(package)
        if package.url:
            packages[i] = package.url
            download_method = 'wheel'
    
    with tempfile.TemporaryDirectory() as tempdir:
        if download_method == 'wheel':
            command.extend(['wheel'])
            
            if no_deps:
                command.append('--no-deps')

            command.extend(['-w', tempdir])
        else:
            command.extend(['download', '--dest', tempdir, '--only-binary', ':all:'])
            if python_version is not None:
                command.extend(['--python-version', python_version])
            if platforms is not None:
                for platform in platforms:
                    command.extend(['--platform', platform])
            if abis is not None:
                for abi in abis:
                    command.extend(['--abi', abi])
            
        command.extend(packages)
            
        log_level = logging.root.getEffectiveLevel()

        if log_level > logging.INFO:
            for level in [logging.WARNING, logging.ERROR, logging.CRITICAL]:
                if log_level > level:
                    command.append('-q')
        
        os.makedirs(output_folder, exist_ok = True)
    
        subprocess.run(
            command,
            check = True,
        )
        
        wheels = os.listdir(tempdir)

        for wheel in wheels:
            if os.path.exists(os.path.join(output_folder, wheel)):
                os.remove(os.path.join(output_folder, wheel))
            
            try:
                os.rename(
                    os.path.join(tempdir, wheel),
                    os.path.join(output_folder, wheel),
                )
                result.append(os.path.join(output_folder, wheel))
            except FileExistsError:
                logging.debug(f'{os.path.join(output_folder, wheel)} already exists')
    
    return result

def download_url(
    url: str,
):
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def get_package_json(
    package: str,
    *,
    index_url: str = 'https://pypi.org/pypi',
):
    if (not index_url.endswith('/')) or (not index_url.endswith('\\')):
        index_url += '/'
    result = requests.get(f'{index_url}{package}/json')
    if result.status_code != 200:
        return {}
    return result.json()

def get_dependencies(packages: list[str]):
    pipgrip = shutil.which('pipgrip')
    if pipgrip is None:
        e = FileNotFoundError("Make sure pipgrip is installed.")
        e.add_note("pip install pipgrip")
        raise e
    
    result = subprocess.run([pipgrip, *packages], capture_output = True, text = True)
    result.check_returncode()
    return result.stdout.splitlines()

def get_wheel_info(
    requirement: Requirement | str,
    python_version: str = '3.11',
):
    if not isinstance(requirement, Requirement):
        requirement = Requirement(requirement)

    pypi_info = get_package_json(requirement.name)

    python_version_obj = Version(python_version)
    
    versions = sorted([Version(version) for version in pypi_info['releases'].keys()], reverse = True)
    version = next(filter(lambda v: v in requirement.specifier, versions))
    
    version_info = pypi_info['releases'][str(version)]

    available_files = []
    
    for file_info in version_info:
        if file_info.get('packagetype') != 'bdist_wheel':
            continue
        
        if file_info['requires_python'] and python_version not in SpecifierSet(file_info['requires_python']):
            continue
        
        parsed_filename = WheelInfo(*parse_wheel_filename(file_info['filename']))

        info: dict[str, set | list | str | dict] = {
            'name': requirement.name,
            'abi': [],
            'interpreter': [],
            'platform': set(),
            'filename': file_info['filename'],
            'url': file_info['url'],
            'info': file_info,
        }
        
        compatible = True
        
        for tag in parsed_filename.tag:
            if tag.platform:
                interpreter_tags = parse_python_tag(tag.interpreter)
                abi_tags = parse_python_tag(tag.abi)
                
                compatible = False
                
                for interpreter in interpreter_tags:
                    if interpreter.version is None or (interpreter.version <= python_version_obj and interpreter.version.major == python_version_obj.major):
                        if interpreter.name in SUPPORTED_INTERPRETERS:
                            compatible = True
                            break
                
                for abi in abi_tags:
                    if abi.version is None or (abi.version <= python_version_obj and abi.version.major == python_version_obj.major):
                        if abi.name in SUPPORTED_INTERPRETERS:
                            compatible = True
                            break
                
                if not compatible:
                    break
                
                info['abi'].append(interpreter_tags)
                info['interpreter'].append(abi_tags)
                info['platform'].add(tag.platform)

        
        if compatible:
            available_files.append(info)

        
    
    def file_sorter(
        file1: dict[str, set | list[list[PythonTag]] | str | dict],
        file2: dict[str, set | list[list[PythonTag]] | str | dict],
    ):
        file1_max = None
        file2_max = None
        
        def find_max(file: dict[str, set | list[list[PythonTag]] | str | dict]):
            max_interpreter = None
            for interpreter_tags, abi_tags in zip(file['interpreter'], file['abi']):
                for interpreter, abi in zip(interpreter_tags, abi_tags):
                    if ((interpreter.version is None or (interpreter.version <= python_version_obj and interpreter.version.major == python_version_obj.major))
                    and (abi.version is None or (abi.version <= python_version_obj and abi.version.major == python_version_obj.major))):
                        if ((interpreter.name in SUPPORTED_INTERPRETERS)
                        and (abi.name in SUPPORTED_INTERPRETERS)):
                            if ((max_interpreter is None)
                            or  (max_abi is None)):
                                max_interpreter = interpreter
                                max_abi = abi
                            elif (SUPPORTED_INTERPRETERS.index(interpreter.name) >= SUPPORTED_INTERPRETERS.index(max_interpreter.name)):
                                if (interpreter.name == max_interpreter.name):
                                    if interpreter.version == max_interpreter.version:
                                        if SUPPORTED_INTERPRETERS.index(abi.name) > SUPPORTED_INTERPRETERS.index(max_abi.name):
                                            max_interpreter = interpreter
                                            max_abi = abi
                                        elif max_abi.version is None:
                                            max_interpreter = interpreter
                                            max_abi = abi
                                        elif abi.version is not None and abi.version >= max_abi.version:
                                            max_interpreter = interpreter
                                            max_abi = abi
                                    elif max_interpreter.version is None:
                                        max_interpreter = interpreter
                                        max_abi = abi
                                    elif interpreter.version is not None and interpreter.version >= max_interpreter.version:
                                        max_interpreter = interpreter
                                        max_abi = abi
                                elif (SUPPORTED_INTERPRETERS.index(interpreter.name) > SUPPORTED_INTERPRETERS.index(max_interpreter.name)):
                                    max_interpreter = interpreter
                                    max_abi = abi
            
            return max_interpreter, max_abi
        
        file1_max = find_max(file1)
        file2_max = find_max(file2)

        if SUPPORTED_INTERPRETERS.index(file1_max[0].name) > SUPPORTED_INTERPRETERS.index(file2_max[0].name):
            return -1
        elif file1_max[0].name == file2_max[0].name:
            if SUPPORTED_INTERPRETERS.index(file1_max[1].name) > SUPPORTED_INTERPRETERS.index(file2_max[1].name):
                return -1
            elif file1_max[1].name == file2_max[1].name:
                if file1_max[0].version == file2_max[0].version:
                    if file1_max[1].version == file2_max[1].version:
                        return 0
                    elif file1_max[1].version is None or file2_max[1].version is None:
                        if file1_max[0].version is None:
                            return -1
                        else:
                            return 1
                    elif file1_max[1].version > file2_max[1].version:
                        return -1
                    else:
                        return 1
                elif file1_max[0].version is None or file2_max[0].version is None:
                    if file1_max[0].version is None:
                        return -1
                    else:
                        return 1
                elif file1_max[0].version > file2_max[0].version:
                    return -1
                else:
                    return 1
            else:
                return 1
        else:
            return 1
    
    available_files.sort(key = cmp_to_key(file_sorter))

    by_platforms = {}

    for file in available_files:
        by_platforms.setdefault('-'.join(file['platform']), []).append(file)

    return by_platforms

def filter_platform_files(
    files: dict[str, list[dict[str, set | list[list[PythonTag]] | str | dict]]],
    platforms: list[str] | None = None,
):
    result = {}
    if platforms is None:
        platforms = BLENDER_PLATFORMS.copy()
    
    def get_blender_platform(platform: str):
        accepted_platforms = []
        if 'linux' in platform:
            if 'x86' in platform:
                accepted_platforms.append(BlenderPlatform.linux_x64)
        if 'win' in platform:
            if '32' in platform or 'amd64' in platform:
                accepted_platforms.append(BlenderPlatform.windows_x64)
            if 'arm64' in platform:
                accepted_platforms.append(BlenderPlatform.windows_arm64)
        if 'macosx' in platform:
            if 'x86' in platform or 'universal' in platform:
                accepted_platforms.append(BlenderPlatform.macos_x64)
            if 'arm64' in platform or 'universal' in platform:
                accepted_platforms.append(BlenderPlatform.macos_arm64)
        
        if platform == 'any':
            accepted_platforms.append('any')
        
        return accepted_platforms
                
    
    for platform, file in files.items():
        blender_platforms = get_blender_platform(platform)
        for blender_platform_name in blender_platforms:
            if blender_platform_name in platforms or blender_platform_name == 'any':
                result.setdefault(blender_platform_name, []).append(file)
    
    return result

def download_packages(
    packages: str | list[str],
    output_folder: str = './',
    no_deps: bool = False,
    all_wheels: bool = False,
    platforms: list[str] | None = None,
    python_version: str = '3.11',
):
    result = []
    used_platforms = platforms.copy()
    python_version_obj = Version(python_version)

    if platforms is None:
        platforms = BLENDER_PLATFORMS.copy()
    
    for i, package in enumerate(packages):
        requirement = Requirement(package)
        requirement.name = NormalizedName(requirement.name)
        packages[i] = str(requirement)
    
    if not all_wheels:
        wheels = download_wheels(
            packages,
            output_folder,
            no_deps = no_deps,
            python_version = python_version,
        )
        result.extend(wheels)
    else:
        logging.info('gathering dependencies')
        dependencies = get_dependencies(packages)
        packages_by_platform: dict[str, list[dict]] = {}

        for dependency in dependencies:
            requirement = Requirement(dependency)

            if requirement.url is not None:
                for platform in platforms:
                    packages_by_platform.setdefault(platform, {}).setdefault('names', set()).add(str(requirement))
                    packages_by_platform.setdefault(platform, {}).setdefault('files', []).append({
                        'name': requirement.name,
                        'type': 'url',
                        'requirement': requirement,
                    })
                continue
            
            wheel_info = get_wheel_info(
                requirement,
                python_version,
            )
            by_platform = filter_platform_files(
                wheel_info,
                platforms,
            )
            
            for platform, wheels in by_platform.items():
                if platform == 'any':
                    logging.debug(f'adding {requirement.name} to all')
                    for platform_name in platforms:
                        packages_by_platform.setdefault(platform_name, {}).setdefault('names', set()).add(str(requirement))
                        packages_by_platform.setdefault(platform_name, {}).setdefault('files', []).append({
                            'name': requirement.name,
                            'type': 'direct',
                            'wheels': wheels,
                        })
                else:
                    logging.debug(f'adding {requirement.name} to {platform}')
                    packages_by_platform.setdefault(platform, {}).setdefault('names', set()).add(str(requirement))
                    packages_by_platform.setdefault(platform, {}).setdefault('files', []).append({
                        'name': requirement.name,
                        'type': 'direct',
                        'wheels': wheels,
                    })
        
        for platform, requirements in packages_by_platform.items():
            logging.debug(f'{platform} | {len(requirements["names"])} | {len(requirements["files"])}')
        
        platforms_to_download = {platform: requirements for platform, requirements in packages_by_platform.items() if len(requirements['names']) >= len(dependencies)}
        used_platforms = list(platforms_to_download.keys())
        if 'any' in used_platforms:
            used_platforms.remove('any')
        
        downloaded_urls = []
        
        for requirements in platforms_to_download.values():
            for requirement in requirements['files']:
                if requirement['type'] == 'url':
                    if str(requirement['requirement']) in downloaded_urls:
                        continue
                    result.extend(download_wheels(
                        str(requirement['requirement']),
                        output_folder,
                        no_deps = True,
                    ))
                    downloaded_urls.append(str(requirement['requirement']))
                elif requirement['type'] == 'direct':
                    for files in requirement['wheels']:
                        wheel = files[0]
                        output_filename = os.path.join(output_folder, wheel['info']['filename'])
                        if output_filename in result:
                            logging.debug(f'{output_filename} already downloaded')
                            continue
                        
                        logging.info(f'downloading {wheel["info"]["filename"]}')
                        data = download_url(wheel['info']['url'])
                        with open(output_filename, 'wb') as file:
                            file.write(data)
                        result.append(output_filename)
        
                        
                # 
                # result.extend(download_wheels(
                #     str(requirement),
                #     output_folder = output_folder,
                #     no_deps = True,
                #     platforms = list(file_platforms),
                #     abis = list(file_abis),
                #     python_version = python_version,
                # ))
    
    return result, used_platforms
