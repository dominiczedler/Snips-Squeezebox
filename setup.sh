#!/usr/bin/env bash

DEFAULT_CONFIG_FILE="./config.ini.default"
CONFIG_FILE="./config.ini"

# user config version checking
if [ ! -e $CONFIG_FILE ]
then
    cp config.ini.default config.ini
else
    user_ver=$(grep "config_ver" $CONFIG_FILE | sed 's/^config_ver=\([0-9]\.[0-9]\)/\1/g')
    def_ver=$(grep "config_ver" $DEFAULT_CONFIG_FILE | sed 's/^config_ver=\([0-9]\.[0-9]\)/\1/g')

    if [ "$def_ver" != "$user_ver" ]
    then
        echo -e "\033[1;32;31m[!]\033[m Current config options are overwrote by the new default value since they are out of date"
        echo -e "\033[1;32;31m[*]\033[m The lastest config.ini version is \033[0;35m<$def_ver>\033[m"
        echo -e "\033[1;32;31m[*]\033[m Please change it manually to adapt to your old setup after installation"
        cp config.ini.default config.ini
    else
        echo -e "\033[1;32;34m[*]\033[m Good config.ini version: \033[0;35m<$user_ver>\033[m"
    fi
fi

PYTHON=$(command -v python3)
VENV=venv

if [ -f "$PYTHON" ]
then

    if [ ! -d $VENV ]
    then
        # Create a virtual environment if it doesn't exist.
        $PYTHON -m venv $VENV
    fi

    # Activate the virtual environment and install requirements.
    # shellcheck source=/dev/null
    . $VENV/bin/activate
    pip3 install -r requirements.txt

else
    >&2 echo "Cannot find Python 3. Please install it."
fi
