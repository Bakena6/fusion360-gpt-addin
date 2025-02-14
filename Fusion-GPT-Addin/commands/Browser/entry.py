# browser
#  Copyright 2022 by Autodesk, Inc.
#  Permission to use, copy, modify, and distribute this software in object code form
#  for any purpose and without fee is hereby granted, provided that the above copyright
#  notice appears in all copies and that both that copyright notice and the limited
#  warranty and restricted rights notice below appear in all supporting documentation.
#
#  AUTODESK PROVIDES THIS PROGRAM "AS IS" AND WITH ALL FAULTS. AUTODESK SPECIFICALLY
#  DISCLAIMS ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR USE.
#  AUTODESK, INC. DOES NOT WARRANT THAT THE OPERATION OF THE PROGRAM WILL BE
#  UNINTERRUPTED OR ERROR FREE.

from datetime import datetime
import adsk.core
from adsk.core import ValueInput
from adsk.core import MessageBoxButtonTypes, ObjectCollection
#from adsk.fusion import CombineFeature
#from adsk.core import Camera
import os
import sys
import json
import math
import time

from ... import config
from ...lib import fusion360utils as futil
import importlib

# custom modules
#from ...lib.sutil import fusion_interface, gpt_client
from ...f_interface import gpt_client

app = adsk.core.Application.get()
ui = app.userInterface

PALETTE_NAME = 'STSi-Fusion-GPT'
IS_PROMOTED = False

# Using "global" variables by referencing values from /config.py
PALETTE_ID = config.palette_id

# Specify the full path to the local html. You can also use a web URL
# such as 'https://www.autodesk.com/'
PALETTE_URL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'html', 'index.html')

# The path function builds a valid OS path. This fixes it to be a valid local URL.
PALETTE_URL = PALETTE_URL.replace('\\', '/')

# Set a default docking behavior for the palette
PALETTE_DOCKING = adsk.core.PaletteDockingStates.PaletteDockStateRight
#PALETTE_DOCKING = adsk.core.PaletteDockingStates.PaletteDockStateFloating

#CMD_NAME = os.path.basename(os.path.dirname(__file__))
CMD_NAME = "Prompt Window"

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'
CMD_Description = "Prompt Window"
IS_PROMOTED = False

# Global variables by referencing values from /config.py
WORKSPACE_ID = config.design_workspace
TAB_ID = config.tools_tab_id
TAB_NAME = config.my_tab_name

PANEL_ID = config.my_panel_id
PANEL_NAME = config.my_panel_name
PANEL_AFTER = config.my_panel_after

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Holds references to event handlers
local_handlers = []

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))


# Executed when add-in is run.
def start():
    # ******************************** Create Command Definition ********************************
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Add command created handler. The function passed here will be executed when the command is executed.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******************************** Create Command Control ********************************
    # Get target workspace for the command.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get target toolbar tab for the command and create the tab if necessary.
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    if toolbar_tab is None:
        toolbar_tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)

    # Get target panel for the command and and create the panel if necessary.
    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID)
    if panel is None:
        panel = toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME, PANEL_AFTER, False)

    # Create the command control, i.e. a button in the UI.
    control = panel.controls.addCommand(cmd_def)

    # Now you can set various options on the control such as promoting it to always be shown.
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)
    palette = ui.palettes.itemById(PALETTE_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    # Delete the Palette
    if palette:
        palette.deleteMe()


# Function to be called when a user clicks the corresponding button in the UI.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME} Command Created Event')

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    #futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# connects to Assistant Interface running on external process
# server interface
server_itf = gpt_client.GptClient()

def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command execute event.')

    palettes = ui.palettes
    palette = palettes.itemById(PALETTE_ID)

    if palette is None:
        palette = palettes.add(
            id=PALETTE_ID,
            name=PALETTE_NAME,
            htmlFileURL=PALETTE_URL,
            isVisible=True,
            showCloseButton=True,
            isResizable=True,
            width=1000,
            height=2000,
            useNewWebBrowser=True
        )
        futil.add_handler(palette.closed, palette_closed)
        futil.add_handler(palette.navigatingURL, palette_navigating)
        futil.add_handler(palette.incomingFromHTML, palette_incoming)
        futil.log(f'{CMD_NAME}: Created a new palette: ID = {palette.id}, Name = {palette.name}')

    if palette.dockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
        palette.dockingState = PALETTE_DOCKING

    palette.isVisible = True

    server_itf.reload_interface()

# Use this to handle a user closing your palette.
def palette_closed(args: adsk.core.UserInterfaceGeneralEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Palette was closed.')

# Use this to handle a user navigating to a new page in your palette.
def palette_navigating(args: adsk.core.NavigationEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Palette navigating event.')

    # Get the URL the user is navigating to:
    url = args.navigationURL

    log_msg = f"User is attempting to navigate to {url}\n"
    futil.log(log_msg, adsk.core.LogLevels.InfoLogLevel)

    # Check if url is an external site and open in user's default browser.
    if url.startswith("http"):
        args.launchExternally = True



def palette_incoming(html_args: adsk.core.HTMLEventArgs):
    """
    handles events sent from javascript in palette
    """

    # read message sent from browser input javascript function
    message_data = json.loads(html_args.data)
    message_action = html_args.action

    #importlib.reload(gpt_client)
    # connects to Assistant Interface running on external process
    #server_itf = gpt_client.GptClient(fusion_itf)

    if message_action == "error":
        print(message_data)


    # upload function/ prompt to assistant
    elif message_action == "cb_change":
        server_itf.fusion_itf.set_class_attr(message_data)

    elif message_action == "reload_modules":
        server_itf.reload_modules()
        html_args.returnData = ""

    elif message_action == "reload_fusion_intf":
        #server_itf.reload_interface()
        server_itf.reload_fusion_intf()
        html_args.returnData = ""


    # upload function/ prompt to assistant
    elif message_action == "upload_tools":
        server_itf.upload_tools()

    elif message_action == "submit_prompt":
        prompt_text = message_data['promptText']
        if prompt_text != "":
            server_itf.send_message(prompt_text)

    elif message_action == "execute_tool_call":
        #server_itf.reload_interface()
        function_name = message_data["function_name"]
        function_args = message_data["function_args"]

        # convert to dict if passed as str when manually testing
        if isinstance(function_args, str):
            function_args = json.loads(function_args)

        method = getattr(server_itf.fusion_itf, function_name, None)

        if callable(method):
            result = method(**function_args)
        html_args.returnData = ""

    elif message_action == "start_record":
        server_itf.start_record()
        html_args.returnData = ""

    elif message_action == "stop_record":
        audio_text = server_itf.stop_record()
        #audio_text = {"audio_text": audio_text["content"]}
        html_args.returnData = json.dumps(audio_text)

    elif message_action == "get_tools":
        """
        get available tools, display in window
        """
        methods = server_itf.fusion_itf.get_tools()
        html_args.returnData = json.dumps(methods)

    elif message_action == "reconnect":
        server_itf.connect()
        html_args.returnData = ""

    elif message_action == "reset_all":
        server_itf.reload_modules()
        server_itf.reload_fusion_intf()
        html_args.returnData = ""




# This function will be called when the user completes the command.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []







