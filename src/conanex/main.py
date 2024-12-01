import copy
import hashlib
import os
import re
import shutil
import tarfile
import tempfile
import argparse
import sys

from enum import Enum
from io import BytesIO
from pathlib import Path
from subprocess import Popen, PIPE, DEVNULL
from typing import List, Dict
from urllib.parse import urlparse
from urllib.request import urlopen
from zipfile import ZipFile

nenv = copy.copy(os.environ)
paths = nenv["PATH"].split(os.pathsep)
npaths = []
for path in paths:
    if path not in npaths:
        npaths.append(path)
nenv["PATH"] = os.pathsep.join(npaths)

detect_external_package = r"(?P<package>(-|\w)+)(\/(?P<version>[.\d\w]+))?(@((?P<user>\w+)\/(?P<channel>\w+))?)?\s*\{"
detect_external_package_re = re.compile(detect_external_package)
external_package_property = r"^\s*(?P<property>.+?)\s*=\s*(?P<value>.+?)\s*$"
external_package_property_re = re.compile(external_package_property)
new_section = r"\[.*\]"
new_section_re = re.compile(new_section)
option = r"\s*(?P<name>.*?)\s*:\s*(?P<option>.*?)\s*=\s*(?P<value>.*)"
option_re = re.compile(option)


class ConanArgs:
    def __init__(self, args):
        self.__dict__['_args'] = args

    def __copy__(self):
        return ConanArgs(self.__dict__['_args'])

    def __getattr__(self, name):
        if name == '_args':
            return self.__dict__['_args']
        if hasattr(self._args, name):
            return getattr(self._args, name)
        return False


class ConanFileSection(Enum):
    No = 0
    Requires = 1
    ToolRequires = 2
    Options = 3


class ExternalPackage:
    def __init__(self, name, version, user, channel, protocol, url, **kwargs):
        self.name = name
        self.version = version
        self.user = user
        self.channel = channel
        self.protocol = protocol
        self.url = url
        self.attrs = dict(kwargs)
        self.options = []

    @property
    def package_name(self):
        return "{}/{}".format(self.name, self.version)

    @property
    def full_package_name(self):
        if self.user and self.channel:
            return "{}@{}/{}".format(self.package_name, self.user, self.channel)
        else:
            return "{}@".format(self.package_name)

    @property
    def package_hash_algo(self):
        hash_algo = None
        if 'md5' in self.attrs:
            hash_algo = 'md5'
        if 'sha256' in self.attrs:
            hash_algo = 'sha256'
        if 'sha512' in self.attrs:
            hash_algo = 'sha512'
        return hash_algo

    @property
    def package_hash_code(self):
        hash = None
        if self.package_hash_algo:
            hash = self.attrs[self.package_hash_algo]
        return hash.lower().replace("'", "").replace('"', '')


def parse_inspect_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    inspect_parser = subparsers.add_parser('inspect')
    inspect_parser.add_argument('-f', '--format', type=str, help='FORMAT')
    inspect_parser.add_argument('-a', '--attribute', type=str, help="ATTRIBUTE")
    inspect_parser.add_argument('-r', '--remote', type=str, help="REMOTE")
    inspect_parser.add_argument('--raw', action='store_true')
    inspect_parser.add_argument('-j', '--json', type=str, help='JSON')
    inspect_parser.add_argument('path_or_reference', type=str)
    return parser.parse_args()


