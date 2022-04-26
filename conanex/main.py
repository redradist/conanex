import os
import re
import tempfile
from subprocess import Popen, PIPE, DEVNULL

import argparse
import sys


external_package = r"(?P<package>(-|\w)+)(\/(?P<version>[.\d]+))?(@((?P<user>\w+)\/(?P<channel>\w+))?)?\s*\{\s*(?P<protocol>(git|https))\s*=\s*\"(?P<url>.+?)\"\s*(,\s*tag\s*=\s*\"(?P<tag>.+?)\"\s*)?\}"
external_package_re = re.compile(external_package)


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    install_parser = subparsers.add_parser('install')
    install_parser.add_argument('-g', type=str, help='GENERATOR')
    install_parser.add_argument('-if', type=str, help='INSTALL_FOLDER')
    install_parser.add_argument('-of', type=str, help='OUTPUT_FOLDER')
    install_parser.add_argument('-m', type=str, nargs='+', help='MANIFESTS')
    install_parser.add_argument('-mi', type=str, nargs='+', help='MANIFESTS_INTERACTIVE')
    install_parser.add_argument('-v', type=str, nargs='+', help='VERIFY')
    install_parser.add_argument('--no-imports', action='store_true')
    install_parser.add_argument('--build-require', action='store_true')
    install_parser.add_argument('-j', type=str, help='JSON')
    install_parser.add_argument('-b', type=str, nargs='+', help='BUILD')
    install_parser.add_argument('-r', type=str, help='REMOTE')
    install_parser.add_argument('-u', type=str)
    install_parser.add_argument('-l', type=str, help='LOCKFILE')
    install_parser.add_argument('--lockfile-out', type=str, help='LOCKFILE_OUT')
    install_parser.add_argument('-e', type=str, help='ENV_HOST')
    install_parser.add_argument('-e:b', type=str, help='ENV_BUILD')
    install_parser.add_argument('-e:h', type=str, help='ENV_HOST')
    install_parser.add_argument('-o', type=str, help='OPTIONS_HOST')
    install_parser.add_argument('-o:b', type=str, help='OPTIONS_BUILD')
    install_parser.add_argument('-o:h', type=str, help='OPTIONS_HOST')
    install_parser.add_argument('-pr', type=str, help='PROFILE_HOST')
    install_parser.add_argument('-pr:b', type=str, help='PROFILE_BUILD')
    install_parser.add_argument('-pr:h', type=str, help='PROFILE_HOST')
    install_parser.add_argument('-s', type=str, help='SETTINGS_HOST')
    install_parser.add_argument('-s:b', type=str, help='SETTINGS_BUILD')
    install_parser.add_argument('-s:h', type=str, help='SETTINGS_HOST')
    install_parser.add_argument('-c', type=str, help='CONF_HOST')
    install_parser.add_argument('-c:b', type=str, help='CONF_BUILD')
    install_parser.add_argument('-c:h', type=str, help='CONF_HOST')
    install_parser.add_argument('--lockfile-node-id', type=str, help='LOCKFILE_NODE_ID')
    install_parser.add_argument('--require-override', type=str, help='REQUIRE_OVERRIDE')
    install_parser.add_argument('path_or_reference', type=str)
    install_parser.add_argument('reference', type=str, nargs='?')
    return parser.parse_args()


