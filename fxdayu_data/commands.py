# encoding:utf-8
from fxdayu_data import config
import os


def add(name, path, copy=False):
    """Add a config path into DataAPI"""
    if copy:
        import shutil
        path = shutil.copy(path, config.get_root())

    path = os.path.abspath(path)

    paths = config.get_config_paths()
    paths[name] = path
    config.set_config_paths(paths)
    print("Add %s: %s" % (name, path))


def use(name):
    """Find and Set a config path as the main path in DataAPI by its name"""
    paths = config.get_config_paths()
    paths[config.DEFAULT] = paths[name]
    config.set_config_paths(paths)
    print("Use %s: %s as main config" % (name, paths[name]))


def delete(names):
    """Delete config paths by names"""
    paths = config.get_config_paths()
    for name in names:
        paths.pop(name)
    config.set_config_paths(paths)


def show():
    """Show all config paths"""
    for item in list(config.get_config_paths().items()):
        print("%s: %s" % item)


def export(path, type, name, copy):
    """Export default config"""
    from fxdayu_data import default

    if os.path.isdir(path):
        path = os.path.join(path, "config.py")

    with open(path, "w") as f:
        f.write(default.defaults.get(type, default.MONGOCONFIG))
        if name:
            add(name, os.path.abspath(path), copy)


def execute(arguments):
    """
    Read data from DataAPI
    """

    from fxdayu_data import DataAPI

    func = arguments[0]

    def catch_values(values):
        if "," in values:
            return values.split(",")
        else:
            return values

    def separate_key(kv):
        key, value = kv.split("=")
        return key, catch_values(value)

    args = []
    kwargs = {}

    for arg in arguments[1:]:
        if "=" in arg:
            kwargs.__setitem__(*separate_key(arg))
        else:
            args.append(catch_values(arg))

    print(DataAPI.get(func, *args, **kwargs))


def extract(source, target, name="bundle", ignore=False):
    from tarfile import TarFile

    os.makedirs(target, exist_ok=True)

    print("Extracting bundle to %s" % target)

    tf = TarFile.open(source)
    tf.extractall(target)
    tf.close()

    add(name, os.path.join(target, "config.py"))
    if not ignore:
        use(name)


__all__ = ["add", "use", "delete", "show", "export", "execute", "extract"]


if __name__ == '__main__':
    target = os.path.join(config.get_root(), "bundle")
    extract("D:/WorkingArea/bundle.2017-11-30.tar.gz", target)