def parse_info_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    info_parser = subparsers.add_parser('info')
    info_parser.add_argument('-f', '--format', type=str, help='FORMAT')
    info_parser.add_argument('--paths', action='store_true')
    info_parser.add_argument('-bo', '--build-order', type=str, help='BUILD_ORDER')
    info_parser.add_argument('-n', '--only', type=str, help='ONLY')
    info_parser.add_argument('-if', '--install-folder', type=str, help='INSTALL_FOLDER')
    info_parser.add_argument('-g', '--graph', type=str, help='GRAPH')
    info_parser.add_argument('-db', '--dry-build', type=str, help='DRY_BUILD')
    info_parser.add_argument('--package-filter', type=str, nargs='?', help='PACKAGE_FILTER')
    info_parser.add_argument('-j', '--json', type=str, nargs='?', help='JSON')
    info_parser.add_argument('-b', '--build', type=str, nargs='?', const='default', help='BUILD')
    info_parser.add_argument('-r', '--remote', type=str, help='REMOTE')
    info_parser.add_argument('-u', '--update', action='store_true')
    info_parser.add_argument('-l', '--lockfile', type=str, help='LOCKFILE')
    info_parser.add_argument('--lockfile-out', type=str, help='LOCKFILE_OUT')
    info_parser.add_argument('-e', '--env', type=str, help='ENV_HOST')
    info_parser.add_argument('-e:b', '--env:build', type=str, help='ENV_BUILD')
    info_parser.add_argument('-e:h', '--env:host', type=str, help='ENV_HOST')
    info_parser.add_argument('-o', '--options', type=str, help='OPTIONS_HOST')
    info_parser.add_argument('-o:b', '--options:build', type=str, help='OPTIONS_BUILD')
    info_parser.add_argument('-o:h', '--options:host', type=str, help='OPTIONS_HOST')
    info_parser.add_argument('-pr', '--profile', type=str, help='PROFILE_HOST')
    info_parser.add_argument('-pr:b', '--profile:build', type=str, help='PROFILE_BUILD')
    info_parser.add_argument('-pr:h', '--profile:host', type=str, help='PROFILE_HOST')
    info_parser.add_argument('-s', '--settings', type=str, action='append', help='SETTINGS_HOST')
    info_parser.add_argument('-s:b', '--settings:build', type=str, action='append', nargs='+', help='SETTINGS_BUILD')
    info_parser.add_argument('-s:h', '--settings:host', type=str, action='append', nargs='+', help='SETTINGS_HOST')
    info_parser.add_argument('-c', '--conf', type=str, help='CONF_HOST')
    info_parser.add_argument('-c:b', '--conf:build', type=str, help='CONF_BUILD')
    info_parser.add_argument('-c:h', '--conf:host', type=str, help='CONF_HOST')
    info_parser.add_argument('path_or_reference', type=str)
    return parser.parse_args()


