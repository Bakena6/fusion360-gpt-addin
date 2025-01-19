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
from adsk.fusion import CombineFeature #IntersectFeatureOperation
#from adsk.core import Camera
import os
import sys
import json
import math
import time

from ... import config
from ...lib import fusion360utils as futil

import importlib

# custom module
from ...lib.sutil import fusion_interface

app = adsk.core.Application.get()
ui = app.userInterface

PALETTE_NAME = 'STSi-Fusion-GPT'
IS_PROMOTED = False

# Using "global" variables by referencing values from /config.py
PALETTE_ID = config.sample_pallette_id

# Specify the full path to the local html. You can also use a web URL
# such as 'https://www.autodesk.com/'
PALETTE_URL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'html', 'index.html')

# The path function builds a valid OS path. This fixes it to be a valid local URL.
PALETTE_URL = PALETTE_URL.replace('\\', '/')

# Set a default docking behavior for the palette
PALETTE_DOCKING = adsk.core.PaletteDockingStates.PaletteDockStateRight
CMD_NAME = os.path.basename(os.path.dirname(__file__))
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'
CMD_Description = 'Browser Input'
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

DESIGN =  {}
STATE_DATA = {
    'model_attrs': {}
}

# Fusion360 interface, methodods availible to OpenAI Assistant
fusion_itf = fusion_interface.FusionInterface(app, ui)
# connects to Assistant Interface running on external process
server_itf = fusion_interface.GptClient(fusion_itf)


def print(string):
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
            width=900,
            height=200,
            useNewWebBrowser=True
        )
        futil.add_handler(palette.closed, palette_closed)
        futil.add_handler(palette.navigatingURL, palette_navigating)
        futil.add_handler(palette.incomingFromHTML, palette_incoming)
        futil.log(f'{CMD_NAME}: Created a new palette: ID = {palette.id}, Name = {palette.name}')

    if palette.dockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
        palette.dockingState = PALETTE_DOCKING

    palette.isVisible = True

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







STATE_DATA = {}
def palette_incoming(html_args: adsk.core.HTMLEventArgs):
    """
     handles events sent from javascript in palette
    """

    # read message sent from browser input javascript function
    message_data = json.loads(html_args.data)
    message_action = html_args.action

    # connects to Assistant Interface running on external process
    

    print("message_data")
    print(message_data)

    if message_action == "error":
        print(message_dat)

    elif message_action == "create_thread":
        """get gpt thread and create instance"""
        #initial_message = gpt_main.get_initial_values()
        #gpt = gpt_init.get_gpt(initial_message)
        #STATE_DATA['gpt'] = gpt

    elif message_action == "submit_prompt":

        prompt_text = message_data['promptText']

        server_itf.send_message(prompt_text)

        print(prompt_text)


        #try:
        #    # send initial prompt
        #    gpt.execute_message(prompt_text)
        #except:
        #    gpt.cancel_run()
        #    return

        #return_val = ''
        #call_num = 0
        #run_status = 'in_progress'

        #try:
        #    while run_status != 'completed':

        #        # execute steps
        #        step_resp = gpt.execute_steps()

        #        resp_type = step_resp['resp_type']
        #        resp_val = step_resp['value']
        #        STATE_DATA['last_resp'] = resp_val
        #        return_args = {'message_text': 'none'}

        #        if resp_type == 'tool_calls':
        #            function_resps = gpt_main.run_functions(resp_val)
        #            gpt.send_func_response(function_resps)
        #            return_val += json.dumps(resp_val)

        #        if resp_type == 'message':
        #             return_val += resp_val

        #        time.sleep(4)
        #        run_status = gpt.run_status()
        #        print(run_status)

        #        if run_status == 'failed':
        #            break

        #        call_num += 1
        #        if call_num > 20:
        #            print('broke')
        #            break

        #    html_args.returnData = json.dumps({'resp_val': return_val})
        #except:
        #    gpt.cancel_run()
        #    return

    elif message_action == "run_last":
        '''run last promt response'''
        pass

    elif message_action == "test_tools":
        pass

    elif message_action == "get_steps":
        pass




# This function will be called when the user clicks the OK button in the command dialog.
def command_execute_o(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')



# This function will be called when the user completes the command.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []







