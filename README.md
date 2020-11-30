# Usage

This application depends on the bluepy and crcmod packages, so be sure they are installed in your environment. By default, the application expects a virtual environment to be setup as follows:

    $ sudo apt install python3-venv python3-pip libglib2.0-dev
    $ python3 -m venv env
    $. env/bin/activate
    (env) $ python3 -m pip install bluepy crcmod
    (env) $ deactivate

Setting up the environment in a different manner may require the first line of the update.py file to be modified. The usage of the application is as follows:

    $ update.py application_file [target_MAC_address]

The first argument is required and is the path to the application image file. The second argument is optional. If the MAC address of the target device is known, the user can provide it here and skip the process of scanning for available devices. If the second argument is not provided, the application will present the user with a list of available BLE devices from which the user must choose a device to update.

# Documentation

See the article [PSoC Device Firmware Updates with Python](https://www.digikey.com/eewiki/display/microcontroller/PSoC+Device+Firmware+Updates+with+Python) for more information. 
