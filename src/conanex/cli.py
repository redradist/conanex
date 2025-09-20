import argparse
import copy
import os
import sys
from subprocess import Popen, PIPE
from typing import List, Optional

from filelock import FileLock

from .types import ExternalPackage, Package

nenv = copy.copy(os.environ)
paths = nenv["PATH"].split(os.pathsep)
npaths = []
for path in paths:
    if path not in npaths:
        npaths.append(path)
nenv["PATH"] = os.pathsep.join(npaths)


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
    info_parser.add_argument('-s:b', '--settings:build', type=str, action='append', help='SETTINGS_BUILD')
    info_parser.add_argument('-s:h', '--settings:host', type=str, action='append', help='SETTINGS_HOST')
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
    install_parser.add_argument('-o', '--options', type=str, action='append', help='OPTIONS_HOST')
    install_parser.add_argument('-o:b', '--options:build', type=str, action='append', help='OPTIONS_BUILD')
    install_parser.add_argument('-o:h', '--options:host', type=str, action='append', help='OPTIONS_HOST')
    install_parser.add_argument('-o:a', '--options:all', type=str, action='append', help='OPTIONS_ALL')
    install_parser.add_argument('-s', '--settings', type=str, action='append', help='SETTINGS_HOST')
    install_parser.add_argument('-s:b', '--settings:build', type=str, action='append', help='SETTINGS_BUILD')
    install_parser.add_argument('-s:h', '--settings:host', type=str, action='append', help='SETTINGS_HOST')
    install_parser.add_argument('-s:a', '--settings:all', type=str, action='append', help='SETTINGS_ALL')
    install_parser.add_argument('-c', '--conf', type=str, action='append', help='CONF_HOST')
    install_parser.add_argument('-c:b', '--conf:build', type=str, action='append', help='CONF_BUILD')
    install_parser.add_argument('-c:h', '--conf:host', type=str, action='append', help='CONF_HOST')
    install_parser.add_argument('-c:a', '--conf:all', type=str, action='append', help='CONF_ALL')
    install_parser.add_argument('--path', dest="path_or_reference",type=str)
    install_parser.add_argument('--tools', dest='tool-requires', type=str, nargs='+', help='TOOL_REQUIRES')
    install_parser.add_argument('requires', type=str, nargs='*', help='REQUIRES')
    return parser.parse_args()


def build_create_args(args, tmpdirname, package: ExternalPackage):
    new_args = ['create']

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


def build_install_args(args, path_or_reference: Optional[ExternalPackage | str]):
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
            new_args.append('--requires')
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

    if path_or_reference:
        if isinstance(path_or_reference, ExternalPackage):
            new_args.append(f'--requires={path_or_reference.full_package_name}')
        else:
            new_args.append(path_or_reference)
    return new_args


def run_command(command: List[str], ignore_output=False):
    with Popen(command, stdout=PIPE, stderr=PIPE, env=nenv) as proc:
        stdout, stderr = proc.communicate()
        stdout = str(stdout, encoding='utf-8', errors='replace')
        stderr = str(stderr, encoding='utf-8', errors='replace')
    exit_code = proc.returncode
    if not ignore_output:
        print(stdout)
    if exit_code != 0:
        raise Exception(f"Failed command\n{' '.join(command)}:\n{stderr}")

    return exit_code, stdout, stderr


def get_global_filelock_path() -> FileLock:
    _, conan_home, _ = run_command([sys.executable, "-m", "conans.conan", "config", "home"], ignore_output=True)
    return FileLock(os.path.join(conan_home.strip(), "conan.lock"))


def get_filelock_path(package: Package) -> FileLock:
    _, conan_home, _ = run_command([sys.executable, "-m", "conans.conan", "config", "home"], ignore_output=True)
    if package.user is not None:
        lock = FileLock(os.path.join(conan_home.strip(), f"{package.name}_{package.version}_{package.user}_{package.channel}.lock"))
    else:
        lock = FileLock(os.path.join(conan_home.strip(), f"{package.name}_{package.version}.lock"))
    return lock


def run_git_command(command_args):
    git_command = ["git", *command_args]
    run_command(git_command)


def run_git_clone_command(tag: Optional[str], temp_dir, url):
    if tag:
        run_git_command(["clone", "--recursive", '-b', tag, url, temp_dir])
    else:
        run_git_command(["clone", "--recursive", url, temp_dir])


def run_conan_command(command_args, ignore_output=False):
    conan_command = [sys.executable, "-m", "conans.conan", *command_args]
    run_command(conan_command, ignore_output=ignore_output)


def _run_graph_info(package: ExternalPackage, temp_dir):
    graph_info_command_args = ["graph", "info", "-c", "tools.build:download_source=True"]
    if package.name:
        graph_info_command_args.append('--name')
        graph_info_command_args.append(package.name)
    if package.version:
        graph_info_command_args.append('--version')
        graph_info_command_args.append(package.version)
    if package.user:
        graph_info_command_args.append('--user')
        graph_info_command_args.append(package.user)
    if package.channel:
        graph_info_command_args.append('--channel')
        graph_info_command_args.append(package.channel)

    graph_info_command_args.append(temp_dir)

    run_conan_command(graph_info_command_args, ignore_output=True)


def run_conan_create_command(args, package: ExternalPackage, temp_dir):
    create_args = build_create_args(args, temp_dir, package)
    run_conan_command(create_args, ignore_output=True)


def run_conan_install_command(args, path_or_reference):
    install_args = build_install_args(args, path_or_reference)
    run_conan_command(install_args)


def run_conan_remove_command(path_or_reference):
    run_conan_command(["remove", "--confirm", path_or_reference])
