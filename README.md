## ConanEx - Conan Extended, conan that more decentralize

### Overview
What it allows ?

Consider the following `conanfile.txt`:

```console
[requires]
poco/1.9.4
flatbuffers/22.10.26 {
    zip = 'https://github.com/google/flatbuffers/archive/refs/tags/v22.10.26.zip',
    sha256 = 'B97C7C017B05F20B17939FEBD413C75201F5B704C8DE49ADB0B35A70D50478CD'
}
ctre/3.6 { remote = "conancenter" }
# Examples:
# flatbuffers/2.0.0 {
#     git = https://github.com/google/flatbuffers,
#     tag = v2.0.0
# }
# flatbuffers/2.0.0@user/testing { zip = "https://github.com/google/flatbuffers/archive/refs/tags/v2.0.0.tar.gz" }
# flatbuffers/2.0.0 { conan = "https://raw.githubusercontent.com/google/flatbuffers/master/conanfile.py" }
# CTRE/3.6 { git = "https://github.com/hanickadot/compile-time-regular-expressions" }
# CTRE/3.6 { path = "../../../../compile-time-regular-expressions" }

[options]
flatbuffers:shared=True
poco:shared=True
```
As you can see in this file we have 5 additional ways to install package

Lets describe them:
1) `git` allow to download package using Git and run `conanfile.py` located in root directory
2) `zip` (_url/file_path_) allow installing package from archive, unpack it and run _conanfile.py_ located in root directory.
   There are the following formats that supported: _zip_, _tar.gz_, _tar.bz2_
3) `conan` (_url/file_path_) if you receipt is completely independent, then you could specify url/path to it to create package.
   Independent means that receipt could download source files by itself.
4) `path` allow to install package from folder
5) `remote` specify separate remote for this particular package

_url/file_path_ supports the hash calculation with options: `md5`, `sha256` and `sha512`

To install `conanex`:
```console
python3 -m pip install conanex
```

To use `conanex` use it the same way you use `conan`:
```console
conanex install <path_to_conanfile.txt> -pr=<path_to_profile>
```

If you are using `cmake-conan`:
```cmake
if(NOT EXISTS "${CMAKE_BINARY_DIR}/conan.cmake")
    message(STATUS "Downloading conan.cmake from https://github.com/conan-io/cmake-conan")
    file(DOWNLOAD "https://raw.githubusercontent.com/conan-io/cmake-conan/0.18.1/conan.cmake"
         "${CMAKE_BINARY_DIR}/conan.cmake"
         TLS_VERIFY ON)
endif()

include(${CMAKE_BINARY_DIR}/conan.cmake)

set(CONAN_COMMAND conanex)
conan_cmake_autodetect(settings)
conan_cmake_install(PATH_OR_REFERENCE ${CMAKE_CURRENT_LIST_DIR}
                    BUILD missing
                    REMOTE conancenter
                    SETTINGS ${settings})
```
Only thing you need is to specify `set(CONAN_COMMAND conanex)` before any conan command
