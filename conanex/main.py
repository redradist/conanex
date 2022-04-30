import os
import re
import tarfile
import tempfile
from enum import Enum
from io import BytesIO
from pathlib import Path
from subprocess import Popen, PIPE, DEVNULL

import argparse
import sys
from typing import List, Dict
from urllib.parse import urlparse
from urllib.request import urlopen
from zipfile import ZipFile
import tarfile

external_package = r"(?P<package>(-|\w)+)(\/(?P<version>[.\d]+))?(@((?P<user>\w+)\/(?P<channel>\w+))?)?\s*" \
                   r"\{\s*(?P<protocol>(git|https|zip|conan|conancenter|path))\s*=\s*\"(?P<url>.+?)\"\s*(,\s*tag\s*=\s*\"(?P<tag>.+?)\"\s*)?\}"
external_package_re = re.compile(external_package)
new_section = r"\[.*\]"
new_section_re = re.compile(new_section)
option = r"\s*(?P<name>.*?)\s*:\s*(?P<option>.*?)\s*=\s*(?P<value>.*)"
option_re = re.compile(option)


class ConanFileSection(Enum):
    No = 0
    Requires = 1
    ToolRequires = 2
    Options = 3


class PackageExternal:
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
            return "{}/{}@".format(self.package_name, self.user, self.channel)
        else:
            return "{}@".format(self.package_name)


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    install_parser = subparsers.add_parser('install')
    install_parser.add_argument('-g', '--generator', type=str, help='GENERATOR')
    install_parser.add_argument('-if', '--install-folder', type=str, help='INSTALL_FOLDER')
    install_parser.add_argument('-of', '--output-folder', type=str, help='OUTPUT_FOLDER')
    install_parser.add_argument('-mi', '--manifests-interactive', type=str, nargs='?', const='default', help='MANIFESTS_INTERACTIVE')
    install_parser.add_argument('-m', '--manifests', type=str, nargs='?', const='default', help='MANIFESTS')
    install_parser.add_argument('-v', '--verify', type=str, nargs='?', const='default', help='VERIFY')
    install_parser.add_argument('--no-imports', action='store_true')
    install_parser.add_argument('--build-require', action='store_true')
    install_parser.add_argument('-j', '--json', type=str, help='JSON')
    install_parser.add_argument('-b', '--build', type=str, nargs='?', const='default', help='BUILD')
    install_parser.add_argument('-r', '--remote', type=str, help='REMOTE')
    install_parser.add_argument('-u', '--update', action='store_true')
    install_parser.add_argument('-l', '--lockfile', type=str, help='LOCKFILE')
    install_parser.add_argument('--lockfile-out', type=str, help='LOCKFILE_OUT')
    install_parser.add_argument('-e', '--env', type=str, help='ENV_HOST')
    install_parser.add_argument('-e:b', '--env:build', type=str, help='ENV_BUILD')
    install_parser.add_argument('-e:h', '--env:host', type=str, help='ENV_HOST')
    install_parser.add_argument('-o', '--options', type=str, help='OPTIONS_HOST')
    install_parser.add_argument('-o:b', '--options:build', type=str, help='OPTIONS_BUILD')
    install_parser.add_argument('-o:h', '--options:host', type=str, help='OPTIONS_HOST')
    install_parser.add_argument('-pr', '--profile', type=str, help='PROFILE_HOST')
    install_parser.add_argument('-pr:b', '--profile:build', type=str, help='PROFILE_BUILD')
    install_parser.add_argument('-pr:h', '--profile:host', type=str, help='PROFILE_HOST')
    install_parser.add_argument('-s', '--settings', type=str, action='append', help='SETTINGS_HOST')
    install_parser.add_argument('-s:b', '--settings:build', type=str, action='append', nargs='+', help='SETTINGS_BUILD')
    install_parser.add_argument('-s:h', '--settings:host', type=str, action='append', nargs='+', help='SETTINGS_HOST')
    install_parser.add_argument('-c', '--conf', type=str, help='CONF_HOST')
    install_parser.add_argument('-c:b', '--conf:build', type=str, help='CONF_BUILD')
    install_parser.add_argument('-c:h', '--conf:host', type=str, help='CONF_HOST')
    install_parser.add_argument('--lockfile-node-id', type=str, help='LOCKFILE_NODE_ID')
    install_parser.add_argument('--require-override', type=str, help='REQUIRE_OVERRIDE')
    install_parser.add_argument('path_or_reference', type=str)
    install_parser.add_argument('reference', type=str, nargs='?')
    return parser.parse_args()


