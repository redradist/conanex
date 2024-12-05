import os
import shutil
from copy import copy

from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps
from conan.tools.scm import Git


class HackRFRecipe(ConanFile):
    name = "hackrf"
    version = "v2024.02.1"
    package_type = "library"

    # Optional metadata
    license = "MIT"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of hackrf package here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    def source(self):
        os.makedirs(self.source_folder, exist_ok=True)

        git = Git(self)
        self.output.info(f"Start cloning hackrf ...")
        git.clone(url="git@github.com:greatscottgadgets/hackrf.git", target=".")
        git.checkout("v2024.02.1")

    def config_options(self):
        if self.settings.os == "Windows":
            self.options.rm_safe("fPIC")

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        cmake_layout(self)
        self.folders.set_base_package(f"packages/{self.settings.build_type}")

    def generate(self):
        deps = CMakeDeps(self)
        tc = CMakeToolchain(self)
        self.output.info(f"Start generate ...")
        deps.generate()
        tc.generate()

    def build(self):
        os.makedirs(self.build_folder, exist_ok=True)

        cmake = CMake(self)
        self.output.info(f"Start build ...")
        cmake.configure(build_script_folder=f"./host")
        cmake.build()

    def package(self):
        os.makedirs(self.package_folder, exist_ok=True)

        cmake = CMake(self)
        cmake.install()

        shutil.copy(f"{self.build_folder}/libhackrf/src/libhackrf.a", f"{self.package_folder}/lib")
        shutil.copy(f"{self.build_folder}/libhackrf/src/libhackrf.dylib", f"{self.package_folder}/lib")

    def package_info(self):
        self.cpp_info.libs = ["hackrf"]
        self.cpp_info.libdirs = [f"{self.package_folder}/lib"]

        # Set rpath for dynamic library (optional, for macOS/Linux)
        if self.settings.os in ["Macos", "Linux"]:
            self.cpp_info.system_libs = ["dl", "pthread"]  # Add system dependencies if necessary
