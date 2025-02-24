
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

        self.has_initial_settings = False

        # store call history for mock playback
        self.use_mock_server = False
        self.record_calls = True

        self.mock_server = MockServer()

        # tool call history
        self.user_messages = []


    # TODO sort setting type better
    def update_settings(self, settings_list: list):

        """
        update state settings from js/html interface
        """

        for settings_dict in settings_list:

            input_type = settings_dict["input_type"]
            setting_name = settings_dict["setting_name"]
            setting_val = settings_dict["setting_val"]
            setting_class = settings_dict["setting_class"].split(" ")

            # must match with html classes
            if "server-setting" in setting_class:
                current_val = getattr(self, setting_name, None)
                setattr(self, setting_name, setting_val)
                print(f"client: {setting_name}:  {current_val} => {setting_val}")

            elif "fusion-setting" in setting_class:
                self.fusion_itf.set_class_attr({"setting_name": setting_name, "setting_val": setting_val})

            else:
                print(f"Error: Unlcassified setting : {settings_dict}")





    def get_tools(self):
        """
        return tool to js from fusion interface
        """
        return self.fusion_itf.get_tools()

    def reload_modules(self):
        importlib.reload(fusion_interface)
        self.fusion_itf._reload_modules()
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)
        # Get settings from js
        self.get_initial_settings()
        print("Modules Reloaded")

    def reload_object_dict(self):
        """reload fusion document objects"""
        return self.fusion_itf.reload_object_dict()

    def reload_fusion_intf(self):
        importlib.reload(fusion_interface)
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)
        print("Fusion Interface Reloded")

    def reload_interface(self):
        self.connected = False
        self.palette = self.ui.palettes.itemById(self.PALETTE_ID)
        importlib.reload(fusion_interface)
        self.fusion_itf = fusion_interface.FusionInterface(self.app, self.ui)
        # Get settings from js
        self.get_initial_settings()

        print("fusion_interface reloded")

    # TODO
    def get_initial_settings(self):
        data = {"get_initial": "get_initial"}
        self.palette.sendInfoToHTML("get_initial", json.dumps(data))

    def sendToBrowser(self, function_name, data):
        """send event data to js"""
        json_data = json.dumps(data)
        # create run output section in html
        self.palette.sendInfoToHTML(function_name, json_data)

    # TODO add 
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


    # TODO 
    def resize_palette(self):
        self.palette.setSize(900, 900)

    ### ====== server calls ====== ###

    def connect(self):
        """
        connect to assistant manager class on seperate process
        """

        if self.use_mock_server == True:
            self.conn = self.mock_server
            self.connected = True;
            return
        else:
            try:
                address = ('localhost', 6000)
                self.conn = Client(address, authkey=b'fusion260')
            except Exception as e:
                message = {"error": "connection_error"}
                self.palette.sendInfoToHTML("connection_error", json.dumps(message))
                return None

            self.connected = True;
            print(f"RECONNECTED")
            return True


    def send_msg(self, message):

        if self.connected == False:
            self.connect()

        try:
            self.conn.send(message)
        except Exception as e:
            self.connect()
            self.conn.send(message)


        return True


    # TODO use regulare message format 
    def start_record(self):
        message = {
            "message_type": "start_record",
            "content": None
        }
        message = json.dumps(message)

        message_confirmation = self.send_msg(message)
        print(f"START RECORD: message sent,  waiting for result...")
        start_confirm = self.conn.recv()
        print(f"{start_confirm}")

    def stop_record(self):
        message = {
            "message_type": "stop_record",
            "content": None
        }

        message = json.dumps(message)

        # start message
        self.send_msg(message)
        print(f"END RECORD:  waiting for result...")

        # audio transcription
        audio_text = self.conn.recv()
        audio_text = json.loads(audio_text)
        audio_text = {"audio_text": audio_text["content"]}

        return audio_text

    def upload_model_settings(self):
        """
        upload tools to assistant
        """
        model_name = self.model_name
        reasoning_effort = self.reasoning_effort
        tools = self.fusion_itf.get_docstr()
        instructions_path = os.path.join("system_instructions",self.instructions_name)

        model_settings = {
            "model_name": model_name,
            "tools": tools,
            "instructions_path": instructions_path,
            "reasoning_effort": reasoning_effort
        }

        message = {
            "message_type": "function_call",
            "function_name": "update_settings",
            "function_args": {"model_settings": model_settings}
        }

        message = json.dumps(message)
        #if self.connected == False:

        message_confirmation = self.send_msg(message)
        print(f"SETTINGS SENT,  waiting for result...")

        settings_response = self.conn.recv()
        settings_response = json.loads(settings_response)
        print(settings_response)
        return settings_response


    def get_system_instructions(self):
        """
        get available system_instructions
        """

        message = {
            "message_type": "function_call",
            "function_name": "get_available_system_instructions"
        }
        message = json.dumps(message)
        message_confirmation = self.send_msg(message)

        print(f"REQUEST SENT,  waiting for result...")
        instructions = self.conn.recv()
        instructions = json.loads(instructions)
        return instructions 

    def get_models(self):
        """
        get available models
        """
        message = {
            "message_type": "function_call",
            "function_name": "get_available_models",
        }
        message = json.dumps(message)

        message_confirmation = self.send_msg(message)

        print(f"REQUEST SENT,  waiting for result...")
        models = self.conn.recv()
        models = json.loads(models)

        filtered_models = []
        exclude = [
            "tts",
            "text-embedding",
            "babbage",
            "davinci",
            "dall-e", "audio",
            "omni-moderation",
            "whisper"
        ]

        for m in models:

            if any([t in m for t in exclude]):
                continue

            filtered_models.append(m)

        models = sorted(filtered_models)

        return models

    def send_message(self, message):
        """send message to process server"""

        if message == "":
            return 

        if self.record_calls == True:
            self.user_messages.append(message)

        message = {"message_type": "thread_update", "content": message}
        message = json.dumps(message)

        message_confirmation = self.send_msg(message)
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
                adsk.doEvents()

                message = {"message_type": "thread_update", "content": function_result}
                message = json.dumps(message)

                self.send_msg(function_result)

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

        if function_args != None:
            function_args = json.loads(validate_and_repair_json(function_args))

        print(f"CALL FUNCTION: {function_name}, {function_args}, {tool_call_id}")

        # check of FusionInterface inst has requested method
        function = getattr(self.fusion_itf, function_name, None)

        if callable(function):
            if function_args == None:
                result = function()
            else:
                result = function(**function_args)
        else:
            result = json.dumps({"error": f"Function '{function_name}' not callable"})

        # send function response to js/html
        if tool_call_id != None:

            message_data = {
                "tool_call_id": tool_call_id,
                "function_result": result
            }

            self.sendToBrowser("toolCallResponse", message_data)



        # return function result to Assistant API
        return result