def build_create_args(args, tmpdirname, package: PackageExternal):
    full_package_name = package.full_package_name
    new_args = ['create']
    if args.build_require:
        new_args.append('--build-require')
    if args.update:
        new_args.append('-u')
    if args.require_override:
        new_args.append('--require-override')
        new_args.append(args.require_override)
    if args.manifests:
        new_args.append('-m')
        if args.verify != "manifests":
            new_args.append(args.manifests)
    if args.manifests_interactive:
        new_args.append('-mi')
        if args.verify != "manifests_interactive":
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
    if args.lockfile:
        new_args.append('-l')
        new_args.append(args.lockfile)
    if args.lockfile_out:
        new_args.append('-lockfile-out')
        new_args.append(args.lockfile_out)
    if args.env:
        new_args.append('-e')
        new_args.append(args.env)
    if hasattr(args, 'env:build') and getattr(args, 'env:build'):
        new_args.append('-e:b')
        new_args.append(getattr(args, 'env:build'))
    if hasattr(args, 'env:host') and getattr(args, 'env:host'):
        new_args.append('-e:h')
        new_args.append(getattr(args, 'env:host'))
    if args.profile:
        new_args.append('-pr')
        new_args.append(args.profile)
    if hasattr(args, 'profile:build') and getattr(args, 'profile:build'):
        new_args.append('-pr:b')
        new_args.append(getattr(args, 'profile:build'))
    if hasattr(args, 'profile:host') and getattr(args, 'profile:host'):
        new_args.append('-pr:h')
        new_args.append(getattr(args, 'profile:host'))
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
    if args.conf:
        new_args.append('-c')
        new_args.append(args.conf)
    if hasattr(args, 'conf:build') and getattr(args, 'conf:build'):
        new_args.append('-c:b')
        new_args.append(getattr(args, 'conf:build'))
    if hasattr(args, 'conf:host') and getattr(args, 'conf:host'):
        new_args.append('-c:h')
        new_args.append(getattr(args, 'conf:host'))

    for option in package.options:
        new_args.append('-o')
        new_args.append(option)

    new_args.append(tmpdirname)
    new_args.append(full_package_name)
    return new_args


def build_install_args(args, tmpfilename):
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
    if args.build_require:
        new_args.append('--build-require')
    if args.no_imports:
        new_args.append('--no-imports')
        new_args.append(args.no_imports)
    if args.lockfile_node_id:
        new_args.append('--lockfile-node-id')
        new_args.append(args.lockfile_node_id)
    if args.build_require:
        new_args.append('--build-require')
    if args.json:
        new_args.append('-j')
        new_args.append(args.json)
    if args.update:
        new_args.append('-u')
    if args.require_override:
        new_args.append('--require-override')
        new_args.append(args.require_override)
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
    if args.lockfile:
        new_args.append('-l')
        new_args.append(args.lockfile)
    if args.lockfile_out:
        new_args.append('-lockfile-out')
        new_args.append(args.lockfile_out)
    if args.env:
        new_args.append('-e')
        new_args.append(args.env)
    if hasattr(args, 'env:build') and getattr(args, 'env:build'):
        new_args.append('-e:b')
        new_args.append(getattr(args, 'env:build'))
    if hasattr(args, 'env:host') and getattr(args, 'env:host'):
        new_args.append('-e:h')
        new_args.append(getattr(args, 'env:host'))
    if args.profile:
        new_args.append('-pr')
        new_args.append(args.profile)
    if hasattr(args, 'profile:build') and getattr(args, 'profile:build'):
        new_args.append('-pr:b')
        new_args.append(getattr(args, 'profile:build'))
    if hasattr(args, 'profile:host') and getattr(args, 'profile:host'):
        new_args.append('-pr:h')
        new_args.append(getattr(args, 'profile:host'))
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
    if args.conf:
        new_args.append('-c')
        new_args.append(args.conf)
    if hasattr(args, 'conf:build') and getattr(args, 'conf:build'):
        new_args.append('-c:b')
        new_args.append(getattr(args, 'conf:build'))
    if hasattr(args, 'conf:host') and getattr(args, 'conf:host'):
        new_args.append('-c:h')
        new_args.append(getattr(args, 'conf:host'))
    new_args.append(tmpfilename)
    return new_args


def run_git_clone_command(tag, tmpdirname, url):
    git_clone_command = ["git", "clone", '-b', tag, url, tmpdirname]
    if tag:
        git_clone_command = ["git", "clone", "--recursive", '-b', tag, url, tmpdirname]
    else:
        git_clone_command = ["git", "clone", "--recursive", url, tmpdirname]
    run_conan_command(git_clone_command)


def run_conan_command(conan_command):
    print(' '.join(conan_command))
    with Popen(conan_command) as proc:
        if proc.errors:
            raise Exception("Failed command:\n{}".format(' '.join(conan_command)))


def run_conan_create_command(args, package: PackageExternal, tmpdirname):
    print("\nBuilding {} from sources:".format(package.full_package_name))
    create_args = build_create_args(args, tmpdirname, package)
    conan_create_command = [sys.executable, "-m", "conans.conan", *create_args]
    run_conan_command(conan_create_command)