def parse_install_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    install_parser = subparsers.add_parser('install')
    install_parser.add_argument('-f', '--format', type=str, help='FORMAT')
    install_parser.add_argument('-g', '--generator', type=str, help='GENERATOR')
    install_parser.add_argument('-if', '--install-folder', type=str, help='INSTALL_FOLDER')
    install_parser.add_argument('-of', '--output-folder', type=str, help='OUTPUT_FOLDER')
    install_parser.add_argument('-v', '--verify', type=str, nargs='?', const='default', help='VERIFY')
    install_parser.add_argument('--requires', type=str, action='append', nargs='+', help='REQUIRES')
    install_parser.add_argument('--tool-requires', type=str, action='append', nargs='+', help='TOOL_REQUIRES')
    install_parser.add_argument('--deployer-folder', type=str, help='DEPLOYER_FOLDER')
    install_parser.add_argument('--name', type=str, help='NAME')
    install_parser.add_argument('--version', type=str, help='VERSION')
    install_parser.add_argument('--user', type=str, help='USER')
    install_parser.add_argument('--channel', type=str, help='CHANNEL')
    install_parser.add_argument('--no-imports', action='store_true')
    install_parser.add_argument('--build-require', action='store_true')
    install_parser.add_argument('--packages', type=str, action='append', nargs='+', help='OPTIONS_BUILD')
    install_parser.add_argument('-j', '--json', type=str, help='JSON')
    install_parser.add_argument('-d', '--deployer', type=str, help='DEPLOYER')
    install_parser.add_argument('-b', '--build', type=str, nargs='?', const='default', help='BUILD')
    install_parser.add_argument('-r', '--remote', type=str, help='REMOTE')
    install_parser.add_argument('-nr', '--no-remote', type=str, help='NO_REMOTE')
    install_parser.add_argument('-u', '--update', action='store_true')
    install_parser.add_argument('-l', '--lockfile', type=str, help='LOCKFILE')
    install_parser.add_argument('--lockfile-partial', type=str, help='LOCKFILE_PARTIAL')
    install_parser.add_argument('--lockfile-out', type=str, help='LOCKFILE_OUT')
    install_parser.add_argument('--lockfile-packages', type=str, help='LOCKFILE_PACKAGES')
    install_parser.add_argument('--lockfile-clean', type=str, help='LOCKFILE_CLEAN')
    install_parser.add_argument('--lockfile-overrides', type=str, help='LOCKFILE_OVERRIDES')
    install_parser.add_argument('-pr', '--profile', type=str, help='PROFILE_HOST')
    install_parser.add_argument('-pr:b', '--profile:build', type=str, help='PROFILE_BUILD')
    install_parser.add_argument('-pr:h', '--profile:host', type=str, help='PROFILE_HOST')
    install_parser.add_argument('-pr:a', '--profile:all', type=str, help='PROFILE_ALL')
    install_parser.add_argument('-o', '--options', type=str, action='append', nargs='+', help='OPTIONS_HOST')
    install_parser.add_argument('-o:b', '--options:build', type=str, action='append', nargs='+', help='OPTIONS_BUILD')
    install_parser.add_argument('-o:h', '--options:host', type=str, action='append', nargs='+', help='OPTIONS_HOST')
    install_parser.add_argument('-o:a', '--options:all', type=str, action='append', nargs='+', help='OPTIONS_ALL')
    install_parser.add_argument('-s', '--settings', type=str, action='append', nargs='+', help='SETTINGS_HOST')
    install_parser.add_argument('-s:b', '--settings:build', type=str, action='append', nargs='+', help='SETTINGS_BUILD')
    install_parser.add_argument('-s:h', '--settings:host', type=str, action='append', nargs='+', help='SETTINGS_HOST')
    install_parser.add_argument('-s:a', '--settings:all', type=str, action='append', nargs='+', help='SETTINGS_ALL')
    install_parser.add_argument('-c', '--conf', type=str, action='append', nargs='+', help='CONF_HOST')
    install_parser.add_argument('-c:b', '--conf:build', type=str, action='append', nargs='+', help='CONF_BUILD')
    install_parser.add_argument('-c:h', '--conf:host', type=str, action='append', nargs='+', help='CONF_HOST')
    install_parser.add_argument('-c:a', '--conf:all', type=str, action='append', nargs='+', help='CONF_ALL')
    install_parser.add_argument('path_or_reference', type=str)
    install_parser.add_argument('reference', type=str, nargs='?')
    return parser.parse_args()


