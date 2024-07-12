import os
from pathlib import Path

from conan import ConanFile
from conanex.main import install_package_from_git, install_package_from_zip, install_package_from_path, \
    install_package_from_conanfile, install_package_from_remote, ExternalPackage


class ConanExFile(ConanFile):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_args(self):
        args = object()

        # Reference
        args.name = self.name
        args.version = self.version
        args.user = self.user
        args.channel = self.channel

        # Metadata
        args.url = self.url
        args.license = self.license
        args.author = self.author
        args.description = self.description
        args.topics = self.topics
        args.homepage = self.homepage

        args.build_policy = self.build_policy
        args.upload_policy = self.upload_policy

        args.exports = self.exports
        args.exports_sources = self.exports_sources

        args.generators = self.generators
        args.revision_mode = self.revision_mode

        # Binary model: Settings and Options
        args.settings = self.settings
        args.options = self.options
        args.default_options = self.default_options
        args.default_build_options = self.default_build_options
        args.package_type = self.package_type

        args.implements = self.implements

        args.provides = self.provides
        args.deprecated = self.deprecated

        args.win_bash = self.win_bash
        args.win_bash_run = self.win_bash_run

        # #### Requirements
        args.requires = self.requires
        args.tool_requires = self.tool_requires
        args.build_requires = self.build_requires
        args.test_requires = self.test_requires
        args.tested_reference_str = self.tested_reference_str

        args.no_copy_source = self.no_copy_source
        args.recipe_folder = self.recipe_folder

        # Package information
        args.cpp = self.cpp
        args.buildenv_info = self.buildenv_info
        args.runenv_info = self.runenv_info
        args.conf_info = self.conf_info

        return args

    def __call__(self, *args, **kwargs):
        if 'package' in kwargs:
            package: ExternalPackage = kwargs['package']
            args = self.get_args()
            if package.protocol == 'git':
                install_package_from_git(args, package)
            elif package.protocol == 'zip':
                install_package_from_zip(args, package)
            elif package.protocol == 'path':
                conanfile = package.url
                conanfile_path = os.path.dirname(conanfile)
                conanfile_posix_path = Path(conanfile_path).as_posix()
                path = str(Path("{}/{}".format(conanfile_posix_path, package.url)))
                install_package_from_path(args, package, path)
            elif package.protocol == 'conan':
                install_package_from_conanfile(args, package)
            elif package.protocol == 'remote':
                install_package_from_remote(args, package)
        else:
            self.requires(*args, **kwargs)


__version__ = '2.1.1'