def build_create_args(args, tmpdirname, package):
    new_args = ['create']
    if args.build_require:
        new_args.append('--build-require')
    if args.u:
        new_args.append('-u')
    if args.require_override:
        new_args.append('--require-override')
        new_args.append(args.require_override)
    if args.m:
        new_args.append('-m')
        new_args.extend(args.m)
    if args.mi:
        new_args.append('-mi')
        new_args.extend(args.mi)
    if args.v:
        new_args.append('-v')
        new_args.extend(args.v)
    if args.b:
        new_args.append('-b')
        new_args.extend(args.b)
    if args.r:
        new_args.append('-r')
        new_args.append(args.r)
    if args.l:
        new_args.append('-l')
        new_args.append(args.l)
    if args.lockfile_out:
        new_args.append('-lockfile-out')
        new_args.append(args.lockfile_out)
    if args.e:
        new_args.append('-e')
        new_args.append(args.e)
    if hasattr(args, 'e:b') and getattr(args, 'e:b'):
        new_args.append('-e:b')
        new_args.append(getattr(args, 'e:b'))
    if hasattr(args, 'e:h') and getattr(args, 'e:h'):
        new_args.append('-e:h')
        new_args.append(getattr(args, 'e:h'))
    if hasattr(args, 'e:o') and getattr(args, 'e:o'):
        new_args.append('-e:o')
        new_args.append(getattr(args, 'e:o'))
    if args.pr:
        new_args.append('-pr')
        new_args.append(args.pr)
    if hasattr(args, 'pr:b') and getattr(args, 'pr:b'):
        new_args.append('-pr:b')
        new_args.append(getattr(args, 'pr:b'))
    if hasattr(args, 'pr:h') and getattr(args, 'pr:h'):
        new_args.append('-pr:h')
        new_args.append(getattr(args, 'pr:h'))
    if args.s:
        new_args.append('-s')
        new_args.append(args.s)
    if hasattr(args, 's:b') and getattr(args, 's:b'):
        new_args.append('-s:b')
        new_args.append(getattr(args, 's:b'))
    if hasattr(args, 's:h') and getattr(args, 's:h'):
        new_args.append('-s:h')
        new_args.append(getattr(args, 's:h'))
    if args.c:
        new_args.append('-c')
        new_args.append(args.c)
    if hasattr(args, 'c:b') and getattr(args, 'c:b'):
        new_args.append('-c:b')
        new_args.append(getattr(args, 'c:b'))
    if hasattr(args, 'c:h') and getattr(args, 'c:h'):
        new_args.append('-c:h')
        new_args.append(getattr(args, 'c:h'))
    new_args.append(tmpdirname)
    new_args.append(package)
    return new_args


def build_install_args(args, tmpfilename):
    new_args = ['install']
    if args.g:
        new_args.append('-g')
        new_args.append(args.g)
    if hasattr(args, 'if') and getattr(args, 'if'):
        new_args.append('-if')
        new_args.append(getattr(args, 'if'))
    if hasattr(args, 'of') and getattr(args, 'of'):
        new_args.append('-of')
        new_args.append(getattr(args, 'of'))
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
    if args.j:
        new_args.append('-j')
        new_args.append(args.j)
    if args.u:
        new_args.append('-u')
    if args.require_override:
        new_args.append('--require-override')
        new_args.append(args.require_override)
    if args.m:
        new_args.append('-m')
        new_args.extend(args.m)
    if args.mi:
        new_args.append('-mi')
        new_args.extend(args.mi)
    if args.v:
        new_args.append('-v')
        new_args.extend(args.v)
    if args.b:
        new_args.append('-b')
        new_args.extend(args.b)
    if args.r:
        new_args.append('-r')
        new_args.append(args.r)
    if args.l:
        new_args.append('-l')
        new_args.append(args.l)
    if args.lockfile_out:
        new_args.append('-lockfile-out')
        new_args.append(args.lockfile_out)
    if args.e:
        new_args.append('-e')
        new_args.append(args.e)
    if hasattr(args, 'e:b') and getattr(args, 'e:b'):
        new_args.append('-e:b')
        new_args.append(getattr(args, 'e:b'))
    if hasattr(args, 'e:h') and getattr(args, 'e:h'):
        new_args.append('-e:h')
        new_args.append(getattr(args, 'e:h'))
    if hasattr(args, 'e:o') and getattr(args, 'e:o'):
        new_args.append('-e:o')
        new_args.append(getattr(args, 'e:o'))
    if args.pr:
        new_args.append('-pr')
        new_args.append(args.pr)
    if hasattr(args, 'pr:b') and getattr(args, 'pr:b'):
        new_args.append('-pr:b')
        new_args.append(getattr(args, 'pr:b'))
    if hasattr(args, 'pr:h') and getattr(args, 'pr:h'):
        new_args.append('-pr:h')
        new_args.append(getattr(args, 'pr:h'))
    if args.s:
        new_args.append('-s')
        new_args.append(args.s)
    if hasattr(args, 's:b') and getattr(args, 's:b'):
        new_args.append('-s:b')
        new_args.append(getattr(args, 's:b'))
    if hasattr(args, 's:h') and getattr(args, 's:h'):
        new_args.append('-s:h')
        new_args.append(getattr(args, 's:h'))
    if args.c:
        new_args.append('-c')
        new_args.append(args.c)
    if hasattr(args, 'c:b') and getattr(args, 'c:b'):
        new_args.append('-c:b')
        new_args.append(getattr(args, 'c:b'))
    if hasattr(args, 'c:h') and getattr(args, 'c:h'):
        new_args.append('-c:h')
        new_args.append(getattr(args, 'c:h'))
    new_args.append(tmpfilename)
    return new_args