def build_install_args(args, path_or_reference: ExternalPackage | str):
    new_args = ['install']

    if args.generator:
        new_args.append('-g')
        new_args.append(args.generator)
    if args.install_folder:
        new_args.append('-if')
        new_args.append(args.install_folder)
    if args.output_folder:
        new_args.append('-of')
        new_args.append(args.output_folder)
    if args.format:
        new_args.append('-f')
        new_args.append(args.format)

    if args.name:
        new_args.append('--name')
        new_args.append(args.name)
    if args.version:
        new_args.append('--version')
        new_args.append(args.version)
    if args.user:
        new_args.append('--user')
        new_args.append(args.user)
    if args.channel:
        new_args.append('--channel')
        new_args.append(args.channel)

    if args.deployer_folder:
        new_args.append('--deployer-folder')
        new_args.append(args.deployer_folder)
    if args.deployer:
        new_args.append('--deployer')
        new_args.append(args.deployer)

    if hasattr(args, 'requires') and getattr(args, 'requires'):
        for require in getattr(args, 'requires'):
            new_args.append('-r')
            new_args.append(require)
    if hasattr(args, 'tool-requires') and getattr(args, 'tool-requires'):
        for require in getattr(args, 'tool-requires'):
            new_args.append('--tool-requires')
            new_args.append(require)

    if args.packages:
        for package in getattr(args, 'packages'):
            new_args.append(f'--requires={package}')

    if args.build_require:
        new_args.append('--build-require')
    if args.no_imports:
        new_args.append('--no-imports')
        new_args.append(args.no_imports)
    if args.json:
        new_args.append('-j')
        new_args.append(args.json)
    if args.update:
        new_args.append('-u')
    if args.manifests:
        new_args.append('-m')
        if args.manifests != "default":
            new_args.append(args.manifests)
    if args.manifests_interactive:
        new_args.append('-mi')
        if args.manifests_interactive != "default":
            new_args.append(args.manifests_interactive)
    if args.verify:
        new_args.append('-v')
        if args.verify != "default":
            new_args.append(args.verify)
    if args.build:
        new_args.append('-b')
        if args.build != "default":
            new_args.append(args.build)

    if args.remote:
        new_args.append('-r')
        new_args.append(args.remote)
    if args.no_remote:
        new_args.append('-nr')
        new_args.append(args.no_remote)

    if args.lockfile:
        new_args.append('-l')
        new_args.append(args.lockfile)
    if args.lockfile_partial:
        new_args.append('-lockfile-partial')
        new_args.append(args.lockfile_partial)
    if args.lockfile_out:
        new_args.append('-lockfile-out')
        new_args.append(args.lockfile_out)
    if args.lockfile_packages:
        new_args.append('-lockfile-packages')
        new_args.append(args.lockfile_packages)
    if args.lockfile_clean:
        new_args.append('-lockfile-clean')
        new_args.append(args.lockfile_clean)
    if args.lockfile_overrides:
        new_args.append('-lockfile-overrides')
        new_args.append(args.lockfile_overrides)

    if args.profile:
        new_args.append('-pr')
        new_args.append(args.profile)
    if hasattr(args, 'profile:build') and getattr(args, 'profile:build'):
        new_args.append('-pr:b')
        new_args.append(getattr(args, 'profile:build'))
    if hasattr(args, 'profile:host') and getattr(args, 'profile:host'):
        new_args.append('-pr:h')
        new_args.append(getattr(args, 'profile:host'))
    if hasattr(args, 'profile:all') and getattr(args, 'profile:all'):
        new_args.append('-pr:a')
        new_args.append(getattr(args, 'profile:all'))

    if args.settings:
        for setting in args.settings:
            new_args.append('-s')
            new_args.append(setting)
    if hasattr(args, 'settings:build') and getattr(args, 'settings:build'):
        for setting in getattr(args, 'settings:build'):
            new_args.append('-s:b')
            new_args.append(setting)
    if hasattr(args, 'settings:host') and getattr(args, 'settings:host'):
        for setting in getattr(args, 'settings:host'):
            new_args.append('-s:h')
            new_args.append(setting)
    if hasattr(args, 'settings:all') and getattr(args, 'settings:all'):
        for setting in getattr(args, 'settings:all'):
            new_args.append('-s:a')
            new_args.append(setting)

    if hasattr(args, 'options:build') and getattr(args, 'options:build'):
        for option in getattr(args, 'options:build'):
            new_args.append('-s:b')
            new_args.append(option)
    if hasattr(args, 'options:host') and getattr(args, 'options:host'):
        for option in getattr(args, 'options:host'):
            new_args.append('-s:h')
            new_args.append(option)
    if hasattr(args, 'options:all') and getattr(args, 'options:all'):
        for setting in getattr(args, 'options:all'):
            new_args.append('-s:a')
            new_args.append(setting)

    if args.conf:
        new_args.append('-c')
        new_args.append(args.conf)
    if hasattr(args, 'conf:build') and getattr(args, 'conf:build'):
        new_args.append('-c:b')
        new_args.append(getattr(args, 'conf:build'))
    if hasattr(args, 'conf:host') and getattr(args, 'conf:host'):
        new_args.append('-c:h')
        new_args.append(getattr(args, 'conf:host'))
    if hasattr(args, 'conf:all') and getattr(args, 'conf:all'):
        new_args.append('-c:a')
        new_args.append(getattr(args, 'conf:all'))

    if isinstance(path_or_reference, ExternalPackage):
        new_args.append(f'--requires={path_or_reference.full_package_name}')
    else:
        new_args.append(path_or_reference)
    return new_args