def run_conan_install_command(args, new_conanfile):
    install_args = build_install_args(args, new_conanfile)
    conan_install_command = [sys.executable, "-m", "conans.conan", *install_args]
    run_conan_command(conan_install_command)


def create_package(args, package: PackageExternal, src_package_dir):
    with Popen([sys.executable, "-m", "conans.conan", "search", package.package_name], stdout=PIPE) as proc:
        search_results = str(proc.stdout.read())
        if "Existing package recipes:" in search_results:
            print("{} was found in cache".format(package.full_package_name))
        else:
            run_conan_create_command(args, package, src_package_dir)


def install_package_from_git(args, package: PackageExternal):
    with tempfile.TemporaryDirectory() as tmpdirname:
        run_git_clone_command(package.attrs["tag"], tmpdirname, package.url)
        create_package(args, package, tmpdirname)


def uri_validator(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def extract_from_zip(tmpdirname, url):
    if uri_validator(url):
        resp = urlopen(url)
        with ZipFile(BytesIO(resp.read())) as zipfile:
            zipfile.extractall(tmpdirname)
    else:
        with ZipFile(url, 'r') as zipfile:
            zipfile.extractall(tmpdirname)


def extract_from_tar(tmpdirname, url, archive):
    if uri_validator(url):
        resp = urlopen(url)
        with tarfile.open(fileobj=BytesIO(resp.read()), mode="r:{}".format(archive)) as tar:
            tar.extractall(tmpdirname)
    else:
        with tarfile.open(name=url, mode=f'r:{archive}') as tar:
            tar.extractall(tmpdirname)


def install_package_from_zip(args, package: PackageExternal):
    with tempfile.TemporaryDirectory() as tmpdirname:
        filename, file_ext = os.path.splitext(package.url)
        file_ext = file_ext[1:]
        if file_ext == 'zip':
            extract_from_zip(tmpdirname, package.url)
        elif os.path.splitext(filename)[1][1:] == 'tar':
            extract_from_tar(tmpdirname, package.url, file_ext)

        subfolders = [f.path for f in os.scandir(tmpdirname) if f.is_dir()]
        if len(subfolders) == 1:
            src_package_dir = subfolders[0]
        else:
            src_package_dir = tmpdirname

        create_package(args, package, src_package_dir)


def install_package_from_path(args, package: PackageExternal, path: str):
    create_package(args, package, path)


def run():
    if 'install' not in sys.argv:
        conan_command = [sys.executable, "-m", "conans.conan", *sys.argv[1:]]
        with Popen(conan_command) as proc:
            pass

    args = parse_args()
    file_path = os.path.join(os.path.abspath(args.path_or_reference), "conanfile.txt")
    if os.path.exists(file_path):
        requires: List[PackageExternal] = []
        options: Dict[str, str] = {}

        with open(file_path) as f:
            new_file_lines = []
            context = ConanFileSection.No
            for line in f.readlines():
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
                if line.strip().startswith("#"):
                    new_file_lines.append(str(line))
                    continue

                external_package_match = external_package_re.match(line)
                option_match = option_re.match(line)
                if external_package_match:
                    name = external_package_match.group('package')
                    version = external_package_match.group('version')
                    if not name or not version:
                        raise Exception("name and version of package is required !!"
                                        "Please, specify it in following format: package/version")
                    user = external_package_match.group('user')
                    channel = external_package_match.group('channel')
                    protocol = external_package_match.group('protocol')
                    url = external_package_match.group('url')
                    tag = external_package_match.group('tag')
                    package_info = PackageExternal(name=name,
                                                   version=version,
                                                   user=user,
                                                   channel=channel,
                                                   protocol=protocol,
                                                   url=url,
                                                   tag=tag)
                    requires.append(package_info)
                    new_file_lines.append("{}\n".format(package_info.full_package_name))
                elif option_match:
                    name = option_match.group('name')
                    option = option_match.group('option')
                    value = option_match.group('value')
                    options[name] = "{}={}".format(option, value)
                else:
                    new_file_lines.append(str(line))

        for package in requires:
            if package.name in options:
                package.options.append(options[package.name])

        for package in requires:
            if package.protocol == 'git':
                install_package_from_git(args, package)
            elif package.protocol == 'zip':
                install_package_from_zip(args, package)
            elif package.protocol == 'path':
                conanfile_path = os.path.dirname(file_path)
                conanfile_posix_path = Path(conanfile_path).as_posix()
                path = str(Path("{}/{}".format(conanfile_posix_path, url)))
                install_package_from_path(args, package, path)
        with tempfile.TemporaryDirectory() as tmpdirname:
            new_conanfile = os.path.join(tmpdirname, "conanfile.txt")
            with open(new_conanfile, mode='w') as file:
                file.writelines(new_file_lines)
            run_conan_install_command(args, new_conanfile)


if __name__ == '__main__':
    run()
