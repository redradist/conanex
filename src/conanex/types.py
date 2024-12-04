from enum import Enum


class ConanArgs:
    def __init__(self, args):
        self.__dict__['_args'] = args

    def __copy__(self):
        return ConanArgs(self.__dict__['_args'])

    def __getattr__(self, name):
        if name == '_args':
            return self.__dict__['_args']
        if hasattr(self._args, name):
            return getattr(self._args, name)
        return False


class ConanFileSection(Enum):
    No = 0
    Requires = 1
    ToolRequires = 2
    Options = 3


class ExternalPackage:
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
            return "{}@{}/{}".format(self.package_name, self.user, self.channel)
        else:
            return "{}@".format(self.package_name)

    @property
    def package_hash_algo(self):
        hash_algo = None
        if 'md5' in self.attrs:
            hash_algo = 'md5'
        if 'sha256' in self.attrs:
            hash_algo = 'sha256'
        if 'sha512' in self.attrs:
            hash_algo = 'sha512'
        return hash_algo

    @property
    def package_hash_code(self):
        hash = None
        if self.package_hash_algo:
            hash = self.attrs[self.package_hash_algo]
        return hash.lower().replace("'", "").replace('"', '')