def build_create_args(args, tmpdirname, package: ExternalPackage):
    new_args = ['create']

    if args.format:
        new_args.append('-f')
        new_args.append(args.format)

    if package.name:
        new_args.append('--name')
        new_args.append(package.name)
    if package.version:
        new_args.append('--version')
        new_args.append(package.version)
    if package.user:
        new_args.append('--user')
        new_args.append(package.user)
    if package.channel:
        new_args.append('--channel')
        new_args.append(package.channel)

    if args.build_require:
        new_args.append('--build-require')
    if args.update:
        new_args.append('-u')
    if args.verify:
        new_args.append('-v')
        if args.verify != "default":
            new_args.append(args.verify)
    if args.build:
        new_args.append('-b')
        if args.build != "default":
            new_args.append(args.build)

    if args.remote:
        new_args.append('-r')
        new_args.append(args.remote)
    if args.no_remote:
        new_args.append('-nr')
        new_args.append(args.no_remote)

    if args.lockfile:
        new_args.append('-l')
        new_args.append(args.lockfile)
    if args.lockfile_partial:
        new_args.append('-lockfile-partial')
        new_args.append(args.lockfile_partial)
    if args.lockfile_out:
        new_args.append('-lockfile-out')
        new_args.append(args.lockfile_out)
    if args.lockfile_packages:
        new_args.append('-lockfile-packages')
        new_args.append(args.lockfile_packages)
    if args.lockfile_clean:
        new_args.append('-lockfile-clean')
        new_args.append(args.lockfile_clean)
    if args.lockfile_overrides:
        new_args.append('-lockfile-overrides')
        new_args.append(args.lockfile_overrides)

    if args.profile:
        new_args.append('-pr')
        new_args.append(args.profile)
    if hasattr(args, 'profile:build') and getattr(args, 'profile:build'):
        new_args.append('-pr:b')
        new_args.append(getattr(args, 'profile:build'))
    if hasattr(args, 'profile:host') and getattr(args, 'profile:host'):
        new_args.append('-pr:h')
        new_args.append(getattr(args, 'profile:host'))
    if hasattr(args, 'profile:all') and getattr(args, 'profile:all'):
        new_args.append('-pr:a')
        new_args.append(getattr(args, 'profile:all'))

    if args.settings:
        for setting in args.settings:
            new_args.append('-s')
            new_args.append(setting)
    if hasattr(args, 'settings:build') and getattr(args, 'settings:build'):
        for setting in getattr(args, 'settings:build'):
            new_args.append('-s:b')
            new_args.append(setting)
    if hasattr(args, 'settings:host') and getattr(args, 'settings:host'):
        for setting in getattr(args, 'settings:host'):
            new_args.append('-s:h')
            new_args.append(setting)
    if hasattr(args, 'settings:all') and getattr(args, 'settings:all'):
        for setting in getattr(args, 'settings:all'):
            new_args.append('-s:a')
            new_args.append(setting)

    if hasattr(args, 'options:build') and getattr(args, 'options:build'):
        for option in getattr(args, 'options:build'):
            new_args.append('-s:b')
            new_args.append(option)
    if hasattr(args, 'options:host') and getattr(args, 'options:host'):
        for option in getattr(args, 'options:host'):
            new_args.append('-s:h')
            new_args.append(option)
    if hasattr(args, 'options:all') and getattr(args, 'options:all'):
        for setting in getattr(args, 'options:all'):
            new_args.append('-s:a')
            new_args.append(setting)

    if args.conf:
        new_args.append('-c')
        new_args.append(args.conf)
    if hasattr(args, 'conf:build') and getattr(args, 'conf:build'):
        new_args.append('-c:b')
        new_args.append(getattr(args, 'conf:build'))
    if hasattr(args, 'conf:host') and getattr(args, 'conf:host'):
        new_args.append('-c:h')
        new_args.append(getattr(args, 'conf:host'))
    if hasattr(args, 'conf:all') and getattr(args, 'conf:all'):
        new_args.append('-c:a')
        new_args.append(getattr(args, 'conf:all'))

    new_args.append(tmpdirname)
    return new_args


def run_git_clone_command(tag, tmpdirname, url):
    if tag:
        git_clone_command = ["git", "clone", "--recursive", '-b', tag, url, tmpdirname]
    else:
        git_clone_command = ["git", "clone", "--recursive", url, tmpdirname]
    run_command(git_clone_command)


def run_command(command):
    print(' '.join(command))
    process = Popen(command, stdout=PIPE, env=nenv)
    process.communicate()
    exit_code = process.wait()
    if exit_code != 0:
        raise Exception(f"Failed command\n{' '.join(command)}")


