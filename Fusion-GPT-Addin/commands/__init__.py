# Here you define the commands that will be added to your add-in
# If you want to add an additional command, duplicate one of the existing directories and import it here.
# You need to use aliases (import "entry" as "my_module") assuming you have the default module named "entry"
import sys
from .Browser import entry as browser
# global config settings
from .. import config

from ..lib import fusion360utils as futil


# This Template will automatically call the start() and stop() functions.
# By default the order you add the commands to this list will be the order they appear in the UI
commands = [
    browser,
]

# add user python env to path
if config.PYTHON_ENV_PATH not in sys.path:
    sys.path.append(config.PYTHON_ENV_PATH)



# Assumes you defined a "start" function in each of your modules.
# These functions will be run when the add-in is stopped.
def start():
    for command in commands:
        command.start()


# Assumes you defined a "start" function in each of your modules.
# These functions will be run when the add-in is stopped.
def stop():
    for command in commands:
        command.stop()
