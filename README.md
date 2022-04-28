## ConanEx - Conan Extended, conan that more decentralize

### Overview
What it allows ?

Consider the following `conanfile.txt`:

```console
[requires]
poco/1.9.4
#flatbuffers/2.0.0 { git = "https://github.com/google/flatbuffers", tag = "v2.0.0" }
#flatbuffers/2.0.0 { zip = "https://github.com/google/flatbuffers/archive/refs/tags/v2.0.0.zip" }
flatbuffers/2.0.0 { zip = "https://github.com/google/flatbuffers/archive/refs/tags/v2.0.0.tar.gz" }
#CTRE/3.6 { git = "https://github.com/hanickadot/compile-time-regular-expressions" }
CTRE/3.6 { path = "../../../../compile-time-regular-expressions" }
```
As you can see in this file we have 2 additional packages with custom url for packages

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

### Roadmap
Next I want to add the following syntax for external packages:
```console
CTRE/3.6 { conan = "https://github.com/hanickadot/compile-time-regular-expressions/archive/refs/tags/v3.6.zip" }
CTRE/3.6 { conancenter = "<url>" }
```