def run_conan_create_command(args, package: ExternalPackage, tmpdirname):
    print("\nBuilding {} from sources:".format(package.full_package_name))
    create_args = build_create_args(args, tmpdirname, package)
    conan_create_command = [sys.executable, "-m", "conans.conan", *create_args]
    run_command(conan_create_command)


def run_conan_install_command(args, path_or_reference):
    install_args = build_install_args(args, path_or_reference)
    conan_install_command = [sys.executable, "-m", "conans.conan", *install_args]
    run_command(conan_install_command)


def run_conan_remove_command(path_or_reference):
    conan_remove_command = [sys.executable, "-m", "conans.conan", "remove", "--confirm", path_or_reference]
    run_command(conan_remove_command)


def create_hash_algo(hash_algo):
    hash = None
    if 'md5' == hash_algo:
        hash = hashlib.md5()
    if 'sha256' == hash_algo:
        hash = hashlib.sha256()
    if 'sha512' == hash_algo:
        hash = hashlib.sha512()
    return hash


def calculate_bytes_io_hash(filename: BytesIO, hash):
    # Read and update hash string value in blocks of 4K
    for byte_block in iter(lambda: filename.read(4096), b""):
        hash.update(byte_block)
    return hash.hexdigest().lower()


def calculate_file_hash(filename, hash):
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            hash.update(byte_block)
        return hash.hexdigest().lower()


def verify_hash_code(file: str | BytesIO, package: ExternalPackage):
    if package.package_hash_algo:
        if type(file) == BytesIO:
            hash_code = calculate_bytes_io_hash(copy.copy(file), create_hash_algo(package.package_hash_algo))
        else:
            hash_code = calculate_file_hash(file, create_hash_algo(package.package_hash_algo))
        if package.package_hash_code != hash_code:
            raise Exception("Calculated hash code '{}' of {} file is not equal to {}"
                            .format(hash_code, file, package.package_hash_code))


def is_package_in_cache(package: ExternalPackage):
    conan_command = [sys.executable, "-m", "conans.conan", "search", package.package_name]
    with Popen(conan_command, stdout=PIPE, env=nenv) as proc:
        search_results, _ = proc.communicate(timeout=15)
        search_results = str(search_results)
        return "Existing package recipes:" in search_results


