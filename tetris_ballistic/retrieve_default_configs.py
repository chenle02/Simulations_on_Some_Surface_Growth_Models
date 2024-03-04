from importlib.resources import files


def retrieve_default_configs(pattern="*.yaml", verbose=True):
    """
    Retrieve default YAML configurations.

    Args:
        pattern (str): The glob pattern to match filenames. Defaults to '*.yaml' to match all YAML files.
        verbose (bool): Whether to print the list of configuration files. Defaults to True.

    Returns:
        list of str: A list of paths to YAML files relative to the package.
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
