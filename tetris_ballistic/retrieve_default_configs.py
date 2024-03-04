import os
from importlib.resources import files

package_dir = os.path.dirname(os.path.abspath(__file__))
configs_dir = os.path.join(package_dir, 'configs')


def retrieve_default_configs(pattern="*.yaml", verbose=True):
    """
    Retrieve default YAML configurations.

    Args:
        pattern (str): The glob pattern to match filenames. Defaults to '*.yaml' to match all YAML files.
        verbose (bool): Whether to print the list of configuration files. Defaults to True.

    Returns:
        list of str: A list of paths to YAML files relative to the package. Only the basename of the file is included.
    """
    config_dir = files("tetris_ballistic") / 'configs'
    config_filenames = sorted(str(file.name) for file in config_dir.glob(pattern))
    if verbose:
        print("The following configuration files are included:")
        for index, filename in enumerate(config_filenames, start=1):
            print(f"{index}. {filename}")
    return config_filenames


# Example usage
if __name__ == "__main__":
    config_filenames = retrieve_default_configs(pattern="*_sticky*.yaml")
    for index, filename in enumerate(config_filenames, start=1):
        print(f"{index}. {filename}")
    print(f"config_dir: {config_dir}")
