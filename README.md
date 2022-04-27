## ConanEx - Conan Extended, conan that more decentralize

What it allows ?

Consider the following `conanfile.txt`:

```console
[requires]
poco/1.9.4
flatbuffers/2.0.0 { git = "https://github.com/google/flatbuffers", tag = "v2.0.0" }
CTRE/3.6 { git = "https://github.com/hanickadot/compile-time-regular-expressions" }
```
As you can see in this file we have 2 additional packages with custom url for packages

To use `conanex` use it the same way you use `conan`:
```console
conanex install <path_to_conanfile.txt> -pr=<path_to_profile>
```