# TODO put json validation code somewhere else
def validate_and_repair_json(json_str: str) -> str:
    """
    Tries to load the given json_str as JSON. If it fails due to structural errors
    like extra/missing brackets/braces, applies simple heuristics to fix them.
    Returns a *string* containing valid JSON or raises ValueError if it can't fix.

    NOTE: This function is minimal and won't fix all possible JSON issues, but
    it demonstrates how to handle common bracket or brace mismatches. 
    More advanced or specialized logic may be needed for complicated errors.
    """

    # 1) First, try a direct json.loads
    try:
        parsed = json.loads(json_str)
        # If no exception, it was valid
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        pass  # We'll attempt repairs below

    # We'll store the original for fallback
    original_str = json_str

    # Heuristic approach:
    # a) Balanced brackets/braces: We'll try to count braces/brackets.
    # b) Fix trailing commas, if present. 
    # c) Fix unquoted keys, if any. (This is optional or advanced.)

    # a) Attempt bracket/brace balancing
    repaired = basic_bracket_repair(json_str)

    # b) Attempt removing trailing commas
    repaired = remove_trailing_commas(repaired)

    # c) Possibly try other heuristics (like ensuring top-level braces if it looks like an object)
    repaired = ensure_top_level_braces_if_needed(repaired)

    # 2) Try again
    try:
        parsed = json.loads(repaired)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError as e:
        # If we still fail, we can either raise or fallback
        raise ValueError(f"Could not repair JSON. Original error: {str(e)}\n"
                         f"Original:\n{original_str}\n\nAttempted Repair:\n{repaired}")


def basic_bracket_repair(s: str) -> str:
    """
    Attempt to fix counts of square brackets [] or curly braces {} if they differ by 1.
    We'll do minimal attempts like:
      - If we have one more '{' than '}', we append '}' at the end.
      - If we have one more '}' than '{', we remove the last '}' or the first if found extra.
    Similarly for brackets.
    """
    opens_curly  = s.count('{')
    closes_curly = s.count('}')
    if opens_curly == closes_curly + 1:
        # We have one extra '{' => add a '}' at the end
        s += '}'
    elif closes_curly == opens_curly + 1:
        # We have one extra '}' => remove the last one
        # (this might cause issues if the extra is in the middle, but it's a guess)
        idx = s.rfind('}')
        if idx != -1:
            s = s[:idx] + s[idx+1:]

    opens_square  = s.count('[')
    closes_square = s.count(']')
    if opens_square == closes_square + 1:
        s += ']'
    elif closes_square == opens_square + 1:
        idx = s.rfind(']')
        if idx != -1:
            s = s[:idx] + s[idx+1:]

    return s


def remove_trailing_commas(s: str) -> str:
    """
    Removes commas that appear right before a closing bracket or brace or end of string.
    E.g. "...,}" => "...}" or "...,]" => "...]". This helps fix some JSON errors.
    """
    # Regex to find a comma followed by optional whitespace + a closing brace/bracket 
    # or end of string
    pattern = re.compile(r",\s*(?=[}\]])")
    s = pattern.sub("", s)
    return s


def ensure_top_level_braces_if_needed(s: str) -> str:
    """
    If the string doesn't parse as JSON but looks like it's missing top-level
    braces for an object, we might wrap it. This is guesswork and optional.
    For example, if we see it starts with some key but no braces, we do { ... }.
    We'll do a naive check: if it doesn't start with [ or {, let's try wrapping with braces.
    """
    st = s.strip()
    if not st.startswith("{") and not st.startswith("["):
        # Maybe we wrap it in braces
        # e.g. "key: val, ..." => we do "{ key: val, ... }"
        # But we'd need quotes for "key", so this is advanced. We'll keep it minimal.
        s = "{" + s + "}"
    return s


def example_usage():
    bad_json = """
    {
      "name": "example",
      "values": [
        1,
        2
      "flag": true,
    }
    """  # missing comma, bracket mismatch

    try:
        fixed = validate_and_repair_json(bad_json)
        print("Fixed JSON:")
        print(fixed)
    except ValueError as e:
        print("Could not fix JSON:", str(e))

