# SKALAB
## SKA in LAB

**skalab** is a tool that allow to easy access to the SKA-Low devices without the need of deploy the Tango Framework.

**skalab** is the container of each subsytem that can be also run in stand alone mode.

**skalab** must be installed along the aavs-system repository (https://gitlab.com/ska-telescope/aavs-system) in the **utilities** folder:

`cd $AAVS_HOME/aavs-system/python/utilities`

`git clone https://github.com/amattana/skalab.git`

It requires the following additional python packages:

`pip3 install python-usbtmc get_nic pyqt5 pyusb typing_extensions`


