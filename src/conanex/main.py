import copy
import hashlib
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import sys

from io import BytesIO
from pathlib import Path
from subprocess import Popen, STDOUT, PIPE, DEVNULL
from typing import List, Dict, Optional
from urllib.parse import urlparse
from urllib.request import urlopen
from zipfile import ZipFile

from conan import conan_version

from .cli import nenv, parse_info_args, parse_install_args, run_git_clone_command, \
    run_conan_create_command, run_conan_install_command, run_conan_remove_command, run_conan_command, get_filelock_path, \
    get_global_filelock_path
from .types import ExternalPackage, ConanFileSection, ConanArgs, Package

detect_conan_center_package = r"(?P<package>(-|\w)+)(\/(?P<version>[.\d\w]+))?(@((?P<user>\w+)\/(?P<channel>\w+))?)?"
detect_conan_center_package_re = re.compile(detect_conan_center_package)

detect_external_package = r"(?P<package>(-|\w)+)(\/(?P<version>[.\d\w]+))?(@((?P<user>\w+)\/(?P<channel>\w+))?)?\s*\{"
detect_external_package_re = re.compile(detect_external_package)
external_package_property = r"^\s*(?P<property>.+?)\s*=\s*(?P<value>.+?)\s*$"
external_package_property_re = re.compile(external_package_property)
new_section = r"\[.*\]"
new_section_re = re.compile(new_section)
option = r"\s*(?P<name>.*?)\s*:\s*(?P<option>.*?)\s*=\s*(?P<value>.*)"
option_re = re.compile(option)


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
    conan_command = [sys.executable, "-m", "conans.conan", "cache", "path", package.package_name]
    with Popen(conan_command, stdout=PIPE, stderr=PIPE, env=nenv) as proc:
        _, search_errors = proc.communicate(timeout=15)
        search_errors = str(search_errors, encoding='utf-8')
        return "ERROR: Recipe" not in search_errors


