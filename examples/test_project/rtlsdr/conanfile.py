import os
import shutil

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout, CMakeDeps
from conan.tools.files import copy, save
from conan.tools.scm import Git


class LibRtlSdrConan(ConanFile):
    name = "rtlsdr"
    version = "v0.9.0"

    # Optional metadata
    license = "MIT"
    author = "KrakenRF"
    url = "https://github.com/krakenrf/librtlsdr"
    description = "Library to access RTL-SDR software defined radios"
    topics = ("sdr", "rtl-sdr", "radio")
    settings = "os", "compiler", "build_type", "arch"

    def layout(self):
        cmake_layout(self)

    def source(self):
        git = Git(self)
        self.output.info(f"Start cloning rtlsdr ...")
        git.clone("https://github.com/krakenrf/librtlsdr.git", target=".")
        git.checkout("master")

    def requirements(self):
        pass

    def build_requirements(self):
        self.tool_requires("cmake/[>=3.15]")

    def generate(self):
        deps = CMakeDeps(self)
        tc = CMakeToolchain(self)
        if self.settings.os == "Linux":
            tc.variables["INSTALL_UDEV_RULES"] = "ON"
        deps.generate()
        tc.generate()

    def build(self):
        cmake = CMake(self)
        self.output.info(f"Start build ...")
        cmake.configure(build_script_folder=".")
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

        shutil.copy(f"{self.build_folder}/src/librtlsdr.a", f"{self.package_folder}/lib")
        shutil.copy(f"{self.build_folder}/src/librtlsdr.dylib", f"{self.package_folder}/lib")

        if self.settings.os == "Linux":
            copy(self,
                 "rtl-sdr.rules",
                 src=os.path.join(self.build_folder, "librtlsdr", "udev"),
                 dst=os.path.join(self.package_folder, "udev"))

    def package_info(self):
        # Provide library information to consumers
        self.cpp_info.libs = ["rtlsdr"]
        self.cpp_info.libdirs = [f"{self.package_folder}/lib"]

        # Set rpath for dynamic library (optional, for macOS/Linux)
        if self.settings.os in ["Macos", "Linux"]:
            self.cpp_info.system_libs = ["dl", "pthread"]  # Add system dependencies if necessary

    def deploy(self):
        if self.settings.os == "Linux":
            # Blacklist the kernel module on Linux
            blacklist_file = "/etc/modprobe.d/blacklist-dvb_usb_rtl28xxu.conf"
            content = "blacklist dvb_usb_rtl28xxu"
            save(self, blacklist_file, content, append=True)
            self.output.info(f"Appended to {blacklist_file}: {content}")
