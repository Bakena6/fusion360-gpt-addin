import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import sys
import math
import os
import json
import inspect

import importlib

from multiprocessing.connection import Client
from array import array
import time

import functools

from ... import config
from ...lib import fusion360utils as futil

from . import fusion_interface



def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))



class GptClient:
    """
    connects to command server running on seperate process
    """
    def __init__(self):
        """
        fusion_interface : class inst whose methods call Fusion API
        """

        # send info to html palette
        self.PALETTE_ID = config.palette_id
        self.app = adsk.core.Application.get()

        self.ui = self.app.userInterface
        self.palette = self.ui.palettes.itemById(self.PALETTE_ID)

        print(f"palette: {self.palette}:")
        print(f"PALETTE_ID: {self.PALETTE_ID}:")

        # Fusion360 interface, methodods availible to OpenAI Assistant
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)

        # must be defined here,
        self.app = adsk.core.Application.get()

        # current connection status
        self.connected = False

        # tool call history
        self.call_history = {}

    def reload_interface(self):

        self.palette = self.ui.palettes.itemById(self.PALETTE_ID)
        print(f"PALETTE_ID: {self.PALETTE_ID}:")
        print(f"palette: {self.palette}:")

        importlib.reload(fusion_interface)
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)
        print("fusion_interface reloded")


    def connect(self):
        """
        connect to assistant manager class on seperate process
        """
        address = ('localhost', 6000)
        self.conn = Client(address, authkey=b'fusion260')
        #print(dir(self.conn))

        self.connected = True;


    def sendToBrowser(self, function_name, data):
        json_data = json.dumps(data)
        # create run output section in html

        self.palette.sendInfoToHTML(function_name, json_data)


    def upload_tools(self):
        """
        upload tools to assistant
        """

        tools = self.fusion_itf.get_docstr()

        message = {
            "message_type": "tool_update",
            "content": tools
        }
        message = json.dumps(message)


        if self.connected == False:
            self.connect()

        print(f"conn closed: {self.conn.closed}")
        message_confirmation = self.conn.send(message)

        print(f"  message sent,  waiting for result...")


    def send_message(self, message):
        """send message"""

        if self.connected == False:
            self.connect()

        message = {"message_type": "thread_update", "content": message}
        message = json.dumps(message)

        message_confirmation = self.conn.send(message)
        print(f"MESSAGE SENT,  waiting for result...")

        # continue to run as loong thread is open
        run_complete = False
        while run_complete == False:

            # result from server
            api_result = self.conn.recv()
            api_result = json.loads(api_result)

            response_type = api_result.get("response_type")
            event_type = api_result.get("event")
            run_status = api_result.get("run_status")

            content = api_result.get("content")

            # streaming call outputs
            if event_type == "thread.run.created":
                #print(event_type)
                #print(content)
                self.sendToBrowser("runCreated", content)

            # streaming call outputs
            elif event_type == "thread.run.step.created":
                self.sendToBrowser("stepCreated", content)

            # streaming call outputs
            elif event_type == "thread.message.created":
                self.sendToBrowser("messageCreated", content)

            # streaming call outputs
            elif event_type == "thread.message.delta":
                self.sendToBrowser("messageDelta", content)

            #elif event_type in ["thread.run.step.delta", "thread.run.step.completed"]:
            elif event_type in ["thread.run.step.delta"]:
                self.sendToBrowser("stepDelta", content)

            # TODO, use event type not response type
            elif response_type == "tool_call":

                function_name = api_result["function_name"]
                function_args = api_result["function_args"]
                function_result = self.call_function(function_name, function_args)

                message = {"message_type": "thread_update", "content": function_result}
                message = json.dumps(message)

                self.conn.send(function_result)

            # thread complete break loop
            if run_status == "thread.run.completed":
                run_complete = True

            adsk.doEvents()

        return api_result


    def call_function(self, name, function_args):
        """
        call function passed from Assistants API
        """


        if function_args == "":
            function_args = None

        #if function_args != None:
        if function_args != None:
            function_args = json.loads(function_args)

        print(f"CALL FUNCTION: {name}, {function_args}")

        # check of FusionInterface inst has requested method
        function = getattr(self.fusion_itf, name, None )

        if callable(function):
            if function_args == None:
                result = function()
            else:
                result = function(**function_args)

        else:
            result = ""

        if "Error:" in result:
            print(result)


        return result







