

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

from .. import config
from ..lib import fusion360utils as futil

from . import fusion_interface

import time
#import asyncio

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))

print(f"RELOADED: {__name__.split("%2F")[-1]}")


class MockServer:

    """
    test Fusion side code without OpenAI API call

    """
    def __init__(self):

        self.call_history = []
        self.msg_index = 0

    def set_index(self, index):
        self.msg_index = index

    def send(self, message):
        time.sleep(.0001)
        return True;


    def recv(self):
        time.sleep(.0001)
        msg = self.call_history[self.msg_index]
        self.msg_index += 1
        return msg

    def add_call(self, call):
        self.call_history.append(call)


    def download_call_hostory(self):
        pass



class GptClient:
    """
    Instantiated in entry.py
    connects to command server running on separate process
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
        #print(f"PALETTE_ID: {self.PALETTE_ID}:")

        # Fusion360 interface, methods available to OpenAI Assistant
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)

        # must be defined here,
        self.app = adsk.core.Application.get()

        # current connection status
        self.connected = False

        # store call history for mock playback
        self.use_mock_server = False
        self.record_calls = True
        self.mock_server = MockServer()

        # tool call history
        self.user_messages = []


    def start_record(self):
        message = {
            "message_type": "start_record",
            "content": None
        }
        message = json.dumps(message)

        if self.connected == False:
            self.connect()

        message_confirmation = self.conn.send(message)
        print(f"START RECORD: message sent,  waiting for result...")
        start_confirm = self.conn.recv()
        print(f"{start_confirm}")


    def stop_record(self):

        message = {
            "message_type": "stop_record",
            "content": None
        }

        message = json.dumps(message)
        if self.connected == False:
            print("connect")
            self.connect()

        # start message
        self.conn.send(message)
        print(f"END RECORD:  waiting for result...")

        # audio transcription
        audio_text = self.conn.recv()
        audio_text = json.loads(audio_text)

        return audio_text


    def reload_modules(self):
        #importlib.reload(fusion_interface)
        self.fusion_itf._reload_modules()
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)
        print("Modules Reloaded")

    def reload_fusion_intf(self):
        importlib.reload(fusion_interface)
        #self.fusion_itf._reload_modules()
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)
        print("Fusion Interface Reloded")

    def reload_interface(self):
        self.connected = False
        self.palette = self.ui.palettes.itemById(self.PALETTE_ID)
        importlib.reload(fusion_interface)
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)
        print("fusion_interface reloded")


    def connect(self):
        """
        connect to assistant manager class on seperate process
        """

        if self.use_mock_server == True:
            self.conn = self.mock_server
            self.connected = True;
            return

        address = ('localhost', 6000)
        self.conn = Client(address, authkey=b'fusion260')

        self.connected = True;
        #print(self.conn)

    def sendToBrowser(self, function_name, data):
        """send event data to js"""

        json_data = json.dumps(data)
        # create run output section in html
        self.palette.sendInfoToHTML(function_name, json_data)

    def resize_palette(self):
        self.palette.setSize(400, 900)

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
        print(f"TOOLS SENT,  waiting for result...")


    def playback(self):
        """run recorded calls"""
        print(f"start playback")


        self.use_mock_server = True
        self.record_calls = False
        self.conn = self.mock_server
        self.mock_server.set_index(0)

        self.connected = True;

        for message in self.user_messages:
            self.send_message(message)

        self.use_mock_server = False
        self.record_calls = True


    def send_message(self, message):
        """send message to process server"""

        if self.connected == False:
            self.connect()

        if self.record_calls == True:
            self.user_messages.append(message)

        message = {"message_type": "thread_update", "content": message}
        message = json.dumps(message)

        message_confirmation = self.conn.send(message)
        print(f"MESSAGE SENT,  waiting for result...")

        # continue to run as long thread is open
        run_complete = False
        while run_complete == False:

            # result from server
            api_result = self.conn.recv()

            if self.record_calls == True:
                self.mock_server.add_call(api_result)

            api_result = json.loads(api_result)

            response_type = api_result.get("response_type")
            event_type = api_result.get("event")
            run_status = api_result.get("run_status")

            content = api_result.get("content")

            # streaming call outputs
            if event_type == "thread.run.created":
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

            elif event_type in ["thread.run.step.delta"]:
                self.sendToBrowser("stepDelta", content)

            # TODO, use event type not response type
            elif response_type == "tool_call":

                tool_call_id = api_result["tool_call_id"]
                function_name = api_result["function_name"]
                function_args = api_result["function_args"]

                function_result = self.call_function(function_name, function_args, tool_call_id)

                message = {"message_type": "thread_update", "content": function_result}
                message = json.dumps(message)

                adsk.doEvents()
                self.conn.send(function_result)

            # thread complete break loop
            if run_status == "thread.run.completed":
                run_complete = True

            adsk.doEvents()

        return api_result


    def call_function(self, function_name: str, function_args: str, tool_call_id=None):
        """
        called from Assistants API
        calls function passed from Assistants API
        """
        #print(f"function_name: {type(function_name)}, {function_name}")
        #print(f"function_args: {type(function_args)}, {function_args}")
        #print(f"tool_call_id: {type(tool_call_id)}, {tool_call_id}")


        # TODO make this better
        #if function_args == "":
        #    function_args = None

        if function_args != None:
            function_args = json.loads(function_args)

        print(f"CALL FUNCTION: {function_name}, {function_args}, {tool_call_id}")

        # check of FusionInterface inst has requested method
        function = getattr(self.fusion_itf, function_name, None)

        if callable(function):
            if function_args == None:
                result = function()
            else:
                result = function(**function_args)
        else:
            result = ""

        # send function response to js/html
        if tool_call_id != None:

            message_data = {
                "tool_call_id": tool_call_id,
                "function_result": result
            }

            self.sendToBrowser("toolCallResponse", message_data)



        # return function result to Assistant API
        return result