def uri_validator(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def extract_from_zip(tmpdirname, url, package: ExternalPackage):
    if uri_validator(url):
        print("wget {}".format(url))
        resp = urlopen(url)
        bytes_io = BytesIO(resp.read())
        verify_hash_code(bytes_io, package)
        with ZipFile(bytes_io) as zipfile:
            zipfile.extractall(tmpdirname)
    else:
        verify_hash_code(url, package)
        with ZipFile(url, 'r') as zipfile:
            zipfile.extractall(tmpdirname)


def extract_from_tar(tmpdirname, url, archive, package: ExternalPackage):
    if uri_validator(url):
        print("wget {}".format(url))
        resp = urlopen(url)
        bytes_io = BytesIO(resp.read())
        verify_hash_code(bytes_io, package)
        with tarfile.open(fileobj=bytes_io, mode="r:{}".format(archive)) as tar:
            tar.extractall(tmpdirname)
    else:
        verify_hash_code(url, package)
        with tarfile.open(name=url, mode=f'r:{archive}') as tar:
            tar.extractall(tmpdirname)


def install_package_from_git(args, package: ExternalPackage):
    with tempfile.TemporaryDirectory() as tmpdirname:
        run_git_clone_command(package.attrs["tag"], tmpdirname, package.url)
        run_conan_create_command(args, package, tmpdirname)


def install_package_from_zip(args, package: ExternalPackage):
    with tempfile.TemporaryDirectory() as tmpdirname:
        filename, file_ext = os.path.splitext(package.url)
        file_ext = file_ext[1:]
        if file_ext == 'zip':
            extract_from_zip(tmpdirname, package.url, package)
        elif os.path.splitext(filename)[1][1:] == 'tar':
            extract_from_tar(tmpdirname, package.url, file_ext, package)

        subfolders = [f.path for f in os.scandir(tmpdirname) if f.is_dir()]
        if len(subfolders) == 1:
            src_package_dir = subfolders[0]
        else:
            src_package_dir = tmpdirname

        run_conan_create_command(args, package, src_package_dir)


def install_package_from_path(args, package: ExternalPackage, path: str):
    run_conan_create_command(args, package, path)


def install_package_from_conanfile(args, package: ExternalPackage):
    if not package.url.endswith("conanfile.py"):
        raise Exception("Url [{}] should contain conanfile.py".format(package.url))
    with tempfile.TemporaryDirectory() as tmpdirname:
        if uri_validator(package.url):
            print("wget {}".format(package.url))
            resp = urlopen(package.url)
            new_conanfile_path = os.path.join(tmpdirname, "conanfile.py")
            bytes_io = BytesIO(resp.read())
            with open(new_conanfile_path, "wb") as f:
                f.write(bytes_io.getbuffer())
            verify_hash_code(new_conanfile_path, package)
        else:
            shutil.copy2(package.url, tmpdirname)

        run_conan_create_command(args, package, tmpdirname)


def install_package_from_remote(args, package: ExternalPackage):
    install_args = copy.copy(args)
    install_args.remote = package.url
    run_conan_install_command(install_args, package)


def is_command_to_modify():
    return 'install' in sys.argv or \
           'info' in sys.argv


def generate_new_conanfile(args, orig_conanfile_path, new_conanfile):
    if os.path.exists(orig_conanfile_path):
        requires: List[ExternalPackage] = []
        options: Dict[str, str] = {}

        with open(orig_conanfile_path) as f:
            new_file_lines = []
            context = ConanFileSection.No
            external_package_lines = []
            for line in f.readlines():
                line = line.strip()
                if "#" in line:
                    line = line[:line.find("#")]
                if len(line) == 0:
                    continue
                line = f"{line}\n"

                if "[requires]" in line:
                    context = ConanFileSection.Requires
                elif "[tool_requires]" in line:
                    context = ConanFileSection.ToolRequires
                elif "[options]" in line:
                    context = ConanFileSection.Options
                elif new_section_re.match(line):
                    context = ConanFileSection.No

                if context == ConanFileSection.No:
                    new_file_lines.append(str(line))
                    continue

                detect_external_package_match = detect_external_package_re.match(line)
                option_match = option_re.match(line)
                if detect_external_package_match or len(external_package_lines) > 0:
                    external_package_lines.append(line)
                    if '}' not in line:
                        continue

                    external_package_match = detect_external_package_re.match(external_package_lines[0])

                    external_package_str = "".join(external_package_lines)
                    start_props = external_package_str.find('{') + 1
                    end_props = external_package_str.find('}', start_props)
                    external_package_props_str = external_package_str[start_props:end_props]
                    props_str = external_package_props_str.split(',')
                    properties = {}
                    for prop in props_str:
                        external_package_property_match = external_package_property_re.match(prop)
                        if not external_package_property_match:
                            continue
                        properties[external_package_property_match.group('property')] = external_package_property_match.group('value')

                    external_package_lines = []
                    name = external_package_match.group('package')
                    version = external_package_match.group('version')
                    if not name or not version:
                        raise Exception("name and version of package is required !!"
                                        "Please, specify it in following format: package/version")
                    user = external_package_match.group('user')
                    channel = external_package_match.group('channel')
                    protocols = []
                    for prot in ["git", "zip", "conan", "remote", "path"]:
                        if prot in properties:
                            protocols.append(prot)

                    if len(protocols) == 0:
                        raise Exception("No protocols where found. Protocol should be specified from the following list: {}"
                                        .format(protocols))
                    if len(protocols) > 1:
                        raise Exception("From the following list, only single protocol should be specified: {}"
                                        .format(protocols))

                    protocol = protocols[0]
                    url = properties[protocol].strip("'").strip('"')

                    package_info = ExternalPackage(name=name,
                                                   version=version,
                                                   user=user,
                                                   channel=channel,
                                                   protocol=protocol,
                                                   url=url,
                                                   **properties)
                    requires.append(package_info)
                    full_package_name = package_info.full_package_name
                    if full_package_name[-1] == '@':
                        full_package_name = full_package_name[:-1]
                    new_file_lines.append("{}\n".format(full_package_name))
                elif option_match:
                    name = option_match.group('name')
                    option = option_match.group('option')
                    value = option_match.group('value')
                    options[name] = "{}={}".format(option, value)
                    new_file_lines.append(str(line))
                else:
                    new_file_lines.append(str(line))

            if len(external_package_lines) > 0:
                raise Exception("external package not fully specified:\n{}\n\n"
                                "Please, check a syntax for conanex !!"
                                .format(''.join(external_package_lines)))

        for package in requires:
            if package.name in options:
                package.options.append(options[package.name])

        with open(new_conanfile, mode='w') as file:
            file.writelines(new_file_lines)

        return requires


def regenerate_conanfile(args, command):
    if '@' in args.path_or_reference:
        command_index = sys.argv.index(command)
        command_arg = copy.copy(sys.argv)[command_index:]
        conan_command = [sys.executable, "-m", "conans.conan", *command_arg]
        run_command(conan_command)
    else:
        with tempfile.TemporaryDirectory() as tmpdirname:
            orig_conanfile_path = args.path_or_reference
            new_conanfile_path = os.path.join(tmpdirname, "conanfile.txt")
            generate_new_conanfile(args, orig_conanfile_path, new_conanfile_path)
            command_index = sys.argv.index(command)
            command_arg = copy.copy(sys.argv)[command_index:]
            path_or_reference_index = command_arg.index(args.path_or_reference)
            command_arg[path_or_reference_index] = tmpdirname
            conan_command = [sys.executable, "-m", "conans.conan", *command_arg]
            run_command(conan_command)


def install_external_packages(args, requires: List[ExternalPackage]):
    orig_conanfile_path = args.path_or_reference
    for package in requires:
        if package.protocol in ['git', 'zip', 'path', 'conan', 'remote']:
            if is_package_in_cache(package):
                print("{} was found in cache".format(package.full_package_name))
                continue
            if package.protocol not in ['zip', 'conan'] and package.package_hash_algo:
                raise Exception("hash[{}] allowed only for zip and conan protocols"
                                .format(package.package_hash_algo))
            try:
                if package.protocol == 'git':
                    install_package_from_git(args, package)
                elif package.protocol == 'zip':
                    install_package_from_zip(args, package)
                elif package.protocol == 'path':
                    conanfile_path = os.path.dirname(orig_conanfile_path)
                    conanfile_posix_path = Path(conanfile_path).as_posix()
                    if not Path(package.url).is_absolute():
                        path = str(Path("{}/{}".format(conanfile_posix_path, package.url)))
                    else:
                        path = package.url
                    install_package_from_path(args, package, path)
                elif package.protocol == 'conan':
                    install_package_from_conanfile(args, package)
                elif package.protocol == 'remote':
                    install_package_from_remote(args, package)
            except:
                run_conan_remove_command(package.full_package_name)
                raise


def run():
    if not is_command_to_modify():
        conan_command = [sys.executable, "-m", "conans.conan", *sys.argv[1:]]
        with Popen(conan_command, shell=True, env=nenv) as proc:
            pass

    if 'info' in sys.argv:
        args = parse_info_args()
        regenerate_conanfile(args, 'info')
    elif 'install' in sys.argv:
        args = parse_install_args()
        args = ConanArgs(args)
        with tempfile.TemporaryDirectory() as tmpdirname:
            new_conanfile_path = os.path.join(tmpdirname, "conanfile.txt")
            if os.path.isdir(args.path_or_reference):
                args.path_or_reference = os.path.join(os.path.abspath(args.path_or_reference), "conanfile.txt")
            elif os.path.isfile(args.path_or_reference):
                args.path_or_reference = args.path_or_reference
            else:
                raise Exception("path_or_reference should be either directory or file")
            requires = generate_new_conanfile(args, args.path_or_reference, new_conanfile_path)
            install_external_packages(args, requires)
            with open(new_conanfile_path, 'r') as f:
                for line in f.readlines():
                    print(f"{line}\n")
            run_conan_install_command(args, new_conanfile_path)


if __name__ == '__main__':
    run()
