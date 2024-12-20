import os
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple

import requests
from packaging.requirements import Requirement
from packaging.tags import Tag
from packaging.utils import BuildTag, NormalizedName, parse_wheel_filename
from packaging.version import Version


class WheelInfo(NamedTuple):
    name: NormalizedName
    version: Version
    build: BuildTag
    tag: frozenset[Tag]


def download_wheels(
    package: str | list[str],
    output_folder: str = './',
    no_deps: bool = False,
    platforms: list[str] | None = None,
    python_version: str | None = '3.11',
):
    result = []
    
    command = [sys.executable, '-m', 'pip', '--isolated', '--disable-pip-version-check']
    with tempfile.TemporaryDirectory() as tempdir:
        if platforms is None:
            command.extend(['wheel'])
            
            if no_deps:
                command.append('--no-deps')

            command.extend(['-w', tempdir])
        else:
            command.extend(['download', '--dest', tempdir, '--only-binary=:all:'])
            if python_version is not None:
                command.extend(['--python-version', python_version])
            for platform in platforms:
                command.extend(['--platform', platform])
        
        
        if isinstance(package, (list, tuple)):
            command.extend(package)
        else:
            command.append(package)
        
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
                print(f'{os.path.join(output_folder, wheel)} already exists')
    
    return result

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

def download_packages(
    packages: str | list[str],
    output_folder: str = './',
    no_deps: bool = False,
    all_wheels: bool = False,
    python_version: str | None = '3.11',
):
    result = []
    
    for i, package in enumerate(packages):
        requirement = Requirement(package)
        requirement.name = NormalizedName(requirement.name)
        packages[i] = str(requirement)
    
    if not all_wheels:
        wheels = download_wheels(
            packages,
            output_folder,
            no_deps = no_deps,
        )
        result.extend(wheels)
    else:
        print('gathering dependencies')
        dependencies = get_dependencies(packages)
        for dependency in dependencies:
            requirement = Requirement(dependency)

            if requirement.url is not None:
                continue
            
            pypi_info = get_package_json(requirement.name)
            
            platforms = set()
            versions = sorted([Version(version) for version in pypi_info['releases'].keys()], reverse = True)
            version = next(filter(lambda v: v in requirement.specifier, versions))
            
            version_info = pypi_info['releases'][str(version)]
            
            for file_info in version_info:
                if file_info.get('packagetype') != 'bdist_wheel':
                    continue
                
                parsed_filename = WheelInfo(*parse_wheel_filename(file_info['filename']))
                
                for tag in parsed_filename.tag:
                    if tag.platform:
                        platforms.add(tag.platform)
                
                result.extend(download_wheels(
                    str(requirement),
                    output_folder = output_folder,
                    no_deps = True,
                    platforms = list(platforms),
                    python_version = python_version,
                ))
    
    return result