def uri_validator(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def extract_from_zip(temp_dir, url, package: ExternalPackage):
    if uri_validator(url):
        print("wget {}".format(url))
        resp = urlopen(url)
        bytes_io = BytesIO(resp.read())
        verify_hash_code(bytes_io, package)
        with ZipFile(bytes_io) as zipfile:
            zipfile.extractall(temp_dir)
    else:
        verify_hash_code(url, package)
        with ZipFile(url, 'r') as zipfile:
            zipfile.extractall(temp_dir)


def extract_from_tar(temp_dir, url, archive, package: ExternalPackage):
    if uri_validator(url):
        print("wget {}".format(url))
        resp = urlopen(url)
        bytes_io = BytesIO(resp.read())
        verify_hash_code(bytes_io, package)
        with tarfile.open(fileobj=bytes_io, mode="r:{}".format(archive)) as tar:
            tar.extractall(temp_dir)
    else:
        verify_hash_code(url, package)
        with tarfile.open(name=url, mode=f'r:{archive}') as tar:
            tar.extractall(temp_dir)


def install_package_from_git(args, package: ExternalPackage):
    with tempfile.TemporaryDirectory() as temp_dir:
        run_git_clone_command(package.attrs["tag"], temp_dir, package.url)
        run_conan_create_command(args, package, temp_dir)


def install_package_from_zip(args, package: ExternalPackage):
    with tempfile.TemporaryDirectory() as temp_dir:
        filename, file_ext = os.path.splitext(package.url)
        file_ext = file_ext[1:]
        if file_ext == 'zip':
            extract_from_zip(temp_dir, package.url, package)
        elif os.path.splitext(filename)[1][1:] == 'tar':
            extract_from_tar(temp_dir, package.url, file_ext, package)

        subfolders = [f.path for f in os.scandir(temp_dir) if f.is_dir()]
        if len(subfolders) == 1:
            src_package_dir = subfolders[0]
        else:
            src_package_dir = temp_dir

        run_conan_create_command(args, package, src_package_dir)


def install_package_from_path(args, package: ExternalPackage, path: str):
    run_conan_create_command(args, package, path)


def install_package_from_conanfile(args, package: ExternalPackage):
    if not package.url.endswith("conanfile.py"):
        raise Exception("Url [{}] should contain conanfile.py".format(package.url))
    with tempfile.TemporaryDirectory() as temp_dir:
        if uri_validator(package.url):
            print("wget {}".format(package.url))
            resp = urlopen(package.url)
            new_conanfile_path = os.path.join(temp_dir, "conanfile.py")
            bytes_io = BytesIO(resp.read())
            with open(new_conanfile_path, "wb") as f:
                f.write(bytes_io.getbuffer())
            verify_hash_code(new_conanfile_path, package)
        else:
            shutil.copy2(package.url, temp_dir)

        run_conan_create_command(args, package, temp_dir)


def install_package_from_remote(args, package: ExternalPackage):
    install_args = copy.copy(args)
    install_args.remote = package.url
    run_conan_install_command(install_args, package)


def is_command_to_modify():
    return 'install' in sys.argv or \
           'info' in sys.argv


def generate_new_conanfile(args, origin_conanfile_path: str, new_conanfile: str):
    if os.path.exists(origin_conanfile_path):
        external_requires: List[ExternalPackage] = []
        conan_center_requires: List[Package] = []
        options: Dict[str, List[str]] = {}

        with open(origin_conanfile_path) as f:
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

                conan_center_package_match = detect_conan_center_package_re.match(line)
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
                        ext_protocol = external_package_property_match.group('property')
                        ext_value = external_package_property_match.group('value')
                        if ext_protocol == 'conan':
                            char_back = ''
                            if '"' in ext_value:
                                char_back = '"'
                                ext_value = ext_value.strip('"')
                            if "'" in ext_value:
                                char_back = "'"
                                ext_value = ext_value.strip("'")
                            if not os.path.isabs(ext_value):
                                ext_value = os.path.join(os.path.dirname(origin_conanfile_path), ext_value)
                            ext_value = f"{char_back}{ext_value}{char_back}"
                        properties[ext_protocol] = ext_value

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
                    external_requires.append(package_info)
                    full_package_name = package_info.full_package_name
                    if full_package_name[-1] == '@':
                        full_package_name = full_package_name[:-1]
                    new_file_lines.append("{}\n".format(full_package_name))
                elif option_match:
                    name = option_match.group('name')
                    option = option_match.group('option')
                    value = option_match.group('value')

                    option_str = "{}={}".format(option, value)
                    if name == "*":
                        if "*" not in options:
                            options["*"] = []
                        options["*"].append(option_str)
                    else:
                        if name not in options:
                            options[name] = []
                        options[name].append(option_str)

                    new_file_lines.append(str(line))
                elif conan_center_package_match:
                    name = conan_center_package_match.group('package')
                    version = conan_center_package_match.group('version')
                    user = conan_center_package_match.group('user')
                    channel = conan_center_package_match.group('channel')
                    conan_center_requires.append(Package(name=name, version=version, user=user, channel=channel))
                    new_file_lines.append(str(line))
                else:
                    new_file_lines.append(str(line))

            if len(external_package_lines) > 0:
                raise Exception("external package not fully specified:\n{}\n\n"
                                "Please, check a syntax for conanex !!"
                                .format(''.join(external_package_lines)))

        for package in external_requires:
            if "*" in options:
                package.options.extend(options["*"])

            for option_name, option_values in options.items():
                name, version = option_name.split("/")
                if (name == package.name and version == "*") or \
                   (name == package.name and version == package.version):
                    package.options.extend(option_values)

            package.options = list(set(package.options))

        with open(new_conanfile, mode='w') as file:
            file.writelines(new_file_lines)

        return external_requires, conan_center_requires


def regenerate_conanfile(args, command):
    if '@' in args.path_or_reference:
        command_index = sys.argv.index(command)
        command_arg = copy.copy(sys.argv)[command_index:]
        run_conan_command(command_arg)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            origin_conanfile_path = args.path_or_reference
            new_conanfile_path = os.path.join(temp_dir, "conanfile.txt")
            generate_new_conanfile(args, origin_conanfile_path, new_conanfile_path)
            command_index = sys.argv.index(command)
            command_arg = copy.copy(sys.argv)[command_index:]
            path_or_reference_index = command_arg.index(args.path_or_reference)
            command_arg[path_or_reference_index] = temp_dir
            run_conan_command(command_arg)


def install_external_packages(args, requires: List[ExternalPackage]):
    origin_conanfile_path = args.path_or_reference
    for package in requires:
        if package.protocol in ['git', 'zip', 'path', 'conan', 'remote']:
            if is_package_in_cache(package):
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
                    conanfile_path = os.path.dirname(origin_conanfile_path)
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
        if '--version' in sys.argv:
            print(f"ConanEx version {__version__}, Conan version {conan_version}")
            return

        conan_command = [sys.executable, "-m", "conans.conan", *sys.argv[1:]]
        with Popen(conan_command, env=nenv) as proc:
            pass
        return

    if 'info' in sys.argv:
        args = parse_info_args()
        regenerate_conanfile(args, 'info')
    elif 'install' in sys.argv:
        args = parse_install_args()
        args = ConanArgs(args)
        new_conanfile_path = None
        if args.path_or_reference:
            with tempfile.TemporaryDirectory() as temp_dir:
                new_conanfile_path = os.path.join(temp_dir, "conanfile.txt")
                if os.path.isdir(args.path_or_reference):
                    args.path_or_reference = os.path.join(os.path.abspath(args.path_or_reference), "conanfile.txt")
                elif os.path.isfile(args.path_or_reference):
                    args.path_or_reference = args.path_or_reference
                else:
                    raise Exception("path_or_reference should be either directory or file")
                external_requires, conan_center_requires = generate_new_conanfile(args, args.path_or_reference, new_conanfile_path)
                install_external_packages(args, external_requires)

        run_conan_install_command(args, new_conanfile_path)


def main():
    if "--global-lock" in sys.argv:
        lock_option_index = sys.argv.index("--global-lock")
        if lock_option_index < 2:
            raise Exception("Global lock should be after the command")

        sys.argv.remove("--global-lock")

        with get_global_filelock_path():
            run()
    else:
        run()


__version__ = '2.3.0'

if __name__ == '__main__':
    main()
