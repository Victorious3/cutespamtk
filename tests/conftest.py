def pytest_addoption(parser):
    parser.addoption("--data-folder", default = None)


def pytest_generate_tests(metafunc):
    # This is called for every test. Only get/set command line arguments
    # if the argument is specified in the list of test "fixturenames".

    data_folder = metafunc.config.option.data_folder
    if "data_folder" in metafunc.fixturenames:
        metafunc.parametrize("data_folder", [data_folder])