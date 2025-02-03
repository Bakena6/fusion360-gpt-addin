
# FUSION 360 config
# config.py
# Application Global Variables
# Adding application wide global variables here is a convenient technique
# It allows for access across multiple event handlers and modules

# read openai/system specific config vars
import configparser
import os

user_config = configparser.ConfigParser()
# path to config file containing open ai API keys, Python env path
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.env")

user_config.read(config_path)

default_config = user_config["DEFAULT"]

LOCAL_CAD_PATH = default_config["LOCAL_CAD_PATH"]

# Set to False to remove most log messages from text palette
DEBUG = True

ADDIN_NAME = os.path.basename(os.path.dirname(__file__))

COMPANY_NAME = "STS Innovations LLC"

# FIXME explain 
design_workspace = "FusionSolidEnvironment"
tools_tab_id = "ToolsTab"
# Only used if creating a custom Tab
my_tab_name = "gpt_addin"

my_panel_id = f"{ADDIN_NAME}_panel_2"
my_panel_name = ADDIN_NAME
my_panel_after = ''

palette_id = "gpt_addin"

STATE_DATA = { }