def run():
    args = parse_args()
    if args.command == 'install':
        file_path = os.path.join(os.path.abspath(args.path_or_reference), "conanfile.txt")
        with open(file_path) as f:
            new_file_lines = []
            for line in f.readlines():
                external_package_match = external_package_re.match(line)
                if external_package_match:
                    name = external_package_match.group('package')
                    version = external_package_match.group('version')
                    if not name or not version:
                        raise Exception(
                            f"name and version of package is required !! Please, specify it in following format: package/version")
                    user = external_package_match.group('user')
                    channel = external_package_match.group('channel')
                    protocol = external_package_match.group('protocol')
                    url = external_package_match.group('url')
                    tag = external_package_match.group('tag')

                    with tempfile.TemporaryDirectory() as tmpdirname:
                        git_clone_command = ["git", "clone", '-b', tag, url, tmpdirname]
                        if tag:
                            git_clone_command = ["git", "clone", "--recursive", '-b', tag, url, tmpdirname]
                        else:
                            git_clone_command = ["git", "clone", "--recursive", url, tmpdirname]
                        with Popen(git_clone_command, stdout=DEVNULL, stderr=DEVNULL) as proc:
                            pass
                        if version:
                            package_name = f"{name}/{version}"
                        else:
                            package_name = f"{name}"
                        if user and channel:
                            full_package_name = f"{package_name}@{user}/{channel}"
                        else:
                            full_package_name = f"{package_name}@"
                        if not tag:
                            print(f"\nBuilding {full_package_name} from sources:")
                            create_args = build_create_args(args, tmpdirname, full_package_name)
                            conan_create_command = [sys.executable, "-m", "conans.conan", *create_args]
                            with Popen(conan_create_command) as proc:
                                pass
                        else:
                            with Popen([sys.executable, "-m", "conans.conan", "search", package_name],
                                       stdout=PIPE) as proc:
                                search_results = str(proc.stdout.read())
                                if "Existing package recipes:" in search_results:
                                    print(f"{full_package_name} was found in cache")
                                else:
                                    print(f"\nBuilding {full_package_name} from sources:")
                                    create_args = build_create_args(args, tmpdirname, full_package_name)
                                    conan_create_command = [sys.executable, "-m", "conans.conan", *create_args]
                                    with Popen(conan_create_command) as proc:
                                        pass
                        new_file_lines.append(f"{full_package_name}\n")
                else:
                    new_file_lines.append(str(line))
            with tempfile.TemporaryDirectory() as tmpdirname:
                new_conanfile = os.path.join(tmpdirname, "conanfile.txt")
                with open(new_conanfile, mode='w') as file:
                    file.writelines(new_file_lines)
                install_args = build_install_args(args, new_conanfile)
                conan_install_command = [sys.executable, "-m", "conans.conan", *install_args]
                with Popen(conan_install_command) as proc:
                    pass
    else:
        conan_command = [sys.executable, "-m", "conans.conan", *sys.argv[1:]]
        with Popen(conan_command) as proc:
            pass


if __name__ == '__main__':
    run()
